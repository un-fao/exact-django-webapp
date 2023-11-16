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

class YearlyGasEmissionSet:

    def __init__(self,year, gas_type, emissions):
        self.year: int = year
        self.gas_type: GasTypes = gas_type
        self.emissions: list[Emission] = emissions
class YearlyActivityEmissionSet(YearlyGasEmissionSet):

    def __init__(self, year, gas_type, emissions, activity):
        super().__init__(year, gas_type, emissions)
        # Can be a sub-activity, e.g. "Fire on Soil"
        self.activity: ActivityTypes = activity

class Result:

    def __init__(self, time_impl, time_cap):
        self.yearly_emissions_by_sector_by_gas: list[YearlyActivityEmissionSet] = []
        self.total_years = time_impl + time_cap
        self.balance = 0

    def breakdown_by_gas(self):

        aggregated_emissions = {gas_type: YearlyGasEmissionSet(0, gas_type, [0 for i in self.total_years]) for gas_type in GasTypes}

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            aggregated_emissions[yearly_emission.gas_type].emissions = [x + y for x,y in zip(aggregated_emissions[yearly_emission.gas_type].emissions, yearly_emission.emissions)]
        
        return aggregated_emissions.values()
    
    def breakdown_by_activity(self):

        aggregated_emissions = {activity: YearlyActivityEmissionSet(0, activity, [0 for i in self.total_years], activity) for activity in [i.activity for i in self.yearly_emissions_by_sector_by_gas]}

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            aggregated_emissions[yearly_emission.activity].emissions = [x + y for x,y in zip(aggregated_emissions[yearly_emission.activity].emissions, yearly_emission.emissions)]
        
        return aggregated_emissions.values()
    
    def breakdown_by_activity_by_gas(self):

        return self.yearly_emissions_by_sector_by_gas.sort(key=lambda x: x.activity)

    def compute_balance(self):

        self.balance = sum([sum(i.emissions) for i in self.yearly_emissions_by_sector_by_gas])

        return self.balance
    


        

    # Here add all necessary functions for result aggregation depending on what Claudio needs