import copy
import logging as log
import os
from collections import defaultdict
from enum import Enum
import tempfile
import matplotlib.pyplot as plt
import matplotlib
from PIL import Image
import json

matplotlib.use("Agg")


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
    DISTURBANCE_FIRE_AGB = "Disturbance Fire AGB"
    DISTURBANCE_FIRE_BGB = "Disturbance Fire BGB"
    LOGGING_AGB = "Logging AGB"
    LOGGING_BGB = "Logging BGB"
    HWP_LOGGING_AGB = "Harvested Wood Product Logging AGB"
    HWP_LOGGING_BGB = "Harvested Wood Product Logging BGB"
    HWP_ROTATION_AGB = "Harvested Wood Product Rotation AGB"
    HWP_ROTATION_BGB = "Harvested Wood Product Rotation BGB"
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
    METHANE_MANURE_MANAGEMENT_SYSTEM = "Methane Manure Management System"
    METHANE_MANURE_MANAGEMENT_PRP = "Methane Manure Management PRP"
    NITROUS_MANURE_MANAGEMENT_SYSTEM = "Nitrous Oxide Manure Management System"
    NITROUS_MANURE_MANAGEMENT_PRP = "Nitrous Oxide Manure Management PRP"
    NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM = "Nitrous Oxide Manure Management Indirect Volatilization System"
    NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_PRP = "Nitrous Oxide Manure Management Indirect Volatilization PRP"
    NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM = "Nitrous Oxide Manure Management Indirect Leaching System"
    NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_PRP = "Nitrous Oxide Manure Management Indirect Leaching PRP"
    REWETTING_REVEGETATION = "Rewetting Revegetation"
    FIRE_ON_SOIL = "Fire on Soil"
    DRAINAGE = "Drainage"
    REWETTING = "Rewetting"
    DRAINAGE_PEAT = "Drainage Peat Extraction"
    OFFSITE_PEAT = "Offsite Peat Extraction"
    COASTAL_WATERBODIES = "Coastal Waterbodies"
    DEGRADATION_AGB = "Degradation AGB"
    DEGRADATION_BGB = "Degradation BGB"
    DEGRADATION_LITTER = "Degradation Litter"
    DEGRADATION_DEADWOOD = "Degradation Deadwood"


class Emission:

    def __init__(self, value=0.0, gas_type=None):
        self.gas_type: GasTypes | None = gas_type
        self.value: float = value

    def __add__(self, other):
        return Emission(self.value + other.value, self.gas_type)

    def __sub__(self, other):
        return Emission(self.value - other.value, self.gas_type)

    def to_dict(self):
        return {"gas_type": {"name": self.gas_type.name if self.gas_type else None}, "value": self.value}


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

    def to_dict(self):
        return {"year": self.year, "gas_type": {"name": self.gas_type.name if self.gas_type else None}, "emissions": [emission.to_dict() for emission in self.emissions], "activity": self.activity}


