"""Calculator for the Food Processing Wastewater module (CRT 5.D.2).

Resolves each scenario's IPCC defaults (ipcc.FoodIndustryWastewater, ipcc.WastewaterTreatmentSystem) and Tier 2
overrides into math_model/no_time_dependency_final/food_wastewater.py inputs. The with / without runs go from the
start state to the scenario's state over the implementation years, like the other non-land modules.

Imported at the bottom of api/calculators.py so CalculatorFactory finds it by name; import it from there.
"""

from api.calculators import BaseCalculator
from api.models import FoodProcessingWastewater
from ipcc.models import FoodIndustryWastewater, WastewaterTreatmentSystem
from math_model.no_time_dependency_final.food_wastewater import FoodWastewater, ScenarioInputs, TreatmentShare
from math_model.no_time_dependency_final.ghg_emissions_classes import Result as MathResult

SCENARIOS = {"start": "start", "w": "with", "wo": "without"}


class FoodProcessingWastewaterCalculator(BaseCalculator):
    module: FoodProcessingWastewater

    def industry(self, scenario: str) -> FoodIndustryWastewater | None:
        return getattr(self.module, f"industry_type_{scenario}")

    def defaults_for(self, scenario: str) -> dict[str, float | None]:
        industry = self.industry(scenario)
        return {
            "wastewater": industry.wastewater if industry else None,
            "cod": industry.cod if industry else None,
            "tn": industry.total_n if industry else None,
        }

    def get_defaults(self, calculate=False) -> dict:
        super().get_defaults(calculate)
        return {scenario: self.defaults_for(scenario) for scenario in SCENARIOS}

    def scenario_inputs(self, scenario: str) -> ScenarioInputs:
        module = self.module
        values = self.defaults_for(scenario)
        for name in values:
            override = getattr(module, f"{name}_t2_{scenario}")
            if override is not None:
                values[name] = override

        missing = [name for name in ("wastewater", "cod") if values[name] is None]
        if missing:
            industry = self.industry(scenario)
            raise ValueError(
                f"IPCC gives no default {' or '.join(missing)} for {industry.name if industry else 'this industry'}. "
                f"Please provide a tier 2 value for the {SCENARIOS[scenario]} scenario."
            )

        mix = getattr(module, f"treatment_mix_{scenario}") or {}
        systems = {system.code: system for system in WastewaterTreatmentSystem.objects.filter(code__in=mix)}
        treatment = [
            TreatmentShare(share=share, mcf=systems[code].mcf, ef_n2o_plant=systems[code].ef_n2o_plant, n_removal=systems[code].n_removal)
            for code, share in mix.items()
            if code in systems
        ]
        return ScenarioInputs(
            production=getattr(module, f"production_{scenario}") or 0.0,
            wastewater=values["wastewater"],
            cod=values["cod"],
            total_n=values["tn"],
            treatment=treatment,
            sludge_removed=getattr(module, f"sludge_removed_{scenario}") or 0.0,
            ch4_recovered=getattr(module, f"ch4_recovered_{scenario}") or 0.0,
        )

    def _run(self, end_scenario: str) -> FoodWastewater:
        math = FoodWastewater(
            start=self.scenario_inputs("start"),
            end=self.scenario_inputs(end_scenario),
            gwp_ch4=self.project.gwp.ch4,
            gwp_n2o=self.project.gwp.n2o,
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
