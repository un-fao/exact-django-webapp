# Quick Task 260813-fvj: Reference-data ID mismatch on project export/import

**Researched:** 2026-08-13
**Domain:** Django/DRF data portability, reference-data identity, fixture pipeline
**Confidence:** HIGH (root cause proven empirically against the shipped offline database)

## Summary

The `.exactproject` export encodes every reference-data relation as a **raw integer primary
key**, with no natural key, no reference-data version stamp, and no resolution step on import.
The importer's only guard is a single helper for `StatusType` whose own docstring states the
governing assumption verbatim: *"Reference-data PKs are stable across EX-ACT installations, so
this is normally the identity"* [VERIFIED: djangoexact/api/views.py:1109-1124].

That assumption is false in practice, and the reason is not PK instability in the fixture
pipeline. The fixture pipeline is sound: fixtures pin explicit PKs and `dump_reference_data`
guards against renumbering. The problem is that **the offline tool does not use the fixture
pipeline at all**. The `release/offline-tool` branch ships a 53 MB pre-built
`djangoexact/db.sqlite3` [VERIFIED: `git show release/offline-tool --stat`, file added/last
refreshed 2026-04-13 in commit 202c6942 "ref: update db with new migrations"]. That snapshot is
an independently seeded database of a different vintage, so its reference PKs diverged from the
committed fixtures that the online installation is built from.

Measured drift: **83 of 162 manifest reference models differ** between the shipped offline
sqlite and the committed fixtures [VERIFIED: scripted PK/name diff of
`git show release/offline-tool:djangoexact/db.sqlite3` against `api/fixtures/*.json` +
`ipcc/fixtures/*.json`, run this session].

**Primary recommendation:** Fix the cause and the symptom in that order. (1) Stop shipping
`db.sqlite3` as the offline reference source; bootstrap the offline build with
`migrate` + `load_reference_data --app=all` so PKs match by construction, which is exactly what
views.py:1109-1116 already assumes. (2) Because that does nothing for offline builds already in
users' hands, add `formatVersion: 2` dual-encoding: keep the legacy integer alongside a natural
key per reference FK, resolve by natural key on import, and hard-fail with a named, actionable
error when a key cannot be resolved. Do not silently drop or silently accept an integer.

## Root Cause: two candidates, one confirmed

| Candidate | Verdict | Evidence |
|---|---|---|
| PK instability in the fixture pipeline | **NOT the cause** | Fixtures pin explicit `"pk"` values [VERIFIED: api/fixtures/climate.json lines 1-12, `"pk": 4` with `"name": "Boreal"`]. `dump_reference_data` runs with `use_natural_primary_keys=False, use_natural_foreign_keys=False` [VERIFIED: djangoexact/api/management/commands/dump_reference_data.py:62] and refuses to overwrite a PK whose row changed semantic identity [CITED: djangoexact/docs/guides/fixtures-guide.md, "PK stability guardrail"]. Two installations that both run `load_reference_data --app=all` from the same commit **will** have identical PKs. |
| Reference-data source skew between installations | **CONFIRMED** | The offline build bypasses `load_reference_data` entirely and ships a committed sqlite snapshot [VERIFIED: `djangoexact/db.sqlite3 | Bin 0 -> 53694464 bytes` in `git diff --stat develop...release/offline-tool`]. 83/162 models mismatch. |

Note the irony: the fixtures guide's own illustration of a PK-stability violation is
*"pk=50 used to be `Plantation` and is now `Annual Cropland`"* [CITED:
djangoexact/docs/guides/fixtures-guide.md:39]. That exact collision is live in the shipped
offline DB.

### Confirmed drift on the highest-impact tables

`api.ModuleType` [VERIFIED: fixture vs offline sqlite diff, this session]:

```
 !! pk=50   fixture='Annual Cropland Minor Season'    offlinedb='Plantation'
 !! pk=51   fixture='Perennial Cropland Minor Season' offlinedb='OtherLandUse'
 !! pk=52   fixture='Plantation'                      offlinedb='Annual Cropland Minor Season'
 !! pk=55   fixture='Project'                         offlinedb='Storage'
 !! pk=59   fixture='Packaging'                       offlinedb='Processing Entry'
 !! pk=64   fixture='Processing Entry'                offlinedb=None
```

