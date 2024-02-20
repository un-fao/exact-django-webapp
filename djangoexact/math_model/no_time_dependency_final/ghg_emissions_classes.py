from enum import Enum
import copy
class GasTypes(Enum):
    CO2 = "CO2"
    CH4 = "CH4"
    N2O = "N2O"
    CO = "CO"
    OTHER = "Other"
    DOC = "DOC"

class ActivityTypes(Enum):
    SOIL_CO2_CHANGE = "Soil CO2 Change"
    RESIDUE_BURNING = "Residues Burning"
    SOM = "Soil Organic Matter"
    CATCH = "Catch"
    REFRIGERANT = "Refrigerant"
    ICE = "Ice"
    BIOMASS = "Biomass"
    DOM = "Dead Organic Matter"
    AGB_GROWTH = "AGB Growth"
    BGB_GROWTH = "BGB Growth"
    LITTER = "Litter"
    DEADWOOD = "Deadwood"
    ROTATION_AGB = "Rotation AGB"
    ROTATION_BGB = "Rotation BGB"
    DISTURBANCE_AGB = "Disturbance AGB"
    DISTURBANCE_BGB = "Disturbance BGB"
    LOGGING_AGB = "Logging AGB"
    LOGGING_BGB = "Logging BGB"
    CH4_EMITTED_RICE = "CH4 Emitted Rice"
    STRAW_BURNING = "Straw Burning"
    IRRIGATION_OPERATIONAL = "Operational Phase of Irrigation"
    CO2_FIELD = "CO2 Field"
    N20_FIELD = "N2O Field"
    CO2_EQUIVALENT_VC = "CO2 Equivalent VC"
    ROADS = "Roads"
    ELECTRICITY = "Electricity"
    FUEL = "Fuel"
    SOLID_CONSUMPTION = "Solid Consumption"
    NEW_IRRIGATION = "New Irrigation"
    METHANE_ENTERIC_FERMENTATION = "Methane Enteric Fermentation"
    METHANE_MANURE_MANAGEMENT = "Methane Manure Management"
    NITROUS_MANURE_MANAGEMENT = "Nitrous Oxide Manure Management"
    NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION = "Nitrous Oxide Manure Management Indirect Volatilization"
    NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING = "Nitrous Oxide Manure Management Indirect Leaching"
    REWETTING_REVEGETATION = "Rewetting Revegetation"
    FIRE_ON_SOIL = "Fire on Soil"
    DRAINAGE = "Drainage"
    REWETTING = "Rewetting"
    DRAINAGE_PEAT = "Drainage Peat Extraction"
    OFFSITE_PEAT = "Offsite Peat Extraction"
    COASTAL_WATERBODIES = "Coastal Waterbodies"


class Emission:

    def __init__(self, value=0, gas_type=None):
        self.gas_type: GasTypes | None = gas_type
        self.value: float = value

    def __add__(self, other):
        return Emission(self.value + other.value, self.gas_type)
    
    def __sub__(self, other):
        return Emission(self.value - other.value, self.gas_type)

class YearlyGasEmissionSet:

    def __init__(self, year, gas_type, emissions, delay=0):
        self.year: int = year
        self.gas_type: GasTypes = gas_type
        self.delay: int = delay
        self.emissions: list[Emission] = []

        for i in range(self.delay):
            self.emissions.append(Emission(0, emissions[0].gas_type))

        self.emissions.extend(emissions)
class YearlyGasActivityEmissionSet(YearlyGasEmissionSet):

    def __init__(self, year, gas_type, emissions, activity, delay=0):
        super().__init__(year, gas_type, emissions, delay)
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
        result_obj = copy.deepcopy(self)

        for other_yearly_emission in other.yearly_emissions_by_sector_by_gas:
            match_found = False
            for self_yearly_emission in result_obj.yearly_emissions_by_sector_by_gas:
                if (other_yearly_emission.year == self_yearly_emission.year and 
                    other_yearly_emission.gas_type == self_yearly_emission.gas_type and 
                    other_yearly_emission.activity == self_yearly_emission.activity):
                    self_yearly_emission.emissions = [x + y for x, y in zip(self_yearly_emission.emissions, other_yearly_emission.emissions)]
                    match_found = True
                    break
            
            if not match_found:
                result_obj.yearly_emissions_by_sector_by_gas.append(other_yearly_emission)

        return result_obj


    def __sub__(self, other):
        result_obj = copy.deepcopy(self)

        for other_yearly_emission in other.yearly_emissions_by_sector_by_gas:
            match_found = False
            for self_yearly_emission in result_obj.yearly_emissions_by_sector_by_gas:
                if (other_yearly_emission.year == self_yearly_emission.year and 
                    other_yearly_emission.gas_type == self_yearly_emission.gas_type and 
                    other_yearly_emission.activity == self_yearly_emission.activity):
                    self_yearly_emission.emissions = [x - y for x, y in zip(self_yearly_emission.emissions, other_yearly_emission.emissions)]
                    match_found = True
                    break
            
            if not match_found:
                negated_emissions = [Emission(-emission.value, emission.gas_type) for emission in other_yearly_emission.emissions]
                result_obj.yearly_emissions_by_sector_by_gas.append(
                    YearlyGasActivityEmissionSet(other_yearly_emission.year, 
                                                other_yearly_emission.gas_type, 
                                                negated_emissions, 
                                                other_yearly_emission.activity)
                )

        return result_obj


    # Here add all necessary functions for result aggregation depending on what Claudio needs