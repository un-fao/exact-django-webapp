"""GHG Protocol scope catalog for EX-ACT emission fluxes.

A flux is one `ActivityTypes` member and one `GasTypes` member, emitted by a module or by a submodule entry.
This module maps each flux to a provisional scope. Like `api.inventory_labels`, it is presentation-layer only:
the calculators and `math_model` never read it, and it runs no database queries. Importing it still needs
Django apps to be ready, because `api.utilities` imports the models.

Rules are looked up from the most to the least specific key, first match wins:

1. `CLASS_OVERRIDES[class name][(activity, gas)]`
2. `CLASS_OVERRIDES[class name][(activity, None)]`
3. `DEFAULT_RULES[(activity, gas)]`
4. `DEFAULT_RULES[(activity, None)]`

A gas of `None` in a key means "any gas". Overrides are keyed on the Python class name of the source
(`type(source).__name__`), never on `module_type.name`, which modeltranslation translates.

The defaults come from the team's scope mapping document. Rules whose scope is still under discussion carry
`pending_review=True` and name the open question in `note`.
"""

import logging
from dataclasses import dataclass, replace
from enum import Enum

from api.utilities import ScenarioTypes
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

log = logging.getLogger("console")

# IrrigationPhaseCalculator tests electric pumping with this exact-case list, not with the casefolded
# ELECTRIC_FUEL_TYPES that EnergyEntryCalculator uses; the scope must follow the check that produced the numbers.
IRRIGATION_ELECTRIC_FUEL_NAMES = ("Renewable", "Electricity")

_logged_unassigned: set[tuple[str, str, str]] = set()


class Scope(Enum):
    """GHG Protocol scope bucket. Values are stable codes (Excel SUMIFS formulas key on them).

    Definition order is report order: Scope 1, 2, 3, outside scopes, unassigned.
    """

    SCOPE_1 = "1"
    SCOPE_2 = "2"
    SCOPE_3 = "3"
    OUTSIDE_SCOPES = "outside"
    UNASSIGNED = "unassigned"


@dataclass(frozen=True)
class ScopeRule:
    """Scope of one flux.

    `allowed` lists the scopes a user may pick (more than one means user-selectable) and always contains
    `default`. `scope3_category` is the GHG Protocol Scope 3 category the flux falls in when booked as Scope 3.
    """

    default: Scope
    allowed: tuple[Scope, ...]
    scope3_category: int | None = None
    pending_review: bool = False
    note: str = ""

    def __post_init__(self):
        if self.default not in self.allowed:
            raise ValueError(f"default {self.default} is not in allowed {self.allowed}")
        if self.scope3_category is not None and Scope.SCOPE_3 not in self.allowed:
            raise ValueError(f"scope3_category {self.scope3_category} set but Scope 3 is not allowed")


# Declared in ActivityTypes but not emitted by any calculator, as of a grep of math_model, api/calculators.py and
# api/services; re-check when a calculator gains a flux, because the completeness test skips these. PROCESSING is
# only read back by the value-chain report (always zero); processing entries emit FUEL and ELECTRICITY.
NEVER_EMITTED_ACTIVITIES = frozenset(
    {ActivityTypes.TRANSPORT, ActivityTypes.SOLID_CONSUMPTION, ActivityTypes.PROCESSING}
)

LAND_ACTIVITIES = (
    ActivityTypes.SOIL_CO2_CHANGE,
    ActivityTypes.SOM,
    ActivityTypes.BIOMASS,
    ActivityTypes.DOM,
    ActivityTypes.RESIDUE_BURNING,
    ActivityTypes.STRAW_BURNING,
    ActivityTypes.CH4_EMITTED_RICE,
    ActivityTypes.DRAINAGE,
    ActivityTypes.REWETTING,
    ActivityTypes.REWETTING_REVEGETATION,
    ActivityTypes.DRAINAGE_PEAT,
    ActivityTypes.FIRE_ON_SOIL,
)

