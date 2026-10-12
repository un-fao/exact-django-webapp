---
phase: quick-260803-gxo
plan: 01
status: complete
date: 2026-08-03
branch: fix/ci-github-hosted-runners
commit: 0d58b04e
files_modified:
  - .github/workflows/deploy.yaml
  - .github/workflows/deploy-cloudrun.yaml
---

# Quick Task 260803-gxo: Move CI off the offline gcp-temporary self-hosted runner

## What was wrong

Run 30800792218 ("Deploy" on `main`, head_sha 06656789) was reported as not running.
It was not stalled on GitHub's side. Its `test` job carried
`labels: ["gcp-temporary"]` and `runner_name: ""`: a self-hosted label with no
registered runner. GitHub never dispatches such a job to the hosted pool, so it waits
in the queue until a matching runner appears.

The last jobs that actually landed on that label ran on 2026-07-30, on ephemeral GCE
VMs named `gcp-ghrunner-vm-1785405034` and `gcp-ghrunner-vm-1785406451`. Nothing since.
At 2026-08-03T09:40Z, 22 runs were queued behind the label: the `main` push, the
`develop` version bump 1.19.2a5 to 1.20, and 20 Dependabot pull requests opened at
09:19.

The runner infrastructure is not defined in this repository, and the repo and org
runner APIs return 404 and 403 for the available token, so it could not be inspected
or restarted from here.

## What confirmed the diagnosis

Run 30800257762 on branch `feature/id-responses` ran normally the same morning at
09:10. That branch's `deploy.yaml` declares `runs-on: ubuntu-22.04`, and its `test` job
passed on a GitHub-hosted runner in 2.5 minutes. Its `deploy` job then failed on
`SERVICE_DISABLED` for the App Engine Admin API on `fao-exact-review`, which is a
separate, pre-existing condition of the review project and not a runner problem.

## What changed

Three `runs-on` declarations moved from `gcp-temporary` to `ubuntu-22.04`:

- `.github/workflows/deploy.yaml` test job
- `.github/workflows/deploy.yaml` deploy job
- `.github/workflows/deploy-cloudrun.yaml` deploy job

`ubuntu-22.04` rather than `ubuntu-latest`, to match the one configuration this
workflow is empirically known to pass on.

Four comments that asserted properties of the self-hosted runner were corrected. The
most consequential is in the "Verify report download base URL" step of
deploy-cloudrun.yaml, which justified treating an unreachable HTTP probe as
inconclusive because "the self-hosted runner has no public egress to *.run.app". On a
GitHub-hosted runner that premise is false, so a `000` result now means the host really
is unreachable rather than being the expected outcome. The step's logic is unchanged:
`000` stays non-fatal so a transient network failure cannot fail an otherwise correct
deploy, and the `404` branch remains what catches the stale-hostname bug. The gate gets
stronger, not weaker.

## Why leaving GCP is safe for the deploy jobs

The two deploy jobs talk to Google Cloud, but neither depends on running inside it:

- Authentication is Workload Identity Federation via
  `google-github-actions/auth`, driven by the GitHub OIDC token. It never used the GCE
  metadata server.
- `cloud-sql-proxy` is invoked at deploy.yaml:248 and deploy-cloudrun.yaml:135 with
  `-p` and the instance connection name only, with no `--private-ip`. The proxy
  therefore already resolved the instance's public IP and authenticated with an
  ephemeral client certificate minted through the Cloud SQL Admin API. That path works
  from any host with egress and needs no authorized-network entry.
- `gcloud app deploy`, `gcloud run` and `docker push` to gcr.io and Artifact Registry
  are all plain API calls.

If the Cloud SQL instance had no public IP, the previous pipeline could not have worked
either, since it never passed `--private-ip`. The failure mode is loud and early
regardless: the deploy job's readiness loop cats `/tmp/cloud-sql-proxy.log` and exits 1
if the proxy never listens.

## What this does not do

It does not rescue run 30800792218. A workflow run is pinned to the workflow file at
its own head_sha, so that run keeps `runs-on: gcp-temporary` forever and stays queued
no matter what lands on `main` afterwards. The same is true of the other 21 queued
runs. Merging this produces a new run that executes; the stuck ones should be
cancelled.

It also does not decide whether the self-hosted runner should come back. If FAO restores
it, this change is a one-line revert per job, and the comments explain why it was made
so nobody reverts it by accident.

## Verification

- `grep -rn "gcp-temporary" .github/` matches only the two explanatory comments, no
  `runs-on` value.
- Both workflow files parse under `yaml.safe_load`, and all three jobs report
  `runs-on: ubuntu-22.04`.
- No em-dashes introduced.
