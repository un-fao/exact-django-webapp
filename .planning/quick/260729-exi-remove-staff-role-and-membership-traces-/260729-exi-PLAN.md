---
phase: quick-260729-exi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/delete_staff.py
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/verify_staff.py
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/02-deletion.txt
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt
  - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/260729-exi-SUMMARY.md
autonomous: false
requirements:
  - STAFF-01
  - STAFF-02
  - STAFF-03
  - STAFF-04
branch: none (data-only task against the review database, no source changes)

must_haves:
  truths:
    - "After the cleanup, no django.contrib.auth Group named Staff exists in the review database, under any letter casing."
    - "Every CustomUser row present before the cleanup is still present after it, and the count of users with is_staff=True is identical before and after, because the is_staff column is a separate Django concept from the Staff group."
    - "No row in the CustomUser/Group many-to-many through table, in ProjectMembership, or in ProjectInvitation references the deleted Staff group id."
    - "Every Group other than Staff still exists, and every ProjectMembership whose group was not Staff is byte-identical to its pre-cleanup state."
    - "The exact set of removed rows is recorded per trace type, with affected user emails and project names, in the evidence files and in SUMMARY.md."
    - "If no group named Staff exists in the review database, nothing at all is deleted and that outcome is recorded as the result."
    - "No file under djangoexact/ is modified: this task changes data, not source."
  artifacts:
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/delete_staff.py
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/verify_staff.py
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/02-deletion.txt
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt
    - .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/260729-exi-SUMMARY.md
  key_links:
    - "api.models.Group (djangoexact/api/models.py:103) is declared `class Group(auth_models.Group)` with `proxy = True`. It is a proxy, not a separate table, so api.models.Group and django.contrib.auth.models.Group address the same auth_group row. Deleting through either manager is the same delete."
    - "TWO models hold a CASCADE foreign key to Group, not one. ProjectMembership.group (djangoexact/api/models.py:924) AND ProjectInvitation.group (djangoexact/api/models.py:899). The task brief named only ProjectMembership. Deleting the Staff group therefore also destroys every Staff project invitation, and because the constraint is a database-level CASCADE there is no way to delete the group while keeping those invitation rows."
    - "ProjectInvitation inherits Historical (djangoexact/api/models.py:144), whose HistoricalRecords is configured with cascade_delete_history=True. Deleting an invitation therefore also deletes its HistoricalProjectInvitation rows, through a post_delete signal that Django's NestedObjects collector cannot see. Collector output alone understates the true footprint, so the inspection step must count invitation history rows explicitly."
    - "ProjectMembership is a plain models.Model with no HistoricalRecords, so removing membership rows destroys no history."
    - "The many-to-many through table name must be resolved at runtime from CustomUser.groups.through._meta.db_table, never hardcoded, because it is auto-generated from the api app label and the custom user model."
    - "The reverse accessor from a Group to its users is group.user_set, because PermissionsMixin declares the groups field with related_name='user_set'. It is not group.customuser_set."
    - "Database credentials resolve correctly only when the command runs with the working directory set to djangoexact/ and APP_MODE=review, so settings.py loads .env and then .env.review on top and points psycopg2 at 127.0.0.1:5432 where cloud-sql-proxy is listening. Running from the repo root, or without APP_MODE, silently targets a different database."
---

<objective>
Remove the residual "Staff" auth Group and all of its membership traces from the review environment database, preserving every user and everything unrelated to that role.

Purpose: the Staff group is pure data residue. The Python code that once auto-synced it was removed in the "refactor(api): drop Staff group auto-sync signals" commit, and a repository-wide grep confirms no source file references the string "Staff" any more. The group and its membership rows now sit in the review database with nothing maintaining them, so they are misleading residue that can grant or imply access nobody intended.

Output: an executed, evidenced cleanup. Three committed scripts recording exactly what ran against the review database, three evidence transcripts, and a SUMMARY.md capturing the before and after state. No source code under djangoexact/ changes.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@djangoexact/api/models.py

Operational facts already verified by the orchestrator. Do not re-verify these, and in particular do not cat or grep any .env file, because reading them is permission-blocked in this session. Let Django load them in-process.

