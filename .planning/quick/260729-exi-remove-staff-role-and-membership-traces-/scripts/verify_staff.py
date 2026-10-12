"""
Fresh-process verification of the Staff group cleanup, run as a separate
process from delete_staff.py so it reads committed state through a new
database connection.

Reads baseline values from environment variables sourced from the Task 1
transcript, rather than re-deriving them, so a mistake in the deletion step
cannot quietly redefine its own success criteria.

Required environment variables:
    STAFF_MODE
    STAFF_GROUP_ID
    BASELINE_TOTAL_USERS
    BASELINE_USERS_WITH_IS_STAFF_TRUE
    BASELINE_TOTAL_GROUPS
    BASELINE_TOTAL_PROJECT_MEMBERSHIPS
    BASELINE_TOTAL_PROJECT_INVITATIONS
    BASELINE_TOTAL_THROUGH_TABLE_ROWS
    BASELINE_STAFF_MEMBERSHIP_COUNT
    BASELINE_STAFF_INVITATION_COUNT
"""

import os
import sys
import traceback


def env_int(name):
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f"required environment variable {name} is not set")
    return int(value)


def main():
    from django.contrib.auth.models import Group as ConcreteGroup
    from django.db import connection

    from api.models import CustomUser, ProjectInvitation, ProjectMembership

    mode = os.environ.get("STAFF_MODE")
    if mode not in ("proceed-full", "memberships-only"):
        raise RuntimeError(f"STAFF_MODE must be proceed-full or memberships-only, got {mode!r}")

    staff_group_id = env_int("STAFF_GROUP_ID")
    baseline_total_users = env_int("BASELINE_TOTAL_USERS")
    baseline_is_staff_users = env_int("BASELINE_USERS_WITH_IS_STAFF_TRUE")
    baseline_total_groups = env_int("BASELINE_TOTAL_GROUPS")
    baseline_total_memberships = env_int("BASELINE_TOTAL_PROJECT_MEMBERSHIPS")
    baseline_total_invitations = env_int("BASELINE_TOTAL_PROJECT_INVITATIONS")
    env_int("BASELINE_TOTAL_THROUGH_TABLE_ROWS")  # read for completeness, not used directly below
    baseline_staff_memberships = env_int("BASELINE_STAFF_MEMBERSHIP_COUNT")
    baseline_staff_invitations = env_int("BASELINE_STAFF_INVITATION_COUNT")

    through_table = CustomUser.groups.through._meta.db_table

    failures = []

    # Check 1: Staff group presence/absence, mode-dependent.
    staff_exact = ConcreteGroup.objects.filter(name="Staff").first()
    staff_ci = ConcreteGroup.objects.filter(name__iexact="staff").first()
    if mode == "proceed-full":
        ok = staff_exact is None and staff_ci is None
        print(f"CHECK_1_STAFF_GROUP_ABSENT={'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append("CHECK_1_STAFF_GROUP_ABSENT")
    else:
        ok = staff_exact is not None and staff_exact.pk == staff_group_id
        print(f"CHECK_1_STAFF_GROUP_STILL_PRESENT={'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append("CHECK_1_STAFF_GROUP_STILL_PRESENT")

    # Check 2: zero ProjectMembership rows reference the group id.
    remaining_memberships = ProjectMembership.objects.filter(group_id=staff_group_id).count()
    ok = remaining_memberships == 0
    print(f"CHECK_2_ZERO_STAFF_MEMBERSHIPS={'PASS' if ok else 'FAIL'} remaining={remaining_memberships}")
    if not ok:
        failures.append("CHECK_2_ZERO_STAFF_MEMBERSHIPS")

    # Check 3: invitation state, mode-dependent.
    total_invitations_now = ProjectInvitation.objects.count()
    if mode == "proceed-full":
        remaining_invitations = ProjectInvitation.objects.filter(group_id=staff_group_id).count()
        ok = remaining_invitations == 0
        print(f"CHECK_3_ZERO_STAFF_INVITATIONS={'PASS' if ok else 'FAIL'} remaining={remaining_invitations}")
        if not ok:
            failures.append("CHECK_3_ZERO_STAFF_INVITATIONS")
    else:
        ok = total_invitations_now == baseline_total_invitations
        print(
            f"CHECK_3_INVITATION_COUNT_UNCHANGED={'PASS' if ok else 'FAIL'} "
            f"baseline={baseline_total_invitations} now={total_invitations_now}"
        )
        if not ok:
            failures.append("CHECK_3_INVITATION_COUNT_UNCHANGED")

    # Check 4: through table has no row referencing the group id, raw query, runtime-resolved table.
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {through_table} WHERE group_id = %s", [staff_group_id])
        remaining_through_rows = cursor.fetchone()[0]
    ok = remaining_through_rows == 0
    print(f"CHECK_4_ZERO_THROUGH_TABLE_ROWS={'PASS' if ok else 'FAIL'} remaining={remaining_through_rows}")
    if not ok:
        failures.append("CHECK_4_ZERO_THROUGH_TABLE_ROWS")

    # Check 5: users and is_staff flag preserved.
    total_users_now = CustomUser.objects.count()
    is_staff_users_now = CustomUser.objects.filter(is_staff=True).count()
    ok = total_users_now == baseline_total_users and is_staff_users_now == baseline_is_staff_users
    print(
        f"CHECK_5_USERS_PRESERVED={'PASS' if ok else 'FAIL'} "
        f"total_users baseline={baseline_total_users} now={total_users_now}; "
        f"is_staff_users baseline={baseline_is_staff_users} now={is_staff_users_now}"
    )
    if not ok:
        failures.append("CHECK_5_USERS_PRESERVED")

    # Check 6: group count, mode-dependent.
    total_groups_now = ConcreteGroup.objects.count()
    if mode == "proceed-full":
        expected_groups = baseline_total_groups - 1
        count_ok = total_groups_now == expected_groups
        no_staff_left = staff_exact is None and staff_ci is None
        ok = count_ok and no_staff_left
        print(
            f"CHECK_6_GROUP_COUNT_MINUS_ONE={'PASS' if ok else 'FAIL'} "
            f"baseline={baseline_total_groups} expected={expected_groups} now={total_groups_now} "
            f"no_staff_name_remaining={no_staff_left}"
        )
        if not ok:
            failures.append("CHECK_6_GROUP_COUNT_MINUS_ONE")
    else:
        ok = total_groups_now == baseline_total_groups
        print(
            f"CHECK_6_GROUP_COUNT_UNCHANGED={'PASS' if ok else 'FAIL'} "
            f"baseline={baseline_total_groups} now={total_groups_now}"
        )
        if not ok:
            failures.append("CHECK_6_GROUP_COUNT_UNCHANGED")

    # Check 7: ProjectMembership total dropped by exactly the Staff memberships removed.
    total_memberships_now = ProjectMembership.objects.count()
    expected_memberships = baseline_total_memberships - baseline_staff_memberships
    ok = total_memberships_now == expected_memberships
    print(
        f"CHECK_7_MEMBERSHIP_COUNT_DELTA={'PASS' if ok else 'FAIL'} "
        f"baseline={baseline_total_memberships} staff_removed={baseline_staff_memberships} "
        f"expected={expected_memberships} now={total_memberships_now}"
    )
    if not ok:
        failures.append("CHECK_7_MEMBERSHIP_COUNT_DELTA")

    if failures:
        print(f"RESULT: VERIFICATION_FAILED failing_checks={failures}")
        sys.exit(1)
    print("RESULT: VERIFICATION_PASSED")


try:
    main()
except Exception as exc:  # noqa: BLE001 - transcript must record any failure verbatim
    print(f"RESULT: VERIFICATION_FAILED {exc!r}")
    traceback.print_exc()
    sys.exit(1)