`api.StatusType`:

```
 !! pk=3    fixture='SUBMODULES_EMPTY'   offlinedb='IN PROGRESS'
 !! pk=4    fixture='IN PROGRESS'        offlinedb=None
 !! pk=5    fixture=None                 offlinedb='SUBMODULES_EMPTY'
```

`ipcc.GlobalWarmingPotential` is the worst case: the PK ranges are **completely disjoint**.
Fixtures use 8-12, the offline DB uses 1-5 [VERIFIED: ipcc/fixtures/globalwarmingpotential.json
pks 8,9,10,11,12 vs `select id,name from ipcc_globalwarmingpotential` returning 1..5]. AR6 is
pk=12 online and pk=5 offline. `Project.gw_potential` is a **non-nullable** FK
[VERIFIED: djangoexact/api/models.py:694]. Every online-to-offline import therefore fails at the
first row.

`api.LandUseType` is the highest-traffic reference FK (16 declarations in models.py) and has
**135 PKs present in fixtures but absent from the offline DB** (211 fixture rows vs 77 offline
rows). Practically every land module in an online export points at a LandUseType the offline
tool has never heard of.

## Ground Truth: the current mechanism

### Export

- Endpoint: `GET /api/projects/{pk}/export/`, DRF `@action` [VERIFIED: djangoexact/api/views.py:883-927].
- Format: a JSON file named `<project>.exactproject`, envelope
  `{formatVersion: 1, appVersion, compatibilityGroup, exportedAt, exportId, project}`
  [VERIFIED: djangoexact/api/views.py:911-918].
- `appVersion` / `compatibilityGroup` come from `version.config.json`
  [VERIFIED: djangoexact/api/views.py:485-496; version.config.json contains
  `{"appVersion": "1.19.2a0", "compatibilityGroup": 1}`].
- Reference FKs are emitted as **raw integer PKs, always**:
  - Modules: `value = getattr(instance, f'{field.name}_id', None)` with the comment
    `# Store FK / OneToOne as ID` [VERIFIED: djangoexact/api/serializers.py:684-687].
  - Project: nested reference dicts are explicitly *flattened down to* their `id`
    for `country, climate, moisture, soil_type, gw_potential, status`
    [VERIFIED: djangoexact/api/serializers.py:739-745].
  - M2M `Activity.module_types` is emitted as a bare PK list.
- There is **no reference-data version stamp** in the envelope. `compatibilityGroup` is an app
  compatibility number, unrelated to fixture vintage, and it is `1` on both sides.

### Import

- Endpoint: `POST /api/projects/import_project/` [VERIFIED: djangoexact/api/views.py:929-1249].
- Validation is envelope-only: `formatVersion == 1` and `compatibilityGroup` equality
  [VERIFIED: djangoexact/api/serializers.py:748-774]. Neither can detect reference skew.
- Resolution: none. `prepare_model_data` converts every integer FK straight to `<field>_id`
  and hands it to `objects.create()` [VERIFIED: djangoexact/api/views.py:1094 and
  djangoexact/api/views.py:1097-1099].
- `Activity.module_types.set(module_types_data)` writes raw exported PKs into the M2M through
  table with no validation [VERIFIED: djangoexact/api/views.py:1173-1175].
- The **only** reference resolver in the whole path is `resolve_status_id`, and it silently
  drops an unknown id rather than failing [VERIFIED: djangoexact/api/views.py:1109-1124].

### Failure modes, precisely

| Situation | Behavior | Where |
|---|---|---|
| Exported PK absent in target DB | `IntegrityError` inside `transaction.atomic`, caught by a blanket `except Exception`, returned as HTTP 400 with the raw DB error string interpolated into the message | views.py:1244-1249 |
| Exported PK present but points at a **different** reference row | **Silent mis-resolution.** No error. The project imports and displays wrong climate / soil / GWP / module type. Cached results are restored as-is by product decision, so the stored numbers stay while the inputs beside them silently change | views.py:1094, views.py:1232-1236 |
| Exported `StatusType` PK unknown | Silently dropped; module falls back to EMPTY | views.py:1116-1124 |
| Exported `ModuleType` PK swapped | Activity claims the wrong module types; no error | views.py:1175 |

