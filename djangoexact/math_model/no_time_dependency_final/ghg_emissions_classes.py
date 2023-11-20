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
    BIOMASS_LOSS = "Biomass Loss"
    BIOMASS_GAIN = "Biomass Gain"
    DOM = "Dead Organic Matter"
    ROTATION_AGB = "Rotation AGB"
    ROTATION_BGB = "Rotation BGB"
    LITTER = "Litter"
    DEADWOOD = "Deadwood"
    ROTATION = "Rotation"
    DISTURBANCE = "Disturbance"

    


class Emission:

    def __init__(self, value=0, gas_type=None):
        self.gas_type: GasTypes | None = gas_type
        self.value: float = value

    def __add__(self, other):
        return Emission(self.value + other.value, self.gas_type)
    
    def __sub__(self, other):
        return Emission(self.value - other.value, self.gas_type)

class YearlyGasEmissionSet:

    def __init__(self,year, gas_type, emissions):
        self.year: int = year
        self.gas_type: GasTypes = gas_type
        self.emissions: list[Emission] = emissions
class YearlyGasActivityEmissionSet(YearlyGasEmissionSet):

    def __init__(self, year, gas_type, emissions, activity):
        super().__init__(year, gas_type, emissions)
        # Can be a sub-activity, e.g. "Fire on Soil"
        self.activity: ActivityTypes = activity

class YearlyActivityEmissionSet:
    
    def __init__(self, year, emissions, activity):
        self.year: int = year
        self.emissions: list[Emission] = emissions
        self.activity: ActivityTypes = activity

class BreakdownTypes(Enum):
    TOTAL = "total"
    ACTIVITY = "activity"
    ACTIVITY_GAS = "activity_gas"
    GAS = "gas"

class Result:

    def __init__(self, time_impl, time_cap):
        self.yearly_emissions_by_sector_by_gas: list[YearlyGasActivityEmissionSet] = []
        self.balance = 0
        self.time_tot = time_impl + time_cap

    def breakdown(self, by=BreakdownTypes.TOTAL):
        match by:
            case BreakdownTypes.TOTAL:
                return self.compute_balance()
            case BreakdownTypes.GAS:
                return self.breakdown_by_gas()
            case BreakdownTypes.ACTIVITY:
                return self.breakdown_by_activity()
            case BreakdownTypes.ACTIVITY_GAS:
                return self.breakdown_by_activity_by_gas()
            case _:
                raise Exception("Invalid breakdown type")

    def breakdown_by_gas(self):

        aggregated_emissions = {gas_type: YearlyGasEmissionSet(0, gas_type, [Emission(gas_type=gas_type) for i in range(self.time_tot)]) for gas_type in GasTypes}

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            aggregated_emissions[yearly_emission.gas_type].emissions = [x + y for x,y in zip(aggregated_emissions[yearly_emission.gas_type].emissions, yearly_emission.emissions)]
        
        return aggregated_emissions.values()
    
    def breakdown_by_activity(self):

        aggregated_emissions = {activity.value: YearlyActivityEmissionSet(0, [Emission(gas_type=None) for i in range(self.time_tot)], activity.value) for activity in [i.activity for i in self.yearly_emissions_by_sector_by_gas]}

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            aggregated_emissions[yearly_emission.activity.value].emissions = [x + y for x,y in zip(aggregated_emissions[yearly_emission.activity.value].emissions, yearly_emission.emissions)]
        
        return aggregated_emissions.values()
    
    def breakdown_by_activity_by_gas(self):

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            yearly_emission.activity = yearly_emission.activity.value

        return self.yearly_emissions_by_sector_by_gas

    def compute_balance(self):

        self.balance = 0

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            self.balance += sum([i.value for i in yearly_emission.emissions])

        return self.balance
    
    def __add__(self, other):
        self.yearly_emissions_by_sector_by_gas = [YearlyGasActivityEmissionSet(i.year, i.gas_type, [x + y for x,y in zip(i.emissions, j.emissions)], i.activity) for i,j in zip(self.yearly_emissions_by_sector_by_gas, other.yearly_emissions_by_sector_by_gas)]
        return self

    def __sub__(self, other):
        self.yearly_emissions_by_sector_by_gas = [YearlyGasActivityEmissionSet(i.year, i.gas_type, [x - y for x,y in zip(i.emissions, j.emissions)], i.activity) for i,j in zip(self.yearly_emissions_by_sector_by_gas, other.yearly_emissions_by_sector_by_gas)]
        return self

    # Here add all necessary functions for result aggregation depending on what Claudio needs