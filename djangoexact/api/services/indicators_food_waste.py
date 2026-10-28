"""Food-waste indicator group: food waste generated, landfilled, composted and digested, with and without the project.

Reads the ``solid_waste`` results block of every Solid Waste module of the project; the math is in
math_model/indicators_food_waste.py. Headline values are the annual flow in the last year of the accounting period,
when every activity is fully implemented; the yearly series go in ``series``
(once per underlying flow, so the Excel sheet does not repeat the generated-waste series three times).
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

import api.models as api_models
import math_model.indicators_food_waste as mi
from api.services.indicators import IndicatorContext, indicator, register_group

UNIT = "t/yr"


def _food_waste_block(report) -> dict:
    extra = getattr(report.calculator, "results_extra", None)
    if not extra:
        cached = report.module.get_cached_results()
        if cached is not None:
            extra = cached
        else:
            # Report runs that read emissions from the cache never run the calculator.
            report.calculator.calculate()
            extra = report.calculator.results_extra
    return extra["solid_waste"]["food_waste_by_route"]


def food_waste_blocks(ctx: IndicatorContext) -> list[dict]:
    return [
        _food_waste_block(report)
        for ar in ctx.activity_results
        for report in ar._module_reports
        if isinstance(report.module, api_models.SolidWaste)
    ]


@register_group("food_waste", _("Food waste"), order=60)
def food_waste(ctx: IndicatorContext) -> dict | None:
    blocks = food_waste_blocks(ctx)
    if not blocks:
        return None
    by_route = mi.sum_by_route(blocks, ctx.duration)
    s = mi.food_waste_series(by_route)
    years = list(range(ctx.start_year, ctx.start_year + ctx.duration))

    def series(with_key, without_key):
        return {"years": years, "with": s[with_key], "without": s[without_key]}

    def last(key):
        return s[key][-1] if s[key] else 0.0

    return {
        "indicators": [
            indicator(
                "food_waste_reference", _("Total food waste generated, reference"), UNIT,
                without=last("generated_wo"), series=series("generated_w", "generated_wo"),
            ),
            indicator(
                "food_waste_target", _("Total food waste generated, target"), UNIT,
                with_=last("generated_w"),
            ),
            indicator(
                "food_waste_reduction", _("Reduction of food waste"), UNIT,
                value=last("reduction"),
            ),
            indicator(
                "food_waste_landfill_reduction", _("Reduction of food waste to landfill"), UNIT,
                value=last("landfill_reduction"), series=series("landfill_w", "landfill_wo"),
            ),
            indicator(
                "food_waste_composting", _("Food waste valorised by composting"), UNIT,
                with_=last("composting_w"), without=last("composting_wo"),
                series=series("composting_w", "composting_wo"),
            ),
            indicator(
                "food_waste_anaerobic_digestion", _("Food waste valorised by anaerobic digestion"), UNIT,
                with_=last("anaerobic_digestion_w"), without=last("anaerobic_digestion_wo"),
                series=series("anaerobic_digestion_w", "anaerobic_digestion_wo"),
            ),
        ],
        "data": {
            "unit": UNIT,
            "routes": list(by_route["w"]),
            "with": {route: values[-1] if values else 0.0 for route, values in by_route["w"].items()},
            "without": {route: values[-1] if values else 0.0 for route, values in by_route["wo"].items()},
        },
    }
