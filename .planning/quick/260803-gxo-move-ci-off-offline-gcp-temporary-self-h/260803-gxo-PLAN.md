---
phase: quick-260803-gxo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/deploy.yaml
  - .github/workflows/deploy-cloudrun.yaml
autonomous: true
requirements:
  - CI-01
  - CI-02
branch: fix/ci-github-hosted-runners

must_haves:
  truths:
    - "No job in .github/workflows/ targets the gcp-temporary label any more; every runs-on is ubuntu-22.04."
    - "The Deploy workflow's test job runs on a GitHub-hosted runner, which is already proven: run 30800257762 on branch feature/id-responses executed the identical job on ubuntu-22.04 in 2.5 minutes."
    - "The deploy jobs keep working without network topology changes, because cloud-sql-proxy is invoked WITHOUT --private-ip and therefore already connected to the Cloud SQL instance over its public IP using the WIF credential, not over a VPC private path."
    - "Comments that assert self-hosted runner properties no longer describe the runner the job actually gets."
  artifacts:
    - .github/workflows/deploy.yaml
    - .github/workflows/deploy-cloudrun.yaml
  key_links:
    - "deploy.yaml:18 (test job) and deploy.yaml:209 (deploy job) plus deploy-cloudrun.yaml:19 are the only three runs-on declarations in the repo."
    - "deploy.yaml:248 and deploy-cloudrun.yaml:135 invoke ./cloud-sql-proxy with -p and the instance connection name only. No --private-ip flag means the proxy resolves the instance's public IP and authenticates with an ephemeral client cert minted through the Cloud SQL Admin API, which works from any egress-capable host. This is why moving off a GCP-resident runner does not need authorized-network or VPC changes."
    - "deploy-cloudrun.yaml:336-338 and :363-365 justify treating an unreachable HTTP probe as inconclusive on the grounds that 'the self-hosted runner has no public egress to *.run.app'. On a GitHub-hosted runner that premise is false: the probe now returns a real status code, so the gate becomes stronger rather than weaker. The comments must be corrected or they will mislead the next reader into thinking a 000 result is expected."
    - "deploy.yaml:348 and deploy-cloudrun.yaml:186 explain docker/setup-buildx-action as compensating for a 'temporary runner' that may lack the Docker CLI plugin. GitHub-hosted ubuntu-22.04 ships Docker with Buildx, so the step is now belt-and-braces rather than a fix for a specific gap. Keep the step (it pins BuildKit behaviour) but correct the stated reason."
    - "ubuntu-22.04 is chosen over ubuntu-latest to match branch feature/id-responses, which is the only configuration empirically proven against this workflow."
---

<objective>
Move every GitHub Actions job in this repository off the self-hosted `gcp-temporary`
runner label and onto the GitHub-hosted `ubuntu-22.04` image.

Purpose: the `gcp-temporary` runner (ephemeral GCE VMs named `gcp-ghrunner-vm-*`) has
been offline since 2026-07-30. Because a queued job only starts when a runner matching
its label registers, all Deploy runs since then sit in the queue indefinitely. As of
2026-08-03T09:40Z that is 22 runs, including the production push to `main`
(run 30800792218, head_sha 06656789) and 20 Dependabot pull requests. Nothing on the
GitHub side can dispatch those jobs; only a matching runner can.

Output: three `runs-on` values changed, and the four comments that assert properties of
the self-hosted runner corrected so they describe the runner the jobs now get.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

## Task 1: Point all three jobs at ubuntu-22.04

**Files:** `.github/workflows/deploy.yaml`, `.github/workflows/deploy-cloudrun.yaml`

**Action:** Replace the `gcp-temporary` runner label with `ubuntu-22.04` at
deploy.yaml:18 (test job), deploy.yaml:209 (deploy job) and deploy-cloudrun.yaml:19
(Cloud Run deploy job). Add a short comment at each site recording why the label
changed, so the next reader does not silently revert it when the self-hosted runner
comes back.

**Verify:** `grep -rn "gcp-temporary" .github/` returns nothing, and
`python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]"` parses
both files.

**Done:** No workflow in the repository targets a self-hosted label.

## Task 2: Correct the comments that assert self-hosted runner properties

**Files:** `.github/workflows/deploy.yaml`, `.github/workflows/deploy-cloudrun.yaml`

**Action:** Update the two "no public egress to *.run.app" justifications in the
"Verify report download base URL" step of deploy-cloudrun.yaml, which are now false and
would misread a `000` probe result as normal. Update the two "The temporary runner may
not have the Docker CLI plugin installed" comments above `docker/setup-buildx-action`
in both files. Do not change any step logic: the `000` branch stays as a safety net for
transient network failure, it simply stops being the expected outcome.

**Verify:** `grep -rn "self-hosted\|temporary runner" .github/workflows/` returns no
claim that contradicts a GitHub-hosted runner.

**Done:** Every comment describing the execution environment matches ubuntu-22.04.

</tasks>

<risks>
- The Cloud SQL instance must have a public IP for cloud-sql-proxy to reach it. The
  existing invocation omits `--private-ip`, so the proxy was already using the public
  path from inside GCP; if the instance had no public IP the current pipeline could not
  have worked either. Low risk, but it is the one thing that fails loudly and early
  (the deploy job's readiness loop cats /tmp/cloud-sql-proxy.log and exits 1).
- Merging this to `main` triggers a production App Engine deploy, which is the intent
  (main has been undeployable since 2026-07-30) but is not a silent change.
- This does not rescue run 30800792218 itself. A workflow run is pinned to the workflow
  file at its own head_sha, so the queued run keeps its old `runs-on` forever. Merging
  produces a NEW run that executes; the stuck ones should be cancelled.
</risks>
