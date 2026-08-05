---
phase: quick-260805-nsn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/deploy.yaml
  - .github/workflows/deploy-cloudrun.yaml
  - .planning/STATE.md
autonomous: true
requirements:
  - SYNC-01
  - SYNC-02
  - SYNC-03
branch: chore/sync-review-with-main

estimate:
  tokens: 45000
  raw_tokens: 30000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "Branch chore/sync-review-with-main contains a real merge commit whose two parents are origin/review and origin/main, so merging it into review makes review a superset of main and clears the CONFLICTING state on PR #265."
    - "Both deploy workflows still pin docker/setup-buildx-action to the immutable commit SHA 8d2750c68a42422c14e847fe6c8ac0403b4cbd6f applied by quick task 260805-l5b. Adopting the floating major-version ref from main would silently revert a Dependabot security fix and would very likely be rejected by the FAO Public Security Checks ruleset."
    - "Both deploy workflows carry the corrected comment wording written on main, which describes why the Buildx step is kept now that the job runs on a GitHub-hosted image. Keeping review's older wording would leave a comment that describes a runner the job no longer gets."
    - "Every runs-on declaration across the two workflows reads ubuntu-22.04. No runs-on line names the gcp-temporary self-hosted label, which has registered no runner since 2026-07-30. The label still appears in explanatory comment prose inherited verbatim from main, which is expected and must not be edited. This is main's fix from quick task 260803-gxo and it must survive the merge intact."
    - "STATE.md lists all five quick-task rows from both sides: 260803-gxo from main plus 260805-l5b, 260805-mmh, 260805-n82 and 260805-ncv from review, in chronological order."
    - "STATE.md carries exactly one Last activity line, the 2026-08-05 / 260805-ncv one from review, because review is strictly newer than main."
    - "A pull request exists targeting base review with head chore/sync-review-with-main, and it is left open and unmerged for the user to review."
  artifacts:
    - .github/workflows/deploy.yaml
    - .github/workflows/deploy-cloudrun.yaml
    - .planning/STATE.md
  key_links:
    - "PR #265 (review -> main, 'Update: 1.20.1') is CONFLICTING because review lacks main's 4 commits. GitHub's web conflict editor cannot fix it: that editor commits directly onto the head branch, and the org ruleset 'FAO Security Checks (review)' (id 15404692) applies a pull_request rule to refs/heads/review with current_user_can_bypass set to never. So the resolution has to land on a side branch and reach review through its own PR, which needs 0 approvals and only the org SCA workflow."
    - "git merge origin/main produces exactly 3 conflicted files: .github/workflows/deploy.yaml (1 block), .github/workflows/deploy-cloudrun.yaml (1 block), .planning/STATE.md (2 blocks). Everything else auto-merges."
    - "The only region of either workflow file that review changed relative to the merge base is the setup-buildx-action step. Every other main-vs-review difference in those files is a main-side correction that auto-merges. Therefore the correct post-merge workflow file is byte-identical to origin/main's version except for the single uses: line, and `git diff origin/main -- <the two workflows>` must show exactly 4 changed content lines after the merge."
    - "main's change of runs-on from 'gcp-temporary' to ubuntu-22.04 in both files auto-merges cleanly. There is nothing to decide there, but the verify gate asserts it survived because a careless whole-file resolution would silently drop it."
    - "The merge commit necessarily includes .planning/STATE.md. STATE.md is a conflicted file, so it is part of the merge resolution and cannot be excluded. The usual GSD rule about keeping planning docs out of code commits does not apply to this one commit."
---

<objective>
Merge `origin/main` into a side branch off `review`, resolve the three conflicted files,
and open a pull request into `review` so that PR #265 stops being CONFLICTING.

Purpose: PR #265 (`review` -> `main`, "Update: 1.20.1") cannot merge because `review` is
missing main's 4 commits, headed by the CI runner fix from quick task 260803-gxo. The
usual escape hatch, GitHub's web "Resolve conflicts" editor, is unavailable: it commits
straight onto the head branch, and the org ruleset "FAO Security Checks (review)"
(id 15404692) forbids direct pushes to `refs/heads/review` with no bypass. The resolution
therefore has to be made on `chore/sync-review-with-main` and merged into `review` through
a second, lighter pull request.

