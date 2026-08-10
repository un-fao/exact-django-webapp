# Backlog

Migrated out of the beads issue tracker on 2026-07-23, when beads was removed from this repository. Everything below was live at that point: 8 in-progress and 22 open items, plus 4 stored engineering notes.

The original beads ids are kept per item so older commit messages, code comments and planning docs that reference them stay traceable. The full historical store, including closed issues, remains recoverable from git history at `.beads/issues.jsonl`.

---

## In progress (8)

### Add status filter to activity list endpoint

**P2** · `feature` · was `exact-django-webapp-1hp` · owner: claudio.lavacca@fao.org · created 2026-07-15

> ActivityViewSet.list currently filters only by project_id and is_b_intact. Add an optional ?status= query param that filters activities by their computed status (READY / IN PROGRESS / EMPTY). Activity.status is a Python @property derived from module statuses (api/models.py:1186 __get_status), not a DB column, so it cannot be filtered in SQL. Option A: reuse the existing property as the single source of truth and filter in Python before pagination, so the filter can never diverge from the status the endpoint already serializes. No schema change.

### Async report generation and project copy (Cloud Run Jobs)

**P2** · `feature` · was `exact-django-webapp-7xn` · owner: claudio.lavacca@fao.org · created 2026-07-17

> Move PDF/Excel report generation and large-project copy off the request thread onto the existing exact-computation-job Cloud Run Job, tracked by a new generic AsyncJob model, exposed via additive 202+poll endpoints. Reuses the admin_scripts dispatch pattern (no new GCP job resource). Plan: .planning/quick/20260717-async-report-project-copy/IMPLEMENTATION-PLAN.md (12 tasks, 4 phases). Executed on branch feat/async-report-project-copy via subagent-driven development.

**Notes:**

> Implemented on feat/async-report-project-copy (16 commits), subagent-driven with per-task + final whole-branch review. PR #215 -> develop: https://github.com/un-fao/exact-django-webapp/pull/215. Tests authored but not run (no local DB; CI test step disabled). Follow-ups: frontend adoption, Cloud Scheduler for reconciler, GCS lifecycle rule.

### Provision Cloud Run Job + wire review env for scenario compute dispatch

**P2** · `feature` · was `exact-django-webapp-89e` · owner: claudio.lavacca@fao.org · created 2026-05-11

> Finish end-to-end Cloud Run Jobs setup for admin-scripts scenario builder in the GitHub review environment. Application code already exists (cloud_run.py, dispatch_cloud_run_job, app.yaml plumbing, settings.py reads). Missing: google-cloud-run dep, self-contained Dockerfile, CI step to build image, CI step to create/update the Cloud Run Job resource, IAM grants, and the two review env vars. Spec at docs/superpowers/specs/2026-05-11-cloud-run-job-review-env-design.md. Critical gotchas surfaced in spec: Firebase env vars required at Django import time; DB_USERNAME->DB_USER key rename.

**Notes:**

> 2026-05-11T12:05Z — Cloud Run Job provisioned and IAM-bound in fao-exact-review.
>
> Deploy chain:
> - PR #156 merged into review at b92c2cb8. App Engine deploy succeeded; first Build computation-job image step failed (deploy SA blocked by org policy on serviceusage.services.use). Image was built+pushed manually via gcloud builds submit under claudio.lavacca@fao.org creds.
> - Workflow fix PR #157 (merge 4b9bfed1) switched the build step to direct docker build + docker push against gcr.io — bypasses Cloud Build API entirely.
> - Deploy run 25668619593 succeeded end-to-end on commit 4b9bfed1.
>
> Cloud Run Job exact-computation-job (europe-west1):
> - image: gcr.io/fao-exact-review/exact-computation-job:4b9bfed1
> - SA: fao-exact-review@appspot.gserviceaccount.com
> - Cloud SQL: fao-exact-review:europe-west1:fao-exact-review-postgres
> - 25 env vars (DB_USER, all 8 FIREBASE_*, JOB_NOTIFICATIONS_ENABLED, ...)
> - 4Gi/2vCPU/3600s/max-retries=0
> - command/args=<none> so CMD from Dockerfile is used; dispatcher's ContainerOverride.args cleanly replaces it.
>
> IAM:
> - Step 6.2 applied: fao-exact-review@appspot.gserviceaccount.com has roles/run.developer on the Job.
> - Step 6.3 (App Engine SA actAs on itself) NOT applied; claudio.lavacca lacks iam.serviceAccounts.setIamPolicy. Cloud Run docs say actAs is not required at execution time when the runtime SA is bound at deploy time — expected to be a no-op. Confirm via Task 8 dispatch.
>
> Remaining for the user (Task 8): trigger a real scenario gap dispatch from the Compile Scenarios UI on the deployed review site and confirm the ComputationJob row reaches status=completed. If it fails with PERMISSION_DENIED on iam.serviceAccounts.actAs, escalate Step 6.3 to a project IAM admin.