- cloud-sql-proxy is running at 127.0.0.1:5432, attached to the Cloud SQL instance fao-exact-review:europe-west1:fao-exact-review-postgres, which is the review environment database.
- The working Python environment is /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.venv/bin/python, with Django 5.2.14 and psycopg2 installed.
- Every database command in this plan runs with the working directory set to /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact and with APP_MODE=review exported, invoking ../.venv/bin/python manage.py shell.
- api.CustomUser is AUTH_USER_MODEL and extends AbstractUser, so it carries the standard groups many-to-many to auth.Group.

Scope, locked. Remove exactly three trace types plus the group row itself:
1. Rows in the CustomUser/Group many-to-many through table that link any user to the Staff group.
2. ProjectMembership rows whose group is the Staff group.
3. ProjectInvitation rows whose group is the Staff group. This one is a cascade consequence discovered during planning, and is the subject of the approval checkpoint in Task 2.
4. The Staff auth_group row itself, which takes its auth_group_permissions rows with it.

Preserve, explicitly: all user rows, the is_staff boolean flag on users, which is a separate Django concept and must not be touched, every other Group, every membership whose group is not Staff, and all auditlog and simple_history rows for models that are not being deleted. Historical records are history, not "traces in memberships", so they are left alone.

Expected benign side effect: django-auditlog registers post_delete receivers that write new LogEntry rows describing these deletions. That is added traceability, not a trace to remove, and it must not be suppressed.
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Inspect and capture the full Staff footprint, read-only</name>
  <precondition>cloud-sql-proxy is listening on 127.0.0.1:5432 against fao-exact-review. Confirm before running anything, for example with a TCP connect check to that address, and halt if it is not listening rather than letting Django fall back to another host.</precondition>
  <files>.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py, .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt</files>
  <action>
Write a read-only inspection script that performs zero writes and prints a deterministic, greppable transcript. This is the tracer slice: it proves the whole path (proxy shell invocation, review settings loading, cloud-sql-proxy connection, ORM read of every affected model) end to end before anything destructive happens.

The script must, in order:

1. Resolve the group. Query django.contrib.auth.models.Group for name exactly equal to "Staff". If that returns nothing, retry with a case-insensitive name lookup and report any near match found. If neither finds a group, print a single line reading RESULT: STAFF_GROUP_ABSENT followed by the list of all existing group names, and exit without printing any of the sections below. That is a complete, successful outcome for this task, and the plan then stops at Task 2 with nothing to delete.
2. If found, print the group primary key, its exact name, and the count of its permission rows, each on its own labeled line. Print the primary key on a line beginning with STAFF_GROUP_ID= so later steps can read it back mechanically.
3. Resolve the many-to-many through table name at runtime from CustomUser.groups.through._meta.db_table and print it. Do not hardcode it.
4. Count and list the users linked to the group through group.user_set, printing one line per user with the user primary key, the email, and the is_staff flag value. Use group.user_set, not a customuser_set accessor, because PermissionsMixin names the reverse accessor user_set.
5. Count and list ProjectMembership rows whose group_id equals the group primary key, printing one line per row with the membership primary key, the user email, the project primary key, and the project name. Use select_related on user and project so the listing does not fan out into per-row queries.
6. Count and list ProjectInvitation rows whose group_id equals the group primary key, printing one line per row with the invitation primary key, the recipient email, the sender email, the project name, and the invitation status name. Then count the HistoricalProjectInvitation rows attached to those invitation primary keys, reachable through the history manager, and print that count on a line beginning with STAFF_INVITATION_HISTORY_ROWS=. This count matters because ProjectInvitation inherits Historical, whose HistoricalRecords sets cascade_delete_history=True, so deleting an invitation silently deletes its history through a post_delete signal that the collector in step 7 cannot report.
7. Run Django's deletion collector in dry-run form, using django.contrib.admin.utils.NestedObjects against the default database, collecting the single group object, and print the resulting model-to-count mapping. Label this section as the collector view and note in the printed output that it excludes signal-driven history deletions, so it is a floor on the footprint rather than the whole of it.
8. Capture and print baseline totals that later verification compares against: total CustomUser rows, count of users with is_staff=True, total Group rows, total ProjectMembership rows, total ProjectInvitation rows, and total rows in the through table read through a raw query against the runtime-resolved table name. Prefix each with BASELINE_ so verification can grep them back.
9. Print a final line reading RESULT: INSPECTION_COMPLETE.