class YearlyActivityEmissionSet:

    def __init__(self, year, emissions, activity):
        self.year: int = year
        self.emissions: list[Emission] = emissions
        self.activity: ActivityTypes = activity

    def to_dict(self):
        return {"year": self.year, "emissions": [emission.to_dict() for emission in self.emissions], "activity": self.activity.value}


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

    def to_dict(self):
        return [emission_set.to_dict() for emission_set in self.yearly_emissions_by_sector_by_gas]

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
            aggregated_emissions[yearly_emission.gas_type].emissions = [x + y for x, y in zip(aggregated_emissions[yearly_emission.gas_type].emissions, yearly_emission.emissions)]

        return aggregated_emissions.values()

    def breakdown_by_activity(self):

        aggregated_emissions = {activity.value: YearlyActivityEmissionSet(0, [Emission(gas_type=None) for i in range(self.time_tot)], activity.value) for activity in [i.activity for i in self.yearly_emissions_by_sector_by_gas]}

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            aggregated_emissions[yearly_emission.activity.value].emissions = [x + y for x, y in zip(aggregated_emissions[yearly_emission.activity.value].emissions, yearly_emission.emissions)]

        return aggregated_emissions.values()

    def breakdown_by_activity_by_gas(self):

        for yearly_emission in self.yearly_emissions_by_sector_by_gas:
            yearly_emission.activity = ActivityTypes(yearly_emission.activity).value

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
                if other_yearly_emission.year == self_yearly_emission.year and other_yearly_emission.gas_type == self_yearly_emission.gas_type and other_yearly_emission.activity == self_yearly_emission.activity:
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
                if other_yearly_emission.year == self_yearly_emission.year and other_yearly_emission.gas_type == self_yearly_emission.gas_type and other_yearly_emission.activity == self_yearly_emission.activity:
                    self_yearly_emission.emissions = [x - y for x, y in zip(self_yearly_emission.emissions, other_yearly_emission.emissions)]
                    match_found = True
                    break

            if not match_found:
                negated_emissions = [Emission(-emission.value, emission.gas_type) for emission in other_yearly_emission.emissions]
                result_obj.yearly_emissions_by_sector_by_gas.append(YearlyGasActivityEmissionSet(other_yearly_emission.year, other_yearly_emission.gas_type, negated_emissions, other_yearly_emission.activity))

        return result_obj

    def plot_emissions_and_aggregate_by_activity(self, with_or_without_string):
        def save_emission_graphs_with_totals(save_path, emissions_data, with_or_without_string):

            activity_data = defaultdict(lambda: defaultdict(list))
            total_emissions_by_activity = defaultdict(float)

            for entry in emissions_data:
                activity = entry["activity"]
                emissions_list = entry["emissions"]

                for index, emission in enumerate(emissions_list):
                    year = index  # Year starts from 0 and increases by 1 each year
                    gas_type = emission["gas_type"]["name"]
                    value = emission["value"]
                    activity_data[activity][gas_type].append((year, value))
                    total_emissions_by_activity[activity] += value

            for activity, gases in activity_data.items():
                total_emissions = total_emissions_by_activity[activity]
                plt.figure(figsize=(12, 6))
                plt.title(f"{with_or_without_string} - Emissions for Activity: {activity} (Total: {total_emissions:.2f})")
                plt.xlabel("Year (starting from 0)")
                plt.ylabel("Emission Value")

                max_years = max(len(data) for data in gases.values())

                for gas_type, data in gases.items():
                    years = [year for year, _ in data]
                    values = [value for _, value in data]

                    plt.plot(years, values, label=gas_type, marker="o")

                plt.xticks(range(0, max_years))
                plt.legend()

                filename = f"{with_or_without_string}_emissions_{activity}.png"
                plt.savefig(os.path.join(save_path, filename))
                plt.close()

        # Convert the breakdown to a list of dictionaries
        emission_data_dicts = [emission_set.to_dict() for emission_set in self.breakdown_by_activity_by_gas()]

        # Use a temporary directory to save the plots
        with tempfile.TemporaryDirectory() as save_directory:
            # Pass the list of dictionaries instead of the raw objects to json.dumps()
            save_emission_graphs_with_totals(save_directory, emission_data_dicts, with_or_without_string)

            # Combining all images into a single large image
            plot_files = [os.path.join(save_directory, file) for file in os.listdir(save_directory) if file.endswith(".png")]
            images = [Image.open(file) for file in plot_files]

            if not images:
                log.warning("No images found to combine. The results are likely empty.")
                return

            widths, heights = zip(*(i.size for i in images))

            total_width = max(widths)
            total_height = sum(heights)
            combined_image = Image.new("RGB", (total_width, total_height))

            y_offset = 0
            for img in images:
                combined_image.paste(img, (0, y_offset))
                y_offset += img.size[1]

            combined_image_path = f"result_{with_or_without_string}.png"  # Update this path as needed
            combined_image.save(combined_image_path)