Output: a merge commit on `chore/sync-review-with-main`, the branch pushed to `origin`,
and an open PR into `review`. The PR is NOT merged; that is the user's call.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Repository root: `/home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp`
Remote: `un-fao/exact-django-webapp`. SSH push from this sandbox is known to work.

State at plan time, already done by the orchestrator, do NOT redo:
- `chore/sync-review-with-main` was created off `origin/review` with `--no-track` and is
  checked out. No merge is in progress. Working tree is clean apart from this quick-task
  planning directory.
- `origin/review` has the same tree as `origin/develop`.
- `origin/main` holds 4 commits `review` lacks: `8d461756`, `a3fc7efb`, `0d58b04e`,
  `06656789`.

The merge brings exactly 5 files across from main:
`.github/workflows/deploy.yaml`, `.github/workflows/deploy-cloudrun.yaml`,
`.planning/STATE.md`, and two new untouched files under
`.planning/quick/260803-gxo-move-ci-off-offline-gcp-temporary-self-h/`.

Project rule: never use an em-dash anywhere in this repo, including the commit message and
the PR body. Commit messages follow Conventional Commits (commitizen).
</context>

<resolution_reference>

## Workflow conflict: the rule

Both workflow files have a single conflict block, on the "Set up Docker Buildx" step.
The resolution rule is the same for both and it is mechanical:

- Take the **comment lines from the `origin/main` side** of the block, verbatim. They are
  the corrected wording, written once the job moved to a GitHub-hosted image.
- Take the **`uses:` line from the `HEAD` (review) side**, verbatim. It carries the
  immutable commit SHA that quick task 260805-l5b applied as a Dependabot security fix.
  main's line still uses a floating major-version ref, which is exactly what the security
  fix removed.

Because review made no other change to either workflow file relative to the merge base,
an equivalent and simpler mechanic is: take main's whole file, then swap the one `uses:`
line back to the SHA-pinned form.

## Expected final block, `.github/workflows/deploy.yaml`

Base indent is 4 spaces for the list item.

```yaml
    - name: Set up Docker Buildx
      # Originally here because the self-hosted runner might not have the Docker
      # CLI plugin installed. The GitHub-hosted image ships Buildx, so this is
      # now about pinning the builder rather than supplying a missing one; keep
      # it so the build stays BuildKit-backed regardless of image changes.
      uses: docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f # v3.12.0
```

## Expected final block, `.github/workflows/deploy-cloudrun.yaml`

Base indent is 6 spaces for the list item. Note the closing sentence differs from
deploy.yaml; use main's wording for this file, do not copy the other file's.

```yaml
      - name: Set up Docker Buildx
        # Originally here because the self-hosted runner might not have the
        # Docker CLI plugin installed. The GitHub-hosted image ships Buildx, so
        # this is now about pinning the builder rather than supplying a missing
        # one; the build below needs BuildKit for its --secret mount.
        uses: docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f # v3.12.0
```

## STATE.md conflict blocks

**Block A**, around line 33, the `Last activity:` line. Two competing single lines.
Keep review's (2026-08-05, quick task 260805-ncv). Discard main's 2026-08-03 line.
review is strictly newer, so its line is the accurate one.

**Block B**, around line 106, rows of the "Quick Tasks Completed" table. This is a
keep-both merge, not a pick-a-side. main contributes one row, `260803-gxo`. review
contributes four, `260805-l5b`, `260805-mmh`, `260805-n82`, `260805-ncv`. Keep all five.
Order them chronologically, so the `260803-gxo` row sits after the existing `260729-k8y`
row and before the four `260805-*` rows. Do not reword any row.

## Merge commit message

Write it to a file and pass it with `git commit -F`. Suggested content, adapt freely but
keep the conventional subject and no em-dashes:

