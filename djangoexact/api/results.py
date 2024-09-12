from dataclasses import dataclass
import api.models as api_models
import api.calculators as calculators
from typing import Optional
import math_model.no_time_dependency_final.ghg_emissions_classes as math_utils


@dataclass
class BaseModuleResult:
    module: api_models.Module | api_models.LandModule

    calculator: Optional[calculators.BaseCalculator] | Optional[calculators.LandModuleCalculator] = None
    result: Optional[dict] = None

    def __post_init__(self):
        self.result = self.calculator.calculate()

    def get_result(self):
        return NotImplementedError


@dataclass
class AnnualCroplandResult(BaseModuleResult):

    def __post_init__(self):
        self.calculator = calculators.AnnualCroplandCalculator(self.module)
        return super().__post_init__()

    def get_result(self):
        """
        class YearlyGasActivityEmissionSet(YearlyGasEmissionSet):

            def __init__(self, year, gas_type, emissions, activity, delay=0):
                super().__init__(year, gas_type, emissions, delay)
                # Can be a sub-activity, e.g. "Fire on Soil"
                self.activity: ActivityTypes = activity

            def to_dict(self):
                return {"year": self.year, "gas_type": {"name": self.gas_type.name if self.gas_type else None}, "emissions": [emission.to_dict() for emission in self.emissions], "activity": self.activity}
        """

        print(self.calculator.results_w.to_dict())

        module_title = self.module.module_type.name
        emissions_set: list[math_utils.YearlyGasActivityEmissionSet] = self.calculator.results_w.yearly_emissions_by_sector_by_gas
        soil_co2 = emissions_set[emissions_set.index(lambda x: x.activity == math_utils.ActivityTypes.SOIL_CO2_CHANGE and x.gas_type == math_utils.GasTypes.CO2)]
        print(f"{module_title} - CO2 in soils:", soil_co2)