Guard the whole script so that any exception prints RESULT: INSPECTION_FAILED with the exception text and exits non-zero, so a partial transcript can never be mistaken for a clean one.

Run it with the working directory set to djangoexact, with APP_MODE=review exported, feeding the script into manage.py shell on standard input, and tee the combined output into the evidence file. Django's shell command executes standard input as a script when standard input is not a terminal, which holds under a redirect even while stdout is piped to tee.

Do not modify any file under djangoexact/. The scripts live in the planning directory precisely so that what ran against a shared database stays auditable without touching the application.
  </action>
  <verify>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact &amp;&amp; APP_MODE=review ../.venv/bin/python manage.py shell &lt; ../.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py 2&gt;&amp;1 | tee ../.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/01-inspection.txt | grep -qE '^RESULT: (INSPECTION_COMPLETE|STAFF_GROUP_ABSENT)$'</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp &amp;&amp; git status --porcelain djangoexact/ | grep -c . | grep -qx 0</automated>
  </verify>
  <done>evidence/01-inspection.txt exists and ends in either RESULT: INSPECTION_COMPLETE, carrying the group id, the per-trace-type counts and listings, the invitation history row count, the collector mapping, and all BASELINE_ totals, or RESULT: STAFF_GROUP_ABSENT with the full list of existing group names. No file under djangoexact/ is modified.</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <decision>Approve, narrow, or abort the destructive deletion, now that the true footprint is known.</decision>
  <context>
Present the evidence from Task 1 to the developer before anything is deleted, because this operates on a shared review database and the deletion cannot be undone from within this task.

If Task 1 reported STAFF_GROUP_ABSENT, state that plainly, skip Task 3 entirely, and record the no-op outcome. There is nothing to decide.

Otherwise, report the counts per trace type, and lead with the item the original brief did not anticipate: ProjectInvitation also carries a CASCADE foreign key to Group at djangoexact/api/models.py:899. Deleting the Staff group therefore also deletes every Staff project invitation, and, because ProjectInvitation inherits Historical with cascade_delete_history=True, the historical rows for those invitations go with them. State the exact invitation count and the exact invitation history row count from the transcript. Be explicit that this is a database-level cascade, so there is no variant of "delete the group but keep those invitations".

Also confirm to the developer what is not affected: user rows, the is_staff flag, every other group, and every membership whose group is not Staff.

If the invitation count is zero, say so, because then the cascade concern is theoretical and the decision is straightforward.
  </context>
  <options>
    <option id="proceed-full">
      <name>Delete the Staff group and all three trace types</name>
      <pros>Fully satisfies the request. Leaves no residue and no dangling role. Stale Staff invitations, which could never be meaningfully accepted once the role is gone, disappear with it.</pros>
      <cons>Irreversible. Destroys the listed ProjectInvitation rows and their history alongside the memberships.</cons>
    </option>
    <option id="memberships-only">
      <name>Delete only the many-to-many links and the ProjectMembership rows, and keep the Staff group row</name>
      <pros>Preserves every ProjectInvitation row and its history. Strips the effective access, which is what actually matters operationally.</pros>
      <cons>Leaves the Staff group visible in the admin and in any group listing, so the role is not actually removed and the request is only partly met.</cons>
    </option>
    <option id="abort">
      <name>Abort and change nothing</name>
      <pros>Zero risk. Keeps the inspection evidence for a later decision.</pros>
      <cons>The residue remains.</cons>
    </option>
  </options>
  <resume-signal>Select: proceed-full, memberships-only, or abort</resume-signal>
</task>

