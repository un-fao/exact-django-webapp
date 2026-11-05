"""Calculator for the Rewetted Inland Wetland Mineral Soils module (IPCC 2013 Wetlands Supplement ch. 5).

Imported at the bottom of api/calculators.py so CalculatorFactory finds it by name; import it from there.
"""

from api.calculators import BaseCalculator
from api.models import IwmsRewetting
from api.services import iwms_rewetting
from math_model.no_time_dependency_final.ghg_emissions_classes import Result as MathResult
from math_model.no_time_dependency_final.iwms_rewetting import IwmsRewetting as MathIwmsRewetting

SCENARIOS = ("start", "w", "wo")


class IwmsRewettingCalculator(BaseCalculator):
    module: IwmsRewetting

    def default_ef_ch4(self) -> float | None:
        return iwms_rewetting.default_ef_ch4(self.climate)

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)
        return {scenario: self.default_ef_ch4() for scenario in SCENARIOS}

    def ef_ch4(self, scenario: str) -> float:
        override = getattr(self.module, f"ef_ch4_t2_{scenario}")
        if override is not None:
            return override
        default = self.default_ef_ch4()
        if default is None:
            raise ValueError(f"No IPCC CH4 emission factor for rewetted wetland mineral soils in {self.climate.name} climate. Please provide a tier 2 value.")
        return default

    def rewetted_area(self, scenario: str) -> float:
        # An area left over from before the activity soil changed away from Wetland counts nothing.
        if not iwms_rewetting.is_wetland_soil(self.soil_type):
            return 0.0
        return getattr(self.module, f"area_{scenario}") or 0.0

    def _run(self, end: str) -> MathIwmsRewetting:
        math = MathIwmsRewetting(
            area_start=self.rewetted_area("start"),
            area_end=self.rewetted_area(end),
            ef_ch4_start=self.ef_ch4("start"),
            ef_ch4_end=self.ef_ch4(end),
            gwp_ch4=self.project.gwp.ch4,
            implementation_time=self.activity.implementation_years,
            capitalization_time=self.activity.capitalization_years,
            rate_type=self.change_rate.name,
            delay=self.activity.delay,
        )
        math.calculate_emissions()
        return math

    def calculate(self) -> tuple[MathResult, MathResult]:
        self.math_w = self._run("w") if self.module.is_with() else None
        self.math_wo = self._run("wo") if self.module.is_without() else None

        def result(math):
            if math:
                return math.result
            return MathResult(self.activity.implementation_years, self.activity.capitalization_years, self.activity.delay)

        self.results_w, self.results_wo = result(self.math_w), result(self.math_wo)
        return self.results_w, self.results_wo
