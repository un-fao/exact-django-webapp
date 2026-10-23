"""Energy module results broken down by the value-chain stage of each entry."""

from api.calculators import EnergyEntryCalculator, Result
from api.models import Energy
from math_model.no_time_dependency_final.ghg_emissions_classes import BreakdownTypes

VALUE_CHAIN_STAGE_AGGREGATE = "value_chain_stage"


def results_by_value_chain_stage(energy: Energy) -> dict:
    """Total tCO2-eq (with, without, balance) per value-chain stage, plus the module totals.

    Entries without a stage are grouped under ``id: None``. Stages follow their
    reference order, the unspecified group comes last.
    """
    groups: dict = {}
    for entry in energy.entries.select_related("value_chain_stage").order_by("id"):
        result = Result(*EnergyEntryCalculator(entry).calculate())
        stage = entry.value_chain_stage
        groups[stage] = groups[stage] + result if stage in groups else result

    rows = []
    for stage in sorted(groups, key=lambda s: (s is None, s.pk if s else 0)):
        total_w, total_wo, balance = groups[stage].breakdown(by=BreakdownTypes.TOTAL)
        rows.append({
            "id": stage.pk if stage else None,
            "name": stage.name if stage else None,
            "total_w": total_w,
            "total_wo": total_wo,
            "balance": balance,
        })

    return {
        "total_w": sum(r["total_w"] for r in rows),
        "total_wo": sum(r["total_wo"] for r in rows),
        "balance": sum(r["balance"] for r in rows),
        "value_chain_stages": rows,
    }