FOREST_ACTIVITIES = (
    ActivityTypes.AGB_GROWTH,
    ActivityTypes.BGB_GROWTH,
    ActivityTypes.LITTER,
    ActivityTypes.DEADWOOD,
    ActivityTypes.DEGRADATION_AGB,
    ActivityTypes.DEGRADATION_BGB,
    ActivityTypes.DEGRADATION_LITTER,
    ActivityTypes.DEGRADATION_DEADWOOD,
    ActivityTypes.ROTATION_AGB,
    ActivityTypes.ROTATION_BGB,
    ActivityTypes.DISTURBANCE_AGB,
    ActivityTypes.DISTURBANCE_BGB,
    ActivityTypes.DISTURBANCE_FIRE_AGB,
    ActivityTypes.DISTURBANCE_FIRE_BGB,
    ActivityTypes.LOGGING_AGB,
    ActivityTypes.LOGGING_BGB,
)

HARVESTED_WOOD_PRODUCT_ACTIVITIES = (
    ActivityTypes.HWP_POOL,
    ActivityTypes.HWP_LOGGING_AGB,
    ActivityTypes.HWP_LOGGING_BGB,
    ActivityTypes.HWP_ROTATION_AGB,
    ActivityTypes.HWP_ROTATION_BGB,
)

LIVESTOCK_ACTIVITIES = (
    ActivityTypes.METHANE_ENTERIC_FERMENTATION,
    ActivityTypes.METHANE_MANURE_MANAGEMENT_SYSTEM,
    ActivityTypes.METHANE_MANURE_MANAGEMENT_PRP,
    ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM,
    ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP,
    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM,
    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP,
    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM,
    ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP,
)

WASTE_ACTIVITIES = (
    ActivityTypes.SOLID_WASTE_DISPOSAL,
    ActivityTypes.COMPOSTING,
    ActivityTypes.ANAEROBIC_DIGESTION,
    ActivityTypes.WASTE_INCINERATION,
    ActivityTypes.WASTE_OPEN_BURNING,
)

ONLY_SCOPE_1 = (Scope.SCOPE_1,)
SCOPE_1_OR_3 = (Scope.SCOPE_1, Scope.SCOPE_3)
SCOPE_2_OR_3 = (Scope.SCOPE_2, Scope.SCOPE_3)
ONLY_SCOPE_3 = (Scope.SCOPE_3,)

DIRECT_ON_SITE = ScopeRule(Scope.SCOPE_1, ONLY_SCOPE_1)

FOREST_RULE = ScopeRule(
    Scope.SCOPE_1,
    ONLY_SCOPE_1,
    note="GHG Protocol LSR Standard v1.1 (2026) excludes forestry; scope taken from the team doc.",
)

HARVESTED_WOOD_PRODUCT_RULE = ScopeRule(
    Scope.SCOPE_1,
    ONLY_SCOPE_1,
    pending_review=True,
    note=(
        "Team doc: wood products are Scope 1 gross removals. LSR v1.1 reports product carbon storage as a "
        "separate category, never in Scope 1, and excludes forestry."
    ),
)

FUEL_RULE = ScopeRule(
    Scope.SCOPE_1,
    SCOPE_1_OR_3,
    note="Owned or controlled combustion is Scope 1; contracted equipment or services are Scope 3.",
)

BIOGENIC_CO2_NOTE = (
    "Biogenic CO2 from biomass fuels: team doc books it as Scope 1 gross, LSR v1.1 reports it outside the inventory."
)

# Fuel types whose default CO2 factor includes biogenic CO2 (ipcc EnergyDefaultEmissionFactor: Wood 1.75,
# Charcoal 3.30). Ethanol is left out on purpose: its CO2 factor is about 1% of gasoline's, so the biogenic
# share is already excluded from the number. Peat is fossil under IPCC.
# ponytail: matched by FuelType name, add a biogenic flag on FuelType if biomass fuels are added or renamed.
BIOGENIC_CO2_FUEL_NAMES = ("wood", "charcoal")

