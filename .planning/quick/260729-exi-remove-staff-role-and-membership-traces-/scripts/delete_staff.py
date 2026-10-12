"""
Transactional deletion of the Staff auth Group and its approved trace types in
the review database.

Reads:
    STAFF_GROUP_ID  - the group primary key recorded by inspect_staff.py.
    STAFF_MODE      - "proceed-full" or "memberships-only", the Task 2 decision.

Run with:
    cd djangoexact && APP_MODE=review STAFF_GROUP_ID=<id> STAFF_MODE=<mode> \
        ../.venv/bin/python manage.py shell < \
        ../.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/delete_staff.py

Re-resolves the group by name before touching anything, so a database that
changed between inspection and deletion cannot lead to the wrong row being
removed. All writes sit inside a single django.db.transaction.atomic block.
"""

import os
import sys
import traceback


def main():
    from django.contrib.auth.models import Group as ConcreteGroup
    from django.db import transaction

    from api.models import CustomUser, Group as ApiGroup, ProjectInvitation, ProjectMembership

    expected_id_raw = os.environ.get("STAFF_GROUP_ID")
    mode = os.environ.get("STAFF_MODE")

    if expected_id_raw is None:
        raise RuntimeError("STAFF_GROUP_ID environment variable is not set")
    if mode not in ("proceed-full", "memberships-only"):
        raise RuntimeError(f"STAFF_MODE must be proceed-full or memberships-only, got {mode!r}")

    expected_id = int(expected_id_raw)

    # Re-resolve the group by name and assert identity before touching anything.
    group = ConcreteGroup.objects.get(name="Staff")
    if group.pk != expected_id:
        raise RuntimeError(
            f"Staff group pk drifted: expected {expected_id}, found {group.pk}. Aborting without changes."
        )
    print(f"CONFIRMED_STAFF_GROUP_ID={group.pk}")
    print(f"STAFF_MODE={mode}")

    invitation_deleted_count = 0
    group_deleted_count = 0

    with transaction.atomic():
        # Step 1: re-read the three trace counts from inside the transaction.
        m2m_count_before = group.user_set.count()
        membership_count_before = ProjectMembership.objects.filter(group_id=group.pk).count()
        invitation_count_before = ProjectInvitation.objects.filter(group_id=group.pk).count()
        print(f"TX_M2M_LINK_COUNT={m2m_count_before}")
        print(f"TX_MEMBERSHIP_COUNT={membership_count_before}")
        print(f"TX_INVITATION_COUNT={invitation_count_before}")

        # Step 2: clear the many-to-many links.
        removed_links = m2m_count_before
        group.user_set.clear()
        print(f"REMOVED_M2M_LINKS={removed_links}")

        # Step 3: delete ProjectMembership rows.
        membership_deleted_count, membership_mapping = ProjectMembership.objects.filter(group_id=group.pk).delete()
        print(f"REMOVED_MEMBERSHIP_COUNT={membership_deleted_count}")
        print(f"REMOVED_MEMBERSHIP_MAPPING={membership_mapping}")

        if mode == "proceed-full":
            # Step 4: delete ProjectInvitation rows.
            invitation_deleted_count, invitation_mapping = ProjectInvitation.objects.filter(
                group_id=group.pk
            ).delete()
            print(f"REMOVED_INVITATION_COUNT={invitation_deleted_count}")
            print(f"REMOVED_INVITATION_MAPPING={invitation_mapping}")

            # Step 5: delete the group itself through the concrete manager, not the api proxy.
            concrete_group = ConcreteGroup.objects.get(pk=expected_id)
            group_deleted_count, group_mapping = concrete_group.delete()
            print(f"REMOVED_GROUP_COUNT={group_deleted_count}")
            print(f"REMOVED_GROUP_MAPPING={group_mapping}")

            # Step 6: safety assertion over the final mapping.
            allowlist = {
                ConcreteGroup._meta.label,
                ApiGroup._meta.label,
                ConcreteGroup.permissions.through._meta.label,
                CustomUser.groups.through._meta.label,
            }
            print(f"SAFETY_ALLOWLIST={sorted(allowlist)}")
            offending = {
                label: count for label, count in group_mapping.items() if count and label not in allowlist
            }
            if offending:
                print(f"SAFETY_ASSERTION_FAILED offending_mapping={offending}")
                raise RuntimeError(f"Unforeseen cascade deletion detected, rolling back: {offending}")
            print("SAFETY_ASSERTION_PASSED")
        else:
            print(
                "SKIPPED: ProjectInvitation deletion and Group row deletion, "
                "by developer decision (memberships-only)"
            )

    # Step 7: transaction committed.
    print("RESULT: DELETION_COMPLETE")
    print(f"TALLY_M2M_LINKS_REMOVED={removed_links}")
    print(f"TALLY_MEMBERSHIPS_REMOVED={membership_deleted_count}")
    print(f"TALLY_INVITATIONS_REMOVED={invitation_deleted_count}")
    print(f"TALLY_GROUP_ROWS_REMOVED={group_deleted_count}")


try:
    main()
except Exception as exc:  # noqa: BLE001 - transcript must record any failure verbatim
    print(f"RESULT: DELETION_FAILED {exc!r}")
    traceback.print_exc()
    sys.exit(1)
