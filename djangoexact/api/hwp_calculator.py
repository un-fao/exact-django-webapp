"""Calculator for the harvested wood products (HWP) module.

The pool has no inputs of its own besides product shares and half-lives: it runs the calculator of every source module
in the activity (HarvestedWoodProducts.sources), reads the yearly harvest inflow their math modules expose
(``hwp_inflow_co2``, tCO2) and turns it into one HWP_POOL line (CRT 4.G) per scenario with
math_model/no_time_dependency_final/hwp_decay.py. Each source keeps its own sign rule
(``HWP_INFLOW_ALREADY_EMITTED`` on its math class), so the module's line is the sum of the sources' contributions.
The wood each source feeds is also reported in tonnes of dry matter, back from tCO2 with the carbon fraction the
source applied (``HWP_INFLOW_CARBON_FRACTION``).

Imported at the bottom of api/calculators.py so CalculatorFactory finds it by name; import it from there.
"""

from itertools import zip_longest

from api.calculators import BaseCalculator, CalculatorFactory
from api.models import HarvestedWoodProducts, LandUseChange
from math_model.no_time_dependency_final.ghg_emissions_classes import Result as MathResult
from math_model.no_time_dependency_final.hwp_decay import co2_emission_set, hwp_pool_line

SCENARIOS = ("w", "wo")


def _sum(rows: list[list[float]]) -> list[float]:
    return [sum(values) for values in zip_longest(*rows, fillvalue=0.0)]


def _math_by_scenario(calculator) -> list[tuple[str, object, tuple[str, ...]]]:
    """(scenario whose shares apply, math module, result scenarios it adds to) for a source calculator.

    Mirrors how each source calculator combines its math modules into (w, wo) results: forest adds its start run to
    both, perennial adds start_w / start_wo to w / wo, land use change delegates to a deforestation or other land use
    calculator with one run per scenario.
    """
    luc_calculator = getattr(calculator, "luc_calculator", None)
    if luc_calculator is not None:
        return [(scenario, math_module, (scenario,)) for scenario, math_module in luc_calculator.hwp_math.items()]
    return [
        ("start", calculator.math_start, ("w", "wo")),
        ("w", calculator.math_start_w, ("w",)),
        ("wo", calculator.math_start_wo, ("wo",)),
        ("w", calculator.math_w, ("w",)),
        ("wo", calculator.math_wo, ("wo",)),
    ]


def _is_ready(source) -> bool:
    if isinstance(source, LandUseChange):
        # get_modules raises while a scenario's land module is missing: not ready yet, not an error.
        try:
            return all(module.is_ready() for module in source.get_modules())
        except Exception:
            return False
    return source.is_ready()


class HarvestedWoodProductsCalculator(BaseCalculator):
    def calculate(self) -> tuple[MathResult, MathResult]:
        hwp: HarvestedWoodProducts = self.module
        co2 = {scenario: [] for scenario in SCENARIOS}
        stock = {scenario: [] for scenario in SCENARIOS}
        sources = []

        for source in hwp.sources:
            entry = {
                "id": source.pk,
                "module_type": source.module_type.pk,
                "class_name": type(source).__name__,
                "ready": _is_ready(source),
                **{f"{kind}_{scenario}": 0.0 for kind in ("inflow", "inflow_dm", "pool") for scenario in SCENARIOS},
            }
            sources.append(entry)
            if not entry["ready"]:
                continue

            calculator = CalculatorFactory().get_calculator(source)(source)
            calculator.calculate()
            for share_scenario, math_module, targets in _math_by_scenario(calculator):
                inflow = getattr(math_module, "hwp_inflow_co2", None)
                if inflow is None:
                    continue
                inflow = [float(value) for value in inflow]
                line, line_stock = hwp_pool_line(inflow, hwp.shares(share_scenario), hwp.half_lives_t2(share_scenario), math_module.HWP_INFLOW_ALREADY_EMITTED)
                for target in targets:
                    co2[target].append(line)
                    stock[target].append(line_stock)
                    entry[f"inflow_{target}"] += sum(inflow)
                    entry[f"inflow_dm_{target}"] += sum(inflow) * 12 / 44 / math_module.HWP_INFLOW_CARBON_FRACTION
                    entry[f"pool_{target}"] += sum(line)

        for entry in sources:
            entry["balance"] = entry["pool_w"] - entry["pool_wo"]

        results = {}
        for scenario in SCENARIOS:
            result = MathResult(self.activity.implementation_years, self.activity.capitalization_years, self.activity.delay)
            if co2[scenario]:
                result.yearly_emissions_by_sector_by_gas.append(co2_emission_set(_sum(co2[scenario]), self.activity.delay))
            results[scenario] = result

        self.results_w, self.results_wo = results["w"], results["wo"]
        # Read by the results view and cached with the module results: where the wood comes from, for the module page.
        self.results_extra = {
            "hwp": {
                "sources": sources,
                "stock_w": _sum(stock["w"]),
                "stock_wo": _sum(stock["wo"]),
                "warning": None if sources else "no_sources",
            }
        }
        return (self.results_w, self.results_wo)

    def get_defaults(self, calculate=False) -> dict:
        return {}
