"""
Read-only inspection of the Staff auth Group footprint in the review database.

Run with:
    cd djangoexact && APP_MODE=review ../.venv/bin/python manage.py shell < \
        ../.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py

Performs zero writes. Prints a deterministic, greppable transcript documenting
the full footprint of the Staff group so a later, separate deletion step can
be reviewed and approved against real numbers.
"""

import sys
import traceback


def main():
    from django.contrib.admin.utils import NestedObjects
    from django.contrib.auth.models import Group
    from django.db import connection

    from api.models import CustomUser, ProjectInvitation, ProjectMembership

    # Step 1: resolve the group, case-sensitive first, then case-insensitive.
    group = Group.objects.filter(name="Staff").first()
    if group is None:
        near = Group.objects.filter(name__iexact="staff").first()
        if near is not None:
            group = near

    if group is None:
        print("RESULT: STAFF_GROUP_ABSENT")
        all_names = list(Group.objects.order_by("name").values_list("name", flat=True))
        print(f"ALL_GROUP_NAMES={all_names}")
        return

    # Step 2: group identity.
    print(f"STAFF_GROUP_ID={group.pk}")
    print(f"STAFF_GROUP_NAME={group.name!r}")
    print(f"STAFF_GROUP_PERMISSION_COUNT={group.permissions.count()}")

    # Step 3: resolve the through table name at runtime.
    through_table = CustomUser.groups.through._meta.db_table
    print(f"THROUGH_TABLE_NAME={through_table}")

    # Step 4: users linked to the group via user_set (PermissionsMixin related_name).
    linked_users = list(group.user_set.all().order_by("pk"))
    print(f"STAFF_LINKED_USER_COUNT={len(linked_users)}")
    for u in linked_users:
        print(f"STAFF_LINKED_USER pk={u.pk} email={u.email} is_staff={u.is_staff}")

    # Step 5: ProjectMembership rows whose group is Staff.
    memberships = list(
        ProjectMembership.objects.filter(group_id=group.pk).select_related("user", "project").order_by("pk")
    )
    print(f"STAFF_MEMBERSHIP_COUNT={len(memberships)}")
    for m in memberships:
        print(
            f"STAFF_MEMBERSHIP pk={m.pk} user_email={m.user.email} "
            f"project_pk={m.project.pk} project_name={m.project.name!r}"
        )

    # Step 6: ProjectInvitation rows whose group is Staff, plus their history footprint.
    invitations = list(
        ProjectInvitation.objects.filter(group_id=group.pk)
        .select_related("user", "sender", "project", "status")
        .order_by("pk")
    )
    print(f"STAFF_INVITATION_COUNT={len(invitations)}")
    invitation_pks = []
    for inv in invitations:
        invitation_pks.append(inv.pk)
        print(
            f"STAFF_INVITATION pk={inv.pk} recipient_email={inv.user.email} "
            f"sender_email={inv.sender.email} project_name={inv.project.name!r} "
            f"status={inv.status.name!r}"
        )

    if invitation_pks:
        history_count = ProjectInvitation.history.filter(id__in=invitation_pks).count()
    else:
        history_count = 0
    print(f"STAFF_INVITATION_HISTORY_ROWS={history_count}")

    # Step 7: dry-run deletion collector.
    collector = NestedObjects(using="default")
    collector.collect([group])
    model_counts = collector.model_objs if hasattr(collector, "model_objs") else None
    print("COLLECTOR_VIEW_START")
    print(
        "COLLECTOR_VIEW_NOTE: this excludes signal-driven cascade_delete_history "
        "deletions on ProjectInvitation history, so it is a floor on the true footprint."
    )
    counts = {}
    for model, objs in collector.data.items():
        counts[model._meta.label] = len(objs)
    for label, count in sorted(counts.items()):
        print(f"COLLECTOR_MODEL label={label} count={count}")
    print("COLLECTOR_VIEW_END")

    # Step 8: baseline totals for later verification.
    total_users = CustomUser.objects.count()
    staff_flag_users = CustomUser.objects.filter(is_staff=True).count()
    total_groups = Group.objects.count()
    total_memberships = ProjectMembership.objects.count()
    total_invitations = ProjectInvitation.objects.count()

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {through_table}")
        total_through_rows = cursor.fetchone()[0]

    print(f"BASELINE_TOTAL_USERS={total_users}")
    print(f"BASELINE_USERS_WITH_IS_STAFF_TRUE={staff_flag_users}")
    print(f"BASELINE_TOTAL_GROUPS={total_groups}")
    print(f"BASELINE_TOTAL_PROJECT_MEMBERSHIPS={total_memberships}")
    print(f"BASELINE_TOTAL_PROJECT_INVITATIONS={total_invitations}")
    print(f"BASELINE_TOTAL_THROUGH_TABLE_ROWS={total_through_rows}")

    print("RESULT: INSPECTION_COMPLETE")


try:
    main()
except Exception as exc:  # noqa: BLE001 - transcript must record any failure verbatim
    print(f"RESULT: INSPECTION_FAILED {exc!r}")
    traceback.print_exc()
    sys.exit(1)