The second row is the dangerous one. It is a correctness bug in a GHG appraisal tool, not a
usability bug, and it is worse than the crash because nothing surfaces it.

## Natural-key candidates

Full audit of reference models reachable as module/project FKs. `FKrefs` counts
ForeignKey/OneToOneField declarations in `djangoexact/api/models.py`; `drift` is the PK-set
delta measured against the shipped offline DB [VERIFIED: scripted diff, this session].

| Model | FKrefs | `name` unique today | i18n | Fixture rows | Offline rows | PK drift | Natural key gap |
|---|---|---|---|---|---|---|---|
| LandUseType | 16 | **no** | yes | 211 | 77 | 135 missing offline | needs UniqueConstraint; names are de-facto unique (211/211 distinct) |
| ResidueManagementType | 9 | **no** | yes | 3 | 3 | none | needs UniqueConstraint |
| FuelType | 9 | no (`unique_together`) | yes | 19 | 19 | 9 swapped | use `(parent, name)` composite natural key |
| TillageManagementType | 6 | yes | yes | 3 | 3 | none | ready |
| OrganicInputType | 6 | yes | yes | 5 | 4 | 1 | ready |
| ModuleType | 5 (+M2M) | yes | yes | 44 | 44 | **6 semantically swapped** | ready |
| Country | 4 | yes | no | 250 | 256 | 4 + 10, plus renames | ready, but see rename pitfall |
| SoilType | 3 | **no** | yes | 9 | 9 | none | needs UniqueConstraint |
| WaterManagementType{Before,After}Cultivation | 3 each | **no** | yes | 3 / 6 | same | none | needs UniqueConstraint |
| OrganicAmendmentType | 3 | **no** | yes | 7 | 7 | none | needs UniqueConstraint |
| GrasslandManagementType | 3 | **no** | yes | 6 | 6 | none | needs UniqueConstraint |
| LivestockProductionType | 3 | **no** | yes | 3 | 3 | none | needs UniqueConstraint |
| ManureManagementType | 3 | **no** | yes | 16 | 16 | none | needs UniqueConstraint |
| TrophicType | 3 | **no** | yes | 5 | 5 | none | needs UniqueConstraint |
| Small/LargeFisheryGearType | 3 each | yes | yes | 8 / 10 | same | none | ready |
| FireType | 3 | **no** | yes | 3 | 3 | none | needs UniqueConstraint |
| SettlementType | 3 | **no** | yes | 5 | 5 | **all 5 renumbered** | needs UniqueConstraint |
| RefrigerantType | 3 | yes | no | 18 | 17 | 1 | ready |
| PackagingMaterialType | 3 | yes | yes | 5 | 5 | none | ready |
| Climate | 2 | **no** | yes | 5 | 5 | none | needs UniqueConstraint |
| Moisture | 2 | **no** | yes | 3 | 3 | none | needs UniqueConstraint |
| ForestType | 2 | **no** | yes | 2 | 2 | none | needs UniqueConstraint |
| StatusType | 2 | yes | yes | 4 | 4 | 3 shifted | ready |
| EmissionFactorSource | 2 | yes | no | 3 | 2 | 1 + renames | ready |
| IrrigationSystemType | 2 | yes | yes | 12 | 12 | none | ready |
| ipcc.GlobalWarmingPotential | 1 (**NOT NULL**) | **no** | yes | 5 (pk 8-12) | 5 (pk 1-5) | **fully disjoint** | needs UniqueConstraint; highest priority |
| Unit | 1 | **no** | no | 3 | 166 | 163 extra offline | needs UniqueConstraint |
| ProjectStatus | 1 | **no** | no | 2 | 4 | 2 extra offline | needs UniqueConstraint |
| InputType | 1 | yes | yes | 17 | 17 | 1 | ready |
| MacroInputType | 1 | yes | yes | 8 | 7 | 1 renamed | ready |