### LUC role swap leaves stale _start/_w/_wo fields populated

**P2** · `bug` · was `exact-django-webapp-bor` · owner: claudio.lavacca@fao.org · created 2026-07-14

> When editing an activity with a Land Use Change via ActivityBuilderSerializer and swapping module roles (e.g. AnnualCropland start/wo + FloodedRice w -> FloodedRice start/wo + AnnualCropland w), the previously populated _start/_w/_wo scenario fields are not reset to None. Root cause: sanitize_input_entries() (api/serializers.py:1171) runs after module_types.clear() (1090) but before module_types.add() (1173); Activity.modules derives from module_types.all(), so sanitize iterates an empty module set. Fix: move sanitize_input_entries() to after module_types are re-added.

**Notes:**

> PR #199 opened against develop: https://github.com/un-fao/exact-django-webapp/pull/199 (branch fix/luc-swap-stale-scenario-fields, commit 18e34608). Awaiting CI + review/merge.

### [bug] scenario-builder: + Add Scenario does not auto-switch to new tab

**P2** · `bug` · was `exact-django-webapp-cnr` · owner: claudio.lavacca@fao.org · created 2026-05-27

> When the + Add Scenario button is clicked, both the previously active tab/panel and the newly added one remain active simultaneously. The view should switch to the new tab.
>
> Root cause: compile_scenarios.html:31 uses hx-on::after-settle on the + Add Scenario button, but htmx:afterSettle is dispatched on the swap target (#scenario-panels) and bubbles up through its ancestors only. The button is a sibling-branch element (inside the tab bar div, not on the ancestor chain of #scenario-panels), so the event never reaches the button's listener. Meanwhile the new OOB scenario_tab.html hard-codes active styling (border-blue-500 text-blue-600) and scenario_panel.html renders without the hidden class when active=True, so both old and new tabs/panels appear simultaneously.

### Scenario builder per-change climate/soil overrides show only ChangeRecord-derived subset

**P2** · `bug` · was `exact-django-webapp-cpd` · owner: claudio.lavacca@fao.org · created 2026-07-13

> Diagnosed in .planning/debug/scenario-builder-overrides.md. The per-change climate and soil-type override dropdowns in the admin_scripts scenario builder are populated from distinct values already stored in minitool.ChangeRecord (admin_scripts.views._change_record_filter_choices), never from the canonical reference tables api.Climate / api.Moisture / api.SoilType. htmx_filters further narrows options to the selected module_type. Fix direction: source options from the active-filtered reference models and decide whether per-module_type scoping is intended. Diagnosis only; no fix applied yet.

**Notes:**

> Fix applied: commit c33c8036 on fix/scenario-builder-override-options, pushed, PR #198 open into develop (https://github.com/un-fao/exact-django-webapp/pull/198). Product-owner decision 2026-07-13: ChangeRecord rows are computed on demand, so overrides come from api.Climate/Moisture/SoilType (active-filtered); htmx_filters no longer narrows the three overrides by module_type. py_compile clean. DB-backed admin_scripts tests updated but CI suite step is skipped (exact-django-webapp-1b8): run pytest djangoexact/admin_scripts/tests/test_views.py on a DB-equipped machine before merge. Close this issue when PR #198 merges.

### [bug] scenario-builder: mixed valid+gap changes hide the compute prompt

**P2** · `bug` · was `exact-django-webapp-o3j` · owner: claudio.lavacca@fao.org · created 2026-05-27

> When a scenario contains one change with data and one change whose combination is not pre-computed (a gap), the gap-bearing change is silently dropped. The user sees aggregate statistics but no Compute prompt for the missing combination.
>
> Root cause: views.py htmx_run_scenario runs detect_gap() only inside the if stats['count'] == 0 branch. When one change contributes records, stats['count'] > 0 and the gap loop is skipped entirely, so the missing combination never appears in context['gaps']. Fix: lift gap detection out of the count==0 branch and run it per-change unconditionally. Show both statistics and gaps when both are relevant; suppress the No matching records fallback only when every change is a gap (preserve prior all-gaps UX).

### Expand setup-guide.md to be dumb-proof for new hires

**P2** · `task` · was `exact-django-webapp-opv` · owner: claudio.lavacca@fao.org · created 2026-05-11

> Add missing Windows steps, frontend build, migrate/createsuperuser/load_reference_data, .env.example reference, cross-shell APP_MODE matrix, smoke tests, troubleshooting entries, beads/pytest/branching day-2 ops, and MathResult shape diagram. Source for EXACT_guide.pdf.

---

## Open (23)

### CI test gate: full suite ~394/545 red; group permissions not seeded (327x 403) + pre-existing failures

**P1** · `bug` · was `exact-django-webapp-1b8` · owner: claudio.lavacca@fao.org · created 2026-07-10

> The Phase 1 CI test gate (deploy.yaml 'test' job) now loads reference data and runs the full Django suite for the first time. Result: 545 tests, 349 failures + 45 errors.
>
> ROOT CAUSE (dominant, 327 of the failures): group->permission assignments are NOT in the loadable fixtures/seed. api/fixtures/group.json seeds zero auth.group rows; api/fixtures/test_seed_data.json creates 2 bare groups + 2 users but no auth_group_permissions. Project creation grants the creator an 'Admin' group membership (api/views.py:438), but that group has no permissions in the fixture-built test DB, so every project-scoped action is forbidden. BaseModuleTestCase.setUp (api/tests/unit/base_module.py:36) creates a project (201) then an activity and gets 403; every APITestCase inheriting it fails identically -> 327x 'AssertionError: 403 != 200'. In production the group permissions exist (configured outside loadable fixtures); the dump/load pipeline never captured them.
>
> REMAINING ~67 failures/errors (separate, pre-existing): api.tests.test_reference_bootstrap round-trip dump mismatch; api.tests.reports.test_html_context mock-expectation failures (logger.exception, file handle close, FileNotFoundError, generic-error redaction); api.tests.test_project_export errors; admin_scripts.tests.test_views export multi-scenario.
>
> IMPACT: the CI 'test' job can never pass, so it blocks (or would block, if made required) every PR through the gate. First surfaced on PR #196 once the reference-data load was fixed (the load previously aborted before the suite ran).
>
> SCOPE: Phase 1 CI-gate remediation. Not caused by any single feature PR. Likely fix for the 327: seed auth_group_permissions for the standard project groups (Admin, Second Reviewer, etc.) into the reference data or a test-setup step, so fixture-built DBs mirror production group permissions. Then triage the ~67 stragglers.
>
> Ref: PR #196 CI run 29018679553 (attempt 2).

**Design:**

> Options for the 327: (a) add group->permission M2M to reference-data fixtures via dump_reference_data on a permission-configured DB (respects the no-hand-edit rule); (b) a data migration that assigns permissions to groups by codename; (c) a test-only setup step that grants perms. (a) is most consistent with the fixtures-as-truth pipeline but needs a correctly-configured source DB.

### Run unit suite in CI for status-validation refactor (er8) + verify behavioral nuances

**P1** · `task` · was `exact-django-webapp-cgj` · owner: claudio.lavacca@fao.org · created 2026-05-19

> exact-django-webapp-er8 was implemented but the dev sandbox has no Postgres/Docker, so the Django unit suite was not run locally. CI (or a DB-equipped machine) must run: python djangoexact/manage.py test api.tests.unit (focus: energy, settlement, irrigation, land_use_change, base_module, annual_cropland, forest_management, input, perennial_cropland, flooded_rice, grassland, coastal_wetland, storage, processing, packaging, transport). Verify the 3 documented intentional nuances do not break assertions: (1) cascade status persisted via QuerySet.update() -> no history/last_modified/lock-timestamp on cascade-target parents/LUC; (2) land-module create now recomputes status after save (previously always EMPTY) - check base_module create tests; (3) LandUseChange.get_modules() exception now caught -> EMPTY instead of 400. If any fail, the conditional-operator canonicalization (NoScenario used 'not get()' vs Scenario 'is None') and SUBMODULES_EMPTY precedence are the first suspects.

**Notes:**

> SCOPED er8 validation done (local SQLite, branch vs pre-er8 develop baseline via worktree). 39/39 common status/cascade tests (test_modify=READY, test_patch_to_not_ready=EMPTY, test_parent_not_ready_if_submodule_not_ready=SUBMODULES_EMPTY cascade) pass IDENTICALLY on pre-er8 baseline (Ran 39 OK) and er8 branch -> status contract preserved across all module types. Step-4 er8-specific tests added & green: SUBMODULES_EMPTY-over-EMPTY precedence (settlement), conditional-field readiness (grassland), create-path READY (energy). REMAINING UNVALIDATED: LandUseChange calc/scenario tests, blocked by pre-existing non-er8 defects 4ng (auditlog x cached_results deepcopy) and 5gq (results-view get_object_or_404 query explosion). Recommend fixing 4ng/5gq then running api.tests.unit.land_use_change for full LUC coverage.

**Depends on:** {'issue_id': 'exact-django-webapp-cgj', 'depends_on_id': 'exact-django-webapp-er8', 'type': 'blocks', 'created_at': '2026-05-19T09:58:28Z', 'created_by': 'Claudio Lavacca', 'metadata': '{}'}

### Expose granular readiness payload on module detail endpoints

**P2** · `feature` · was `exact-django-webapp-43l` · owner: claudio.lavacca@fao.org · created 2026-05-20

> Surface the per-scenario missing-field codes and blocking-children references that compute_readiness already produces, as an additive readiness object on every module detail GET/PATCH/POST response. Status FK shape unchanged; list endpoints unchanged (thin-list contract preserved). Builds on the er8 refactor (ReadinessMixin.compute_readiness). Frontend will use the structured codes to render per-field 'required' highlights on the module edit form and a banner-level summary composed from its own i18n catalog (backend stays language-neutral).

**Design:**

> Hybrid approach: api/models.py.ReadinessMixin.compute_readiness returns structured code dicts instead of strings; new ReadinessMixin.get_blocking_children method; new api/readiness.py builds the response dict via build_readiness_payload(); BaseGenericModuleSerializer gets a ReadinessSerializerMixin adding readiness = SerializerMethodField. Backend fully language-neutral. Spec at docs/superpowers/specs/2026-05-20-granular-readiness-payload-design.md.

**Acceptance criteria:**

> GET /api/<module>/<id>/ returns readiness object with shape {missing: {start: [{field, reason, trigger?}], with: [], without: []}, blocking_children: [{id, type, status}]}; list endpoints unchanged; existing status assertions in unit tests still pass; new test_readiness.py covers all branches; FE can render per-field highlights using the codes alone.

### auditlog audits multi-MB cached_results_* JSON on every module save (AUDITLOG_INCLUDE_ALL_MODELS=True)

**P2** · `bug` · was `exact-django-webapp-4ng` · owner: claudio.lavacca@fao.org · created 2026-05-19

> Pre-existing, NOT er8-caused (er8 cascade uses .update() which bypasses post_save/auditlog; old code did MORE audited saves). AUDITLOG_INCLUDE_ALL_MODELS=True auto-registers every model incl CachedResultMixin module models. On each module.save() the post_save receiver (auditlog/receivers.py:40 log_create -> _create_log_entry) creates a LogEntry whose JSONField deepcopies all changed fields, including cached_results_total/by_activity/by_gas/by_activity_by_gas (multi-MB after a LUC calculation). copy.deepcopy of that nested blob thrashes (~0 CPU, ~hr, Windows access violation) -> effectively hangs the LUC calculation tests. Surfaced once exact-django-webapp-8ae factory fix let LUC calc tests actually run. Prod impact: every cache write audit-logs huge JSON -> auditlog_logentry table bloat + save latency. Fix options: AUDITLOG_EXCLUDE_TRACKING_FIELDS add cached_results_*/cached_units_breakdown (or exclude CachedResultMixin models from auditing), or wrap cache_results() in auditlog.context.disable_auditlog(). Tests neutralize via settings_test AUDITLOG_INCLUDE_ALL_MODELS=False.

### results view get_object_or_404 query-compilation explosion on LUC-linked modules (effective hang)

**P2** · `bug` · was `exact-django-webapp-5gq` · owner: claudio.lavacca@fao.org · created 2026-05-19

> Pre-existing, NOT er8 (pure read path, predates refactor, untouched by status changes). In api/views.py:2412 GenericModuleViewSet.results -> get_object_or_404(model, pk=pk), Django's SQL compiler is stuck in get_select/build_filter/setup_query forever (~0 useful CPU over ~1h, two faulthandler dumps both in query compilation, then Windows access violation = memory thrash) when the module participates in a LandUseChange scenario (AnnualToForestTestCase etc.). Signature = explosive/recursive query construction (likely select_related/prefetch over the LandModule<->LandUseChange OneToOne cycle, or a default-manager queryset). Only surfaced once exact-django-webapp-8ae factory fix let LUC calc tests run. Blocks all api.tests.unit.land_use_change(_examples) tests -> excluded from the scoped er8 validation. Prod impact: potential pathological latency on the module results endpoint for LUC-linked modules. Repro: python djangoexact/manage.py test api.tests.unit.land_use_change.AnnualToForestTestCase.test_annual_to_forest_calculation --settings=djangoexact.settings_test --keepdb (hangs at get_module_results).

### Reference fixture FK inconsistency: cropnitrousestimationdefaultfactor.json -> missing LandUseType pk 29

**P2** · `bug` · was `exact-django-webapp-5l7` · owner: claudio.lavacca@fao.org · created 2026-05-19

> Pre-existing committed-fixture bug (NOT caused by er8/u7b). ipcc/fixtures/cropnitrousestimationdefaultfactor.json pk 179 (and others) reference api LandUseType pk 29, which api/fixtures/landusetype.json does not contain (211 rows, pk gaps incl 29). A true from-empty 'load_reference_data --app=all' aborts here (Postgres would fail too); only masked because review/dev DBs already had orphan LandUseType rows. test_reference_bootstrap.py would fail from empty. Fix: either add the missing LandUseType rows to landusetype.json or re-dump cropnitrousestimationdefaultfactor against current LandUseType set. SQLite test bootstrap (u7b) currently skips this one fixture via --continue-on-error.

### Production import of test factories — add factory-boy to prod requirements

**P2** · `bug` · was `exact-django-webapp-8zu` · owner: claudio.lavacca@fao.org · created 2026-05-11

> api/minitool.py:588 imports api.tests.factories which imports the factory-boy package as a runtime dependency. factory-boy is not in djangoexact/requirements.txt, so the Cloud Run Job container fails with ModuleNotFoundError on every permutation. App Engine has it available somehow (likely test deps installed in CI before deploy). Adding factory-boy==3.3.3 to prod requirements as the minimum fix. Long-term: api/minitool.py should not import from api.tests.* — that's a code smell that should be fixed in a follow-up.

### Temporarily skip 'Migrate and load reference data' CI step (25 min, seeds only the disabled test suite)

**P2** · `chore` · was `exact-django-webapp-bbz` · owner: claudio.lavacca@fao.org · created 2026-07-14

> The test job's 'Migrate and load reference data' step takes ~1520s (~25 min) and is the sole reason the test gate runs ~29 min, blocking deploys. Its only consumer is the 'Run test suite' step, already disabled via if:false (1b8). Nothing after it (check --deploy, bandit, pip-audit) needs a seeded DB. Add if:false to the step; re-enable together with the test suite. NOTE: load_reference_data --app=all taking ~25 min is itself abnormal and should be investigated separately.

### Compile-scenarios live results: Compare-tab visualization

**P2** · `feature` · was `exact-django-webapp-dtc` · owner: claudio.lavacca@fao.org · created 2026-05-26

> Add a Compare tab to djangoexact/admin_scripts/.../compile_scenarios.html that aggregates per-scenario runs into a side-by-side comparison view (mean+CI bar chart, distribution box plots, per-change composition stack, comparison table, sample-size warning chips). Implementation per docs/superpowers/plans/2026-05-26-scenario-builder-results-visualization.md and spec docs/superpowers/specs/2026-05-26-scenario-builder-results-visualization-design.md. Branch: feature/scenario-builder-results-viz.

### Result.__add__ appends non-overlapping entries by reference (aliasing risk, not a copy)

**P2** · `bug` · was `exact-django-webapp-e5x` · owner: claudio.lavacca@fao.org · created 2026-05-18

> math_model/no_time_dependency_final/ghg_emissions_classes.py Result.__add__ (line ~236): the no-match branch does result_obj.yearly_emissions_by_sector_by_gas.append(other_yearly_emission) — appends the OTHER Result's YearlyGasActivityEmissionSet by reference rather than a deepcopy. result_obj is a deepcopy of self, but entries unique to  are shared. If a source Result is added into multiple targets and subsequently mutated (e.g. reused accumulator, in-place emission edits), the shared reference can cross-contaminate / double-apply. Not the active cause of the report under-count or the Settlement double (those are fixed), but a latent correctness hazard. Recommend appending copy.deepcopy(other_yearly_emission) (mirror __sub__ which constructs a fresh YearlyGasActivityEmissionSet). Add a unit test that mutates a shared source after addition.

### Register ComputationJob in Django admin

**P2** · `bug` · was `exact-django-webapp-huy` · owner: claudio.lavacca@fao.org · created 2026-05-11

> /admin/admin_scripts/computationjob/ returns 404 because admin_scripts has no admin.py and ComputationJob is never registered with the Django admin. Add a minimal ModelAdmin so staff can inspect/delete rows (needed during incident response to clear stuck pending jobs that the UI can't fully delete).

### Dependency vulnerabilities: bump django 5.2.14->5.2.15, pyjwt 2.12.1->2.13.0, weasyprint 68.0 (CVE-2026-49452)

**P2** · `task` · was `exact-django-webapp-oev` · owner: claudio.lavacca@fao.org · created 2026-07-10

> pip-audit -r djangoexact/requirements.txt (CI 'test' job) reports 14 known vulnerabilities in 3 packages, all with fix versions available:
> - django 5.2.14 -> 5.2.15 or 6.0.6 (PYSEC-2026-197, -198, -199, -200, -201)
> - pyjwt 2.12.1 -> 2.13.0 (PYSEC-2026-175, -176, -177, -178, -179)
> - weasyprint 68.0 -> fix TBD (CVE-2026-49452)
>
> TEMPORARY MITIGATION IN PLACE: the pip-audit CI step is marked continue-on-error (non-blocking) so the test job is not red on these while they are remediated. Remove that once the bumps land.
>
> REMEDIATION: bump the three pins in djangoexact/requirements.txt to the fix versions. django 5.2.14->5.2.15 is a patch within the pinned 5.2.x line (low risk); pyjwt is a minor bump; weasyprint is report-critical (PDF generation) so verify report rendering after bumping. Blocked on the test suite being green (exact-django-webapp-1b8) to validate safely, or verify manually.

### scenario-builder: verify new parent+submodule processors against real DB

**P2** · `task` · was `exact-django-webapp-rp5` · owner: claudio.lavacca@fao.org · created 2026-05-26

> The new EnergyProcessor / StorageProcessor / ProcessingProcessor / PackagingProcessor / TransportProcessor (catalog key = parent name) build an unsaved parent and pass the submodule to CalculatorFactory so submodule calculators avoid the .entries.all() DB query. This needs verification against the dev DB: (1) submodule calculators don't internally call self.module.parent.<related_name>.all() expecting persistence; (2) build() pattern yields valid fuel_type/refrigerant_type FKs that the calculators can dereference; (3) ChangeRecord rows land under module_type='Energy' etc. as expected by the UI. Cannot test locally per dev-sandbox memory (no Postgres) - needs CI or a DB-equipped machine.

### Verify LandUseChange + destination land module accounting vs the online EX-ACT tool (possible methodological double-count)

**P2** · `task` · was `exact-django-webapp-v4r` · owner: claudio.lavacca@fao.org · created 2026-05-18

> Activities pairing a LandUseChange module with a destination land module (project 'test may 2026': 'new agroforestry'=PerennialCropland+Grassland+LandUseChange; 'Deforestation'=AnnualCropland+ForestManagement+LandUseChange; 'New facilities'=Settlement+SetAside+LandUseChange) have their activity total = sum of ALL module balances. Whether the one-time transition stock change (LandUseChange) and the destination land dynamics should both be summed, or netted, is an EX-ACT methodology question. The webapp sums them; if the online tool nets/handles transitions differently the totals diverge BY DESIGN (not a code x+=x bug). This is the most likely remaining source of 'general' divergence the user observed. ACTION: compare one such activity (e.g. Deforestation) module-by-module against the online tool to determine whether the webapp's per-module summation matches the reference methodology; only change logic with domain confirmation. No code change made unilaterally.

### scenario-builder: test stats_for_scenario with non-empty global_filters

**P3** · `task` · was `exact-django-webapp-doa` · owner: claudio.lavacca@fao.org · created 2026-05-12

> Final review of PR #166 (per-change units) noted no test covers stats_for_scenario(changes_with_unit, global_filters) where global_filters is non-empty (e.g. soil_type=['Sandy']). The unit/global-filters intersection lives in _build_single_change_q's shared path and is functionally covered by existing build_scenario_query tests, but no test pins the combination with per-change units. Add a test in admin_scripts/tests/test_views.py ScenarioUtilsTest.

### LUC permutations: flatten LandUseChangeCalculator result tuple for DataManager CSV

**P3** · `task` · was `exact-django-webapp-rjk` · owner: claudio.lavacca@fao.org · created 2026-05-28

> _compute_luc_slice in api/services/luc_compute.py stores LandUseChangeCalculator.calculate() return value (a (results_w, results_wo) tuple of Result dataclasses) raw under data[i]['result']. DataManager.save_data pipes this through pd.DataFrame(data).to_csv(), which writes repr(tuple) — lossy. Compare with other module slices that flatten to scalar columns. Decide on a flat schema (e.g. result_w_co2, result_wo_co2, total_co2, ...) and update _serialize_result accordingly. Saved-fixture rollback path is unaffected; only save_results=True output is lossy.

### SetAside (and others): cached inventory value diverges from cached balance (inventory 11425 vs balance 0)

**P3** · `bug` · was `exact-django-webapp-t45` · owner: claudio.lavacca@fao.org · created 2026-05-18

> In 'test may 2026' the New facilities/Set Aside module cached inventory shows Soil CO2 Change=11425.33 but the cached balance for the same module/category sums to 0. Inventory sheet and Results breakdown therefore disagree. Likely a calculator inventory-vs-balance inconsistency or stale partial cache. Investigate SetAsideCalculator inventory population and cache write consistency (save_results_to_cache serializes balance and inventory together — check they come from the same calculation).

### Settlement: roads/buildings rows recalculated (RoadCalculator) drift from cached module balance ROADS

**P3** · `bug` · was `exact-django-webapp-wus` · owner: claudio.lavacca@fao.org · created 2026-05-18

> SettlementReport._compute_submodule_emissions re-runs RoadCalculator/BuildingCalculator and extracts ROADS/CO2 for the buildings/roads/infra display rows, while total_emissions now uses the full module balance (_balance_total). For 'test may 2026', recalculated roads ~106560 vs cached module-balance ROADS ~108037 (~1.4% drift), so the Settlement breakdown rows do not perfectly reconcile to the (now correct) total. Decide: derive roads/buildings from emissions_set too (loses roads-vs-buildings split since both calculators emit ROADS/CO2) or keep recalc and accept display drift.

### Report generation perf: deferred optimizations R4-R8 from 260716-g2x research

**P3** · `task` · was `exact-django-webapp-xjt` · owner: claudio.lavacca@fao.org · created 2026-07-16

> Quick task 260716-g2x (PR #210) implemented R1+R2 (reference-lookup memoization, single Result construction). Research ranked six more optimizations, deferred as MED risk or larger scope: R3 fetch modules once per activity and reuse (Activity.modules property re-queries per access), R4 make project.is_ready pre-pass cheap or merge it, R5 lazy calculator construction on cache hits, R6 batch cache persistence via bulk_update instead of per-module save() during GET, R7 renderer: replace insert_rows loops with precomputed row positions (quadratic shifts), R8 move very large reports to the Cloud Run job path. Full evidence with file:line refs in .planning/quick/260716-g2x-the-excel-report-generation-is-painfully/260716-g2x-RESEARCH.md. Constraint: calculation results and public API contract must not change. Open question A2: profile whether ORM or math_model CPU dominates wall time before attempting R5/R6/R8.

**Notes:**

> R3 implemented on 2026-07-16 in the same PR #210 (commits 6d3b0b8d, fe5323fe, quick task 260716-gu0): opt-in Activity.cache_modules() memo + select_related(status), shared across Excel pre-pass/compute and PDF template context. Remaining: R4 cheap is_ready pre-pass, R5 lazy calculator construction, R6 bulk_update cache persistence, R7 renderer insert_rows restructuring, R8 Cloud Run offload.

### scenario-builder: regression-guard test for Units input surviving HTMX swap

**P4** · `task` · was `exact-django-webapp-4u5` · owner: claudio.lavacca@fao.org · created 2026-05-12

> The Units input in change_fieldset.html is placed outside both HTMX swap targets (-field-container, -values-container) so changing module_type or field cannot clobber a typed unit value. This is correct by construction but untested. Add a test asserting the Units input is rendered outside both swap-target divs, so a future template restructure that moves it inside one of them is caught. Suggested location: admin_scripts/tests/test_views.py CompileScenariosViewTest.

### scenario-builder: decide raw-vs-coerced units in Excel export Changes sheet

**P4** · `task` · was `exact-django-webapp-gh2` · owner: claudio.lavacca@fao.org · created 2026-05-12

> compile_scenarios_export writes change.get('unit', '') (raw POSTed string) into the Units column of the Changes sheet. A user posting garbage like 'abc' would see 'abc' in the Changes sheet while the Summary sheet silently uses 1.0 (via _coerce_unit). Decide: (a) keep raw to reflect user input verbatim, or (b) write _coerce_unit(change.get('unit')) for self-consistency between the two sheets. Document the decision; update views.py compile_scenarios_export if (b).

### LUC compute: refactor cross-layer import (api/services -> admin_scripts)

**P4** · `task` · was `exact-django-webapp-urt` · owner: claudio.lavacca@fao.org · created 2026-05-28

> api/services/luc_compute.py uses function-local imports of admin_scripts.luc_permutations (iterate_concrete_combos at line 26, _compute_luc_slice at line 145). admin_scripts is the higher layer (it consumes api/), so importing from it inverts the usual direction. Lazy imports avoid load-time circularity, but the conceptual cycle would become real if admin_scripts ever imports api/services/luc_compute at module load. Long-term fix: move the LUC preset spec and expansion helpers into api/ (or a neutral package) so api/services/luc_compute owns its dependencies. Not a blocker for the initial LUC permutations work — flagged in the final code review of feat/luc-permutations.

### copy_activity copies a valid module-level cache into the target

**P2** · `bug` · created 2026-08-10

> api/utilities.py:365-427 uses copy.deepcopy(module) then sets pk = None. The deepcopy carries last_cached_at, last_modified, and all cached_results_* blobs. CachedResultMixin.save only stamps last_modified when it is None (api/models.py:1289-1290), and on a copy it is not None, so the copy is born with a valid cache. Inside copy_project the target is a clone of the source, so the numbers happen to agree, but copy_activities_into(source_project, target_project, owner) is generic in its signature and ActivityViewSet.copy also copies. A copy into a project with a different country, climate, moisture, soil type, or GWP would serve the source project's numbers, and it copies multi-megabyte JSON per module for nothing. Note this is a genuine defect rather than an instance of the preserve-untouched-results rule (see Engineering notes): a copy is a newly created project, so it has no prior computation of its own to preserve, and it is born displaying numbers that were never computed for its own parameters. Workaround until fixed: an operator can run scripts/invalidate_results_cache.py, which clears the project-level rows and bumps every non-finalized project's results_stamp.

---

## Engineering notes (5)

Durable findings that were stored as beads memories. These are observations about this codebase and its deployment that were expensive to work out and are not obvious from the source.

### reference-data-reloads-must-not-invalidate-results

> Product rule, confirmed by the product owner on 2026-08-10. load_reference_data invalidating nothing is INTENDED behaviour, not a defect. Do not "fix" it, and do not file it as a bug again. A user's project results must never be recalculated unless the user explicitly does something to trigger it, so an old untouched project is preserved exactly as it was last computed: an EX-ACT appraisal is a record of what the numbers were when it was run, and reloading IPCC emission factors or GWP coefficients must not retroactively rewrite it. Consequences to preserve in any future cache work: (1) the ProjectResultCache key in api/results_cache.py deliberately folds in NO reference-data epoch, (2) api/reference_cache.py clear_reference_caches() is correctly left uncalled by the loader (its docstring at api/reference_cache.py:7-8 predates this rule and describes the mechanism, not a requirement to invoke it), (3) the only sanctioned ways an already-computed project moves off its cached numbers are the user's own edits, which bump Project.results_stamp, and a deliberate operator run of scripts/invalidate_results_cache.py. The single exception is RESULTS_SCHEMA_VERSION / INVENTORY_SCHEMA_VERSION, which force a global recompute without user action and are therefore reserved for fixing defects in our own computation code, never for propagating reference-data changes.

### cloud-sql-proxy-must-use-adc-not-gcloud-auth

> exact-django-webapp deploy.yaml: cloud-sql-proxy must authenticate via ADC (the WIF file google-github-actions/auth@v2 exports as GOOGLE_APPLICATION_CREDENTIALS), i.e. run './cloud-sql-proxy -p 5432 <instance>' WITHOUT -g/--gcloud-auth. The -g flag shells out to 'gcloud config config-helper', which fails 'You do not currently have an active account selected' because auth@v2 never runs gcloud auth activate-service-account. The proxy is backgrounded in the 'Setup cloud-sql-proxy' step and consumed by manage.py migrate in the later 'Deploy' step; its output is redirected to /tmp/cloud-sql-proxy.log (so a step-boundary pipe close can't SIGPIPE-kill it) and the Deploy step waits on 127.0.0.1:5432 before migrate, cat-ing that log on timeout. This same job deploys review AND production (main).

### dirtyfields-keys-by-field-name

> In exact-django-webapp, django-dirtyfields get_dirty_fields(check_relationship=True) keys its dict by field.name for ALL concrete fields, including ForeignKeys (dirtyfields.py:105 does all_field[field.name]=..., NOT attname). So a dirty FK like Project.locked_by / Activity.owner appears under key 'locked_by'/'owner', never 'owner_id'. Consequence for Project.save()/Activity.save() cache-invalidation: exclude_fields must list the FK's field.name ('owner', 'locked_by'), not the '_id' attname. Also why 'any(field not in exclude_fields for field in dirty_fields)' is equivalent to the older 'any(field.name in dirty_fields for field in self._meta.get_fields() if field.name not in exclude_fields)' - dirty_fields keys are a subset of get_fields() names.

### exact-app-engine-to-cloud-run-feasibility

> EX-ACT (exact-django-webapp) 2026-07-23 feasibility review of moving the web API from App Engine Standard to Cloud Run (doc: .planning/quick/260723-jas-cloud-run-migration-feasibility/EVALUATION.md). Verdict: technically feasible and largely de-risked, because deploy/Dockerfile.computation_job already containerizes this exact codebase with psycopg2 + the full WeasyPrint native stack and runs in production as the exact-computation-job Cloud Run Job; zero google.appengine imports exist, the only App Engine coupling is the GAE_APPLICATION branch in settings.py:146, the _ah/warmup route, and app.yaml. Real work items: (1) ingress/custom domain/TLS is the only high-risk item and is FAO IT owned (get a written answer before committing to a date); (2) the move HARD-REQUIRES migrating secrets to Secret Manager first, because the Cloud Run Job currently sources DB_PASSWORD and SECRET_KEY out of the deployed App Engine version via 'gcloud app versions describe' (a workaround for GitHub Actions env interpolation adding 2 chars to secrets containing $ or \\); (3) static files need WhiteNoise since the app.yaml /static handler disappears; (4) set --concurrency explicitly (8-16, not the Cloud Run default of 80) because CONN_MAX_AGE=0 makes every request open a new Postgres connection. Recommended sequence: finish async-jobs work, then Secret Manager while still on App Engine, then the service move (~3-4 days of code). No data migration is needed; both platforms can run side by side against the same Cloud SQL instance and bucket.

### exact-dev-sandbox-has-no-local-postgres-docker

> EXACT dev sandbox has NO local Postgres/Docker; every Django bootstrap (even manage.py shell) fails on DB connect. Cannot run the unit suite locally — rely on CI/DB-equipped machine. py_compile is the only local gate.