ELECTRICITY_RULE = ScopeRule(
    Scope.SCOPE_2,
    SCOPE_2_OR_3,
    scope3_category=3,
    pending_review=True,
    note=(
        "Grid transmission and distribution losses are multiplied into this flux; the GHG Protocol books "
        "those losses as Scope 3 category 3."
    ),
)

IRRIGATION_MIXED_SERIES_NOTE = (
    "Each year interpolates between the start and end scenario, so one series can mix electric and fuel "
    "pumping while it carries the end scenario's scope."
)

IRRIGATION_ELECTRIC_CO2_RULE = replace(
    ELECTRICITY_RULE,
    note=f"Electric pumping. {ELECTRICITY_RULE.note} {IRRIGATION_MIXED_SERIES_NOTE}",
)

IRRIGATION_FUEL_CO2_RULE = replace(
    FUEL_RULE,
    pending_review=True,
    note=f"Fuel pumping. {IRRIGATION_MIXED_SERIES_NOTE}",
)

RuleTable = dict[tuple[ActivityTypes, GasTypes | None], ScopeRule]

DEFAULT_RULES: RuleTable = {
    **{(activity, None): DIRECT_ON_SITE for activity in LAND_ACTIVITIES},
    **{(activity, None): FOREST_RULE for activity in FOREST_ACTIVITIES},
    **{(activity, None): HARVESTED_WOOD_PRODUCT_RULE for activity in HARVESTED_WOOD_PRODUCT_ACTIVITIES},
    **{(activity, None): DIRECT_ON_SITE for activity in LIVESTOCK_ACTIVITIES},
    **{
        (activity, None): ScopeRule(
            Scope.SCOPE_3,
            SCOPE_1_OR_3,
            scope3_category=5,
            pending_review=True,
            note=(
                "Not in the team doc. Waste treated off site is Scope 3 category 5; on-site treatment is "
                "Scope 1. Only fossil CO2 is computed for combustion."
            ),
        )
        for activity in WASTE_ACTIVITIES
    },
    # ponytail: CO rule keyed on the only flux that emits CO, make it gas-wide if another activity starts emitting CO.
    (ActivityTypes.FIRE_ON_SOIL, GasTypes.CO): ScopeRule(
        Scope.OUTSIDE_SCOPES,
        (Scope.OUTSIDE_SCOPES,),
        note="Team doc: CO is not included in the scopes.",
    ),
    (ActivityTypes.OFFSITE_PEAT, None): ScopeRule(
        Scope.SCOPE_1,
        SCOPE_1_OR_3,
        scope3_category=10,
        pending_review=True,
        note="Depends on the peat's use (is_peat_for_energy is stored but not read by the calculation).",
    ),
    (ActivityTypes.COASTAL_WATERBODIES, None): ScopeRule(
        Scope.SCOPE_1,
        SCOPE_1_OR_3,
        pending_review=True,
        note="Team doc: inclusion depends on the function of the waterbody.",
    ),
    **{
        (activity, None): ScopeRule(
            Scope.SCOPE_1,
            SCOPE_1_OR_3,
            scope3_category=3,
            pending_review=True,
            note="LSR v1.1: hydropower reservoir emissions are Scope 3 category 3 for electricity purchasers.",
        )
        for activity in (ActivityTypes.FLOODED_LAND_CH4, ActivityTypes.FLOODED_LAND_CO2)
    },
    (ActivityTypes.CATCH, None): ScopeRule(
        Scope.SCOPE_1,
        SCOPE_1_OR_3,
        note="Owned vessels are Scope 1; leased or contracted vessels are Scope 3.",
    ),
    (ActivityTypes.REFRIGERANT, None): ScopeRule(
        Scope.SCOPE_1,
        SCOPE_1_OR_3,
        pending_review=True,
        note="Should refrigerant leakage follow vessel ownership like fuel?",
    ),
    (ActivityTypes.ICE, None): ScopeRule(
        Scope.SCOPE_1,
        (Scope.SCOPE_1, Scope.SCOPE_2, Scope.SCOPE_3),
        scope3_category=1,
        pending_review=True,
        note=(
            "Team doc: Scope 1 CO2. Stored as gas Other and labelled electricity CO2-eq, so ice made with grid "
            "power would be Scope 2 and purchased ice Scope 3 category 1."
        ),
    ),
    (ActivityTypes.CO2_FIELD, None): DIRECT_ON_SITE,
    (ActivityTypes.N20_FIELD, None): DIRECT_ON_SITE,
    (ActivityTypes.CO2_EQUIVALENT_VC, None): ScopeRule(
        Scope.SCOPE_3,
        ONLY_SCOPE_3,
        scope3_category=1,
        pending_review=True,
        note=(
            "Inferred as manufacturing of purchased inputs; confirm, and check double counting with the "
            "value-chain modules."
        ),
    ),
    (ActivityTypes.FUEL, None): FUEL_RULE,
    (ActivityTypes.ELECTRICITY, None): ELECTRICITY_RULE,
    (ActivityTypes.IRRIGATION_OPERATIONAL, None): FUEL_RULE,
    (ActivityTypes.NEW_IRRIGATION, None): ScopeRule(
        Scope.SCOPE_3,
        ONLY_SCOPE_3,
        scope3_category=2,
        note="Capital goods.",
    ),
    (ActivityTypes.ROADS, None): ScopeRule(
        Scope.SCOPE_3,
        ONLY_SCOPE_3,
        scope3_category=1,
        note="Team doc: construction is purchased goods and services.",
    ),
    (ActivityTypes.PACKAGING, None): ScopeRule(
        Scope.SCOPE_3,
        SCOPE_1_OR_3,
        scope3_category=1,
        note="Purchased packaging material; packaging made on site is Scope 1.",
    ),
    (ActivityTypes.STORAGE, None): ScopeRule(
        Scope.SCOPE_1,
        SCOPE_1_OR_3,
        scope3_category=4,
        note="Refrigerant leakage in owned storage is Scope 1; third-party warehousing is Scope 3 category 4.",
    ),
}


