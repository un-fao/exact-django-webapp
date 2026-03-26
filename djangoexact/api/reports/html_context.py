"""build_template_context – assembles the PDF template context from a ProjectResult.

Extracted from views.py template() method. Chart generation and FAO logo loading
are presentation concerns that live here. All data aggregation uses ProjectResult
instead of API calls.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime
from itertools import zip_longest

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ipcc.models as ipcc_models
from django.conf import settings
from django.utils.translation import activate
from django.utils.translation import gettext as _

import api.models as api_models

import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils

from .data_types import ProjectResult
from .extractors import extract_emissions


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gas_totals(result: ProjectResult, es_attr: str) -> dict[str, float]:
    """Sum total emissions per gas across all modules for one scenario.

    ``es_attr`` is one of ``emissions_set``, ``emissions_set_w``,
    ``emissions_set_wo`` – attributes on BaseModuleReport instances stored in
    ActivityResult._module_reports.
    """
    dur = result.duration
    gas_map = {
        "CO2": math_utils.GasTypes.CO2,
        "CH4": math_utils.GasTypes.CH4,
        "N2O": math_utils.GasTypes.N2O,
        "CO": math_utils.GasTypes.CO,
        "DOC": math_utils.GasTypes.DOC,
        "OTHER": math_utils.GasTypes.OTHER,
    }
    totals = {g: 0.0 for g in gas_map}
    for ar in result.activity_results:
        for report in ar._module_reports:
            es = getattr(report, es_attr, [])
            for gas_name, gas_type in gas_map.items():
                totals[gas_name] += sum(
                    extract_emissions(es, gas_type=gas_type, duration=dur)
                )
    return totals


def _chart_gases_w_wo(data_w: dict, data_wo: dict) -> str:
    """Stacked bar chart (with / without / balance) by gas type. Returns base64 SVG."""
    gas_names = ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    labels = ["With", "Without", "Balance"]

    data_arrays = np.array([
        [data_w[g], data_wo[g], data_w[g] - data_wo[g]]
        for g in gas_names
    ])

    x = np.arange(len(labels))
    width = 0.6
    fig, ax = plt.subplots(figsize=(6.5, 4))
    bottom = np.zeros(len(labels))

    for idx, row in enumerate(data_arrays):
        ax.bar(x, row, width, bottom=bottom, color=colors[idx], label=gas_names[idx])
        bottom += row

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.ticklabel_format(style="plain", axis="y", useOffset=False)
    ax.set_ylabel("Emissions (tonnes)")
    ax.set_title("")
    ax.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format="svg")
    buf.seek(0)
    chart_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close(fig)
    plt.clf()
    buf.close()
    return chart_b64


def _chart_project_balance(total_w: float, total_wo: float, total_balance: float) -> str:
    """Horizontal bar chart: with / without / balance. Returns base64 SVG."""
    fig, ax = plt.subplots(figsize=(6.5, 4))
    labels = ["With", "Without", "Balance"]
    emissions = [total_w, total_wo, total_balance]
    ax.barh(labels, emissions, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
    for i, v in enumerate(emissions):
        ax.text(0 if v > 0 else v, i, f"{v:,.2f}", va="center")
    ax.text(0.5, 1.1, "tCO2e", ha="center", va="bottom", transform=ax.transAxes)
    ax.ticklabel_format(style="plain", axis="x", useOffset=False)
    ax.grid(True, axis="x", linestyle="--", alpha=0.7)

    buf = io.BytesIO()
    plt.savefig(buf, format="svg")
    buf.seek(0)
    chart_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close(fig)
    plt.clf()
    buf.close()
    return chart_b64


def _compute_gas_totals(result: ProjectResult, total_balance: float) -> dict:
    """Compute per-gas totals for all three scenarios and derive GHG ranking.

    Returns a dict with keys:
      gas_totals_w, gas_totals_wo,
      primary/secondary/tertiary ghg name + emissions values.
    """
    gas_totals_w = _gas_totals(result, "emissions_set_w")
    gas_totals_wo = _gas_totals(result, "emissions_set_wo")
    gas_totals_bal = _gas_totals(result, "emissions_set")

    gas_names = ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]
    gases_bal = [{"name": g, "value": gas_totals_bal[g]} for g in gas_names]

    sorted_gases = sorted(
        gases_bal,
        key=lambda x: abs(x["value"]) if x["value"] != 0 else 0,
        reverse=True,
    )

    return {
        "gas_totals_w": gas_totals_w,
        "gas_totals_wo": gas_totals_wo,
        "primary_ghg": sorted_gases[0]["name"],
        "primary_ghg_emissions": sorted_gases[0]["value"],
        "secondary_ghg": sorted_gases[1]["name"],
        "secondary_ghg_emissions": sorted_gases[1]["value"],
        "tertiary_ghg": sorted_gases[2]["name"],
        "tertiary_ghg_emissions": sorted_gases[2]["value"],
    }


def _compute_activity_contexts(
    result: ProjectResult,
    activities_qs: dict,
    total_balance: float,
) -> list:
    """Build the processed activity list used by the template.

    Mutates each ``db_activity`` with ``.modules_emissions``, ``.results``,
    ``.main_impact``, and ``.secondary_impacts`` dynamic attributes, then
    returns the sorted list.
    """
    processed_activities = []

    for ar in result.activity_results:
        db_activity = activities_qs.get(ar.title)
        if db_activity is None:
            continue

        # Per-module balance totals
        modules_with_balance = [
            {"name": mr.title, "balance": sum(mr.total_emissions)}
            for mr in ar.module_results
            if mr.total_emissions
        ]
        modules_by_highest = sorted(
            modules_with_balance,
            key=lambda x: x["balance"],
            reverse=total_balance > 0,
        )
        db_activity.modules_emissions = modules_by_highest
        db_activity.results = {
            "total_w": None,
            "total_wo": None,
            "balance": sum(ar.total_emissions),
        }

        # Main and secondary impacts (locale-aware labels)
        main_impact = None
        secondary_impacts = []
        if db_activity.is_luc:
            main_impact = _("hectares")
        elif db_activity.is_fishery:
            main_impact = _("tonnes of catch")
        elif db_activity.is_livestock:
            main_impact = _("livestock heads")

        if any([
            db_activity.is_energy, db_activity.is_storage,
            db_activity.is_transport, db_activity.is_processing,
        ]):
            secondary_impacts.append(_("energy consumption"))
        if db_activity.is_packaging:
            secondary_impacts.append(_("packaging material"))
        if db_activity.is_input:
            secondary_impacts.append(_("agricultural inputs use"))

        db_activity.main_impact = main_impact
        db_activity.secondary_impacts = ", ".join(secondary_impacts) if secondary_impacts else None
        processed_activities.append(db_activity)

    return sorted(
        processed_activities,
        key=lambda x: x.results["balance"],
        reverse=total_balance > 0,
    )


def _compute_indicator_aggregates(activities_qs: dict, project) -> dict:
    """Aggregate livestock, fishery, aquaculture, land-type and area indicators.

    Returns a dict with keys:
      total_area, total_heads, total_tonnes_of_catch,
      livestock_heads, small_fishery_types, large_fishery_data,
      aquaculture_data, land_types, soc.
    """
    total_area = sum(a.area for a in activities_qs.values())

    livestock_heads = [
        {"name": lct.name, "value_w": 0, "value_wo": 0}
        for lct in api_models.LivestockCategoryType.objects.all()
    ]
    small_fishery_types = [
        {"name": ft.name, "value_w": 0, "value_wo": 0}
        for ft in api_models.FisheryType.objects.all()
    ]
    large_fishery_data = {"name": "Large Fisheries", "value_w": 0, "value_wo": 0}
    aquaculture_data = {"name": "Aquaculture", "value_w": 0, "value_wo": 0}
    land_types = [
        {"name": lt.name, "value_w": 0, "value_wo": 0}
        for lt in api_models.ModuleType.objects.filter(is_luc=True).all()
    ]

    for db_activity in activities_qs.values():
        for m in db_activity.modules:
            if isinstance(m, api_models.SmallFishery):
                for ft in small_fishery_types:
                    if ft["name"] == m.fishery_type.name:
                        ft["value_w"] += m.total_catch_yr_w
                        ft["value_wo"] += m.total_catch_yr_wo
            elif isinstance(m, api_models.LargeFishery):
                large_fishery_data["value_w"] += m.total_catch_yr_w
                large_fishery_data["value_wo"] += m.total_catch_yr_wo
            elif isinstance(m, api_models.Livestock):
                for lh in livestock_heads:
                    if lh["name"] == m.livestock_category_type.name:
                        lh["value_w"] += m.heads_number_w
                        lh["value_wo"] += m.heads_number_wo
            elif isinstance(m, api_models.Aquaculture):
                aquaculture_data["value_w"] += m.annual_production_w
                aquaculture_data["value_wo"] += m.annual_production_wo
            elif isinstance(m, api_models.LandModule):
                for lt in land_types:
                    if lt["name"] == m.module_type.name:
                        if m.is_with() and not m.is_without():
                            lt["value_w"] += m.area
                        elif m.is_without() and not m.is_with():
                            lt["value_wo"] += m.area
                        elif m.is_with() and m.is_without():
                            lt["value_w"] += m.area
                            lt["value_wo"] += m.area

    livestock_heads = [x for x in livestock_heads if x["value_w"] != 0 or x["value_wo"] != 0]
    small_fishery_types = [x for x in small_fishery_types if x["value_w"] != 0 or x["value_wo"] != 0]
    large_fishery_data = (
        {} if large_fishery_data["value_w"] == 0 or large_fishery_data["value_wo"] == 0
        else large_fishery_data
    )
    aquaculture_data = (
        {} if aquaculture_data["value_w"] == 0 or aquaculture_data["value_wo"] == 0
        else aquaculture_data
    )
    land_types = [x for x in land_types if x["value_w"] != 0 or x["value_wo"] != 0]

    total_heads = sum(lh["value_w"] for lh in livestock_heads)
    total_tonnes_of_catch = (
        sum(ft["value_w"] for ft in small_fishery_types)
        + large_fishery_data.get("value_w", 0)
    )

    soc = ipcc_models.SoilOrganicCarbon.objects.get(
        climate=project.climate,
        moisture=project.moisture,
        soil_type=project.soil_type,
    )

    return {
        "total_area": total_area,
        "total_heads": total_heads,
        "total_tonnes_of_catch": total_tonnes_of_catch,
        "livestock_heads": livestock_heads,
        "small_fishery_types": small_fishery_types,
        "large_fishery_data": large_fishery_data,
        "aquaculture_data": aquaculture_data,
        "land_types": land_types,
        "soc": soc,
    }


def _build_chart_data(
    total_w: float,
    total_wo: float,
    total_balance: float,
    gas_totals_w: dict,
    gas_totals_wo: dict,
) -> tuple[str, str]:
    """Generate both charts and return (project_chart_base64, gases_chart_base64)."""
    project_chart_base64 = _chart_project_balance(total_w, total_wo, total_balance)
    project_gases_chart_base64 = _chart_gases_w_wo(gas_totals_w, gas_totals_wo)
    return project_chart_base64, project_gases_chart_base64


def _load_fao_logo(lang: str) -> str:
    """Load the FAO logo SVG for the given language and return it as base64."""
    try:
        faologo = open(os.path.join(settings.BASE_DIR, "media", f"faologo_{lang}.svg"), "rb")
    except FileNotFoundError:
        faologo = open(os.path.join(settings.BASE_DIR, "media", "faologo.svg"), "rb")
    faologo_base64 = base64.b64encode(faologo.read()).decode("utf-8")
    faologo.close()
    return faologo_base64


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_template_context(result: ProjectResult, request, lang: str) -> dict:
    """Return the full context dict for the PDF HTML template."""
    activate(lang)
    project = result.project

    # Project-level totals (from aggregated yearly balances)
    total_w = float(sum(result.aggregated.yearly_balance_w))
    total_wo = float(sum(result.aggregated.yearly_balance_wo))
    total_balance = total_w - total_wo

    # Gas-level totals and GHG ranking
    gas_data = _compute_gas_totals(result, total_balance)

    # Direction helper uses locale-aware strings (activated above)
    INCREASES = _("increases")
    DECREASES = _("decreases")

    def _direction(v):
        return INCREASES if v >= 0 else DECREASES

    # Per-activity processed data (prefetched queryset reused below)
    activities_qs = {
        a.name: a
        for a in project.activities.prefetch_related("modules").all()
    }
    processed_activities = _compute_activity_contexts(result, activities_qs, total_balance)

    # Indicator aggregates (reuses prefetched activities_qs)
    indicators = _compute_indicator_aggregates(activities_qs, project)

    # Charts
    project_chart_base64, project_gases_chart_base64 = _build_chart_data(
        total_w,
        total_wo,
        total_balance,
        gas_data["gas_totals_w"],
        gas_data["gas_totals_wo"],
    )

    # FAO logo
    faologo_base64 = _load_fao_logo(lang)

    return {
        "project": project,
        "start_year_of_activities": project.start_year_of_activities,
        "implementation_years": project.implementation_years,
        "last_year_of_accounting": project.last_year_of_accounting,
        "total_project_years": project.implementation_years + project.capitalization_years,
        "total_carbon_balance": total_balance,
        "project_emissions_w": total_w,
        "project_emissions_wo": total_wo,
        "total_area": indicators["total_area"],
        "total_heads": indicators["total_heads"],
        "total_tonnes_of_catch": indicators["total_tonnes_of_catch"],
        "soc": indicators["soc"].value,
        "project_primary_ghg": gas_data["primary_ghg"],
        "project_primary_ghg_emissions": gas_data["primary_ghg_emissions"],
        "project_primary_ghg_direction": _direction(gas_data["primary_ghg_emissions"]),
        "project_secondary_ghg": gas_data["secondary_ghg"],
        "project_secondary_ghg_emissions": gas_data["secondary_ghg_emissions"],
        "project_secondary_ghg_direction": _direction(gas_data["secondary_ghg_emissions"]),
        "project_tertiary_ghg": gas_data["tertiary_ghg"],
        "project_tertiary_ghg_emissions": gas_data["tertiary_ghg_emissions"],
        "project_tertiary_ghg_direction": _direction(gas_data["tertiary_ghg_emissions"]),
        "activities_total": processed_activities,
        "project_chart_base64": project_chart_base64,
        "project_gases_chart_base64": project_gases_chart_base64,
        "faologo_base64": faologo_base64,
        "livestock_heads": indicators["livestock_heads"],
        "small_fishery_types": indicators["small_fishery_types"],
        "large_fishery_data": indicators["large_fishery_data"],
        "aquaculture_data": indicators["aquaculture_data"],
        "land_types": indicators["land_types"],
        "download_date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