Roughly **half the reference models used as module FKs lack a uniqueness constraint on
`name`**. This is the single largest cost item in any natural-key solution: it needs one
migration adding `UniqueConstraint`s, and a data-cleanup pass wherever duplicates exist today.

Nothing in the codebase implements `natural_key()` or `get_by_natural_key()` today
[VERIFIED: repo-wide grep for `natural_key`, only hit is the explicit `False` flags at
dump_reference_data.py:62].

## Solution Options

### (a) Natural-key serialization on export, resolve-by-natural-key on import

**How:** Django's model-level protocol is `natural_key()` on the model plus
`get_by_natural_key()` on a custom manager, with `natural_key.dependencies` controlling
serialization order [CITED: https://docs.djangoproject.com/en/5.2/topics/serialization].
DRF's boundary equivalent is `SlugRelatedField(slug_field=..., queryset=...)`, which is
read-write and whose docs state the slug field *"should correspond to a model field with
`unique=True`"* [CITED: https://www.django-rest-framework.org/api-guide/relations]. For the
composite cases (FuelType) a custom `RelatedField` with `to_internal_value` is required
[CITED: https://www.django-rest-framework.org/api-guide/relations].

- **Blast radius:** export serializer + import `prepare_model_data` + one migration adding
  ~20 `UniqueConstraint`s. Does not touch calculators, math_model, or the reference pipeline.
- **Migration cost:** medium-high. The uniqueness migration is the bulk of it, and it may
  surface real duplicate rows that need a data decision.
- **Backward compatibility:** good if done as dual-encoding under `formatVersion: 2` (emit
  both `climate: 12` and `climate__nk: "Tropical"`; importer prefers the natural key, falls
  back to the integer for v1 files). Do **not** bump `compatibilityGroup` — that field
  hard-rejects the file at serializers.py:757-767 and would break every export already issued.
- **Constraint check:** public API contract unchanged (new optional keys in the export body
  only); no calculation path touched.

### (b) Reference-data manifest / version stamp in the envelope, hard-fail on mismatch

**How:** add `referenceDataFingerprint` to the envelope, computed as a hash over the manifest
model list plus per-model `(max_pk, row_count, checksum)`. Import compares and refuses on
mismatch with a named message.

- **Blast radius:** tiny. Two functions.
- **Migration cost:** low.
- **Backward compatibility:** v1 files have no fingerprint, so treat absence as "unknown, warn".
- **Weakness:** it converts a silent wrong answer into a loud refusal, which is a real safety
  gain, but on its own it makes the offline tool *stop importing anything* until (c) lands. It
  is a necessary guardrail, not a solution.

### (c) Ship identical fixtures to the offline tool so PKs match by construction

**How:** delete `djangoexact/db.sqlite3` from `release/offline-tool`; build the offline database
during packaging with `manage.py migrate && manage.py load_reference_data --app=all`, from the
same commit as the online deployment.

- **Blast radius:** offline build/packaging only. No application code.
- **Migration cost:** lowest of all four. Removes a 53 MB binary from git as a bonus.
- **Backward compatibility:** does nothing for offline builds already installed, and nothing for
  `.exactproject` files already exported from them. Also fragile long-term: it re-establishes an
  invariant that only holds while nobody edits reference data out-of-band, which is precisely
  what already happened.
- **Constraint check:** fully compliant. It is what `fixtures-guide.md` already prescribes.

### (d) ID remapping / translation table built at import time

**How:** at import, build `{exported_pk -> local_pk}` per reference model.

- **Verdict: not viable standalone.** A remap table needs a shared identity to remap *on*. The
  export carries only the integer, so there is nothing to join by. This option is only
  implementable *as* option (a), with the natural key as the join key. Listing it separately is
  a category error; fold it into (a).

### Recommendation

**Do (c) first, then (a) with (b) as the failure mode.**

1. **(c)** removes the actual cause and is a packaging change with near-zero risk. Ship it
   first so new offline installs stop being broken.
2. **(a)** under `formatVersion: 2` dual-encoding makes the format self-describing, so this
   class of bug cannot recur when reference data legitimately diverges (a new IPCC table, a
   country rename). Sequence the `UniqueConstraint` migration first; it is the long pole.
3. **(b)** replaces the current silent-mis-resolution path: when a natural key does not resolve,
   fail with `"Cannot import: this file references reference data '<model>: <key>' that does
   not exist in this installation (offline build reference data may be out of date)."` Never
   fall back to the integer when a natural key is present but unresolvable, and never silently
   drop as `resolve_status_id` does today.

The order matters because (c) is what makes (a)'s fallback path safe: once both sides bootstrap
from the same fixtures, a natural-key miss genuinely means bad data rather than routine skew.

## Pitfalls specific to this codebase

1. **`unique=True` propagates to every translation column.** modeltranslation copies the wrapped
   field's `__dict__` wholesale onto each language field
   [VERIFIED: .venv/.../modeltranslation/fields.py:125-127, `self.__dict__.update(translated_field.__dict__)`],
   forcing only `null=True` afterward (fields.py:140). Empirically confirmed on the shipped
   schema: `api_moduletype` has `"name" ... UNIQUE, "name_en" ... NULL UNIQUE, "name_es" ... NULL
   UNIQUE, "name_fr" ... NULL UNIQUE, "name_ru" ... NULL UNIQUE`
   [VERIFIED: `select sql from sqlite_master where name='api_moduletype'` on the offline DB].
   Adding `unique=True` to a translated `name` therefore also constrains all four translations;
   two rows sharing a French translation will fail the migration. Prefer an explicit
   `Meta.constraints = [UniqueConstraint(fields=["name_en"], ...)]` and key on `name_en`, not on
   the language-sensitive `name` descriptor.

2. **Never use the translated `name` as the wire key.** `instance.name` resolves through the
   active language with fallback. An export produced with `?lang=fr` would emit French keys.
   All 50-plus reference models are registered with `NameOnlyTranslationOptions`
   [VERIFIED: djangoexact/api/translation.py:5-7 and the `@register` blocks]. Pin the natural
   key to `name_en`.

3. **Renames break natural keys the same way renumbering breaks PKs.** The offline DB has
   `Bolivia` where fixtures have `Bolivia (Plurinational State of)`, and
   `China, Hong Kong Special Administrative Region` where fixtures have `China, Hong Kong SAR`
   [VERIFIED: fixture/DB diff]. The `Turkey -> Türkiye` case is already documented
   [CITED: fixtures-guide.md:43]. A name-based natural key needs an alias table or an explicit
   stable code column for `Country` (there is none today; `Country` has only `name`, `region`,
   `ipcc_region`, `gleam_region` [VERIFIED: djangoexact/api/models.py, `class Country`]).

4. **Multi-table inheritance on Module/LandModule.** `ModuleExportSerializer.to_representation`
   walks `instance._meta.get_fields()` and skips anything without a `column`
   [VERIFIED: djangoexact/api/serializers.py:668-673]. Inherited parent-link columns come along
   automatically, so a natural-key encoder placed in the same loop will cover subclasses without
   per-model registration. Keep it there rather than writing per-model serializers.

5. **`db.sqlite3` in git.** The offline branch commits a 53 MB binary that is simultaneously the
   app database and the reference-data source of truth for that build. Any fix that leaves it in
   place will drift again the moment someone runs a migration locally and commits.

6. **SQLite defers FK checks inside `atomic`.** On the offline build the `IntegrityError` from an
   unknown reference PK surfaces at constraint-check time rather than at the offending
   `create()`, so the 400 message at views.py:1244-1249 names a table, not the module. Any
   error-message improvement must resolve keys *before* hitting the DB to be useful.

7. **Testing constraint.** No `pytest-django`; anything touching the ORM must subclass Django
   `TestCase` / `APITestCase` [CITED: repo CLAUDE.md, "Testing"]. Existing coverage lives in
   `djangoexact/api/tests/test_project_export.py`, which currently uses `TestCase` + `APIClient`
   [VERIFIED: djangoexact/api/tests/test_project_export.py:1-45]. A regression test for this bug
   needs to *simulate* skew, since it cannot boot two databases: create the reference row, note
   its PK, then export a fixture body with a deliberately shifted PK and assert the import either
   resolves correctly by natural key or fails with the named error.

8. **`AppSpecificDatabaseRouter`.** Both routers currently point at `default`
   [CITED: repo CLAUDE.md, "Database routing"], so a natural-key manager lookup will not cross a
   DB boundary today. If the `api`/`ipcc` split is ever executed, `get_by_natural_key` must be
   routed explicitly.

9. **Cached results are restored unconditionally, by product decision.** "restore the cached
   numbers as-is, always. Do not gate on reference-data equality"
   [CITED: .planning/debug/resolved/import-project-loses-results.md, "Decisions from the user
   (binding)"]. That decision stands, but it is what makes silent mis-resolution invisible: the
   numbers survive while their inputs change. Do not reopen the decision; make the *inputs*
   resolve correctly instead.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | The "offline tool" the user means is the `release/offline-tool` branch build, not a separate unrelated desktop product | Root Cause | If it is a different artifact, the sqlite evidence still demonstrates the mechanism but the specific 83-model drift figure would not apply |
| A2 | The deployed online instance's reference data matches the committed fixtures | Root Cause | If production Postgres has drifted from its own fixtures too, the skew is bidirectional and (c) alone is insufficient; (a) becomes mandatory rather than a hardening step |
| A3 | `LandUseType` names being 211/211 distinct in fixtures implies they are distinct in production | Natural keys | The uniqueness migration would fail on real data and need a cleanup pass first |

## Open Questions

1. **Is the online production DB in sync with its own committed fixtures?**
   Cannot be verified from this sandbox (no Postgres). Recommendation: run
   `manage.py dump_reference_data --app=all --dry-run` against production via cloud-sql-proxy and
   check for a diff. This decides whether A2 holds.
2. **How is the offline build actually packaged?** `settings_offline.py` only strips apps and
   routes [VERIFIED: `git show release/offline-tool:djangoexact/djangoexact/settings_offline.py`];
   it says nothing about database provisioning. The packaging step that consumes `db.sqlite3`
   is outside this repo's Django root, so (c)'s exact implementation point is unconfirmed.
3. **How many `.exactproject` files are already in the wild from an offline build?** Determines
   whether v1 files need a one-off remediation path in addition to the v2 format.

## Sources

### Primary (HIGH confidence)
- This repository, read directly this session: `djangoexact/api/views.py`,
  `djangoexact/api/serializers.py`, `djangoexact/api/models.py`,
  `djangoexact/api/fixtures_manifest.py`,
  `djangoexact/api/management/commands/dump_reference_data.py`,
  `djangoexact/api/translation.py`, `djangoexact/api/tests/test_project_export.py`,
  `djangoexact/docs/guides/fixtures-guide.md`,
  `.planning/debug/resolved/import-project-loses-results.md`
- `git show release/offline-tool:djangoexact/db.sqlite3`, queried with sqlite3 and diffed
  against every committed fixture in the manifest
- Django 5.2 serialization docs via Context7 (`/websites/djangoproject_en_5_2`) - natural keys,
  `get_by_natural_key`, `natural_key.dependencies`
- DRF relations docs via Context7 (`/websites/django-rest-framework`) - `SlugRelatedField`,
  custom `RelatedField.to_internal_value`

## Metadata

**Confidence breakdown:**
- Current mechanism: HIGH - every claim cites a line read this session
- Root cause: HIGH - reproduced by direct measurement against the shipped artifact
- Natural-key audit: HIGH for uniqueness and drift (scripted); MEDIUM on whether production data
  satisfies the proposed constraints (A3)
- Recommendation: MEDIUM-HIGH - depends on open question 2 (packaging mechanics)

**Research date:** 2026-08-13
**Valid until:** 2026-09-13 (or the next refresh of `release/offline-tool:db.sqlite3`)