<task type="auto">
  <name>Task 3: Execute the transactional deletion, verify the result, and record evidence</name>
  <precondition>Task 2 returned proceed-full or memberships-only. If Task 2 returned abort, or Task 1 reported STAFF_GROUP_ABSENT, take the no-op path instead: run no deletion at all, write evidence/02-deletion.txt containing a single line reading RESULT: DELETION_SKIPPED followed by the reason, write evidence/03-verification.txt containing a single line reading RESULT: VERIFICATION_PASSED followed by a note that it passes vacuously because nothing was changed, and write SUMMARY.md recording the no-op outcome and the Task 1 inspection evidence. Those two files keep the verify gates below meaningful on the no-op path rather than failing for absence.</precondition>
  <files>.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/delete_staff.py, .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/verify_staff.py, .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/02-deletion.txt, .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt, .planning/quick/260729-exi-remove-staff-role-and-membership-traces-/260729-exi-SUMMARY.md</files>
  <action>
Write and run the deletion script, then the verification script, then the summary.

Deletion script. Read the expected group primary key from a STAFF_GROUP_ID environment variable, taken from the Task 1 transcript, and read the approved mode from a STAFF_MODE environment variable set to the Task 2 selection. Before touching anything, re-resolve the group by the name "Staff" and assert its primary key equals the expected value, aborting with a non-zero exit if it does not, so a database that changed between inspection and deletion cannot lead to the wrong row being removed.

Wrap every write in a single django.db.transaction.atomic block, and perform the deletions in this order so the returned counts stay attributable:

1. Re-read and print the three trace counts from inside the transaction, so the transcript proves what the transaction itself saw rather than what the earlier read saw.
2. Clear the many-to-many links by calling clear on group.user_set, and print the number of links removed, computed before the call.
3. Delete ProjectMembership rows filtered by group_id, and print the returned count mapping.
4. If the approved mode is proceed-full, delete ProjectInvitation rows filtered by group_id, and print the returned count mapping. If the mode is memberships-only, skip this step and skip step 5 entirely, printing an explicit line stating both were skipped by developer decision.
5. If the mode is proceed-full, delete the group itself through the concrete django.contrib.auth.models.Group manager, not the api proxy, and capture the returned count mapping.
6. Apply a safety assertion over that final mapping. Build an allowlist of model labels that may legitimately appear with a non-zero count: the concrete auth Group label, the api proxy Group label, the Group permissions through label, and the user-to-groups through label. If any other label appears with a non-zero count, raise an exception so the atomic block rolls the entire transaction back, and print the offending mapping. This is the net that catches any cascade path this plan did not foresee.
7. After the transaction commits, print a line reading RESULT: DELETION_COMPLETE followed by a per-trace-type tally of what was removed.

Guard the script so any exception prints RESULT: DELETION_FAILED with the exception text and exits non-zero. Because all writes sit inside one atomic block, a failure leaves the database exactly as it was.

Verification script, run afterwards as a separate process so it reads committed state through a fresh connection. It must assert and print, one labeled line per check:

1. No group named Staff exists, checked both case-sensitively and case-insensitively. Under memberships-only, invert this check to assert the group is still present, and say so.
2. Zero ProjectMembership rows reference the recorded group id.
3. Under proceed-full, zero ProjectInvitation rows reference the recorded group id. Under memberships-only, assert the invitation count is unchanged from the Task 1 baseline.
4. Zero rows in the through table reference the recorded group id, checked with a raw query against the table name resolved again at runtime from CustomUser.groups.through._meta.db_table.
5. The total CustomUser count equals the Task 1 baseline, and the count of users with is_staff=True equals the Task 1 baseline. Users and the is_staff flag were preserved.
6. Under proceed-full, the total Group count equals the Task 1 baseline minus one, and every other group name from the baseline listing is still present. Under memberships-only, the total Group count is unchanged.
7. The total ProjectMembership count equals the Task 1 baseline minus the number of Staff memberships removed, which proves no unrelated membership was collateral damage.

