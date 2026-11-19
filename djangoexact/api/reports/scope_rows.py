"""GHG Protocol scope rows of a computed project: one gross flux of one source in one scenario per row.

Scopes apply to gross fluxes per scenario, never to the balance. Each (source, flux, gas) series of the with and the
without scenario is split year by year into emissions (positive values) and removals (negative values), summed over
the Results sheet's year window.

Rows reconcile with each module by construction: per flux and scenario, the entry rows plus a module-level row (the
module set minus the entry sets) equal the module's emission set, which is what the Results sheets add up.

No spreadsheet code lives here, so the rows can serve other outputs than the Excel report.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Sequence

import api.calculators as calculators
from api.inventory_labels import inventory_label
from api.scopes import ScopeRule, scope_rule_for
from api.utilities import ScenarioTypes
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from math_model.no_time_dependency_final.ghg_emissions_classes import GasTypes

from .base import NotReadyError
from .data_types import ProjectResult
from .extractors import _add, iter_fluxes

log = logging.getLogger("console")

REPORTED_SCENARIOS = (ScenarioTypes.WITH, ScenarioTypes.WITHOUT)
MODULE_LEVEL_ENTRY = "(module level)"

# A module-level residual this close to zero is float noise from summing the entries, not a flux of its own.
RESIDUAL_ABS_TOLERANCE_TCO2E = 1e-6

# Entries get their own rows only in these modules (class names, never the translated module_type.name).
# Land modules' submodules (minor seasons, forest disturbances) stay inside the module-level row, and are never
# queried.
MODULES_WITH_ENTRIES = frozenset(
    {"Energy", "Input", "Irrigation", "Settlement", "Transport", "Processing", "Storage", "Packaging"}
)
# The calculator each module report uses for an entry. Entries missing here (OtherInfrastructure is not part of
# the Settlement total today) get no row of their own.
ENTRY_CALCULATORS = {
    "EnergyEntry": calculators.EnergyEntryCalculator,
    "InputEntry": calculators.InputEntryCalculator,
    "IrrigationPhase": calculators.IrrigationPhaseCalculator,
    "IrrigationSystem": calculators.IrrigationSystemCalculator,
    "Building": calculators.BuildingCalculator,
    "Road": calculators.RoadCalculator,
    "TransportEntry": calculators.TransportEntryCalculator,
    "ProcessingEntry": calculators.ProcessingEntryCalculator,
    "StorageEntry": calculators.StorageEntryCalculator,
    "PackagingEntry": calculators.PackagingEntryCalculator,
}
# Entry fields that describe an entry to a reader, first one set wins.
# ponytail: a hand-picked field list, entries of other types read "<type> <position>"; add a descriptor property
# on the submodule models if more entry types need a readable name.
ENTRY_DESCRIPTOR_FIELDS = ("name", "fuel_type_w", "input_type", "irrigation_system_type", "building_type", "road_type")
# What entry calculators raise for data they cannot calculate. They also raise bare Exception for a missing or
# not-ready module (BaseCalculator), so that exact type counts too; its subclasses (AttributeError, DatabaseError,
# ...) are bugs or outages and propagate.
ENTRY_DATA_ERRORS = (NotReadyError, ValueError, ObjectDoesNotExist, ValidationError)

FluxKey = tuple[str, str]
"""(ActivityTypes value, GasTypes name) of a flux: the string forms the result cache stores, so live and cached
emission sets group under the same key."""


@dataclass(frozen=True)
class EntrySets:
    """With and without emission sets of one submodule entry."""

    entry: object
    label: str
    sets_w: Any
    sets_wo: Any


@dataclass(frozen=True)
class ModuleSets:
    """With and without emission sets of one module and of its entries.

    `index` is unique in the project: spreadsheet formulas key on it, never on the module title.
    """

    index: int
    title: str
    module: object
    sets_w: Any
    sets_wo: Any
    entries: tuple[EntrySets, ...] = ()


@dataclass(frozen=True)
class ActivitySets:
    """The modules of one activity. `index` keys spreadsheet formulas, never the activity name."""

    index: int
    title: str
    modules: tuple[ModuleSets, ...] = ()


@dataclass(frozen=True)
class ScopeRow:
    """A gross flux of one source in one scenario, summed over the year window."""

    activity_index: int
    activity_title: str
    module_index: int
    module_title: str
    entry_label: str
    flux_label: str
    gas_label: str
    scenario: ScenarioTypes
    rule: ScopeRule
    emissions: float
    removals: float

    @property
    def is_user_selectable(self) -> bool:
        return len(self.rule.allowed) > 1


def _flux_key(activity: Any, gas: Any) -> FluxKey:
    return getattr(activity, "value", activity), getattr(gas, "name", gas)


def yearly_series_by_flux(sets: Any, year_count: int) -> dict[FluxKey, list[float]]:
    """Sum an emission set per (activity, gas), cut or zero-padded to `year_count` years."""
    series: dict[FluxKey, list[float]] = {}
    for activity, gas, values in iter_fluxes(sets or []):
        key = _flux_key(activity, gas)
        series[key] = _add(series.get(key, []), values)
    return {key: (values + [0.0] * year_count)[:year_count] for key, values in series.items()}


def split_gross(series: Sequence[float]) -> tuple[float, float]:
    """(emissions, removals): the sums of the positive and of the negative yearly values."""
    return sum(v for v in series if v > 0), sum(v for v in series if v < 0)


def module_level_series(
    module_series: dict[FluxKey, list[float]],
    entry_series: Sequence[dict[FluxKey, list[float]]],
    year_count: int,
    module_index: int,
) -> dict[FluxKey, list[float]]:
    """The module set minus the sum of its entry sets, per flux, with yearly float noise snapped to zero.

    All series are `year_count` long (see `yearly_series_by_flux`). A flux the entries also carry should leave no
    residual, so one that does is logged: the entry calculators drifted from the module calculator.
    """
    entry_keys = dict.fromkeys(key for series in entry_series for key in series)
    residuals = {}
    for key in dict.fromkeys([*module_series, *entry_keys]):
        zeros = [0.0] * year_count
        entries_total = [sum(year) for year in zip(zeros, *(series.get(key, zeros) for series in entry_series))]
        residual = [
            0.0 if math.isclose(module_value, entries_value, abs_tol=RESIDUAL_ABS_TOLERANCE_TCO2E)
            else module_value - entries_value
            for module_value, entries_value in zip(module_series.get(key, zeros), entries_total)
        ]
        if key in entry_keys and any(residual):
            log.warning(
                "Scope sheets: module %s, activity %r, gas %r differs from the sum of its entries "
                "(residual sum %s, max abs %s tCO2e)",
                module_index, key[0], key[1], sum(residual), max(map(abs, residual)),
            )
        residuals[key] = residual
    return residuals


def _gas_label(gas_code: str) -> str:
    return GasTypes[gas_code].value if gas_code in GasTypes.__members__ else str(gas_code)


def _source_rows(
    activity: ActivitySets,
    module: ModuleSets,
    source: object,
    entry_label: str,
    series_by_scenario: dict[ScenarioTypes, dict[FluxKey, list[float]]],
) -> list[ScopeRow]:
    """Rows of one source, With and Without of the same flux side by side; all-zero fluxes are skipped."""
    rows = []
    flux_keys = dict.fromkeys(key for series in series_by_scenario.values() for key in series)
    for activity_code, gas_code in flux_keys:
        for scenario in REPORTED_SCENARIOS:
            series = series_by_scenario[scenario].get((activity_code, gas_code))
            if series is None:
                continue
            emissions, removals = split_gross(series)
            if emissions == 0 and removals == 0:
                continue
            rows.append(ScopeRow(
                activity_index=activity.index,
                activity_title=activity.title,
                module_index=module.index,
                module_title=module.title,
                entry_label=entry_label,
                flux_label=inventory_label(module.module, activity_code),
                gas_label=_gas_label(gas_code),
                scenario=scenario,
                rule=scope_rule_for(source, activity_code, gas_code, scenario),
                emissions=emissions,
                removals=removals,
            ))
    return rows


def _series_by_scenario(holder: EntrySets | ModuleSets, year_count: int) -> dict[ScenarioTypes, dict]:
    """The yearly series by flux of a module's or an entry's with and without sets."""
    return {
        ScenarioTypes.WITH: yearly_series_by_flux(holder.sets_w, year_count),
        ScenarioTypes.WITHOUT: yearly_series_by_flux(holder.sets_wo, year_count),
    }


def build_scope_rows(activities: Sequence[ActivitySets], year_count: int) -> list[ScopeRow]:
    """Every scope row: entry rows, then the module-level row, of each module in report order."""
    rows: list[ScopeRow] = []
    for activity in activities:
        for module in activity.modules:
            entry_series = [_series_by_scenario(entry, year_count) for entry in module.entries]
            for entry, series in zip(module.entries, entry_series):
                rows += _source_rows(activity, module, entry.entry, entry.label, series)
            module_series = _series_by_scenario(module, year_count)
            residual = {
                scenario: module_level_series(
                    module_series[scenario], [series[scenario] for series in entry_series], year_count, module.index
                )
                for scenario in REPORTED_SCENARIOS
            }
            rows += _source_rows(activity, module, module.module, MODULE_LEVEL_ENTRY, residual)
    return rows


def _entry_label(entry: object, position: int) -> str:
    module_type = getattr(entry, "module_type", None)
    label = f"{getattr(module_type, 'name', None) or type(entry).__name__} {position}"
    for field in ENTRY_DESCRIPTOR_FIELDS:
        value = getattr(entry, field, None)
        descriptor = value if isinstance(value, str) else getattr(value, "name", None)
        if descriptor:
            return f"{label}: {descriptor}"
    return label


def _is_entry_data_error(error: Exception) -> bool:
    # Deferred like in BaseModuleReport: api.services.finalization imports the reports package.
    from api.services.finalization import FrozenResultMissingError

    return isinstance(error, (FrozenResultMissingError, *ENTRY_DATA_ERRORS)) or type(error) is Exception


def _entry_sets(report: Any) -> tuple[EntrySets, ...]:
    """The with/without sets of a module report's entries, or none when any entry cannot provide them.

    All or nothing, so the module-level row then carries the whole module instead of a partial split.
    """
    module = report.module
    if type(module).__name__ not in MODULES_WITH_ENTRIES:
        return ()
    # ponytail: Storage and Packaging reports never calculate their entries, so this calculates each entry once
    # more; have those reports split their rows per entry too if report time matters.
    entries = []
    for position, entry in enumerate(module.submodules, start=1):
        calculator_class = ENTRY_CALCULATORS.get(type(entry).__name__)
        if calculator_class is None:
            continue
        try:
            sets = report.submodule_scenario_sets(entry, calculator_class)
        except Exception as error:
            # A finalized project without the entry's snapshot, or an entry the module calculator could
            # aggregate but its own calculator cannot (Storage and Packaging do not calculate entries otherwise).
            # ponytail: one failing entry drops the split of the whole module; skip only that entry (and keep its
            # fluxes out of the drift warning) if partial snapshots become common.
            if not _is_entry_data_error(error):
                raise
            log.warning(
                "Scope sheets: no emission sets for %s %s, module %s %s is reported at module level only: %s",
                type(entry).__name__, entry.pk, type(module).__name__, module.pk, error,
            )
            return ()
        entries.append(EntrySets(entry, _entry_label(entry, position), sets["total_w"], sets["total_wo"]))
    return tuple(entries)


def collect_activity_sets(result: ProjectResult) -> list[ActivitySets]:
    """The with/without emission sets of every module and entry of a computed project, in report order."""
    activities = []
    module_index = 0
    for activity_index, activity_result in enumerate(result.activity_results, start=1):
        modules = []
        for module_result, report in zip(activity_result.module_results, activity_result._module_reports):
            module_index += 1
            modules.append(ModuleSets(
                index=module_index,
                title=module_result.title,
                module=report.module,
                sets_w=report.emissions_set_w,
                sets_wo=report.emissions_set_wo,
                entries=_entry_sets(report),
            ))
        activities.append(ActivitySets(activity_index, activity_result.title, tuple(modules)))
    return activities
