"""Forest management results under the stock-difference approach (IPCC 2006 Vol. 4, ch. 2, eq. 2.5).

Called by ForestManagementCalculator when ``ForestManagement.approach == "stock_difference"``.
The math lives in math_model/no_time_dependency_final/forest_stock_difference.py.
"""

import ipcc.models as ipcc
from api.models import DataSource
from api.utilities import NON_MANGROVE_FACTOR
from math_model.no_time_dependency_final.forest_stock_difference import ForestStockDifference

STOCK_DIFFERENCE_LUC_ERROR = (
    "The stock-difference approach is only available for forest remaining forest. "
    "Use the gain-loss approach for afforestation or other land-use changes."
)


def supports_stock_difference(module) -> bool:
    return module.is_luc_remaining_same() and module.is_business_as_usual()


def calculate_stock_difference(calculator):
    """Fill the calculator's math_* / results_* like the gain-loss path and return (start + w, start + wo)."""
    forest = calculator.forest
    if not supports_stock_difference(calculator.module):
        raise ValueError(STOCK_DIFFERENCE_LUC_ERROR)

    def build(end_scenario: str) -> ForestStockDifference:
        module = ForestStockDifference(
            implementation_time=calculator.activity.implementation_years,
            capitalization_time=calculator.activity.capitalization_years,
            rate_type=calculator.change_rate.name,
            delay=calculator.activity.delay,
            hectares=calculator.area,
            stocks_start=forest.stock_difference_stocks("start"),
            stocks_end=forest.stock_difference_stocks(end_scenario),
        )
        module.calculate_emissions()
        return module

    # The start module carries the inventory (start stocks) and no flux, so start + w is the with-project change.
    calculator.math_start = build("start")
    calculator.math_w = build("w")
    calculator.math_wo = build("wo")
    calculator.results_start = calculator.math_start.result
    calculator.results_w = calculator.math_w.result
    calculator.results_wo = calculator.math_wo.result

    return (calculator.results_start + calculator.results_w, calculator.results_start + calculator.results_wo)


def _ipcc_stocks(forest) -> dict[str, float | None]:
    """Pool -> IPCC reference stock (tC/ha) for forest remaining forest; None where the table has no row.

    AGB: ForestManagementAGB (IPCC 2019 Vol. 4 ch. 4 Table 4.7), same row and mean as the gain-loss agb_max, x 0.47 tC/t d.m.
    BGB: AGB x root-to-shoot (Table 4.4), whose classes are bounded by the AGB stock in t d.m./ha.
    Litter/deadwood: LitterDeadwoodCarbonStock (IPCC 2019 Vol. 4 ch. 2 Table 2.2).
    """
    activity = forest.activity
    project = activity.project
    climate = activity.climate_t2 or project.climate
    region = project.country.region
    land_use_type = forest.land_use_type_start
    stocks = dict.fromkeys(forest.STOCK_DIFFERENCE_POOLS)

    if land_use_type is None or forest.forest_type is None or forest.forest_condition_type is None:
        return stocks

    litter_dw = ipcc.LitterDeadwoodCarbonStock.objects.filter(climate=climate, forest_type=forest.forest_type, land_use_type=land_use_type).first()
    if litter_dw:
        stocks["litter"], stocks["deadwood"] = litter_dw.litter, litter_dw.dw

    from_year = 21 if "Secondary" in forest.forest_condition_type.name else 0
    agb_ref = forest.get_agb_growth_ref(land_use_type=land_use_type, from_year=from_year)
    if agb_ref is None or agb_ref.agb_min is None or agb_ref.agb_max is None:
        return stocks
    agb_dm = (agb_ref.agb_min + agb_ref.agb_max) / 2
    stocks["agb"] = agb_dm * NON_MANGROVE_FACTOR

    rshoot = ipcc.ForestManagementRootToShoot.objects.get_max_below_threshold(
        climate=climate, forest_type=forest.forest_type, region=region, land_use_type=land_use_type, threshold=agb_dm
    )
    if rshoot:
        stocks["bgb"] = stocks["agb"] * rshoot.value
    return stocks


def _fra_reference(forest) -> dict | None:
    """The country's FRA stocks (tC/ha): latest year up to the project start, else the nearest later year.

    Pools FRA leaves empty count as 0 (user decision).
    """
    data_source = DataSource.objects.filter(short_name="FRA").first()
    if data_source is None:
        return None
    project = forest.activity.project
    rows = ipcc.FRACarbonStock.objects.filter(country=project.country)
    row = rows.filter(year__lte=project.start_year_of_activities).order_by("-year").first() or rows.order_by("year").first()
    pools = forest.STOCK_DIFFERENCE_POOLS
    reference = {"data_source": data_source.id, "country": project.country.name, "year": row.year if row else None}
    reference.update({pool: (getattr(row, pool) or 0) if row else None for pool in pools})
    return reference


def stock_difference_defaults(forest) -> dict:
    """Prefill values for the 12 stock inputs (IPCC; end stocks default to the start stock) plus the FRA alternative.

    Never raises on missing reference data: the inputs are user-editable, so a gap just means no prefill.
    """
    stocks = _ipcc_stocks(forest)
    values = {f"stock_{pool}_{scenario}_default": stocks[pool] for pool in forest.STOCK_DIFFERENCE_POOLS for scenario in ("start", "w", "wo")}
    values["stock_fra_reference"] = _fra_reference(forest)
    return values
