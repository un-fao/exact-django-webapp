import csv
import os

import numpy as np
import pandas as pd
from api.models import *
from ipcc.models import *


def capitalize_all(string):
    # Capitalize all words that have a space or a dash or a slash between them
    if " " in string:
        return " ".join([word.capitalize() for word in string.split(" ")])
    if "-" in string:
        return "-".join([word.capitalize() for word in string.split("-")])
    if "/" in string:
        return "/".join([word.capitalize() for word in string.split("/")])

    return string


def parse_csv_number(number, nan_value=0):
    if isinstance(number, str) and ("," in number or "." in number):
        return float(number.replace(",", "."))
    elif pd.isna(number):
        return nan_value
    else:
        return float(number)


def sanitize(s: str):
    if not s or pd.isna(s):
        return None
    return s.replace("ï»¿", "").title().strip()


"""
with open("scripts/ipcc_data/AboveGroundBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)  # skip the headers
    data = list(
        reader
    )  # read everything else into a list of rows to iterate multiple times

    for i, head in enumerate(header):
        vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
        for row in data:
            continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
            AboveGroundBiomass.objects.get_or_create(
                vegetation_type=vegetation_type,
                continent=continent,
                value=row[i + 1],
            )

with open("scripts/ipcc_data/BelowGroundBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    thresholds = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        threshold = sanitize(thresholds[i])
        if threshold == "> 125" or threshold == ">75":
            threshold = None
        elif "125" in threshold:
            threshold = 125
        elif "75" in threshold:
            threshold = 75

        vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
        for row in data:
            continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
            BelowGroundBiomass.objects.get_or_create(
                vegetation_type=vegetation_type,
                continent=continent,
                threshold=threshold,
                value=row[i + 1],
            )

with open("scripts/ipcc_data/LitterDeadwoodCarbonStock.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        vegtype, foo = VegetationType.objects.get_or_create(name=sanitize(row[0]))
        LitterDeadwoodCarbonStock.objects.get_or_create(
            vegetation_type=vegtype, litter=row[1], dw=row[2]
        )

with open("scripts/ipcc_data//Countries.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        Country.objects.get_or_create(
            name=sanitize(row[0]),
            continent=Continent.objects.get_or_create(name=sanitize(row[1]))[0],
        )

with open("scripts/ipcc_data/SoilOrganicCarbon.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head)
        soil_type = SoilType.objects.get_or_create(name=sanitize(head))[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue
            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            # FIXME: N/A and NO mean 2 different things. Differentiate them
            value = row[i + 2] if row[i + 2] not in ["", "N/A", "NO"] else None
            SoilOrganicCarbon.objects.get_or_create(
                climate=climate, moisture=moisture, soil_type=soil_type, value=value
            )

with open("scripts/ipcc_data/ForestTotalBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head)
        if head == "":
            continue
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if row[i + 3] == "":
                continue
            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            continent = Continent.objects.get_or_create(name=sanitize(row[2]))[0]
            value = row[i + 3]
            ForestTotalBiomass.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                continent=continent,
                value=value,
            )

with open("scripts/ipcc_data/AfforestationLandUseStockExchangeFactor.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head)
        if head == "":
            continue
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if row[i + 2] == "":
                continue
            climate = Climate.objects.get_or_create(name=sanitize(sanitize(row[0])))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(sanitize(row[1])))[
                0
            ]
            value = row[i + 2]
            AfforestationLandUseStockExchangeFactor.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/AboveGroundNetBiomassGrowth.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        vegetation_type = VegetationType.objects.get_or_create(name=sanitize(row[0]))[0]
        continent = Continent.objects.get_or_create(name=sanitize(row[1]))[0]
        value_after_20_years = row[2]
        value_upto_20_years = row[3]
        AboveGroundNetBiomassGrowth.objects.get_or_create(
            vegetation_type=vegetation_type,
            continent=continent,
            value_after_20_years=value_after_20_years,
            value_upto_20_years=value_upto_20_years,
        )

with open("scripts/ipcc_data/AfforestationCombustionFactorValues.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    cf = 1
    co2 = 2
    ch4 = 3
    n2o = 4

    for row in data:
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(row[0]))[0]
        AfforestationCombustionFactorValues.objects.get_or_create(
            land_use_type=land_use_type,
            value=row[cf],
            co2=row[co2],
            ch4=row[ch4],
            n2o=row[n2o],
        )

with open("scripts/ipcc_data/BurningEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for row in data:
        category = 0
        co2 = 1
        co = 2
        ch4 = 3
        n2o = 4
        nox = 5

        emission_factor_category = EmissionFactorCategory.objects.get_or_create(
            name=row[category]
        )[0]

        BurningEmissionFactor.objects.get_or_create(
            category=emission_factor_category,
            co2=row[co2],
            co=row[co],
            ch4=row[ch4],
            n2o=row[n2o],
            nox=row[nox],
        )

with open("scripts/ipcc_data/CoastalAboveGroundBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            CoastalAboveGroundBiomass.objects.get_or_create(
                vegetation_type=vegetation_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/CoastalBGAGRatio.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            CoastalBGAGRatio.objects.get_or_create(
                vegetation_type=vegetation_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/CoastalLitter.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            CoastalLitter.objects.get_or_create(
                vegetation_type=vegetation_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/RewettingEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            RewettingCarbonFactor.objects.get_or_create(
                vegetation_type=vegetation_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/RewettingMethaneFactors_salinity-lt18.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            salinity = SalinityType.objects.get_or_create(value="<18")[0]

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            RewettingMethaneFactor.objects.get_or_create(
                vegetation_type=vegetation_type,
                climate=climate,
                moisture=moisture,
                salinity=salinity,
                value=value,
            )

with open("scripts/ipcc_data/OtherConstructedWaterbodiesEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        waterbody_type = WaterbodyType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{waterbody_type}, {climate}, {moisture}, {value}")

            OtherConstructedWaterbodiesEmissionFactor.objects.get_or_create(
                waterbody_type=waterbody_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/Atwood.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        # FIXME: Some countries have no continent in the database. Link them
        country = Country.objects.get_or_create(name=sanitize(row[0]))[0]

        n = sanitize(row[1])
        area_2014_km2 = sanitize(row[2])
        mg_c_ha = sanitize(row[3])
        sd = sanitize(row[4]) if sanitize(row[4]) != "" else None
        score = sanitize(row[5]) if sanitize(row[5]) != "" else None

        Atwood.objects.get_or_create(
            country=country,
            n=n,
            area_2014_km2=area_2014_km2,
            mg_c_ha=mg_c_ha,
            sd=sd,
            score=score,
        )

with open("scripts/ipcc_data/CroplandFMG.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        tillage_type = TillageManagementType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{tillage_type}, {climate}, {moisture}, {value}")

            CroplandFMG.objects.get_or_create(
                tillage_management_type=tillage_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )



with open("scripts/ipcc_data/CroplandFMG.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        tillage_type = TillageManagementType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{tillage_type}, {climate}, {moisture}, {value}")

            CroplandFMG.objects.get_or_create(
                tillage_management_type=tillage_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

with open("scripts/ipcc_data/PerennialAGB.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        if head == "":
            continue

        land_use_type = LandUseType.objects.get(name=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name=sanitize(row[0]))
            moisture = Moisture.objects.get(name=sanitize(row[1]))
            continent = Continent.objects.get(name=sanitize(row[2]))

            value = row[i + 4]

            if value == "" and i != 0:
                continue

            print(f"{land_use_type}, {climate}, {moisture}, {continent}, {value}")

            PerennialAGB.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                continent=continent,
                value=value,
            )



with open("scripts/ipcc_data/PerennialMaximumAGB_C.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get(name=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue
            try:
                # FIXME: This skips rows in that don't have moisture values. Must be fixed. Ask team.
                # Some rows in the Excel are only matched to a climate, not climate and moisture.
                float(row[1])
                continue
            except ValueError:
                pass

            climate = Climate.objects.get(name=sanitize(row[0]).title())

            print(f"i = {i}")
            print(f"{land_use_type}, {climate}, {moisture}")

            value = row[i + 2]

            print(f"Value {value}")

            PerennialMaxAGB.objects.get_or_create(
                land_use_type=land_use_type, climate=climate, value=value
            )

with open("scripts/ipcc_data/GrasslandSOC.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        grassland_management_type = GrasslandManagementType.objects.get_or_create(
            name=sanitize(row[0]).title()
        )[0]
        value = row[1]

        print(f"{grassland_management_type}, {value}")

        GrasslandSOC.objects.get_or_create(
            grassland_management_type=grassland_management_type, value=value
        )

with open("scripts/ipcc_data/EnergyDefaultEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        fuel_type = FuelType.objects.get_or_create(name=sanitize(row[0]).title())[0]

        foo = EnergyDefaultEmissionFactor()
        foo.fuel_type = fuel_type
        foo.t_co2_eq_m3 = row[1] if row[1] != "" else None
        foo.tj_gg = row[2] if row[2] != "" else None
        foo.kg_ch4_tj = row[3] if row[3] != "" else None
        foo.kg_n2o_tj = row[4] if row[4] != "" else None
        foo.density_kg_m3 = row[5] if row[5] != "" else None
        foo.co2_emissions = row[6] if row[6] != "" else None
        foo.ch4_emissions = row[7] if row[7] != "" else None
        foo.n2o_emissions = row[8] if row[8] != "" else None
        foo.save()

        print(
            f"{fuel_type}, {row[1]}, {row[2]}, {row[3]}, {row[4]}, {row[5]}, {row[6]}, {row[7]}, {row[8]}"
        )


with open("scripts/ipcc_data/ElectricityEmissions.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        country = Country.objects.get_or_create(name=sanitize(row[0]).title())[0]
        continent = Continent.objects.get_or_create(name=sanitize(row[1]).title())[0]

        i = 2

        ef_grid = row[i + 0] if row[i + 0] != "" else None
        year = row[i + 1] if row[i + 1] != "" else None
        final_ef = row[i + 2] if row[i + 2] != "" else None
        op_margin = row[i + 3] if row[i + 3] != "" else None
        combined_margin = row[i + 4] if row[i + 4] != "" else None

        print(
            f"{country}, {continent}, {ef_grid}, {year}, {final_ef}, {op_margin}, {combined_margin}"
        )

        ElectricityEmission.objects.get_or_create(
            country=country,
            continent=continent,
            ef_grid=ef_grid,
            year=year,
            final_ef_grid=final_ef,
            operating_margin=op_margin,
            combined_margin=combined_margin,
        )
LivestockManureEF.objects.all().delete()





# print("AO")
# nsed = LargeFisheryFUI.objects.filter(gear_type__name="Not Specified")
# print(nsed)
# for n in nsed:
#     _all = LargeFisheryFUI.objects.filter(fish_type=n.fish_type)
#     for a in _all:
#         if a.gear_type.name != "Not Specified":
#             print(a.value)
#             print(n.value)

with open("scripts/ipcc_data/ListRegionsIPCC.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        ipcc_region = IPCCRegion.objects.get_or_create(name=row[0])[0]

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ListCountries.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    continent = Continent.objects.get_or_create(name=row["EX-ACT"])[0]
    gleam_region = GLEAMRegion.objects.get_or_create(name=row["GLEAM"])[0]
    ipcc_region = IPCCRegion.objects.get_or_create(name=row["IPCC"])[0]

    country = Country.objects.filter(name=row["Countries"]).first()

    if country:
        country.continent = continent
        country.gleam_region = gleam_region
        country.ipcc_region = ipcc_region
        country.save()












with open("scripts/ipcc_data/SmallFisheryDatabaseFish.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        gear_type = SmallFisheryGearType.objects.get_or_create(name=head)[0]
        for row in data:
            if row[i + 1] == "":
                continue

            fishery_type = FisheryType.objects.get_or_create(
                name=sanitize(row[0]).title()
            )[0]
            value = float(row[i + 1])

            print(f"{fishery_type}, {gear_type}, {value}")

            SmallFisheryFUI.objects.get_or_create(
                fishery_type=fishery_type, gear_type=gear_type, value=value
            )




with open("scripts/ipcc_data/LargeFisheryFUI.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        gear_type = LargeFisheryGearType.objects.get_or_create(name=head)[0]
        for row in data:
            if row[i + 1] == "":
                continue

            fish_type = FishType.objects.get_or_create(name=sanitize(row[0]).title())[0]
            value = float(row[i + 1])

            print(f"{fish_type}, {gear_type}, {value}")

            LargeFisheryFUI.objects.get_or_create(
                fish_type=fish_type, gear_type=gear_type, value=value
            )




df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "DefaultEmissionFactors.csv"),
    header=[0],
    sep=",",
)

for i, row in df.iterrows():
    organic_input_type = OrganicInputType.objects.get_or_create(
        name=sanitize(row["organic_input_type"])
    )[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    emission_factor = DefaultEmissionFactor.objects.get_or_create(
        organic_input_type=organic_input_type,
        moisture=moisture,
        value=float(row["value"]),
    )[0]

    print(emission_factor)


CropYieldStats.objects.all().delete()



with open("scripts/ipcc_data/CroplandFI.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        organic_input_type = OrganicInputType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{organic_input_type}, {climate}, {moisture}, {value}")

            CroplandFI.objects.get_or_create(
                organic_input_type=organic_input_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )


df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "DefaultEmissionFactors.csv"),
    header=[0],
    sep=",",
)

for i, row in df.iterrows():
    organic_input_type = OrganicInputType.objects.get_or_create(
        name=sanitize(row["organic_input_type"])
    )[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    emission_factor = DefaultEmissionFactor.objects.get_or_create(
        organic_input_type=organic_input_type,
        moisture=moisture,
        value=float(row["value"]),
    )[0]

    print(emission_factor)

Atwood.objects.all().delete()

with open("scripts/ipcc_data/Atwood.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        # FIXME: Some countries have no continent in the database. Link them
        country = Country.objects.get_or_create(name=capitalize_all(row[0]))[0]

        n = sanitize(row[1])
        area_2014_km2 = sanitize(row[2])
        mg_c_ha = sanitize(row[3])
        sd = sanitize(row[4]) if sanitize(row[4]) != "" else None
        score = sanitize(row[5]) if sanitize(row[5]) != "" else None

        Atwood.objects.get_or_create(
            country=country,
            n=n,
            area_2014_km2=area_2014_km2,
            mg_c_ha=mg_c_ha,
            sd=sd,
            score=score,
        )

ElectricityEmission.objects.all().delete()

with open("scripts/ipcc_data/ElectricityEmissions.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        country = Country.objects.get_or_create(name=capitalize_all(row[0]))[0]
        continent = Continent.objects.get_or_create(name=capitalize_all(row[1]))[0]

        i = 2

        ef_grid = row[i + 0] if row[i + 0] != "" else None
        year = row[i + 1] if row[i + 1] != "" else None
        final_ef = row[i + 2] if row[i + 2] != "" else None
        op_margin = row[i + 3] if row[i + 3] != "" else None
        combined_margin = row[i + 4] if row[i + 4] != "" else None

        print(
            f"{country}, {continent}, {ef_grid}, {year}, {final_ef}, {op_margin}, {combined_margin}"
        )

        ElectricityEmission.objects.get_or_create(
            country=country,
            continent=continent,
            ef_grid=ef_grid,
            year=year,
            final_ef_grid=final_ef,
            operating_margin=op_margin,
            combined_margin=combined_margin,
        )

with open("scripts/ipcc_data/CroplandFMG.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = capitalize_all(sanitize(head)).title()
        tillage_type = TillageManagementType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{tillage_type}, {climate}, {moisture}, {value}")

            CroplandFMG.objects.get_or_create(
                tillage_management_type=tillage_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "ManureEntericFermentationFactor.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    ipcc_region = IPCCRegion.objects.get_or_create(name=sanitize(row["ipcc_region"]))[0]
    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=sanitize(row["livestock_production_type"])
    )[0]
    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category_type = LivestockCategoryType.objects.get_or_create(
            name=sanitize(df_headers[j])
        )[0]

        print(
            ipcc_region,
            livestock_production_type,
            livestock_category_type,
            row[df_headers[j]],
        )

        MethaneEntericFermentationFactor.objects.get_or_create(
            ipcc_region=ipcc_region,
            livestock_production_type=livestock_production_type,
            livestock_category_type=livestock_category_type,
            value=parse_csv_number(row[df_headers[j]]),
        )






df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEF2.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(
        name=capitalize_all(row["emission_type"])
    )[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(
        name=sanitize(row["livestock_category_type"])
    )[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=sanitize(row["livestock_production_type"])
    )[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get_or_create(
            name=sanitize(df_headers2[j])
        )[0]

        print(
            emission_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break










df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEFLlamas.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(
        name=capitalize_all(row["emission_type"])
    )[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(
        name=sanitize(row["livestock_category_type"])
    )[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=sanitize(row["livestock_production_type"])
    )[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get_or_create(
            name=sanitize(df_headers2[j])
        )[0]

        print(
            emission_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockTAM.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    production_type = LivestockProductionType.objects.get_or_create(
        name=capitalize_all(row["production_type"])
    )[0]
    region = IPCCRegion.objects.get_or_create(name=row["ipcc_region"])[0]

    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category = LivestockCategoryType.objects.get_or_create(
            name=capitalize_all(df_headers[j])
        )[0]

        print(
            production_type,
            livestock_category,
            region,
            row[df_headers[j]],
        )

        LivestockTAM.objects.get_or_create(
            livestock_production_type=production_type,
            livestock_category_type=livestock_category,
            ipcc_region=region,
            value=parse_csv_number(row[df_headers[j]]),
        )





df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEFN2O.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(
        name=sanitize(row["emission_type"])
    )[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(
        name=sanitize(row["livestock_category_type"])
    )[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=sanitize(row["livestock_production_type"])
    )[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get_or_create(
            name=sanitize(df_headers2[j])
        )[0]

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "AnimalWasteManagementSystem.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    livestock_category_type = LivestockCategoryType.objects.get_or_create(
        name=capitalize_all(row["livestock_category_type"])
    )[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=capitalize_all(row["livestock_production_type"])
    )[0]

    ipcc_region = IPCCRegion.objects.get_or_create(name=row["ipcc_region"])[0]

    print(f"{livestock_category_type}, {livestock_production_type}, {ipcc_region}")

    for j in range(3, len(df_headers)):
        manure_management_type = ManureManagementType.objects.get_or_create(
            name=capitalize_all(df_headers[j])
        )[0]

        print(manure_management_type)

        LivestockAnimalWasteManagementSystem.objects.get_or_create(
            manure_management_type=manure_management_type,
            livestock_category_type=livestock_category_type,
            livestock_production_type=livestock_production_type,
            ipcc_region=ipcc_region,
            value=parse_csv_number(row[df_headers[j]]),
        )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ListCountries.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    continent = Continent.objects.get_or_create(name=sanitize(row["EX-ACT"]))[0]
    gleam_region = GLEAMRegion.objects.get_or_create(name=sanitize(row["GLEAM"]))[0]
    ipcc_region = IPCCRegion.objects.get_or_create(name=sanitize(row["IPCC"]))[0]

    country = Country.objects.get_or_create(name=sanitize(row["Countries"]))[0]

    print(
        continent,
        gleam_region,
        ipcc_region,
        country,
    )

    if country:
        country.continent = continent
        country.gleam_region = gleam_region
        country.ipcc_region = ipcc_region
        country.save()

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "LivestockManureEFLeeching.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(
        name=sanitize(row["emission_type"])
    )[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(
        name=sanitize(row["livestock_category"])
    )[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=sanitize(row["livestock_production"])
    )[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get_or_create(
            name=sanitize(df_headers2[j])
        )[0]

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEF2.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(
        name=capitalize_all(row["emission_type"])
    )[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(
        name=sanitize(row["livestock_category_type"])
    )[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(
        name=sanitize(row["livestock_production_type"])
    )[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.get_or_create(
            name=sanitize(df_headers2[j])
        )[0]

        print(
            emission_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "InputsEmissionFactors.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    input_type = InputType.objects.get_or_create(name=sanitize(row["input_type"]))[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    # read floats from dataframe that have , as decimal separator
    co2_value = parse_csv_number(row["co2_value"], nan_value=None)
    n2o_value = parse_csv_number(row["n2o_value"], nan_value=None)
    co2_eq_value = parse_csv_number(row["co2_eq_value"], nan_value=None)

    print(
        input_type,
        climate,
        moisture,
        co2_value,
        n2o_value,
        co2_eq_value,
    )

    InputEmissionFactor.objects.get_or_create(
        input_type=input_type,
        climate=climate,
        moisture=moisture,
        co2_value=co2_value,
        n2o_value=n2o_value,
        co2_eq_value=co2_eq_value,
    )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LiquidFuelTypes.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    macro_fuel_type = (
        MacroFuelType.objects.get_or_create(name=sanitize(row["macro_fuel_type"]))[0]
        if row["macro_fuel_type"]
        else None
    )
    fuel_use_type = (
        FuelUseType.objects.get_or_create(name=sanitize(row["fuel_use_type"]))[0]
        if pd.notna(row["fuel_use_type"])
        else None
    )
    fuel_type = (
        FuelType.objects.get_or_create(
            name=sanitize(row["fuel_type"]),
            macro_type=macro_fuel_type,
            fuel_use_type=fuel_use_type,
        )[0]
        if row["fuel_type"]
        else None
    )

    print(
        fuel_type,
        row["t_co2_eq"],
        row["co2"],
        row["ch4"],
        row["n2o"],
        row["density"],
        row["net_calorific_value"],
    )

    EnergyDefaultEmissionFactor.objects.get_or_create(
        fuel_type=fuel_type,
        t_co2_eq=parse_csv_number(row["t_co2_eq"], nan_value=None),
        co2=parse_csv_number(row["co2"], nan_value=None),
        ch4=parse_csv_number(row["ch4"], nan_value=None),
        n2o=parse_csv_number(row["n2o"], nan_value=None),
        density=parse_csv_number(row["density"], nan_value=None),
        net_calorific_value=parse_csv_number(
            row["net_calorific_value"], nan_value=None
        ),
    )


df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "IrrigationSystems.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    irrigation_system = IrrigationSystemType.objects.get_or_create(
        name=sanitize(row["irrigation_system_type"])
    )[0]
    value = parse_csv_number(row["value"], nan_value=None)

    print(irrigation_system, value)

    IrrigationSystemData.objects.get_or_create(
        irrigation_system_type=irrigation_system,
        value=value,
    )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "IrrigationPhaseData.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    fuel_type = FuelType.objects.get_or_create(
        name=sanitize(row["fuel_type"]),
    )[0]

    print(
        fuel_type,
        row["emission_factor"],
        row["calorific_value"],
        row["co2_emissions"],
        row["ch4_emissions"],
        row["n2o_emissions"],
        row["density"],
    )

    data = IrrigationPhaseData.objects.get_or_create(
        fuel_type=fuel_type,
        emission_factor=parse_csv_number(row["emission_factor"], nan_value=None),
        calorific_value=parse_csv_number(row["calorific_value"], nan_value=None),
        co2_emissions=parse_csv_number(row["co2_emissions"], nan_value=None),
        ch4_emissions=parse_csv_number(row["ch4_emissions"], nan_value=None),
        n2o_emissions=parse_csv_number(row["n2o_emissions"], nan_value=None),
        density=parse_csv_number(row["density"], nan_value=None),
    )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "IrrigationPressureRequirements.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    irrigation_system_type = IrrigationSystemType.objects.get_or_create(
        name=sanitize(row["irrigation_system_type"])
    )[0]

    print(
        irrigation_system_type,
        row["bar"],
        row["avg_pressure"],
        row["head"],
    )

    try:
        bar_ranges = row["bar"].split("-")
    except AttributeError:
        bar_ranges = [row["bar"], row["bar"]]

    bar_start = parse_csv_number(bar_ranges[0], nan_value=None)
    bar_end = parse_csv_number(bar_ranges[1], nan_value=None)

    data = IrrigationPressureRequirement.objects.get_or_create(
        irrigation_system_type=irrigation_system_type,
        bar_start=bar_start,
        bar_end=bar_end,
        avg_pressure=parse_csv_number(row["avg_pressure"], nan_value=None),
        head=parse_csv_number(row["head"], nan_value=None),
    )
PerennialMaxAGB.objects.all().delete()




df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "RiceDefaultEmissionFactor.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    continent = Continent.objects.get_or_create(name=sanitize(row["continent"]))[0]

    print(continent, row["value"], row["cultivation_period"])

    bar_start = parse_csv_number(row["value"], nan_value=0)
    bar_end = parse_csv_number(row['cultivation_period'], nan_value=0)

    RiceDefaultEmissionFactor.objects.get_or_create(
        continent=continent,
        value=bar_start,
        cultivation_period=bar_end,
    )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "RiceSFO.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    organic_amendment_type = OrganicAmendmentType.objects.get_or_create(name=sanitize(row["organic_amendment_type"]))[0]

    print(continent, row["organic_amendment_type"], row["value"])

    value = parse_csv_number(row["value"], nan_value=0)

    RiceSFO.objects.get_or_create(
        organic_amendment_type=organic_amendment_type,
        value=value,
    )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "RiceSFP.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    water_management_type_before_cultivation = WaterManagementTypeBeforeCultivation.objects.get_or_create(name=sanitize(row["water_regime_type"]))[0]
    value = parse_csv_number(row["value"], nan_value=0)

    print(continent, row["water_regime_type"], value)

    RiceSFP.objects.get_or_create(
        water_management_type_before_cultivation=water_management_type_before_cultivation,
        value=value,
    )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "RiceSFW.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    water_management_type_after_cultivation = WaterManagementTypeAfterCultivation.objects.get_or_create(name=sanitize(row["water_regime_type"]))[0]
    value = parse_csv_number(row["value"], nan_value=0)

    print(continent, row["water_regime_type"], value)

    RiceSFW.objects.get_or_create(
        water_management_type_after_cultivation=water_management_type_after_cultivation,
        value=value,
    )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "RiceYield.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    continent = Continent.objects.get_or_create(name=sanitize(row["continent"]))[0]
    value = parse_csv_number(row["value"], nan_value=0)

    print(continent, value)

    RiceYield.objects.get_or_create(
        continent=continent,
        value=value,
    )

df = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "TrophicStateFactor.csv"
    ),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    trophic_type = TrophicType.objects.get_or_create(name=sanitize(row["trophic_type"]))[0]
    value = parse_csv_number(row["value"], nan_value=0)
    chloa = parse_csv_number(row["chloa"], nan_value=0)

    print(trophic_type, value, chloa)

    TrophicStateFactor.objects.get_or_create(
        trophic_type=trophic_type,
        value=value,
        chloa=chloa,
    )

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "DefaultSoilCarbonStock1Meter.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    soil_type = SoilType.objects.get_or_create(name=sanitize(row["soil_type"]))[0]
    unit = sanitize(row["unit"])

    for j, header in enumerate(df_headers2, start=4):
        vegetation_type = VegetationType.objects.get_or_create(name=sanitize(df_headers2[j]))[0]

        print(
            climate,
            moisture,
            soil_type,
            vegetation_type,
            row[df_headers2[j]],
        )

        DefaultSoilCarbonStock1Meter.objects.get_or_create(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            vegetation_type=vegetation_type,
            unit=unit,
            value=row[df_headers2[j]],
        )

        if j == len(df_headers2) - 1:
            break

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "RoadEmissionFactors.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    road_type = RoadType.objects.get_or_create(name=sanitize(row["road_type"]))[0]
    value = parse_csv_number(row["value"], nan_value=0)

    print(road_type, value)

    RoadEmissionFactor.objects.get_or_create(
        road_type=road_type,
        value=value,
    )

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "OrganicSoilDrainageEmissionFactor.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    site_location_type = SiteLocationType.objects.get_or_create(name=sanitize(row["site_location_type"]))[0]
    peat_type = PeatType.objects.get_or_create(name=sanitize(row["peat_type"]))[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    module_type = ModuleType.objects.get_or_create(name=sanitize(row["module_type"]))[0]
    co2 = parse_csv_number(row["co2"], nan_value=0)
    ch4 = parse_csv_number(row["ch4"], nan_value=0)
    doc = parse_csv_number(row["doc"], nan_value=0)
    n2o = parse_csv_number(row["n2o"], nan_value=0)

    print(
        site_location_type,
        peat_type,
        climate,
        moisture,
        module_type,
        co2,
        ch4,
        doc,
        n2o,
    )

    OrganicSoilDrainageEmissionFactor.objects.get_or_create(
        site_location_type=site_location_type,
        peat_type=peat_type,
        climate=climate,
        moisture=moisture,
        module_type=module_type,
        co2=co2,
        ch4=ch4,
        doc=doc,
        n2o=n2o,
    )
df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "OrganicSoilFuelConsumption.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    

    for j, header in enumerate(df_headers2, start=2):
        fire_type = FireType.objects.get_or_create(name=sanitize(df_headers2[j]))[0]

        print(
            climate,
            moisture,
            fire_type,
            row[df_headers2[j]],
        )

        OrganicSoilFuelConsumption.objects.get_or_create(
            climate=climate,
            moisture=moisture,
            fire_type=fire_type,
            value=parse_csv_number(row[df_headers2[j]])
        )

        if j == len(df_headers2) - 1:
            break
            
df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "OrganicSoilGefEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    co2 = parse_csv_number(row["co2"], nan_value=0)
    ch4 = parse_csv_number(row["ch4"], nan_value=0)
    co = parse_csv_number(row["co"], nan_value=0)

    print(
        climate,
        moisture,
        co2,
        ch4,
        co,
    )

    OrganicSoilGefEmissionFactor.objects.get_or_create(
        climate=climate,
        moisture=moisture,
        co2=co2,
        ch4=ch4,
        co=co,
    )

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "OrganicSoilRewettingEmissionFactor.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    peat_type = PeatType.objects.get_or_create(name=sanitize(row["peat_type"]))[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    module_type = ModuleType.objects.get_or_create(name=sanitize(row["module_type"]))[0]
    co2 = parse_csv_number(row["co2"], nan_value=0)
    ch4 = parse_csv_number(row["ch4"], nan_value=0)
    doc = parse_csv_number(row["doc"], nan_value=0)
    n2o = parse_csv_number(row["n2o"], nan_value=0)

    print(
        peat_type,
        climate,
        moisture,
        module_type,
        co2,
        ch4,
        doc,
        n2o,
    )

    OrganicSoilRewettingEmissionFactor.objects.get_or_create(
        peat_type=peat_type,
        climate=climate,
        moisture=moisture,
        module_type=module_type,
        co2=co2,
        ch4=ch4,
        doc=doc,
        n2o=n2o,
    )
df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "RewettingEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    soil_type = SoilType.objects.get_or_create(name=sanitize(row["soil_type"]))[0]

    for j, header in enumerate(df_headers2, start=4):
        vegetation_type = VegetationType.objects.get_or_create(name=sanitize(df_headers2[j]))[0]

        print(
            climate,
            moisture,
            soil_type,
            vegetation_type,
            row[df_headers2[j]],
        )

        RewettingEmissionFactor.objects.get_or_create(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            vegetation_type=vegetation_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break
            

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PeatExtractionEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    peat_type = PeatType.objects.get_or_create(name=sanitize(row["peat_type"]))[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    site_location_type = SiteLocationType.objects.get_or_create(name=sanitize(row["site_location_type"]))[0]
    co2 = parse_csv_number(row["co2"], nan_value=0)
    doc = parse_csv_number(row["doc"], nan_value=0)
    ch4 = parse_csv_number(row["ch4"], nan_value=0)
    n2o = parse_csv_number(row["n2o"], nan_value=0)

    print(
        peat_type,
        climate,
        moisture,
        site_location_type,
        co2,
        ch4,
        doc,
        n2o,
    )

    PeatExtractionEmissionFactor.objects.get_or_create(
        peat_type=peat_type,
        climate=climate,
        moisture=moisture,
        site_location_type=site_location_type,
        co2=co2,
        ch4=ch4,
        doc=doc,
        n2o=n2o,
    )

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PeatExtractionConversionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    peat_type = PeatType.objects.get_or_create(name=sanitize(row["peat_type"]))[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    weight = parse_csv_number(row["weight"], nan_value=0)
    volume = parse_csv_number(row["volume"], nan_value=0)

    print(
        peat_type,
        climate,
        moisture,
        weight,
        volume,
    )

    PeatExtractionConversionFactor.objects.get_or_create(
        peat_type=peat_type,
        climate=climate,
        moisture=moisture,
        weight=weight,
        volume=volume,
    )

# CropNitrousEstimationDefaultFactor.objects.all().delete()
with open("scripts/ipcc_data/CropNitrousEstimationDefaultFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for row in data:
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(row[0]))[0]
        CropNitrousEstimationDefaultFactor.objects.get_or_create(
            land_use_type=land_use_type,
            slope=row[1] if row[1] != "NA" else None,
            intercept=row[2] if row[2] != "NA" else None,
            n_ag_residues=row[3],
            rs_t=row[4],
            n_bg_t=row[5],
        )

# CropYieldStats.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "CropYieldStats.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]
    continent = Continent.objects.get_or_create(name=sanitize(row["continent"]))[0]
    yr_2016 = float(row["2016"])
    yr_2017 = float(row["2017"])
    yr_2018 = float(row["2018"])
    yr_2019 = float(row["2019"])
    yr_2020 = float(row["2020"])

    average = (yr_2016 + yr_2017 + yr_2018 + yr_2019 + yr_2020) / 5 / 10000

    print(
        f"{land_use_type}, {continent}, {yr_2016}, {yr_2017}, {yr_2018}, {yr_2019}, {yr_2020}, {average}"
    )

    stat = CropYieldStats.objects.get_or_create(
        land_use_type=land_use_type,
        continent=continent,
        year_2016=yr_2016,
        year_2017=yr_2017,
        year_2018=yr_2018,
        year_2019=yr_2019,
        year_2020=yr_2020,
        average=average,
    )[0]

CropNitrousEstimationDefaultFactor.objects.all().delete()
with open("scripts/ipcc_data/CropNitrousEstimationDefaultFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for row in data:
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(row[0]))[0]
        CropNitrousEstimationDefaultFactor.objects.get_or_create(
            land_use_type=land_use_type,
            slope=row[1] if row[1] != "NA" else None,
            intercept=row[2] if row[2] != "NA" else None,
            n_ag_residues=row[3],
            rs_t=row[4],
            n_bg_t=row[5],
        )

# PerennialAGB.objects.all().delete()
with open("scripts/ipcc_data/PerennialAGB.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        if head == "":
            continue

        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            continent = Continent.objects.get_or_create(name=sanitize(row[2]))[0]

            # FIXME: Maybe skip instead of setting to None?
            value = row[i + 4] if row[i + 4] != "" else None

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            PerennialAGB.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                continent=continent,
                value=value,
            )

# PerennialBGB.objects.all().delete()
with open("scripts/ipcc_data/PerennialBGB.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        if head == "":
            continue

        land_use_type = LandUseType.objects.get(name=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name=sanitize(row[0]).title())
            moisture = Moisture.objects.get(name=sanitize(row[1]).title())
            continent = Continent.objects.get(name=sanitize(row[2]).title())

            value = row[i + 4]

            if value == "" and i != 0:
                continue

            print(f"{land_use_type}, {climate}, {moisture}, {continent}, {value}")

            PerennialBGB.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                continent=continent,
                value=value,
            )

# PerennialMaxAGB.objects.all().delete()
# with open("scripts/ipcc_data/PerennialMaximumAGB_C.csv", "r") as f:
#     reader = csv.reader(f)
#     header = next(reader, None)
#     data = list(reader)

#     for i, head in enumerate(header):
#         land_use_type = LandUseType.objects.get_or_create(name=head)[0]
#         for row in data:
#             if sanitize(row[0]) == "":
#                 continue
#             try:
#                 # FIXME: This skips rows in PerennialMaximumAGB_C that don't have moisture values. Must be fixed. Ask team.
#                 # Some rows in the Excel are only matched to a climate, not climate and moisture.
#                 float(row[1])
#                 continue
#             except ValueError:
#                 pass

#             climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
#             moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

#             print(f"i = {i}")
#             print(f"{land_use_type}, {climate}, {moisture}")

#             value = row[i + 2]

#             print(f"Value {value}")

#             PerennialMaxAGB.objects.get_or_create(
#                 land_use_type=land_use_type,
#                 climate=climate,
#                 value=value,
#             )

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "PerennialMaxAGB.csv"
    ),
    header=0,
    sep=",",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]

    for j, header in enumerate(df_headers2, start=1):
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(df_headers2[j]))[0]

        print(
            climate,
            land_use_type,
            row[df_headers2[j]],
        )

        PerennialMaxAGB.objects.get_or_create(
            climate=climate,
            land_use_type=land_use_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "LandUseTypes.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

# Iterate rows
for i, row in enumerate(df_dict2):
    land_use_type: LandUseType = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]

    land_use_type.climates.add(Climate.objects.get(name=sanitize(row["climate"])))
    if pd.notna(row["moisture"]):
        land_use_type.moistures.add(Moisture.objects.get(name=sanitize(row["moisture"])))
    land_use_type.module_types.add(ModuleType.objects.get(class_name=row["module_type"]))

    print(
        land_use_type,
        row["climate"],
        row["moisture"],
        row["module_type"],
    )

    if i == len(df_dict2) - 1:
        break


# CombustionFactor
CombustionFactor.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "CombustionFactorValues.csv"), header=0, sep=",")

for row in df.to_dict("records"):
    lut,_ = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))
    cf = parse_csv_number(row["cf"])
    co2 = parse_csv_number(row["co2"])
    ch4 = parse_csv_number(row["ch4"])
    n2o = parse_csv_number(row["n2o"])

    print(
        lut,
        cf,
        co2,
        ch4,
        n2o
    )

    CombustionFactor.objects.create(
        land_use_type = lut,
        value = cf,
        co2 = co2,
        ch4 = ch4,
        n2o = n2o
    )

# LitterDeadwoodCarbonStock

LitterDeadwoodCarbonStock.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "LitterDeadwoodCarbonStock.csv"), header=0, sep=",")

for row in df.to_dict("records"):
    lut,_ = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))
    litter = parse_csv_number(row["litter"])
    deadwood = parse_csv_number(row["deadwood"])

    print(
        lut,
        litter,
        deadwood
    )

    LitterDeadwoodCarbonStock.objects.create(
        land_use_type = lut,
        litter = litter,
        dw = deadwood,
    )

#AboveGroundBiomass
AboveGroundBiomass.objects.all().delete()
with open("scripts/ipcc_data/AboveGroundBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)  # skip the headers
    data = list(reader)  # read everything else into a list of rows to iterate multiple times

    for i, head in enumerate(header):
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(head))[0]
        for row in data:
            continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
            AboveGroundBiomass.objects.get_or_create(
                land_use_type=land_use_type,
                continent=continent,
                value=parse_csv_number(row[i + 1])
            )

# ForestManagementAGB
ForestManagementAGB.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGB.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]
    continent = Continent.objects.get_or_create(name=sanitize(row["continent"]))[0]
    forest_condition_type = ForestConditionType.objects.get_or_create(name=sanitize(row["forest_condition_type"]))[0]
    forest_type = ForestType.objects.get_or_create(name=sanitize(row["forest_type"]))[0]
    agb_min = parse_csv_number(row["agb_min"], nan_value=0)
    agb_max = parse_csv_number(row["agb_max"], nan_value=0)
    agb_growth_min = parse_csv_number(row["agb_growth_min"], nan_value=0)
    agb_growth_max = parse_csv_number(row["agb_growth_max"], nan_value=0)

    print(
        land_use_type,
        continent,
        forest_condition_type,
        forest_type,
        agb_min,
        agb_max,
        agb_growth_min,
        agb_growth_max,
    )
    
    ForestManagementAGB.objects.get_or_create(
        land_use_type=land_use_type,
        continent=continent,
        forest_condition_type=forest_condition_type,
        forest_type=forest_type,
        agb_min=agb_min,
        agb_max=agb_max,
        agb_growth_min=agb_growth_min,
        agb_growth_max=agb_growth_max,
    )

# BelowGroundBiomass
BelowGroundBiomass.objects.all().delete()
with open("scripts/ipcc_data/BelowGroundBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    thresholds = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        threshold = sanitize(thresholds[i])
        if threshold == "> 125" or threshold == ">75":
            threshold = None
        elif "125" in threshold:
            threshold = 125
        elif "75" in threshold:
            threshold = 75

        land_use_type = LandUseType.objects.get_or_create(name=sanitize(head))[0]
        for row in data:
            continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
            BelowGroundBiomass.objects.get_or_create(
                land_use_type=land_use_type,
                continent=continent,
                threshold=threshold,
                value=parse_csv_number(row[i + 1]),
            )

# AboveGroundNetBiomasGrowth
AboveGroundNetBiomassGrowth.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "AboveGroundNetBiomassGrowth.csv"), header=0, sep=",")

for row in df.to_dict("records"):
    lut,_ = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))
    continent,_ = Continent.objects.get_or_create(name=sanitize(row["continent"]))
    gt_20_yrs = parse_csv_number(row["gt_20_yrs"])
    le_20_yrs = parse_csv_number(row["le_20_yrs"])

    print(
        lut,
        continent,
        gt_20_yrs,
        le_20_yrs
    )

    AboveGroundNetBiomassGrowth.objects.create(
        land_use_type = lut,
        continent = continent,
        value_after_20_years = gt_20_yrs,
        value_upto_20_years = le_20_yrs
    )

# CoastalAGB
CoastalAGB.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "CoastalAGB.csv"), header=0, sep=";")
with open("scripts/ipcc_data/CoastalAGB.csv", "r") as f:

    for row in df.to_dict("records"):
        climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
        moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]
        unit = row["unit"]
        value = parse_csv_number(row["value"])

        print(
            climate,
            moisture,
            land_use_type,
            unit,
            value,
        )

        CoastalAGB.objects.get_or_create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
            unit=unit
        )

# CoastalBGB
CoastalBGB.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "CoastalBGB.csv"), header=0, sep=";")

for row in df.to_dict("records"):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]
    unit = row["unit"]
    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        land_use_type,
        unit,
        value,
    )

    CoastalBGB.objects.get_or_create(
        land_use_type=land_use_type,
        climate=climate,
        moisture=moisture,
        value=value,
        unit=unit
    )

# CoastalLitter

CoastalLitter.objects.all().delete()
with open("scripts/ipcc_data/CoastalLitter.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            CoastalLitter.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

# CoastalDeadwood

CoastalDeadwood.objects.all().delete()
with open("scripts/ipcc_data/CoastalLitter.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            CoastalDeadwood.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

# DefaultSoilCarbonStock1Meter

DefaultSoilCarbonStock1Meter.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(
        os.path.dirname(__file__), "ipcc_data", "DefaultSoilCarbonStock1Meter.csv"
    ),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    soil_type = SoilType.objects.get_or_create(name=sanitize(row["soil_type"]))[0]
    unit = sanitize(row["unit"])

    for j, header in enumerate(df_headers2, start=4):
        land_use_type = LandUseType.objects.get_or_create(name=sanitize(df_headers2[j]))[0]

        print(
            climate,
            moisture,
            soil_type,
            land_use_type,
            row[df_headers2[j]],
        )

        DefaultSoilCarbonStock1Meter.objects.get_or_create(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            land_use_type=land_use_type,
            unit=unit,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

# RewettingCarbonFactor

RewettingCarbonFactor.objects.all().delete()

with open("scripts/ipcc_data/RewettingEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            RewettingCarbonFactor.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

# RewettingMethaneFactor



# DefaultSoilCarbonStock

DefaultSoilCarbonStock.objects.all().delete()

with open("scripts/ipcc_data/DefaultSoilCarbonStockMineralSoil.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            soil_type = SoilType.objects.get_or_create(name="Mineral")[0]

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            DefaultSoilCarbonStock.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                soil_type=soil_type,
                value=value,
            )

with open("scripts/ipcc_data/DefaultSoilCarbonStockOrganicSoil.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            soil_type = SoilType.objects.get_or_create(name="Organic")[0]

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            DefaultSoilCarbonStock.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                soil_type=soil_type,
                value=value,
            )

with open("scripts/ipcc_data/DefaultSoilCarbonStockAggregatedSoil.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            soil_type = SoilType.objects.get_or_create(name="Aggregated")[0]

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            DefaultSoilCarbonStock.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                soil_type=soil_type,
                value=value,
            )

# DrainageEmissionFactor
DrainageEmissionFactor.objects.all().delete()
with open("scripts/ipcc_data/DrainageEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            DrainageEmissionFactor.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

# ForestManagementAGB
ForestManagementAGB.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGB.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["vegetation_type"]))[0]
    continent = Continent.objects.get_or_create(name=sanitize(row["continent"]))[0]
    forest_condition_type = ForestConditionType.objects.get_or_create(name=sanitize(row["forest_condition_type"]))[0]
    forest_type = ForestType.objects.get_or_create(name=sanitize(row["forest_type"]))[0]
    agb_min = parse_csv_number(row["agb_min"], nan_value=0)
    agb_max = parse_csv_number(row["agb_max"], nan_value=0)
    agb_growth_min = parse_csv_number(row["agb_growth_min"], nan_value=0)
    agb_growth_max = parse_csv_number(row["agb_growth_max"], nan_value=0)

    print(
        land_use_type,
        continent,
        forest_condition_type,
        forest_type,
        agb_min,
        agb_max,
        agb_growth_min,
        agb_growth_max,
    )
    
    ForestManagementAGB.objects.get_or_create(
        land_use_type=land_use_type,
        continent=continent,
        forest_condition_type=forest_condition_type,
        forest_type=forest_type,
        agb_min=agb_min,
        agb_max=agb_max,
        agb_growth_min=agb_growth_min,
        agb_growth_max=agb_growth_max,
    )

CropNitrousEstimationDefaultFactor.objects.all().delete()
with open("scripts/ipcc_data/CropNitrousEstimationDefaultFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for row in data:
        land_use_type, _ = LandUseType.objects.get_or_create(name=sanitize(row[0]))
        CropNitrousEstimationDefaultFactor.objects.get_or_create(
            land_use_type=land_use_type,
            slope=parse_csv_number(row[1]),
            intercept=parse_csv_number(row[2]),
            n_ag_residues=parse_csv_number(row[3]),
            rs_t=parse_csv_number(row[4]),
            n_bg_t=parse_csv_number(row[5]),
        )

CroplandFLU.objects.all().delete()
with open("scripts/ipcc_data/CroplandFLU.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get_or_create(name=head)[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

            value = row[i + 2]

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            CroplandFLU.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

FiresCombustionFactor.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FiresCombustionFactors.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]
    combustion_factor = FiresCombustionFactor.objects.get_or_create(
        land_use_type=land_use_type,
        value=float(row["value"]),
    )[0]

    print(combustion_factor)


NitrousEmissionFactor.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NitrousEmissionFactors.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]
    name = sanitize(row["input_type"])
    value = parse_csv_number(row["value"])

    print(
        moisture,
        name,
        value,
    )

    NitrousEmissionFactor.objects.get_or_create(
        moisture=moisture,
        name=name,
        value=value,
    )
CropYieldStats.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "CropYieldStats.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    land_use_type = LandUseType.objects.get_or_create(name=sanitize(row["land_use_type"]))[0]
    continent = Region.objects.get_or_create(name=sanitize(row["continent"]))[0]
    yr_2016 = parse_csv_number(row["2016"])
    yr_2017 = parse_csv_number(row["2017"])
    yr_2018 = parse_csv_number(row["2018"])
    yr_2019 = parse_csv_number(row["2019"])
    yr_2020 = parse_csv_number(row["2020"])

    average = (yr_2016 + yr_2017 + yr_2018 + yr_2019 + yr_2020) / 5 / 10000

    print(
        f"{land_use_type}, {continent}, {yr_2016}, {yr_2017}, {yr_2018}, {yr_2019}, {yr_2020}, {average}"
    )

    stat = CropYieldStats.objects.get_or_create(
        land_use_type=land_use_type,
        continent=continent,
        year_2016=yr_2016,
        year_2017=yr_2017,
        year_2018=yr_2018,
        year_2019=yr_2019,
        year_2020=yr_2020,
        average=average,
    )[0]




# annualcropland = LandUseType.objects.get(name="Annual Cropland")
# crops = LandUseType.objects.filter(module_types__class_name="AnnualCropping").all()

with open("scripts/ipcc_data/ForestTotalBiomass.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head)
        if head == "":
            continue
        land_use_type = LandUseType.objects.get(name=head)

        for row in data:
            if row[i + 3] == "":
                continue

            climate = Climate.objects.get(name=sanitize(row[0]))
            moisture = Moisture.objects.get(name=sanitize(row[1]))
            continent = Region.objects.get(name=sanitize(row[2]))
            value = parse_csv_number(row[i + 3])

            # if land_use_type == annualcropland:
            #     for crop in crops:
            #         print(f"{crop}, {climate}, {moisture}, {continent}, {value}")

            #         ForestTotalBiomass.objects.get_or_create(
            #             land_use_type=crop,
            #             climate=climate,
            #             moisture=moisture,
            #             continent=continent,
            #             value=value,
            #         )

            print(f"{land_use_type}, {climate}, {moisture}, {continent}, {value}")

            ForestTotalBiomass.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                continent=continent,
                value=value,
            )

LargeFisheryFUI.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LargeFisheryFUI.csv"),
    header=[0],
    sep=";",
)

rows = df.to_dict("records")

for row in rows:
    gear_type = row["gear_type"]
    fish_type = row["fish_type"]
    value = parse_csv_number(row["value"])

    print(f"{gear_type}, {fish_type}, {value}")

    gear_type = LargeFisheryGearType.objects.get_or_create(name=capitalize_all(gear_type))[0]
    fish_type = FishType.objects.get_or_create(name=capitalize_all(fish_type))[0]

    LargeFisheryFUI.objects.get_or_create(fish_type=fish_type, gear_type=gear_type, value=value)


df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockVSER.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    production_type = LivestockProductionType.objects.get_or_create(name=sanitize(row["production_type"]))[0]
    region = IPCCRegion.objects.get_or_create(name=sanitize(row["ipcc_region"]))[0]

    for j, header in enumerate(df_headers):
        livestock_category = LivestockCategoryType.objects.get_or_create(name=sanitize(df_headers[j + 2]))[0]

        print(
            production_type,
            livestock_category,
            region,
            row[df_headers[j + 2]],
        )

        LivestockVSER.objects.get_or_create(
            livestock_production_type=production_type,
            livestock_category_type=livestock_category,
            ipcc_region=region,
            value=parse_csv_number(row[df_headers[j + 2]]),
        )

        if j + 2 == len(df_headers) - 1:
            break

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEFN2O.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(name=capitalize_all(row["emission_type"]))[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(name=capitalize_all(row["livestock_category_type"]))[0]
    livestock_production_type = LivestockProductionType.objects.get_or_create(name=capitalize_all(row["livestock_production_type"]))[0]
    climate = Climate.objects.get_or_create(name=capitalize_all(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=capitalize_all(row["moisture"]))[0]

    for j, header in enumerate(df_headers2):
        manure_management_type = ManureManagementType.objects.get_or_create(name=capitalize_all(df_headers2[j + 5]))[0]

        print(
            emission_type,
            livestock_category,
            livestock_production_type,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j + 5]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j + 5]]),
        )

        if j + 5 == len(df_headers2) - 1:
            break

ForestManagementAGB.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGB.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    print(row)

    land_use_type = LandUseType.objects.get(name=sanitize(row["land_use_type"]))
    continent = Region.objects.get(name=sanitize(row["continent"]))
    forest_condition_type = ForestConditionType.objects.get(name=sanitize(row["forest_condition_type"]))
    forest_type = ForestType.objects.get(name=sanitize(row["forest_type"]))
    agb_min = parse_csv_number(row["agb_min"], nan_value=0)
    agb_max = parse_csv_number(row["agb_max"], nan_value=0)
    agb_growth_min = parse_csv_number(row["agb_growth_min"], nan_value=0)
    agb_growth_max = parse_csv_number(row["agb_growth_max"], nan_value=0)

    print(
        land_use_type,
        continent,
        forest_condition_type,
        forest_type,
        agb_min,
        agb_max,
        agb_growth_min,
        agb_growth_max,
    )

    ForestManagementAGB.objects.get_or_create(
        land_use_type=land_use_type,
        continent=continent,
        forest_condition_type=forest_condition_type,
        forest_type=forest_type,
        agb_min=agb_min,
        agb_max=agb_max,
        agb_growth_min=agb_growth_min,
        agb_growth_max=agb_growth_max,
    )

FLUData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FLU.csv"),
    header=[0],
    sep=";",
)

annualcropland = LandUseType.objects.get(name="Annual Cropland")
crops = LandUseType.objects.filter(module_types__class_name="AnnualCropping").all()
perennials = LandUseType.objects.filter(module_types__class_name="PerennialCropping").all()

for i, row in df.iterrows():
    print(row)
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))
    if row["land_use_type"] != "Perennial Cropland":
        land_use_type = LandUseType.objects.get(name=sanitize(row["land_use_type"]))
    value = parse_csv_number(row["value"])

    if land_use_type == annualcropland:
        for crop in crops:
            print(
                climate,
                moisture,
                crop,
                value,
            )
            FLUData.objects.get_or_create(
                climate=climate,
                moisture=moisture,
                land_use_type=crop,
                value=value,
            )
    if row["land_use_type"] == "Perennial Cropland":
        for perennial in perennials:
            print(
                climate,
                moisture,
                perennial,
                value,
            )
            FLUData.objects.get_or_create(
                climate=climate,
                moisture=moisture,
                land_use_type=perennial,
                value=value,
            )
    else:
        print(
            climate,
            moisture,
            land_use_type,
            value,
        )

        FLUData.objects.get_or_create(
            climate=climate,
            moisture=moisture,
            land_use_type=land_use_type,
            value=value,
        )

# FIData.objects.all().delete()



FMGData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FMG.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    print(i, row)
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))
    tillage_management_type = TillageManagementType.objects.get(name=sanitize(row["tillage_management_type"]))

    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        tillage_management_type,
        value,
    )

    FMGData.objects.get_or_create(
        climate=climate,
        moisture=moisture,
        tillage_management_type=tillage_management_type,
        value=value,
    )

with open("scripts/ipcc_data/GrasslandAGB.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        climate = Climate.objects.get_or_create(name=sanitize(row[0]).title())[0]
        moisture = Moisture.objects.get_or_create(name=sanitize(row[1]).title())[0]

        value = row[2]

        print(f"{climate}, {moisture}, {value}")

        GrasslandAGB.objects.get_or_create(climate=climate, moisture=moisture, value=value)
        
with open("scripts/ipcc_data/SoilOrganicCarbon.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head)
        soil_type = SoilType.objects.get_or_create(name=sanitize(head))[0]
        for row in data:
            if sanitize(row[0]) == "":
                continue
            climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            # FIXME: N/A and NO mean 2 different things. Differentiate them
            value = row[i + 2] if row[i + 2] not in ["", "N/A", "NO"] else None
            SoilOrganicCarbon.objects.get_or_create(climate=climate, moisture=moisture, soil_type=soil_type, value=value)

GrasslandStockExchangeFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "GrasslandStockExchangeFactor.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    grassland_management_type = GrasslandManagementType.objects.get(name=sanitize(row["grassland_management_type"]))
    flu = parse_csv_number(row["flu"])
    fmg = parse_csv_number(row["fmg"])
    fi = parse_csv_number(row["fi"])

    print(
        climate,
        grassland_management_type,
        flu,
        fmg,
        fi,
    )

    GrasslandStockExchangeFactor.objects.get_or_create(
        climate=climate,
        grassland_management_type=grassland_management_type,
        flu=flu,
        fmg=fmg,
        fi=fi,
    )

FIData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FI.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))
    organic_input_type = OrganicInputType.objects.get(name=row["organic_input_type"])

    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        organic_input_type,
        value,
    )

    FIData.objects.get_or_create(
        climate=climate,
        moisture=moisture,
        organic_input_type=organic_input_type,
        value=value,
    )

    if i == len(df) - 1:
        break

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestCombustionFactor.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    land_use_type = LandUseType.objects.get(name=sanitize(row["land_use_type"]))
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    forest_type = ForestType.objects.get(name=sanitize(row["forest_type"]))

    co2 = parse_csv_number(row["co2"])
    ch4 = parse_csv_number(row["ch4"])
    n2o = parse_csv_number(row["n2o"])
    value = parse_csv_number(row["cf"])

    print(
        land_use_type,
        climate,
        forest_type,
        co2,
        ch4,
        n2o,
        value,
    )

    ForestCombustionFactor.objects.get_or_create(
        land_use_type=land_use_type,
        climate=climate,
        forest_type=forest_type,
        co2=co2,
        ch4=ch4,
        n2o=n2o,
        value=value,
    )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGBGrowth.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    try:
        climate = Climate.objects.get(name=row["climate"])
        region = Region.objects.get(name=row["region"])
        forest_type = ForestType.objects.get(name=row["forest_type"])
        land_use_type = LandUseType.objects.get(name=row["land_use_type"])
        gt_20_yrs = parse_csv_number(row["gt_20_yrs"])
        le_20_yrs = parse_csv_number(row["le_20_yrs"])

        print(climate, region, forest_type, land_use_type, gt_20_yrs, le_20_yrs)

        ForestManagementAGBGrowth.objects.get_or_create(climate=climate, region=region, forest_type=forest_type, land_use_type=land_use_type, value_after_20_years=gt_20_yrs, value_upto_20_years=le_20_yrs)
    except Exception as e:
        print(row)
        print(e)

LitterDeadwoodCarbonStock.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LitterDeadwoodCarbonStock.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    try:
        climate = Climate.objects.get(name=row["climate"])
        forest_type = ForestType.objects.get(name=row["forest_type"])
        land_use_type = LandUseType.objects.get(name=row["land_use_type"])
        litter = parse_csv_number(row["litter"])
        dw = parse_csv_number(row["deadwood"])

        print(climate, forest_type, land_use_type, litter, dw)

        LitterDeadwoodCarbonStock.objects.get_or_create(climate=climate, forest_type=forest_type, land_use_type=land_use_type, litter=litter, dw=dw)
    except Exception as e:
        print(row)
        print(e)

AfforestationFLU.objects.all().delete()

with open("scripts/ipcc_data/AfforestationFLU.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        print(head)
        land_use_type = LandUseType.objects.get(name=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name=sanitize(row[0]).title())
            moisture = Moisture.objects.get(name=sanitize(row[1]).title())

            value = row[i + 2]

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            AfforestationFLU.objects.get_or_create(
                land_use_type=land_use_type,
                climate=climate,
                moisture=moisture,
                value=value,
            )

lct = LivestockCategoryType.objects.all()
lpt = LivestockProductionType.objects.all()
tropicalmontane = Climate.objects.get(name="Tropical Montane")
dry = Moisture.objects.get(name="Dry")
emissiontypes = EmissionType.objects.all()
manuremanagementtypes = ManureManagementType.objects.all()

for livestock_category in lct:
    for livestock_production_type in lpt:
        for emission_type in emissiontypes:
            for manure_management_type in manuremanagementtypes:
                foo = LivestockManureEF.objects.filter(
                    livestock_category_type=livestock_category,
                    livestock_production_type=livestock_production_type,
                    emission_type=emission_type,
                    climate=tropicalmontane,
                    moisture=dry,
                    manure_management_type=manure_management_type,
                )

                if not foo:
                    LivestockManureEF.objects.create(
                        livestock_category_type=livestock_category,
                        livestock_production_type=livestock_production_type,
                        emission_type=emission_type,
                        climate=tropicalmontane,
                        moisture=dry,
                        manure_management_type=manure_management_type,
                        value=0,
                    )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEFPROPER.csv"),
    header=0,
    sep=";",
)


headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):

    print(row["climate"])
    print(row["moisture"])

    if row["moisture"] == "Montane":
        continue

    lcts = []
    if row["livestock_category_type"] == "All":
        lcts = LivestockCategoryType.objects.all()
    else:
        lcts = [LivestockCategoryType.objects.get(name=row["livestock_category_type"])]

    livestock_production_type = LivestockProductionType.objects.get(name=row["livestock_production_type"])
    climate = Climate.objects.get(name=row["climate"])
    moisture = Moisture.objects.get(name=row["moisture"])
    emission_type = EmissionType.objects.get(name=row["emission_type"])

    for j, header in enumerate(headers, start=5):

        if j == len(headers):
            break

        manure_management_type = ManureManagementType.objects.get(name=headers[j])
        value = parse_csv_number(row[headers[j]])

        for lct in lcts:
            print(
                livestock_production_type,
                lct,
                emission_type,
                manure_management_type,
                climate,
                moisture,
                value,
            )

            foo = LivestockManureEF.objects.filter(
                livestock_category_type=lct,
                livestock_production_type=livestock_production_type,
                emission_type=emission_type,
                manure_management_type=manure_management_type,
                climate=climate,
                moisture=moisture,
            ).first()

            if not foo:
                LivestockManureEF.objects.get_or_create(
                    livestock_category_type=lct,
                    livestock_production_type=livestock_production_type,
                    emission_type=emission_type,
                    manure_management_type=manure_management_type,
                    climate=climate,
                    moisture=moisture,
                    value=value,
                )
            else:
                foo.value = value
                foo.save()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGB.csv"),
    header=0,
    sep=";",
)

for i, row in df.iterrows():
    print(row)

    # TODO: Clarify with Lorenzo what sub-tropical is in terms of climate. Skip for now.
    if row["climate"] == "Sub-tropical":
        continue

    if row["climate"] == "Tropical":
        climates = [climate for climate in Climate.objects.filter(name__in=["Tropical"]).all()]
    elif row["climate"] == "Temperate":
        climates = [climate for climate in Climate.objects.filter(name__in=["Temperate"]).all()]
    else:
        climates = [Climate.objects.get(name=row["climate"])]

    print(row["land_use_type"])
    land_use_type = LandUseType.objects.get(name=row["land_use_type"])

    regions = []
    if "South" in row["region"] and "America" in row["region"]:
        print("South America")
        regions += [region for region in Region.objects.filter(name__in=["South America", "Caribbean", "Central America"])]
    if "North" in row["region"] and "America" in row["region"]:
        print("North America")
        regions += [region for region in Region.objects.filter(name__in=["North America"])]
    if "Asia" in row["region"]:
        print("Asia")
        regions += [region for region in Region.objects.filter(name__in=["Southern Asia", "Eastern Asia", "South-Eastern Asia", "Western Asia", "Central Asia"])]
    if "Africa" in row["region"]:
        print("Africa")
        regions += [region for region in Region.objects.filter(name__in=["Northern Africa", "Western Africa", "Central Africa", "Eastern Africa", "Southern Africa"])]

    if not regions:
        print("No regions found for ", row["region"])
        regions += [Region.objects.get(name=row["region"])]

    print(regions)

    forest_condition_type = ForestConditionType.objects.get(name=row["forest_condition_type"])

    forest_types = ForestType.objects.filter(name__in=["Natural", "Plantaion"]).all()

    if not isinstance(row["agb_range"], float) and len(row["agb_range"].split("-")) == 2:
        agb_range_min = parse_csv_number(row["agb_range"].split("-")[0])
        agb_range_max = parse_csv_number(row["agb_range"].split("-")[1])
    elif row["agb_range"] != "n.a.":
        agb_range_min = parse_csv_number(row["agb_range"])
        agb_range_max = parse_csv_number(row["agb_range"])

    if not row["agb_growth"].startswith("-") and not isinstance(row["agb_growth"], float) and len(row["agb_growth"].split("-")) == 2:
        agb_growth_min = parse_csv_number(row["agb_growth"].split("-")[0])
        agb_growth_max = parse_csv_number(row["agb_growth"].split("-")[1])
    elif row["agb_growth"] != "n.a.":
        agb_growth_min = parse_csv_number(row["agb_growth"])
        agb_growth_max = parse_csv_number(row["agb_growth"])

    if not isinstance(row["agb_range_plantation"], float) and len(row["agb_range_plantation"].split("-")) == 2:
        agb_range_min_plantation = parse_csv_number(row["agb_range_plantation"].split("-")[0])
        agb_range_max_plantation = parse_csv_number(row["agb_range_plantation"].split("-")[1])
    elif row["agb_range_plantation"] != "n.a.":
        agb_range_min_plantation = parse_csv_number(row["agb_range_plantation"])
        agb_range_max_plantation = parse_csv_number(row["agb_range_plantation"])

    if not isinstance(row["agb_growth_plantation"], float) and len(row["agb_growth_plantation"].split("-")) == 2:
        agb_growth_min_plantation = parse_csv_number(row["agb_growth_plantation"].split("-")[0])
        agb_growth_max_plantation = parse_csv_number(row["agb_growth_plantation"].split("-")[1])
    elif row["agb_growth_plantation"] != "n.a.":
        agb_growth_min_plantation = parse_csv_number(row["agb_growth_plantation"])
        agb_growth_max_plantation = parse_csv_number(row["agb_growth_plantation"])

    print("Climates: ", climates)
    print("Regions: ", regions)
    print("Forest Types: ", forest_types)

    for region in regions:
        for climate in climates:
            for type in forest_types:
                if type.name == "Plantation" and row["agb_range_plantation"] == "n.a." and row["agb_growth_plantation"] == "n.a.":
                    continue
                if type.name == "Natural" and row["agb_range"] == "n.a." and row["agb_growth"] == "n.a.":
                    continue
                if type.name == "Plantation" and forest_condition_type.name == "Primary":
                    continue

                print(
                    land_use_type,
                    region,
                    climate,
                    forest_condition_type,
                    type,
                    agb_range_min,
                    agb_range_max,
                    agb_growth_min,
                    agb_growth_max,
                    agb_range_min_plantation,
                    agb_range_max_plantation,
                    agb_growth_min_plantation,
                    agb_growth_max_plantation,
                )

                ForestManagementAGB.objects.get_or_create(
                    land_use_type=land_use_type,
                    region=region,
                    climate=climate,
                    forest_condition_type=forest_condition_type,
                    forest_type=type,
                    agb_min=agb_range_min,
                    agb_max=agb_range_max,
                    agb_growth_min=agb_growth_min,
                    agb_growth_max=agb_growth_max,
                )

# ForestManagementBGB.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementBGB_EasternAfrica_Addendum.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    try:
        climate = Climate.objects.get(name=row["climate"])
        region = Region.objects.get(name=row["region"])
        forest_type = ForestType.objects.get(name=row["forest_type"])
        land_use_type = LandUseType.objects.get(name=row["land_use_type"])
        threshold = row["threshold"]
        if threshold == "> 125" or threshold == ">75":
            threshold = None
        elif "125" in threshold:
            threshold = 125
        elif "75" in threshold:
            threshold = 75
        value = parse_csv_number(row["value"])

        print(climate, region, forest_type, land_use_type, threshold, value)

        ForestManagementBGB.objects.get_or_create(climate=climate, region=region, forest_type=forest_type, land_use_type=land_use_type, threshold=threshold, value=value)
    except Exception as e:
        print(row)
        print(e)

soil = SoilType.objects.get(name="Mineral")
for climate in Climate.objects.all():
    for moisture in climate.moistures.all():
        SoilOrganicCarbon.objects.get_or_create(climate=climate, moisture=moisture, soil_type=soil, value=0)

TotalBiomassAfterDefo.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "TotalBiomassAfterDefo.csv"),
    header=0,
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))
    region = Region.objects.get(name=sanitize(row["region"]))

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        print(headers[j])
        land_use_type = LandUseType.objects.get(name=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])
        if not value:
            continue

        print(
            land_use_type,
            climate,
            moisture,
            region,
            value,
        )

        TotalBiomassAfterDefo.objects.get_or_create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            continent=region,
            value=value,
        )

LandUseCarbonStockExchangeFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LandUseStockExchangeFactor.csv"),
    header=[0],
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])
        if not value:
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        LandUseCarbonStockExchangeFactor.objects.get_or_create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )

agbs = ForestManagementAGB.objects.all()
foo = ForestConditionType.objects.get(name="Secondary ≤20 Years")

for agb in agbs:
    if ">20" in agb.forest_condition_type.name:
        print(agb)
        agb.forest_condition_type = foo
        agb.save()

LivestockManureEF.objects.filter(livestock_category_type__name="Deer").all().delete()
LivestockManureEF.objects.filter(livestock_category_type__name="Ostrich").all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEFDeer.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get_or_create(name=capitalize_all(row["emission_type"]))[0]
    livestock_category = LivestockCategoryType.objects.get_or_create(name=sanitize(row["livestock_category_type"]))[0]

    livestock_production_type = LivestockProductionType.objects.get_or_create(name=sanitize(row["livestock_production_type"]))[0]
    climate = Climate.objects.get_or_create(name=sanitize(row["climate"]))[0]
    moisture = Moisture.objects.get_or_create(name=sanitize(row["moisture"]))[0]

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get_or_create(name=sanitize(df_headers2[j]))[0]

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get_or_create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break


# deer = LivestockCategoryType.objects.get(name="Deer")
# ostrich = LivestockCategoryType.objects.get(name="Ostrich")

# LivestockManureEF.objects.filter(livestock_category_type=deer).all().delete()
# LivestockManureEF.objects.filter(livestock_category_type=ostrich).all().delete()

# for climate in Climate.objects.all():
#     for moisture in Moisture.objects.all():
#         for mmt in ManureManagementType.objects.all().exclude(name="Other (Pls. Go Tier 2)"):
#             for lpt in LivestockProductionType.objects.all():
#                 foo = LivestockManureEF.objects.get_or_create(
#                     livestock_category_type=deer,
#                     livestock_production_type=lpt,
#                     emission_type=EmissionType.objects.get(name="CH4"),
#                     climate=climate,
#                     moisture=moisture,
#                     manure_management_type=mmt,
#                     value=0.22,
#                 )
#                 print(foo)

#                 foo2 = LivestockManureEF.objects.get_or_create(
#                     livestock_category_type=ostrich,
#                     livestock_production_type=lpt,
#                     emission_type=EmissionType.objects.get(name="CH4"),
#                     climate=climate,
#                     moisture=moisture,
#                     manure_management_type=mmt,
#                     value=5.67,
#                 )
#                 print(foo2)

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "DrainageEmissionFactors.csv"),
    header=[0],
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])
        if not value:
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        DrainageEmissionFactor.objects.get_or_create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "RewettingCarbonEmissionFactor.csv"),
    header=[0],
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))
    soil_type = SoilType.objects.get(name=sanitize(row["soil_type"]))

    for j, header in enumerate(headers, start=4):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])
        if not value:
            continue

        print(
            land_use_type,
            climate,
            moisture,
            soil_type,
            value,
        )

        RewettingCarbonFactor.objects.get_or_create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            value=value,
            # unit="tC/ha/yr",
        )

CoastalDeadwood.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "CoastalDeadwood.csv"),
    header=[0],
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        lut = LandUseType.objects.get(name=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])

        print(
            lut,
            climate,
            moisture,
            value,
        )

        CoastalDeadwood.objects.get_or_create(
            land_use_type=lut,
            climate=climate,
            moisture=moisture,
            value=value,
        )

RewettingMethaneFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "RewettingMethaneFactors_salinity-lt18.csv"),
    header=[0],
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))
    salinity = SalinityType.objects.get_or_create(value=sanitize(row["salinity_type"]))[0]

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])

        print(
            land_use_type,
            climate,
            moisture,
            salinity,
            value,
        )

        RewettingMethaneFactor.objects.get_or_create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            salinity=salinity,
            value=value,
        )

LivestockTAM.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockTAM.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    region = IPCCRegion.objects.filter(name__iexact=sanitize(row["ipcc_region"])).first()

    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category = LivestockCategoryType.objects.filter(name__iexact=sanitize(df_headers[j])).first()

        print(
            production_type,
            livestock_category,
            region,
            row[df_headers[j]],
        )

        LivestockTAM.objects.create(
            livestock_production_type=production_type,
            livestock_category_type=livestock_category,
            ipcc_region=region,
            value=parse_csv_number(row[df_headers[j]]),
        )

LivestockNER.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockNER.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    ipcc_region = IPCCRegion.objects.filter(name__iexact=sanitize(row["ipcc_region"])).first()
    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category_type = LivestockCategoryType.objects.filter(name__iexact=sanitize(df_headers[j])).first()

        print(
            ipcc_region,
            livestock_production_type,
            livestock_category_type,
            row[df_headers[j]],
        )

        LivestockNER.objects.create(
            ipcc_region=ipcc_region,
            livestock_production_type=livestock_production_type,
            livestock_category_type=livestock_category_type,
            value=parse_csv_number(row[df_headers[j]]),
        )

LivestockVSER.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockVSER.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    region = IPCCRegion.objects.filter(name__iexact=sanitize(row["ipcc_region"])).first()

    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category = LivestockCategoryType.objects.filter(name__iexact=sanitize(df_headers[j])).first()

        print(
            production_type,
            livestock_category,
            region,
            row[df_headers[j]],
        )

        LivestockVSER.objects.create(
            livestock_production_type=production_type,
            livestock_category_type=livestock_category,
            ipcc_region=region,
            value=parse_csv_number(row[df_headers[j]]),
        )

print("Deleting all LivestockManureEF...")
LivestockManureEF.objects.all().delete()
print("Deleted all LivestockManureEF.")

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockManureEF_CH4.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name=row["emission_type"])
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=sanitize(row["livestock_category_type"])).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    climate = Climate.objects.filter(name__iexact=sanitize(row["climate"])).first()
    moisture = Moisture.objects.filter(name__iexact=sanitize(row["moisture"])).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=sanitize(df_headers2[j])).first()

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewNewLivestockManureEF_N2O_semicolon.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name=sanitize(row["emission_type"]))
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=sanitize(row["livestock_category_type"])).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    climate = Climate.objects.filter(name__iexact=sanitize(row["climate"])).first()
    moisture = Moisture.objects.filter(name__iexact=sanitize(row["moisture"])).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=sanitize(df_headers2[j])).first()

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )


df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewNewLivestockManureEF_Volatilization.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name=sanitize(row["emission_type"]))
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=sanitize(row["livestock_category_type"])).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    climate = Climate.objects.filter(name__iexact=sanitize(row["climate"])).first()
    moisture = Moisture.objects.filter(name__iexact=sanitize(row["moisture"])).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=sanitize(df_headers2[j])).first()

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewNewLivestockManureEF_Leaching.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name=sanitize(row["emission_type"]))
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=sanitize(row["livestock_category_type"])).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    climate = Climate.objects.filter(name__iexact=sanitize(row["climate"])).first()
    moisture = Moisture.objects.filter(name__iexact=sanitize(row["moisture"])).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=sanitize(df_headers2[j])).first()

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.create(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

print("Deleting all MethaneEntericFermentationFactor...")
MethaneEntericFermentationFactor.objects.all().delete()
print("Deleted all MethaneEntericFermentationFactor.")

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockMethaneEntericFermentationFactor.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    ipcc_region = IPCCRegion.objects.filter(name__iexact=sanitize(row["ipcc_region"])).first()
    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()
    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category_type = LivestockCategoryType.objects.filter(name__iexact=sanitize(df_headers[j])).first()

        print(
            ipcc_region,
            livestock_production_type,
            livestock_category_type,
            row[df_headers[j]],
        )

        MethaneEntericFermentationFactor.objects.create(
            ipcc_region=ipcc_region,
            livestock_production_type=livestock_production_type,
            livestock_category_type=livestock_category_type,
            value=parse_csv_number(row[df_headers[j]]),
        )

print("Deleting all MethaneManureManagementFactor...")
LivestockAWMS.objects.all().delete()
print("Deleted all MethaneManureManagementFactor.")

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockAWMS.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    livestock_category_type = LivestockCategoryType.objects.filter(name__iexact=sanitize(row["livestock_category_type"])).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()

    ipcc_region = IPCCRegion.objects.filter(name__iexact=sanitize(row["ipcc_region"])).first()

    print(f"{livestock_category_type}, {livestock_production_type}, {ipcc_region}")

    for j, header in enumerate(df_headers, start=3):

        if j == len(df_headers):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=sanitize(df_headers[j])).first()

        print(manure_management_type)

        LivestockAWMS.objects.create(
            manure_management_type=manure_management_type,
            livestock_category_type=livestock_category_type,
            livestock_production_type=livestock_production_type,
            ipcc_region=ipcc_region,
            value=parse_csv_number(row[df_headers[j]]),
        )

"""

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LandUseNitrousEmissionFactor.csv"),
    header=0,
    sep=",",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    moisture = Moisture.objects.get(name=sanitize(row["moisture"]))

    print(moisture, row["value"])

    LandUseNitrousEmissionFactor.objects.create(
        moisture=moisture,
        value=parse_csv_number(row["value"]),
    )
