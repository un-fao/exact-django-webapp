from enum import Enum

class GasTypes(Enum):
    CO2 = "CO2"
    CH4 = "CH4"
    N2O = "N2O"
    OTHER = "Other"

class ActivityTypes(Enum):
    SOIL_CO2_CHANGE = "Soil CO2 Change"
    RESIDUE_BURNING = "Residues Burning"
    SOM = "Soil Organic Matter"
    CATCH = "Catch"
    REFRIGERANT = "Refrigerant"
    ICE = "Ice"
    


class Emission:

    def __init__(self, value, gas_type=None):
        self.gas_type: GasTypes | None = gas_type
        self.value: float = value

class YearlyActivityEmissionSet:

    def __init__(self, year, gas_type, emissions, activity):
        self.year: int = year
        self.gas_type: GasTypes = gas_type
        self.emissions: list[Emission] = emissions
        self.activity: ActivityTypes = activity

class Result:

    def __init__(self):
       
        self.yearly_emissions_by_sector_by_gas: list[YearlyActivityEmissionSet] = []

    # Here add all necessary functions for result aggregation depending on what Claudio needs