```
chore: merge main into the review sync branch

review was missing main's 4 commits, headed by the 260803-gxo CI runner fix,
which left PR #265 (review -> main) in a CONFLICTING state. The review branch
ruleset forbids direct pushes, so the resolution lands here and reaches review
through its own PR.

Three files conflicted:

* .github/workflows/deploy.yaml and .github/workflows/deploy-cloudrun.yaml,
  both on the Set up Docker Buildx step. Kept main's corrected comment text and
  review's SHA-pinned action ref. Taking main's floating major-version ref would
  revert the Dependabot fix applied by quick task 260805-l5b and would likely be
  rejected by the FAO Public Security Checks ruleset.

* .planning/STATE.md, on the Last activity line and the Quick Tasks Completed
  table. Kept review's newer Last activity line and merged both sides' table
  rows in chronological order.

main's move of every runs-on onto ubuntu-22.04 auto-merged and is preserved.
```

## PR body

Write it to a file and pass it with `gh pr create --body-file`. Suggested content:

```
Unblocks #265.

PR #265 (`review` -> `main`, "Update: 1.20.1") is CONFLICTING because `review`
is missing the 4 commits on `main` headed by the 260803-gxo CI runner fix.
GitHub's web conflict editor cannot resolve it, because that editor commits
directly onto the head branch and the "FAO Security Checks (review)" ruleset
applies a pull_request rule to `refs/heads/review` with no bypass. So the
resolution is made here and merged into `review` through this PR.

## Conflicts and how they were resolved

**`.github/workflows/deploy.yaml` and `.github/workflows/deploy-cloudrun.yaml`**,
one block each, on the `Set up Docker Buildx` step. Kept **main's corrected
comment text** and **review's SHA-pinned action ref**
(`docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f # v3.12.0`).

Taking main's floating major-version ref would revert the SHA pinning applied by
quick task 260805-l5b as a Dependabot security fix, and would very likely trip
the FAO Public Security Checks ruleset. Taking review's comment would leave text
describing a self-hosted runner that these jobs no longer run on.

**`.planning/STATE.md`**, two blocks, both keep-what-is-newer or keep-both:
the `Last activity` line keeps review's 2026-08-05 entry, and the Quick Tasks
Completed table keeps all five rows from both sides in chronological order.

main's move of every `runs-on` from `gcp-temporary` to `ubuntu-22.04` auto-merged
and is preserved: 3 jobs, 3 `ubuntu-22.04` declarations, no `runs-on` naming `gcp-temporary`.
The label survives only inside main's own explanatory comments, which is correct.

## Scope

