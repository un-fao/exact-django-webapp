"""Energy module results broken down by the value-chain stage of each entry."""

from api.calculators import EnergyEntryCalculator, Result
from api.models import Energy, EnergyEntry
from api.services.finalization import frozen_result
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

VALUE_CHAIN_STAGE_AGGREGATE = "value_chain_stage"
# Same order as Result.breakdown(TOTAL), because the live branch below returns that tuple positionally.
TOTAL_BREAKDOWN_KEYS = ("total_w", "total_wo", "balance")


def _entry_totals(entry: EnergyEntry) -> tuple[float, ...]:
    """(total_w, total_wo, balance) of one entry: frozen for a finalized project, calculated otherwise.

    Raises FrozenResultMissingError when the project is finalized but the entry has no snapshot.
    """
    frozen = frozen_result(entry)
    if frozen is not None:
        totals = frozen.results(BreakdownTypes.TOTAL)
        return tuple(totals[key] for key in TOTAL_BREAKDOWN_KEYS)
    return Result(*EnergyEntryCalculator(entry).calculate()).breakdown(by=BreakdownTypes.TOTAL)


def results_by_value_chain_stage(energy: Energy) -> dict:
    """Total tCO2-eq (with, without, balance) per value-chain stage, plus the module totals.

    Entries without a stage are grouped under ``id: None``. Stages follow their
    reference order, the unspecified group comes last.
    """
    groups: dict = {}
    for entry in energy.entries.select_related("value_chain_stage").order_by("id"):
        stage = entry.value_chain_stage
        stage_totals = groups.get(stage, (0.0, 0.0, 0.0))
        groups[stage] = tuple(a + b for a, b in zip(stage_totals, _entry_totals(entry)))

    rows = [
        {
            "id": stage.pk if stage else None,
            "name": stage.name if stage else None,
            **dict(zip(TOTAL_BREAKDOWN_KEYS, groups[stage])),
        }
        for stage in sorted(groups, key=lambda s: (s is None, s.pk if s else 0))
    ]

    return {
        **{key: sum(r[key] for r in rows) for key in TOTAL_BREAKDOWN_KEYS},
        "value_chain_stages": rows,
    }