def _fuel_with_scope3_category(category: int, when_scope_3: str) -> RuleTable:
    """FUEL rule for a value-chain entry whose outsourced energy use has a known Scope 3 category."""
    return {
        (ActivityTypes.FUEL, None): replace(
            FUEL_RULE, scope3_category=category, note=f"{FUEL_RULE.note} {when_scope_3}"
        ),
    }


CLASS_OVERRIDES: dict[str, RuleTable] = {
    "TransportEntry": _fuel_with_scope3_category(4, "Third-party transport is Scope 3 category 4."),
    "StorageEntry": _fuel_with_scope3_category(4, "Third-party warehousing is Scope 3 category 4."),
    "ProcessingEntry": _fuel_with_scope3_category(1, "Outsourced processing is Scope 3 category 1."),
    "PackagingEntry": _fuel_with_scope3_category(1, "Outsourced packaging is Scope 3 category 1."),
}


def _coerce(enum_cls: type[Enum], raw: Enum | str) -> Enum:
    """Accept an enum member or either stored string form.

    The result cache stores activity by `.value` and gas by `.name` (see `api.reports.extractors._eq`), so both
    forms are tried for both enums.
    """
    if isinstance(raw, enum_cls):
        return raw
    try:
        return enum_cls(raw)
    except ValueError:
        return enum_cls[raw]


def _fuel_name(source: object, scenario: ScenarioTypes) -> str | None:
    return getattr(getattr(source, f"fuel_type_{scenario.value}", None), "name_en", None)