Have the verification script print RESULT: VERIFICATION_PASSED only when every check passes, and RESULT: VERIFICATION_FAILED plus the failing check labels otherwise, exiting non-zero on failure. Pass the baseline values in through environment variables read from the Task 1 transcript, rather than re-deriving them, so a mistake in the deletion cannot quietly redefine its own success criteria.

Finally write SUMMARY.md. Record the selected Task 2 option, the group id and name, the per-trace-type counts with the affected user emails and project names taken from the Task 1 listing, the invitation and invitation-history counts, the verification results, and an explicit statement that no source file under djangoexact/ was changed. Note the two planning discoveries for whoever reads this later: that ProjectInvitation also cascaded from the group, and that api.models.Group is a proxy over the same auth_group row rather than a second table.
  </action>
  <verify>
    <automated>grep -qE '^RESULT: (DELETION_COMPLETE|DELETION_SKIPPED)$' /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/02-deletion.txt</automated>
    <automated>grep -qx 'RESULT: VERIFICATION_PASSED' /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/evidence/03-verification.txt</automated>
    <automated>cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp &amp;&amp; git status --porcelain djangoexact/ | grep -c . | grep -qx 0</automated>
  </verify>
  <done>The Staff group and its approved trace types are gone from the review database, evidence/02-deletion.txt records the per-type tally, evidence/03-verification.txt reads RESULT: VERIFICATION_PASSED with every check labeled, SUMMARY.md captures the before and after state and the affected users, and djangoexact/ has no modified file.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local shell to review Cloud SQL | Destructive DDL-free DML crosses into a shared, multi-user environment database over cloud-sql-proxy. |
| .env.review to process environment | Database credentials load into the process; they must never reach a transcript, an evidence file, or a commit. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260729-01 | Tampering | delete_staff.py against the wrong database | high | mitigate | Every invocation pins the working directory to djangoexact and exports APP_MODE=review, and Task 1 asserts cloud-sql-proxy is listening on 127.0.0.1:5432 before any command runs. |
| T-260729-02 | Denial of Service | over-broad cascade removing unrelated rows | high | mitigate | All writes sit in one transaction.atomic block, and an allowlist assertion over the returned deletion mapping raises and rolls back if any unexpected model label appears with a non-zero count. |
| T-260729-03 | Tampering | group id drift between inspection and deletion | medium | mitigate | The deletion script re-resolves the group by name and asserts its primary key matches the STAFF_GROUP_ID recorded in Task 1, aborting on mismatch. |
| T-260729-04 | Repudiation | no record of what was removed from a shared database | medium | mitigate | Three committed scripts plus three tee'd evidence transcripts plus SUMMARY.md, and django-auditlog post_delete receivers are deliberately left enabled so the database keeps its own record. |
| T-260729-05 | Information Disclosure | database credentials leaking into evidence files | high | mitigate | Scripts print only model data and counts, never settings.DATABASES or environment contents, and no .env file is read, catted, or grepped at any point. |
| T-260729-06 | Elevation of Privilege | residual Staff group implying access nobody granted | medium | mitigate | This task removes the group and its links, which is the mitigation itself. |
</threat_model>

<verification>
Read the three evidence transcripts end to end, not just their RESULT lines. Confirm the per-trace-type counts in evidence/02-deletion.txt match the listings captured in evidence/01-inspection.txt, and that the baseline totals asserted in evidence/03-verification.txt are the ones Task 1 actually recorded rather than values recomputed after the deletion.

Confirm git status shows changes only under .planning/, never under djangoexact/.
</verification>

<success_criteria>
No auth Group named Staff remains in the review database under any casing, unless the developer selected memberships-only or abort at the Task 2 checkpoint, in which case the selected outcome is what holds and SUMMARY.md says so plainly.

Zero rows reference the removed group id across the CustomUser/Group through table, ProjectMembership, and ProjectInvitation.

The CustomUser count and the is_staff=True count are identical before and after. The total ProjectMembership count dropped by exactly the number of Staff memberships and by no more. Every non-Staff group survives.

Every removed row is attributable from the evidence to a named user and, where applicable, a named project.
</success_criteria>

<output>
Create `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/260729-exi-SUMMARY.md` when done.
</output>