Nothing outside the conflict resolution changed. Relative to `main`, the two
workflow files differ by exactly the two `uses:` lines.
```

</resolution_reference>

<tasks>

<task type="tracer">
  <name>Task 1: Merge origin/main and resolve both workflow conflicts</name>
  <files>.github/workflows/deploy.yaml, .github/workflows/deploy-cloudrun.yaml</files>
  <precondition>HEAD is `chore/sync-review-with-main`, no merge is in progress, and the working tree has no unstaged tracked changes. Assert with `git rev-parse --abbrev-ref HEAD`, `git rev-parse -q --verify MERGE_HEAD` returning nothing, and `git status --porcelain --untracked-files=no` returning empty. Halt if any of these fails.</precondition>
  <action>
Run `git fetch origin` then `git merge --no-ff origin/main` from the repository root. Expect
it to stop with conflicts in exactly three files. Confirm with `git diff --name-only
--diff-filter=U` that the unmerged set is exactly the two workflow files plus
`.planning/STATE.md`. If any other path is unmerged, halt and report: the diagnosis assumed
a three-file conflict and a fourth means something changed upstream.

Resolve `.github/workflows/deploy.yaml` and `.github/workflows/deploy-cloudrun.yaml` per the
rule in `<resolution_reference>`: keep the comment lines from the `origin/main` side of the
block, keep the `uses:` line from the `HEAD` side, delete the marker lines. The two expected
final blocks are quoted verbatim in `<resolution_reference>`, including the differing closing
sentence and the differing indentation between the two files. Match them exactly.

Do not resolve `.planning/STATE.md` yet, that is Task 2.

Note the auto-merged content you must NOT disturb while editing: main rewrote the comments
above each `runs-on` declaration and the comments around the Cloud Run HTTP reachability
probe. Those regions merged cleanly and already hold main's corrected text. Only touch the
conflict block.

`git add` the two workflow files once resolved. Do not commit yet.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp && \
WF=".github/workflows/deploy.yaml .github/workflows/deploy-cloudrun.yaml" && \
test "$(cat $WF | grep -cP '^(\x3c{7}|={7}|\x3e{7})')" = "0" && \
test "$(cat $WF | grep -v '^[[:space:]]*#' | grep -c 'uses: docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f')" = "2" && \
test "$(cat $WF | grep -v '^[[:space:]]*#' | grep -cE 'setup-buildx-action@v[0-9]')" = "0" && \
test "$(cat $WF | grep -cE '^[[:space:]]*runs-on:[[:space:]]*.?ubuntu-22\.04')" = "3" && \
test "$(cat $WF | grep -cE '^[[:space:]]*runs-on:.*gcp-temporary')" = "0" && \
test "$(cat $WF | grep -c 'Originally here because')" = "2" && \
test "$(cat $WF | grep -c 'may not have the Docker CLI plugin installed')" = "0" && \
test "$(git diff origin/main -- $WF | grep -cE '^[+-][^+-]')" = "4" && \
python3 -c "import yaml,sys;[yaml.safe_load(open(f)) for f in sys.argv[1:]]" $WF && \
echo VERIFY-T1-OK
    </automated>
  </verify>
  <done>
Both workflow files are free of conflict markers, both SHA-pin `setup-buildx-action` to
`8d2750c6...`, no floating major-version ref of that action survives anywhere in the two
files, all 3 `runs-on` declarations read `ubuntu-22.04` and none names `gcp-temporary`,
main's corrected comment wording is present twice and review's older wording zero times,
both files still parse as YAML, and the whole content diff against `origin/main` for these
two files is exactly 4 lines (2 removed, 2 added), which proves nothing else was disturbed.
Both files are staged. `.planning/STATE.md` is still unmerged.
  </done>
</task>

<task type="auto">
  <name>Task 2: Resolve STATE.md and create the merge commit</name>
  <files>.planning/STATE.md</files>
  <action>
Resolve the two conflict blocks in `.planning/STATE.md` per `<resolution_reference>`.

Block A, the `Last activity:` line: keep review's 2026-08-05 / 260805-ncv line, drop main's
2026-08-03 line, delete the marker lines. Exactly one `Last activity:` line must remain.

Block B, the "Quick Tasks Completed" table: keep every row from both sides. main supplies
the `260803-gxo` row, review supplies `260805-l5b`, `260805-mmh`, `260805-n82` and
`260805-ncv`. Place the `260803-gxo` row after the existing `260729-k8y` row and before the
four `260805-*` rows so the table stays chronological. Copy each row verbatim from its side,
do not reword or reflow.

Stage the file, then create the merge commit with `git commit -F <message-file>` using a
message file written to the scratchpad directory. Draft message in `<resolution_reference>`.
Conventional subject, no em-dash anywhere in it.

Exception to the usual rule, stated deliberately: this merge commit DOES include
`.planning/STATE.md`. STATE.md is one of the three conflicted files, so its resolution is
part of the merge and cannot be split out. The normal instruction to keep planning docs out
of code commits does not apply to this commit. It applies to every other commit on this
branch, so commit this quick task's own PLAN and SUMMARY separately under a `docs(...)`
subject if you commit them at all.

Do not `git add -A`. Stage only `.planning/STATE.md`, so the untracked 260805-nsn planning
directory stays out of the merge commit.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp && \
S=".planning/STATE.md" && \
T="$(mktemp -d)" && \
test "$(grep -cP '^(\x3c{7}|={7}|\x3e{7})' $S)" = "0" && \
for t in 260803-gxo 260805-l5b 260805-mmh 260805-n82 260805-ncv; do grep -q "^| $t |" $S || { echo "MISSING-ROW $t"; exit 1; }; done && \
test "$(grep -n '^| 260803-gxo |' $S | cut -d: -f1)" -lt "$(grep -n '^| 260805-l5b |' $S | cut -d: -f1)" && \
test "$(grep -n '^| 260729-k8y |' $S | cut -d: -f1)" -lt "$(grep -n '^| 260803-gxo |' $S | cut -d: -f1)" && \
test "$(grep -c '^Last activity:' $S)" = "1" && \
grep -q '^Last activity: 2026-08-05 .*260805-ncv' $S && \
test -z "$(git diff --name-only --diff-filter=U)" && \
test -z "$(git rev-parse -q --verify MERGE_HEAD 2>/dev/null)" && \
test "$(git cat-file -p HEAD | grep -c '^parent ')" = "2" && \
test "$(git log -1 --pretty=%s | grep -c '^chore')" = "1" && \
test "$(git log -1 --pretty=%B | LC_ALL=C grep -cP '\xe2\x80\x94')" = "0" && \
git diff --name-only origin/review HEAD | grep -v '^\.planning/quick/260805-nsn' | sort > "$T/nsn-actual-vs-review.txt" && \
printf '%s\n' '.github/workflows/deploy-cloudrun.yaml' '.github/workflows/deploy.yaml' '.planning/STATE.md' '.planning/quick/260803-gxo-move-ci-off-offline-gcp-temporary-self-h/260803-gxo-PLAN.md' '.planning/quick/260803-gxo-move-ci-off-offline-gcp-temporary-self-h/260803-gxo-SUMMARY.md' | sort > "$T/nsn-expected-vs-review.txt" && \
diff "$T/nsn-actual-vs-review.txt" "$T/nsn-expected-vs-review.txt" && \
git diff --name-only origin/main HEAD | grep -v '^\.planning/quick/260805-nsn' | sort > "$T/nsn-actual-vs-main.txt" && \
git diff --name-only origin/main...origin/review | sort > "$T/nsn-expected-vs-main.txt" && \
diff "$T/nsn-actual-vs-main.txt" "$T/nsn-expected-vs-main.txt" && \
echo VERIFY-T2-OK
    </automated>
  </verify>
  <done>
STATE.md has no conflict markers, carries all five quick-task rows in chronological order
(260729-k8y before 260803-gxo before 260805-l5b), and has exactly one `Last activity:` line,
review's. The merge is committed: no unmerged paths, no MERGE_HEAD, HEAD has two parents, a
conventional `chore` subject and no em-dash in the message. Relative to `origin/review` the
branch changes exactly the 5 expected files and nothing else. Relative to `origin/main` the
branch's changed-file set is identical to review's own changed-file set, which proves the
merge neither reverted any of main's work nor dropped any of review's.
  </done>
</task>

<task type="auto">
  <name>Task 3: Push the branch and open the PR into review</name>
  <files>(no repository files, remote state only)</files>
  <precondition>`gh auth status` reports an authenticated account with repo scope on `un-fao/exact-django-webapp`, and `git push` over SSH works from this sandbox. If `gh` is unauthenticated, halt and report rather than falling back to a browser flow.</precondition>
  <action>
Push with `git push -u origin chore/sync-review-with-main`.

Open the PR with `gh pr create --base review --head chore/sync-review-with-main`, a
conventional title such as `chore: sync review with main and resolve the deploy workflow
conflicts`, and `--body-file` pointing at a body file written to the scratchpad. Draft body
in `<resolution_reference>`: it must state both resolution decisions (main's comment text
plus review's SHA-pinned ref; keep-both on the STATE.md table) and that this unblocks #265.
No em-dash anywhere in the title or body.

Do NOT merge this PR and do NOT touch PR #265. Leave both for the user. Report the new PR
number and URL.

If GitHub reports `mergeable` as UNKNOWN immediately after creation, that is just the
background mergeability computation. Wait a few seconds and re-query before concluding
anything.
  </action>
  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp && \
P="$(mktemp)" && \
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/chore/sync-review-with-main)" && \
gh pr view chore/sync-review-with-main --json number,state,baseRefName,headRefName,mergeable,url > "$P" && \
PRJSON="$P" python3 -c "
import json,os
d=json.load(open(os.environ['PRJSON']))
assert d['state']=='OPEN', d
assert d['baseRefName']=='review', d
assert d['headRefName']=='chore/sync-review-with-main', d
assert d['mergeable']!='CONFLICTING', d
print('PR', d['number'], d['url'], d['mergeable'])
" && \
gh pr view 265 --json state,mergeable --jq '.state' | grep -q OPEN && \
echo VERIFY-T3-OK
    </automated>
  </verify>
  <done>
`origin/chore/sync-review-with-main` points at the local merge commit. An OPEN PR exists
with base `review`, head `chore/sync-review-with-main`, and a mergeable state that is not
CONFLICTING. Its body names both resolution decisions and references #265. PR #265 is still
OPEN and untouched. The new PR is not merged.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GitHub Actions runner -> third-party action | The workflow resolves and executes `docker/setup-buildx-action` at job start, with the job's WIF credential in scope |
| Local branch -> protected `review` ref | Changes reach `review` only through a pull request, enforced by ruleset id 15404692 |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-nsn-01 | Tampering | `docker/setup-buildx-action` reference in both deploy workflows | high | mitigate | Conflict resolution keeps the immutable commit SHA from review, not main's floating major-version tag. Task 1's verify asserts the SHA appears twice and that no floating major-version ref of that action survives in either file. This is a Dependabot finding already fixed by quick task 260805-l5b; resolving the conflict the other way would silently reintroduce it |
| T-nsn-02 | Tampering | Merge resolution scope | medium | mitigate | A whole-file or careless resolution could revert main's runner fix or drop review's work without any test noticing, since neither workflow file is covered by the test suite. Task 1 asserts the content diff against `origin/main` for the two workflows is exactly 4 lines; Task 2 asserts the branch's changed-file set against `origin/main` equals review's own changed-file set |
| T-nsn-03 | Elevation of Privilege | Protected `review` branch | low | accept | Resolution deliberately routes through a side branch and a PR rather than a direct push, which is the control working as designed. No bypass is attempted |
| T-nsn-04 | Tampering | npm/pip/cargo installs | n/a | accept | No package-manager install tasks in this plan. No dependency is added, removed or version-changed. The `requirements.txt` and `package-lock.json` bumps from 260805-l5b ride along inside review's existing commits and are not re-resolved here |
</threat_model>

<verification>
Run from the repository root after all three tasks:

1. No conflict markers survive in any of the three files.
2. `git diff origin/main -- .github/workflows/deploy.yaml .github/workflows/deploy-cloudrun.yaml`
   shows exactly 2 removed and 2 added content lines, and those 4 lines are only the
   `uses: docker/setup-buildx-action` line in each file.
3. `grep -rnE '^\s*runs-on:.*gcp-temporary' .github/workflows/` returns nothing. Bare
   `gcp-temporary` matches remain in main's comment prose and are expected.
4. `grep -rn 'runs-on' .github/workflows/deploy.yaml .github/workflows/deploy-cloudrun.yaml`
   returns 3 lines, all `ubuntu-22.04`.
5. STATE.md lists all five quick-task rows, chronologically ordered, and one `Last activity:`
   line.
6. `git diff --name-only origin/review HEAD` returns only the 5 expected paths, ignoring any
   `.planning/quick/260805-nsn*` artifact.
7. `git diff --name-only origin/main HEAD` equals `git diff --name-only origin/main...origin/review`,
   ignoring any `.planning/quick/260805-nsn*` artifact.
8. `gh pr view chore/sync-review-with-main` shows an OPEN PR into `review` that is not
   CONFLICTING, and `gh pr view 265` still shows OPEN.
</verification>

<success_criteria>
- A merge commit with two parents sits on `chore/sync-review-with-main`, conventional
  subject, no em-dash.
- All three conflicted files are resolved per the locked decisions: main's comment text plus
  review's SHA-pinned ref in both workflows, keep-newer plus keep-both in STATE.md.
- main's `ubuntu-22.04` runner fix and review's Buildx SHA pin both survive.
- No file changed beyond the merge itself.
- The branch is pushed and an open PR into `review` explains both decisions and references
  #265.
- Neither this PR nor #265 is merged.
</success_criteria>

<output>
Create `.planning/quick/260805-nsn-merge-main-into-review-on-a-sync-branch-/260805-nsn-SUMMARY.md`
when done. Record the new PR number and URL, and note explicitly that merging is left to the
user.
</output>
