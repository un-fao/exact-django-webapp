"""Forest management results under the stock-difference approach (IPCC 2006 Vol. 4, ch. 2, eq. 2.5).

Called by ForestManagementCalculator when ``ForestManagement.approach == "stock_difference"``.
The math lives in math_model/no_time_dependency_final/forest_stock_difference.py.
"""

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