def _burns_biomass(source: object, scenario: ScenarioTypes) -> bool:
    """True when the scenario's fuel, or the start fuel its series ramps from, is a biomass fuel."""
    names = (_fuel_name(source, scenario), _fuel_name(source, ScenarioTypes.START))
    return any(name and name.casefold() in BIOGENIC_CO2_FUEL_NAMES for name in names)


def _irrigation_operational_co2(source: object, scenario: ScenarioTypes) -> ScopeRule:
    """CO2 of irrigation pumping is Scope 2 when the scenario's pump is electric, Scope 1 when it burns fuel.

    Without a fuel type for the scenario, IrrigationPhaseCalculator raises instead of computing, so a flux
    arriving here without one (for example a stale cache) has no pumping type to classify: it stays UNASSIGNED.
    """
    # ponytail: one scope per scenario series although the series ramps from the start fuel to this scenario's,
    # split the series by fuel share if mixed electric/fuel irrigation totals need to be exact.
    fuel_name = _fuel_name(source, scenario)
    if not fuel_name:
        return _unassigned(
            source,
            ActivityTypes.IRRIGATION_OPERATIONAL,
            GasTypes.CO2,
            note=f"No fuel type for scenario {scenario.value}, so the pump cannot be classified as electric or fuel.",
        )
    if fuel_name in IRRIGATION_ELECTRIC_FUEL_NAMES:
        return IRRIGATION_ELECTRIC_CO2_RULE
    return IRRIGATION_FUEL_CO2_RULE


def scope_rule_for(
    source: object, activity: ActivityTypes | str, gas: GasTypes | str, scenario: ScenarioTypes | str
) -> ScopeRule:
    """Resolve the scope rule of one flux emitted by `source` in `scenario`.

    Args:
        source: The module or submodule entry instance that emits the flux. Its class name selects overrides;
            its attributes are read where the scope depends on input (irrigation and biomass fuel types).
        activity: An `ActivityTypes` member, or its `.value` as stored in the result cache.
        gas: A `GasTypes` member, or its `.name` as stored in the result cache.
        scenario: A `ScenarioTypes` member or its value ("start", "w", "wo").

    Returns:
        The matching rule. An unknown activity or gas, or a flux with no rule, returns an UNASSIGNED rule and
        logs an error instead of raising, so a report never fails on a new flux.

    Raises:
        ValueError: `scenario` is not a scenario code (a caller bug, not data).
    """
    scenario = ScenarioTypes(scenario)
    try:
        activity = _coerce(ActivityTypes, activity)
        gas = _coerce(GasTypes, gas)
    except (KeyError, ValueError):
        return _unassigned(source, activity, gas)

    if activity is ActivityTypes.IRRIGATION_OPERATIONAL and gas is GasTypes.CO2:
        return _irrigation_operational_co2(source, scenario)

    class_rules = CLASS_OVERRIDES.get(type(source).__name__, {})
    for rules, key in (
        (class_rules, (activity, gas)),
        (class_rules, (activity, None)),
        (DEFAULT_RULES, (activity, gas)),
        (DEFAULT_RULES, (activity, None)),
    ):
        if key in rules:
            rule = rules[key]
            break
    else:
        return _unassigned(source, activity, gas)

    if activity is ActivityTypes.FUEL and gas is GasTypes.CO2 and _burns_biomass(source, scenario):
        return replace(rule, pending_review=True, note=f"{rule.note} {BIOGENIC_CO2_NOTE}")
    return rule


def _unassigned(source: object, activity: object, gas: object, note: str = "") -> ScopeRule:
    key = (type(source).__name__, repr(activity), repr(gas))
    if key not in _logged_unassigned:
        _logged_unassigned.add(key)
        log.error("No GHG scope rule for activity %r, gas %r on %s", activity, gas, key[0])
    return ScopeRule(Scope.UNASSIGNED, (Scope.UNASSIGNED,), note=note or f"No scope rule for {activity} / {gas}.")
