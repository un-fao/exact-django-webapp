"""Natural keys for reference data crossing an installation boundary.

`.exactproject` v1 encoded every reference relation as a raw integer primary key
and resolved nothing on import, which is only safe while both installations
agree on what primary key N means. They do not: an offline build seeded outside
the fixture pipeline drifts, and the import then either fails at the first row or,
worse, silently resolves to a different climate / soil type / GWP report.

This module is the single source of truth for the identity used instead. It is
shared by three callers:

- `check_reference_natural_keys` (duplicate detection, run before the migration),
- `ModuleExportSerializer` / `ProjectExportSerializer` (encode `<field>__nk`),
- `prepare_model_data` in the import path (resolve `<field>__nk` to a local pk).

Registry membership is the gate for all of it. A ForeignKey whose target model is
absent from `NATURAL_KEY_SPECS` gets no natural key on export and no resolution
on import, which is what keeps user-data relations (`Activity.owner`,
`Module.activity`, the cross-module OneToOne refs) on their existing paths.

**The v1 half.** A file produced before formatVersion 2 existed, or by an
installation that has not been upgraded yet, carries no key at all. Nothing can
resolve those integers, so `verify_legacy_reference_pk` checks them instead: a
registered target whose pk names no local row raises `LegacyReferenceIdError`
rather than being written through. The write-through is what produced a bare
`FOREIGN KEY constraint failed` from the sqlite driver, naming neither table nor
column, and it is why an online-to-offline import failure was undiagnosable.

Two rules that are easy to get wrong here:

1. **Key on `name_en`, never on `name`, for any translated model.**
   `instance.name` resolves through the active language, so an export produced
   under `?lang=fr` would emit French keys. Explicit language columns are not
   rewritten by modeltranslation and are therefore stable.

2. **Never put `unique=True` on a translated field.** modeltranslation copies the
   wrapped field's `__dict__` onto every language column, so `unique=True` on
   `name` silently constrains `name_es`, `name_fr` and `name_ru` too, and two
   rows sharing a French translation would fail the migration. The uniqueness
   behind these keys is declared as an explicit
   `Meta.constraints = [UniqueConstraint(fields=["name_en"], ...)]`.

**Renames.** A name-based natural key breaks on a rename exactly as a primary key
breaks on renumbering. `Country` has no stable code column today (only `name`,
`region`, `ipcc_region`, `gleam_region`), and adding an ISO column is a data
migration project out of scope here, so renames are handled by the explicit
`COUNTRY_NAME_ALIASES` table below. An unaliased rename surfaces as a named
import failure rather than as a wrong country. That is the intended trade: a
loud stop beats a silent substitution in a GHG appraisal. A future ISO-code
column would retire the alias table.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class NaturalKeySpec:
    """The ORM lookup paths that identify one reference row across installations.

    `fields` are ORM lookup paths, so the same tuple both encodes
    (`values_list(*fields)`) and decodes (`filter(**dict(zip(fields, key)))`).
    That covers direct columns and FK traversals uniformly, at one query each.
    """

    fields: Tuple[str, ...]
    label: str


class ReferenceResolutionError(Exception):
    """Base for every failure to point an imported relation at a local row.

    Two subclasses, one per encoding the payload can use. Callers that do not
    distinguish the cause catch this base: `import_project` does, because both
    render as the same 400 with their own already-actionable message.
    """


class UnresolvableNaturalKeyError(ReferenceResolutionError):
    """A natural key in an import payload names no row in this installation.

    Raised instead of falling back to the encoded integer primary key. The
    fallback is precisely the silent mis-resolution this module exists to remove.
    """

    def __init__(self, label, key, detail=None):
        self.label = label
        self.key = tuple(key) if key is not None else ()
        self.detail = detail
        rendered = " / ".join("" if part is None else str(part) for part in self.key)
        message = (
            f"Cannot import: this file references reference data "
            f"'{label}: {rendered}' that does not exist in this installation "
            f"(offline build reference data may be out of date)."
        )
        if detail:
            message = f"{message} {detail}"
        super().__init__(message)


class LegacyReferenceIdError(ReferenceResolutionError):
    """A formatVersion 1 payload names reference data by primary key alone, and
    no row with that primary key exists here.

    A primary key is private to the database that issued it. v1 carries no
    natural key beside it, so there is nothing left to resolve the row by: the
    integer cannot be repaired, only re-exported. Raised rather than written
    through, because writing it through is what produces the bare
    ``FOREIGN KEY constraint failed`` that names neither the table nor the row.
    """

    def __init__(self, label, field_name, pk):
        self.label = label
        self.field_name = field_name
        self.pk = pk
        super().__init__(
            f"Cannot import: this file was produced by an older version of EX-ACT "
            f"(file format 1), which identifies reference data by database id "
            f"instead of by name. It sets '{field_name}' to '{label}' id {pk}, "
            f"which does not exist in this installation. Ids are not shared "
            f"between EX-ACT installations, so this file cannot be repaired on "
            f"import. Export the project again from the online tool once it has "
            f"been updated, then import the new file."
        )


# Historical country names mapped to their current name. Seeded with the renames
# observed between the committed fixtures and the shipped offline database.
COUNTRY_NAME_ALIASES: Dict[str, str] = {
    "Turkey": "Türkiye",
    "Bolivia": "Bolivia (Plurinational State of)",
    "China, Hong Kong Special Administrative Region": "China, Hong Kong SAR",
}


def _name_en(label):
    return NaturalKeySpec(fields=("name_en",), label=label)


def _name(label):
    return NaturalKeySpec(fields=("name",), label=label)


# Every reference model reachable as a Project / Activity / Module foreign key.
# The comment on each block records the uniqueness situation, because that is
# what decides whether the key is trustworthy.
NATURAL_KEY_SPECS: Dict[str, NaturalKeySpec] = {
    # --- translated, `name_en` already unique because `unique=True` on the
    # wrapped `name` propagates to every language column. No new constraint.
    "api.StatusType": _name_en("api.StatusType"),
    "api.TillageManagementType": _name_en("api.TillageManagementType"),
    "api.OrganicInputType": _name_en("api.OrganicInputType"),
    "api.ModuleType": _name_en("api.ModuleType"),
    "api.LargeFisheryGearType": _name_en("api.LargeFisheryGearType"),
    "api.SmallFisheryGearType": _name_en("api.SmallFisheryGearType"),
    "api.PackagingMaterialType": _name_en("api.PackagingMaterialType"),
    "api.InputType": _name_en("api.InputType"),
    "api.MacroInputType": _name_en("api.MacroInputType"),
    "api.IrrigationSystemType": _name_en("api.IrrigationSystemType"),
    # --- untranslated, `name` already unique=True. No new constraint.
    "api.Country": _name("api.Country"),
    "api.RefrigerantType": _name("api.RefrigerantType"),
    "api.EmissionFactorSource": _name("api.EmissionFactorSource"),
    # --- translated and NOT unique today: a UniqueConstraint on `name_en` is
    # added alongside this registry (api migration 0290, ipcc migration 0065).
    "api.LandUseType": _name_en("api.LandUseType"),
    "api.SettlementType": _name_en("api.SettlementType"),
    "api.SoilType": _name_en("api.SoilType"),
    "api.ResidueManagementType": _name_en("api.ResidueManagementType"),
    "api.OrganicAmendmentType": _name_en("api.OrganicAmendmentType"),
    "api.WaterManagementTypeBeforeCultivation": _name_en("api.WaterManagementTypeBeforeCultivation"),
    "api.WaterManagementTypeAfterCultivation": _name_en("api.WaterManagementTypeAfterCultivation"),
    "api.GrasslandManagementType": _name_en("api.GrasslandManagementType"),
    "api.LivestockProductionType": _name_en("api.LivestockProductionType"),
    "api.ManureManagementType": _name_en("api.ManureManagementType"),
    "api.FireType": _name_en("api.FireType"),
    "api.TrophicType": _name_en("api.TrophicType"),
    "api.Climate": _name_en("api.Climate"),
    "api.Moisture": _name_en("api.Moisture"),
    "api.ForestType": _name_en("api.ForestType"),
    # Highest priority entry in this registry. GlobalWarmingPotential primary key
    # ranges are fully disjoint between installations (fixtures 8-12, shipped
    # offline database 1-5) and `Project.gw_potential` is NOT NULL, so this is
    # what makes every online-to-offline import fail at the first row.
    "ipcc.GlobalWarmingPotential": _name_en("ipcc.GlobalWarmingPotential"),
    # --- untranslated and NOT unique today: new UniqueConstraint on `name`.
    # api.Unit is the exception: it has NO uniqueness guarantee and gets no
    # constraint, because `check_reference_natural_keys` found 66 duplicate and
    # 100 blank-named rows in the shipped offline database against 3 rows in the
    # fixtures. Deduping reference data to force the constraint through was
    # refused; see .planning/quick/260813-fvj-*/260813-fvj-DUPLICATES.md.
    # Registered anyway, and inert: Unit's only ForeignKey anywhere in the model
    # layer is FuelType.unit, reference data pointing at reference data, so no
    # exported payload carries a Unit relation to encode or resolve.
    "api.Unit": _name("api.Unit"),
    "api.ProjectStatus": _name("api.ProjectStatus"),
    # --- composite. The existing `unique_together` constrains the base `name`
    # column, not `name_en`, so a matching UniqueConstraint on
    # (name_en, fuel_use_type, macro_fuel_type) is added.
    "api.FuelType": NaturalKeySpec(
        fields=("name_en", "fuel_use_type__name_en", "macro_fuel_type__name_en"),
        label="api.FuelType",
    ),
}


def spec_for(model) -> Optional[NaturalKeySpec]:
    """Return the natural-key spec for a model, or None if it is not registered."""
    if model is None:
        return None
    meta = getattr(model, "_meta", None)
    if meta is None:
        return None
    return NATURAL_KEY_SPECS.get(meta.label)


def natural_key_for_pk(model, pk, cache=None) -> Optional[tuple]:
    """Encode: return the natural key of `model` row `pk`, or None.

    None means "no natural key available": the model is unregistered, the pk is
    null, or the row does not exist. Callers treat that as "emit nothing" rather
    than as an error, so an unregistered relation keeps its existing behaviour.

    `cache` is an optional caller-supplied dict, deliberately not `lru_cache`:
    an export or import request must never be served reference data cached by an
    earlier request. Contrast `module_type_for_class` in api/models.py, which is
    process-cached on purpose because it is read-only at runtime.
    """
    spec = spec_for(model)
    if spec is None or pk is None:
        return None

    cache_key = ("encode", spec.label, pk)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    row = model.objects.filter(pk=pk).values_list(*spec.fields).first()
    key = tuple(row) if row is not None else None

    if cache is not None:
        cache[cache_key] = key
    return key


def natural_key_for(instance) -> Optional[tuple]:
    """Encode: return the natural key of a model instance, or None."""
    if instance is None:
        return None
    return natural_key_for_pk(type(instance), instance.pk)


def resolve_natural_key(model, key, cache=None) -> int:
    """Decode: return the local primary key for `key`, or raise.

    Never returns None and never falls back to an encoded integer. An
    unresolvable key is a hard failure by design.
    """
    spec = spec_for(model)
    label = spec.label if spec is not None else getattr(getattr(model, "_meta", None), "label", str(model))

    if spec is None:
        raise UnresolvableNaturalKeyError(
            label, key, detail="This model has no declared natural key."
        )

    key = tuple(key) if key is not None else ()
    if len(key) != len(spec.fields):
        raise UnresolvableNaturalKeyError(
            label,
            key,
            detail=f"Expected {len(spec.fields)} key component(s), got {len(key)}.",
        )

    cache_key = ("decode", spec.label, key)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    pk = _lookup_pk(model, spec, key)

    # Renames break name-based keys the same way renumbering breaks primary keys.
    if pk is None and spec.label == "api.Country":
        aliased = COUNTRY_NAME_ALIASES.get(key[0])
        if aliased is not None:
            pk = _lookup_pk(model, spec, (aliased,))

    if pk is None:
        raise UnresolvableNaturalKeyError(label, key)

    if cache is not None:
        cache[cache_key] = pk
    return pk


def verify_legacy_reference_pk(model, field_name, pk, cache=None) -> int:
    """Return `pk` if it names a row of `model` here, else raise.

    The formatVersion 1 counterpart of `resolve_natural_key`. A v1 payload has
    no key to resolve, so the only honest thing left is to check the integer
    before it reaches the database and fail by name if it means nothing here.
    Unregistered targets never reach this function: registry membership is the
    gate on the way in exactly as it is on the way out, which is what keeps
    user-data relations on their existing paths.

    `cache` shares the dict used by `resolve_natural_key`, under its own
    namespace, so a payload naming the same bad reference on 400 modules costs
    one query rather than 400. A miss is memoised as None and re-raised, because
    the failure is a property of this installation and cannot change mid-import.
    """
    spec = spec_for(model)
    label = spec.label if spec is not None else getattr(
        getattr(model, "_meta", None), "label", str(model)
    )

    cache_key = ("verify", label, pk)
    if cache is not None and cache_key in cache:
        if cache[cache_key] is None:
            raise LegacyReferenceIdError(label, field_name, pk)
        return cache[cache_key]

    exists = model.objects.filter(pk=pk).exists()

    if cache is not None:
        cache[cache_key] = pk if exists else None
    if not exists:
        raise LegacyReferenceIdError(label, field_name, pk)
    return pk


def _lookup_pk(model, spec, key):
    """Return the lowest matching pk, or None.

    Lowest rather than arbitrary so the result is deterministic if duplicates
    somehow exist. Duplicates are meant to be impossible: they are detected by
    `manage.py check_reference_natural_keys` before the uniqueness constraints
    are applied, and prevented by those constraints afterwards.

    A None component is a genuine part of the identity for a nullable composite
    member (`api.FuelType.macro_fuel_type`), so it becomes an `__isnull` lookup
    rather than an equality test against NULL, which would match nothing.
    """
    if all(part is None or part == "" for part in key):
        # Nothing left to identify a row by.
        return None

    lookups = {}
    for lookup_path, value in zip(spec.fields, key):
        if value is None:
            lookups[f"{lookup_path}__isnull"] = True
        else:
            lookups[lookup_path] = value

    return (
        model.objects.filter(**lookups)
        .order_by("pk")
        .values_list("pk", flat=True)
        .first()
    )
