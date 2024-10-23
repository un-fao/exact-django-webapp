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


def parse_csv_number(number, nan_value=None):
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
        vegetation_type = VegetationType.objects.get(name__iexact=sanitize(head))
        for row in data:
            continent = Continent.objects.get(name__iexact=sanitize(row[0]))
            AboveGroundBiomass.objects.get(
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

        vegetation_type = VegetationType.objects.get(name__iexact=sanitize(head))
        for row in data:
            continent = Continent.objects.get(name__iexact=sanitize(row[0]))
            BelowGroundBiomass.objects.get(
                vegetation_type=vegetation_type,
                continent=continent,
                threshold=threshold,
                value=row[i + 1],
            )

with open("scripts/ipcc_data/LitterDeadwoodCarbonStock.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        vegtype, foo = VegetationType.objects.get(name__iexact=sanitize(row[0]))
        LitterDeadwoodCarbonStock.objects.get(
            vegetation_type=vegtype, litter=row[1], dw=row[2]
        )

with open("scripts/ipcc_data//Countries.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        Country.objects.get(
            name__iexact=sanitize(row[0]),
            continent=Continent.objects.get(name__iexact=sanitize(row[1])),
        )

with open("scripts/ipcc_data/AboveGroundNetBiomassGrowth.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        vegetation_type = VegetationType.objects.get(name__iexact=sanitize(row[0]))
        continent = Continent.objects.get(name__iexact=sanitize(row[1]))
        value_after_20_years = row[2]
        value_upto_20_years = row[3]
        AboveGroundNetBiomassGrowth.objects.get(
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
        land_use_type = LandUseType.objects.get(name__iexact=sanitize(row[0]))
        AfforestationCombustionFactorValues.objects.get(
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

        emission_factor_category = EmissionFactorCategory.objects.get(
            name__iexact=row[category]
        )

        BurningEmissionFactor.objects.get(
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
        vegetation_type = VegetationType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            CoastalAboveGroundBiomass.objects.get(
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
        vegetation_type = VegetationType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            CoastalBGAGRatio.objects.get(
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
        vegetation_type = VegetationType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            CoastalLitter.objects.get(
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
        vegetation_type = VegetationType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            RewettingCarbonFactor.objects.get(
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
        vegetation_type = VegetationType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))
            salinity = SalinityType.objects.get(value="<18")

            value = row[i + 2]

            print(f"{vegetation_type}, {climate}, {moisture}, {value}")

            RewettingMethaneFactor.objects.get(
                vegetation_type=vegetation_type,
                climate=climate,
                moisture=moisture,
                salinity=salinity,
                value=value,
            )

with open("scripts/ipcc_data/Atwood.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        # FIXME: Some countries have no continent in the database. Link them
        country = Country.objects.get(name__iexact=sanitize(row[0]))

        n = sanitize(row[1])
        area_2014_km2 = sanitize(row[2])
        mg_c_ha = sanitize(row[3])
        sd = sanitize(row[4]) if sanitize(row[4]) != "" else None
        score = sanitize(row[5]) if sanitize(row[5]) != "" else None

        Atwood.objects.get(
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
        tillage_type = TillageManagementType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{tillage_type}, {climate}, {moisture}, {value}")

            CroplandFMG.objects.get(
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
        tillage_type = TillageManagementType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{tillage_type}, {climate}, {moisture}, {value}")

            CroplandFMG.objects.get(
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

        land_use_type = LandUseType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))
            continent = Continent.objects.get(name__iexact=sanitize(row[2]))

            value = row[i + 4]

            if value == "" and i != 0:
                continue

            print(f"{land_use_type}, {climate}, {moisture}, {continent}, {value}")

            PerennialAGB.objects.get(
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
        land_use_type = LandUseType.objects.get(name__iexact=head)
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

            climate = Climate.objects.get(name__iexact=sanitize(row[0]).title())

            print(f"i = {i}")
            print(f"{land_use_type}, {climate}, {moisture}")

            value = row[i + 2]

            print(f"Value {value}")

            PerennialMaxAGB.objects.get(
                land_use_type=land_use_type, climate=climate, value=value
            )

with open("scripts/ipcc_data/GrasslandSOC.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        grassland_management_type = GrasslandManagementType.objects.get(
            name__iexact=sanitize(row[0]).title()
        )
        value = row[1]

        print(f"{grassland_management_type}, {value}")

        GrasslandSOC.objects.get(
            grassland_management_type=grassland_management_type, value=value
        )

LivestockManureEF.objects.all().delete()

# print("AO")
# nsed = LargeFisheryFUI.objects.filter(gear_type__name__iexact="Not Specified")
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
        ipcc_region = IPCCRegion.objects.get(name__iexact=row[0])


with open("scripts/ipcc_data/SmallFisheryDatabaseFish.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        gear_type = SmallFisheryGearType.objects.get(name__iexact=head)
        for row in data:
            if row[i + 1] == "":
                continue

            fishery_type = FisheryType.objects.get(
                name__iexact=sanitize(row[0]).title()
            )
            value = float(row[i + 1])

            print(f"{fishery_type}, {gear_type}, {value}")

            SmallFisheryFUI.objects.get(
                fishery_type=fishery_type, gear_type=gear_type, value=value
            )




with open("scripts/ipcc_data/LargeFisheryFUI.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        gear_type = LargeFisheryGearType.objects.get(name__iexact=head)
        for row in data:
            if row[i + 1] == "":
                continue

            fish_type = FishType.objects.get(name__iexact=sanitize(row[0]).title())
            value = float(row[i + 1])

            print(f"{fish_type}, {gear_type}, {value}")

            LargeFisheryFUI.objects.get(
                fish_type=fish_type, gear_type=gear_type, value=value
            )




df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "DefaultEmissionFactors.csv"),
    header=[0],
    sep=",",
)

for i, row in df.iterrows():
    organic_input_type = OrganicInputType.objects.get(
        name__iexact=sanitize(row["organic_input_type"])
    )
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    emission_factor = DefaultEmissionFactor.objects.get(
        organic_input_type=organic_input_type,
        moisture=moisture,
        value=float(row["value"]),
    )

    print(emission_factor)


CropYieldStats.objects.all().delete()



with open("scripts/ipcc_data/CroplandFI.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        organic_input_type = OrganicInputType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{organic_input_type}, {climate}, {moisture}, {value}")

            CroplandFI.objects.get(
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
    organic_input_type = OrganicInputType.objects.get(
        name__iexact=sanitize(row["organic_input_type"])
    )
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    emission_factor = DefaultEmissionFactor.objects.get(
        organic_input_type=organic_input_type,
        moisture=moisture,
        value=float(row["value"]),
    )

    print(emission_factor)

Atwood.objects.all().delete()

with open("scripts/ipcc_data/Atwood.csv", "r") as f:
    reader = csv.reader(f)
    data = list(reader)

    for row in data:
        # FIXME: Some countries have no continent in the database. Link them
        country = Country.objects.get(name__iexact=capitalize_all(row[0]))

        n = sanitize(row[1])
        area_2014_km2 = sanitize(row[2])
        mg_c_ha = sanitize(row[3])
        sd = sanitize(row[4]) if sanitize(row[4]) != "" else None
        score = sanitize(row[5]) if sanitize(row[5]) != "" else None

        Atwood.objects.get(
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
        head = capitalize_all(sanitize(head)).title()
        tillage_type = TillageManagementType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{tillage_type}, {climate}, {moisture}, {value}")

            CroplandFMG.objects.get(
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
    ipcc_region = IPCCRegion.objects.get(name__iexact=sanitize(row["ipcc_region"]))
    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=sanitize(row["livestock_production_type"])
    )
    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category_type = LivestockCategoryType.objects.get(
            name__iexact=sanitize(df_headers[j])
        )

        print(
            ipcc_region,
            livestock_production_type,
            livestock_category_type,
            row[df_headers[j]],
        )

        MethaneEntericFermentationFactor.objects.get(
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
    emission_type = EmissionType.objects.get(
        name__iexact=capitalize_all(row["emission_type"])
    )
    livestock_category = LivestockCategoryType.objects.get(
        name__iexact=sanitize(row["livestock_category_type"])
    )

    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=sanitize(row["livestock_production_type"])
    )
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get(
            name__iexact=sanitize(df_headers2[j])
        )

        print(
            emission_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get(
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
    emission_type = EmissionType.objects.get(
        name__iexact=capitalize_all(row["emission_type"])
    )
    livestock_category = LivestockCategoryType.objects.get(
        name__iexact=sanitize(row["livestock_category_type"])
    )

    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=sanitize(row["livestock_production_type"])
    )
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get(
            name__iexact=sanitize(df_headers2[j])
        )

        print(
            emission_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get(
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
    production_type = LivestockProductionType.objects.get(
        name__iexact=capitalize_all(row["production_type"])
    )
    region = IPCCRegion.objects.get(name__iexact=row["ipcc_region"])

    for j, header in enumerate(df_headers, start=2):
        if j == len(df_headers):
            break

        livestock_category = LivestockCategoryType.objects.get(
            name__iexact=capitalize_all(df_headers[j])
        )

        print(
            production_type,
            livestock_category,
            region,
            row[df_headers[j]],
        )

        LivestockTAM.objects.get(
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
    emission_type = EmissionType.objects.get(
        name__iexact=sanitize(row["emission_type"])
    )
    livestock_category = LivestockCategoryType.objects.get(
        name__iexact=sanitize(row["livestock_category_type"])
    )

    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=sanitize(row["livestock_production_type"])
    )
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get(
            name__iexact=sanitize(df_headers2[j])
        )

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get(
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
    livestock_category_type = LivestockCategoryType.objects.get(
        name__iexact=capitalize_all(row["livestock_category_type"])
    )

    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=capitalize_all(row["livestock_production_type"])
    )

    ipcc_region = IPCCRegion.objects.get(name__iexact=row["ipcc_region"])

    print(f"{livestock_category_type}, {livestock_production_type}, {ipcc_region}")

    for j in range(3, len(df_headers)):
        manure_management_type = ManureManagementType.objects.get(
            name__iexact=capitalize_all(df_headers[j])
        )

        print(manure_management_type)

        LivestockAnimalWasteManagementSystem.objects.get(
            manure_management_type=manure_management_type,
            livestock_category_type=livestock_category_type,
            livestock_production_type=livestock_production_type,
            ipcc_region=ipcc_region,
            value=parse_csv_number(row[df_headers[j]]),
        )

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
    emission_type = EmissionType.objects.get(
        name__iexact=sanitize(row["emission_type"])
    )
    livestock_category = LivestockCategoryType.objects.get(
        name__iexact=sanitize(row["livestock_category"])
    )

    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=sanitize(row["livestock_production"])
    )
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get(
            name__iexact=sanitize(df_headers2[j])
        )

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get(
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
    emission_type = EmissionType.objects.get(
        name__iexact=capitalize_all(row["emission_type"])
    )
    livestock_category = LivestockCategoryType.objects.get(
        name__iexact=sanitize(row["livestock_category_type"])
    )

    livestock_production_type = LivestockProductionType.objects.get(
        name__iexact=sanitize(row["livestock_production_type"])
    )
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.get(
            name__iexact=sanitize(df_headers2[j])
        )

        print(
            emission_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get(
            emission_type=emission_type,
            livestock_category_type=livestock_category,
            livestock_production_type=livestock_production_type,
            climate=climate,
            moisture=moisture,
            manure_management_type=manure_management_type,
            value=parse_csv_number(row[df_headers2[j]]),
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
        MacroFuelType.objects.get(name__iexact=sanitize(row["macro_fuel_type"]))
        if row["macro_fuel_type"]
        else None
    )
    fuel_use_type = (
        FuelUseType.objects.get(name__iexact=sanitize(row["fuel_use_type"]))
        if pd.notna(row["fuel_use_type"])
        else None
    )
    fuel_type = (
        FuelType.objects.get(
            name__iexact=sanitize(row["fuel_type"]),
            macro_type=macro_fuel_type,
            fuel_use_type=fuel_use_type,
        )
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

    EnergyDefaultEmissionFactor.objects.get(
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
    os.path.join(os.path.dirname(__file__), "ipcc_data", "IrrigationPhaseData.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    fuel_type = FuelType.objects.get(
        name__iexact=sanitize(row["fuel_type"]),
    )

    print(
        fuel_type,
        row["emission_factor"],
        row["calorific_value"],
        row["co2_emissions"],
        row["ch4_emissions"],
        row["n2o_emissions"],
        row["density"],
    )

    data = IrrigationPhaseData.objects.get(
        fuel_type=fuel_type,
        emission_factor=parse_csv_number(row["emission_factor"], nan_value=None),
        calorific_value=parse_csv_number(row["calorific_value"], nan_value=None),
        co2_emissions=parse_csv_number(row["co2_emissions"], nan_value=None),
        ch4_emissions=parse_csv_number(row["ch4_emissions"], nan_value=None),
        n2o_emissions=parse_csv_number(row["n2o_emissions"], nan_value=None),
        density=parse_csv_number(row["density"], nan_value=None),
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
    continent = Continent.objects.get(name__iexact=sanitize(row["continent"]))

    print(continent, row["value"], row["cultivation_period"])

    bar_start = parse_csv_number(row["value"], nan_value=0)
    bar_end = parse_csv_number(row['cultivation_period'], nan_value=0)

    RiceDefaultEmissionFactor.objects.get(
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
    organic_amendment_type = OrganicAmendmentType.objects.get(name__iexact=sanitize(row["organic_amendment_type"]))

    print(continent, row["organic_amendment_type"], row["value"])

    value = parse_csv_number(row["value"], nan_value=0)

    RiceSFO.objects.get(
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
    water_management_type_before_cultivation = WaterManagementTypeBeforeCultivation.objects.get(name__iexact=sanitize(row["water_regime_type"]))
    value = parse_csv_number(row["value"], nan_value=0)

    print(continent, row["water_regime_type"], value)

    RiceSFP.objects.get(
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
    water_management_type_after_cultivation = WaterManagementTypeAfterCultivation.objects.get(name__iexact=sanitize(row["water_regime_type"]))
    value = parse_csv_number(row["value"], nan_value=0)

    print(continent, row["water_regime_type"], value)

    RiceSFW.objects.get(
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
    continent = Continent.objects.get(name__iexact=sanitize(row["continent"]))
    value = parse_csv_number(row["value"], nan_value=0)

    print(continent, value)

    RiceYield.objects.get(
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
    trophic_type = TrophicType.objects.get(name__iexact=sanitize(row["trophic_type"]))
    value = parse_csv_number(row["value"], nan_value=0)
    chloa = parse_csv_number(row["chloa"], nan_value=0)

    print(trophic_type, value, chloa)

    TrophicStateFactor.objects.get(
        trophic_type=trophic_type,
        value=value,
        chloa=chloa,
    )

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
    road_type = RoadType.objects.get(name__iexact=sanitize(row["road_type"]))
    value = parse_csv_number(row["value"], nan_value=0)

    print(road_type, value)

    RoadEmissionFactor.objects.get(
        road_type=road_type,
        value=value,
    )

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "RewettingEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    soil_type = SoilType.objects.get(name__iexact=sanitize(row["soil_type"]))

    for j, header in enumerate(df_headers2, start=4):
        vegetation_type = VegetationType.objects.get(name__iexact=sanitize(df_headers2[j]))

        print(
            climate,
            moisture,
            soil_type,
            vegetation_type,
            row[df_headers2[j]],
        )

        RewettingEmissionFactor.objects.get(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            vegetation_type=vegetation_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break
            


df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PeatExtractionConversionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    peat_type = PeatType.objects.get(name__iexact=sanitize(row["peat_type"]))
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    weight = parse_csv_number(row["weight"], nan_value=0)
    volume = parse_csv_number(row["volume"], nan_value=0)

    print(
        peat_type,
        climate,
        moisture,
        weight,
        volume,
    )

    PeatExtractionConversionFactor.objects.get(
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
        land_use_type = LandUseType.objects.get(name__iexact=sanitize(row[0]))
        CropNitrousEstimationDefaultFactor.objects.get(
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
    land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
    continent = Continent.objects.get(name__iexact=sanitize(row["continent"]))
    yr_2016 = float(row["2016"])
    yr_2017 = float(row["2017"])
    yr_2018 = float(row["2018"])
    yr_2019 = float(row["2019"])
    yr_2020 = float(row["2020"])

    average = (yr_2016 + yr_2017 + yr_2018 + yr_2019 + yr_2020) / 5 / 10000

    print(
        f"{land_use_type}, {continent}, {yr_2016}, {yr_2017}, {yr_2018}, {yr_2019}, {yr_2020}, {average}"
    )

    stat = CropYieldStats.objects.get(
        land_use_type=land_use_type,
        continent=continent,
        year_2016=yr_2016,
        year_2017=yr_2017,
        year_2018=yr_2018,
        year_2019=yr_2019,
        year_2020=yr_2020,
        average=average,
    )

CropNitrousEstimationDefaultFactor.objects.all().delete()
with open("scripts/ipcc_data/CropNitrousEstimationDefaultFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for row in data:
        land_use_type = LandUseType.objects.get(name__iexact=sanitize(row[0]))
        CropNitrousEstimationDefaultFactor.objects.get(
            land_use_type=land_use_type,
            slope=row[1] if row[1] != "NA" else None,
            intercept=row[2] if row[2] != "NA" else None,
            n_ag_residues=row[3],
            rs_t=row[4],
            n_bg_t=row[5],
        )

# PerennialMaxAGB.objects.all().delete()
# with open("scripts/ipcc_data/PerennialMaximumAGB_C.csv", "r") as f:
#     reader = csv.reader(f)
#     header = next(reader, None)
#     data = list(reader)

#     for i, head in enumerate(header):
#         land_use_type = LandUseType.objects.get(name__iexact=head)
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

#             climate = Climate.objects.get(name__iexact=sanitize(row[0]))
#             moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

#             print(f"i = {i}")
#             print(f"{land_use_type}, {climate}, {moisture}")

#             value = row[i + 2]

#             print(f"Value {value}")

#             PerennialMaxAGB.objects.get(
#                 land_use_type=land_use_type,
#                 climate=climate,
#                 value=value,
#             )

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
    land_use_type: LandUseType = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))

    land_use_type.climates.add(Climate.objects.get(name__iexact=sanitize(row["climate"])))
    if pd.notna(row["moisture"]):
        land_use_type.moistures.add(Moisture.objects.get(name__iexact=sanitize(row["moisture"])))
    land_use_type.module_types.add(ModuleType.objects.get(class_name__iexact=row["module_type"]))

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
    lut,_ = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
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
    lut,_ = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
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
        land_use_type = LandUseType.objects.get(name__iexact=sanitize(head))
        for row in data:
            continent = Continent.objects.get(name__iexact=sanitize(row[0]))
            AboveGroundBiomass.objects.get(
                land_use_type=land_use_type,
                continent=continent,
                value=parse_csv_number(row[i + 1])
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

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(head))
        for row in data:
            continent = Continent.objects.get(name__iexact=sanitize(row[0]))
            BelowGroundBiomass.objects.get(
                land_use_type=land_use_type,
                continent=continent,
                threshold=threshold,
                value=parse_csv_number(row[i + 1]),
            )

# AboveGroundNetBiomasGrowth
AboveGroundNetBiomassGrowth.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "AboveGroundNetBiomassGrowth.csv"), header=0, sep=",")

for row in df.to_dict("records"):
    lut,_ = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
    continent,_ = Continent.objects.get(name__iexact=sanitize(row["continent"]))
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

# CoastalLitter

CoastalLitter.objects.all().delete()
with open("scripts/ipcc_data/CoastalLitter.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = parse_csv_number(row[i + 2])

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            CoastalLitter.objects.get(
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
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    soil_type = SoilType.objects.get(name__iexact=sanitize(row["soil_type"]))
    unit = sanitize(row["unit"])

    for j, header in enumerate(df_headers2, start=4):
        land_use_type = LandUseType.objects.get(name__iexact=sanitize(df_headers2[j]))

        print(
            climate,
            moisture,
            soil_type,
            land_use_type,
            row[df_headers2[j]],
        )

        DefaultSoilCarbonStock1Meter.objects.get(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            land_use_type=land_use_type,
            unit=unit,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

# RewettingMethaneFactor

# DrainageEmissionFactor
DrainageEmissionFactor.objects.all().delete()
with open("scripts/ipcc_data/DrainageEmissionFactors.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head).title()
        land_use_type = LandUseType.objects.get(name__iexact=head)
        for row in data:
            if sanitize(row[0]) == "":
                continue

            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))

            value = row[i + 2]

            print(f"{land_use_type}, {climate}, {moisture}, {value}")

            DrainageEmissionFactor.objects.get(
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
    land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["vegetation_type"]))
    continent = Continent.objects.get(name__iexact=sanitize(row["continent"]))
    forest_condition_type = ForestConditionType.objects.get(name__iexact=sanitize(row["forest_condition_type"]))
    forest_type = ForestType.objects.get(name__iexact=sanitize(row["forest_type"]))
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
    
    ForestManagementAGB.objects.get(
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
        land_use_type, _ = LandUseType.objects.get(name__iexact=sanitize(row[0]))
        CropNitrousEstimationDefaultFactor.objects.get(
            land_use_type=land_use_type,
            slope=parse_csv_number(row[1]),
            intercept=parse_csv_number(row[2]),
            n_ag_residues=parse_csv_number(row[3]),
            rs_t=parse_csv_number(row[4]),
            n_bg_t=parse_csv_number(row[5]),
        )

FiresCombustionFactor.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FiresCombustionFactors.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
    combustion_factor = FiresCombustionFactor.objects.get(
        land_use_type=land_use_type,
        value=float(row["value"]),
    )

    print(combustion_factor)


NitrousEmissionFactor.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NitrousEmissionFactors.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    name = sanitize(row["input_type"])
    value = parse_csv_number(row["value"])

    print(
        moisture,
        name,
        value,
    )

    NitrousEmissionFactor.objects.get(
        moisture=moisture,
        name__iexact=name,
        value=value,
    )
CropYieldStats.objects.all().delete()
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "CropYieldStats.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
    continent = Region.objects.get(name__iexact=sanitize(row["continent"]))
    yr_2016 = parse_csv_number(row["2016"])
    yr_2017 = parse_csv_number(row["2017"])
    yr_2018 = parse_csv_number(row["2018"])
    yr_2019 = parse_csv_number(row["2019"])
    yr_2020 = parse_csv_number(row["2020"])

    average = (yr_2016 + yr_2017 + yr_2018 + yr_2019 + yr_2020) / 5 / 10000

    print(
        f"{land_use_type}, {continent}, {yr_2016}, {yr_2017}, {yr_2018}, {yr_2019}, {yr_2020}, {average}"
    )

    stat = CropYieldStats.objects.get(
        land_use_type=land_use_type,
        continent=continent,
        year_2016=yr_2016,
        year_2017=yr_2017,
        year_2018=yr_2018,
        year_2019=yr_2019,
        year_2020=yr_2020,
        average=average,
    )

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockVSER.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    production_type = LivestockProductionType.objects.get(name__iexact=sanitize(row["production_type"]))
    region = IPCCRegion.objects.get(name__iexact=sanitize(row["ipcc_region"]))

    for j, header in enumerate(df_headers):
        livestock_category = LivestockCategoryType.objects.get(name__iexact=sanitize(df_headers[j + 2]))

        print(
            production_type,
            livestock_category,
            region,
            row[df_headers[j + 2]],
        )

        LivestockVSER.objects.get(
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
    emission_type = EmissionType.objects.get(name__iexact=capitalize_all(row["emission_type"]))
    livestock_category = LivestockCategoryType.objects.get(name__iexact=capitalize_all(row["livestock_category_type"]))
    livestock_production_type = LivestockProductionType.objects.get(name__iexact=capitalize_all(row["livestock_production_type"]))
    climate = Climate.objects.get(name__iexact=capitalize_all(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=capitalize_all(row["moisture"]))

    for j, header in enumerate(df_headers2):
        manure_management_type = ManureManagementType.objects.get(name__iexact=capitalize_all(df_headers2[j + 5]))

        print(
            emission_type,
            livestock_category,
            livestock_production_type,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j + 5]],
        )

        LivestockManureEF.objects.get(
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

with open("scripts/ipcc_data/SoilOrganicCarbon.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    data = list(reader)

    for i, head in enumerate(header):
        head = sanitize(head)
        soil_type = SoilType.objects.get(name__iexact=sanitize(head))
        for row in data:
            if sanitize(row[0]) == "":
                continue
            climate = Climate.objects.get(name__iexact=sanitize(row[0]))
            moisture = Moisture.objects.get(name__iexact=sanitize(row[1]))
            # FIXME: N/A and NO mean 2 different things. Differentiate them
            value = row[i + 2] if row[i + 2] not in ["", "N/A", "NO"] else None
            SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type, value=value)

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGBGrowth.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    try:
        climate = Climate.objects.get(name__iexact=row["climate"])
        region = Region.objects.get(name__iexact=row["region"])
        forest_type = ForestType.objects.get(name__iexact=row["forest_type"])
        land_use_type = LandUseType.objects.get(name__iexact=row["land_use_type"])
        gt_20_yrs = parse_csv_number(row["gt_20_yrs"])
        le_20_yrs = parse_csv_number(row["le_20_yrs"])

        print(climate, region, forest_type, land_use_type, gt_20_yrs, le_20_yrs)

        ForestManagementAGBGrowth.objects.get(climate=climate, region=region, forest_type=forest_type, land_use_type=land_use_type, value_after_20_years=gt_20_yrs, value_upto_20_years=le_20_yrs)
    except Exception as e:
        print(row)
        print(e)

lct = LivestockCategoryType.objects.all()
lpt = LivestockProductionType.objects.all()
tropicalmontane = Climate.objects.get(name__iexact="Tropical Montane")
dry = Moisture.objects.get(name__iexact="Dry")
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
        lcts = [LivestockCategoryType.objects.get(name__iexact=row["livestock_category_type"])]

    livestock_production_type = LivestockProductionType.objects.get(name__iexact=row["livestock_production_type"])
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])
    emission_type = EmissionType.objects.get(name__iexact=row["emission_type"])

    for j, header in enumerate(headers, start=5):

        if j == len(headers):
            break

        manure_management_type = ManureManagementType.objects.get(name__iexact=headers[j])
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
                LivestockManureEF.objects.get(
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

soil = SoilType.objects.get(name__iexact="Mineral")
for climate in Climate.objects.all():
    for moisture in climate.moistures.all():
        SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil, value=0)

agbs = ForestManagementAGB.objects.all()
foo = ForestConditionType.objects.get(name__iexact="Secondary ≤20 Years")

for agb in agbs:
    if ">20" in agb.forest_condition_type.name:
        print(agb)
        agb.forest_condition_type = foo
        agb.save()

LivestockManureEF.objects.filter(livestock_category_type__name__iexact="Deer").all().delete()
LivestockManureEF.objects.filter(livestock_category_type__name__iexact="Ostrich").all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEFDeer.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name__iexact=capitalize_all(row["emission_type"]))
    livestock_category = LivestockCategoryType.objects.get(name__iexact=sanitize(row["livestock_category_type"]))

    livestock_production_type = LivestockProductionType.objects.get(name__iexact=sanitize(row["livestock_production_type"]))
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(df_headers2, start=5):
        manure_management_type = ManureManagementType.objects.get(name__iexact=sanitize(df_headers2[j]))

        print(
            emission_type,
            livestock_production_type,
            livestock_category,
            climate,
            moisture,
            manure_management_type,
            row[df_headers2[j]],
        )

        LivestockManureEF.objects.get(
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


# deer = LivestockCategoryType.objects.get(name__iexact="Deer")
# ostrich = LivestockCategoryType.objects.get(name__iexact="Ostrich")

# LivestockManureEF.objects.filter(livestock_category_type=deer).all().delete()
# LivestockManureEF.objects.filter(livestock_category_type=ostrich).all().delete()

# for climate in Climate.objects.all():
#     for moisture in Moisture.objects.all():
#         for mmt in ManureManagementType.objects.all().exclude(name__iexact="Other (Pls. Go Tier 2)"):
#             for lpt in LivestockProductionType.objects.all():
#                 foo = LivestockManureEF.objects.get(
#                     livestock_category_type=deer,
#                     livestock_production_type=lpt,
#                     emission_type=EmissionType.objects.get(name__iexact="CH4"),
#                     climate=climate,
#                     moisture=moisture,
#                     manure_management_type=mmt,
#                     value=0.22,
#                 )
#                 print(foo)

#                 foo2 = LivestockManureEF.objects.get(
#                     livestock_category_type=ostrich,
#                     livestock_production_type=lpt,
#                     emission_type=EmissionType.objects.get(name__iexact="CH4"),
#                     climate=climate,
#                     moisture=moisture,
#                     manure_management_type=mmt,
#                     value=5.67,
#                 )
#                 print(foo2)

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "RewettingCarbonEmissionFactor.csv"),
    header=[0],
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    soil_type = SoilType.objects.get(name__iexact=sanitize(row["soil_type"]))

    for j, header in enumerate(headers, start=4):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(headers[j]))
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

        RewettingCarbonFactor.objects.get(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            value=value,
            # unit="tC/ha/yr",
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

# Climate.objects.get(name__iexact="Tropical Montane").delete()
Moisture.objects.get(name__iexact="Montane").delete()
Climate.objects.create(name="Tropical Montane")

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestClimateAssociationTable.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for lut in LandUseType.objects.filter(module_types__name__in=["Forest Management"]).all():
    print(f"Clearing climates for {lut.name}")
    lut.climates.clear()
    lut.save()

for i, row in enumerate(rows):
    lut = LandUseType.objects.get(name__iexact=sanitize(row["forest_type"]))
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    lut.climates.add(climate)
    lut.save()
    print(f"Added {climate} to {lut}")

print("Deleting all SettlementTypes...")
SettlementType.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "SettlementTypes.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    name = row["name"]
    SettlementType.objects.create(name=name)
    print(f"Added {name}")

LandUseCarbonStockExchangeFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "LandUseStockExchangeFactor.csv"),
    header=[0],
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])
        if not value:
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        LandUseCarbonStockExchangeFactor.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )

AfforestationLandUseStockExchangeFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "AfforestationLandUseStockExchangeFactor.csv"),
    header=0,
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(headers[j]))
        value = row[headers[j]]

        if not value or pd.isna(value):
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        AfforestationLandUseStockExchangeFactor.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )

# CoastalAGB
CoastalAGB.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "CoastalAGB.csv"), header=0, sep=";")

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
    unit = row["unit"]
    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        land_use_type,
        unit,
        value,
    )

    CoastalAGB.objects.create(land_use_type=land_use_type, climate=climate, moisture=moisture, value=value, unit=unit)

with open("scripts/ipcc_data/CoastalAGB.csv", "r") as f:

    for row in df.to_dict("records"):
        climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
        moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
        land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
        unit = row["unit"]
        value = parse_csv_number(row["value"])

        print(
            climate,
            moisture,
            land_use_type,
            unit,
            value,
        )

        CoastalAGB.objects.create(land_use_type=land_use_type, climate=climate, moisture=moisture, value=value, unit=unit)

# CoastalBGB
CoastalBGB.objects.all().delete()
df = pd.read_csv(os.path.join(os.path.dirname(__file__), "ipcc_data", "CoastalBGB.csv"), header=0, sep=";")

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for row in rows:
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
    unit = row["unit"]
    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        land_use_type,
        unit,
        value,
    )

    CoastalBGB.objects.create(land_use_type=land_use_type, climate=climate, moisture=moisture, value=value, unit=unit)

# RewettingCarbonFactor

RewettingCarbonFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "RewettingCarbonEmissionFactor.csv"),
    header=[0],
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    soil_type = SoilType.objects.get(name__iexact=sanitize(row["soil_type"]))

    for j, header in enumerate(headers, start=4):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(headers[j]))
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

        RewettingCarbonFactor.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            value=value,
            # unit="tC/ha/yr",
        )

DefaultSoilCarbonStock1Meter.objects.all().delete()
DefaultSoilCarbonStock.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "DefaultSoilCarbonStock1Meter.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    soil_type = SoilType.objects.get(name__iexact=sanitize(row["soil_type"]))
    unit = sanitize(row["unit"])

    for j, header in enumerate(df_headers2, start=4):

        if j == len(df_headers2):
            break

        vegetation_type = LandUseType.objects.get(name__iexact=sanitize(df_headers2[j]))

        print(
            climate,
            moisture,
            soil_type,
            vegetation_type,
            row[df_headers2[j]],
        )

        DefaultSoilCarbonStock1Meter.objects.create(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            land_use_type=vegetation_type,
            unit=unit,
            value=row[df_headers2[j]],
        )

        DefaultSoilCarbonStock.objects.create(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            land_use_type=vegetation_type,
            value=row[df_headers2[j]],
        )


PerennialAGB.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PerennialAGB.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    continent = Region.objects.get(name__iexact=sanitize(row["region"]))

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])

        if pd.isna(value):
            continue

        print(
            land_use_type,
            climate,
            moisture,
            continent,
            value,
        )

        PerennialAGB.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            continent=continent,
            value=value,
        )

PerennialMaxAGB.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PerennialMaxAGB.csv"),
    header=0,
    sep=",",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get(name__iexact=row["climate"])

    for j, header in enumerate(df_headers2, start=1):
        land_use_type = LandUseType.objects.get(name__iexact=df_headers2[j])

        print(
            climate,
            land_use_type,
            row[df_headers2[j]],
        )

        PerennialMaxAGB.objects.create(
            climate=climate,
            land_use_type=land_use_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

        if j == len(df_headers2) - 1:
            break

CroplandFLU.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "CroplandFLU.csv"),
    header=0,
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])

        if pd.isna(value):
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        CroplandFLU.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )

AfforestationFLU.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "AfforestationFLU.csv"),
    header=0,
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])

        if pd.isna(value):
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        AfforestationFLU.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )

GrasslandStockExchangeFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "GrasslandStockExchangeFactor.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    climate = Climate.objects.get(name__iexact=row["climate"])
    grassland_management_type = GrasslandManagementType.objects.get(name__iexact=row["grassland_management_type"])
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

    GrasslandStockExchangeFactor.objects.create(
        climate=climate,
        grassland_management_type=grassland_management_type,
        flu=flu,
        fmg=fmg,
        fi=fi,
    )

InputEmissionFactor.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "InputsEmissionFactors.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    input_type = InputType.objects.get(name__iexact=row["input_type"])
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    co2_value = parse_csv_number(row["co2_value"])
    n2o_value = parse_csv_number(row["n2o_value"])
    co2_eq_value = parse_csv_number(row["co2_eq_value"])

    print(
        input_type,
        climate,
        moisture,
        co2_value,
        n2o_value,
        co2_eq_value,
    )

    InputEmissionFactor.objects.create(
        input_type=input_type,
        climate=climate,
        moisture=moisture,
        co2_value=co2_value,
        n2o_value=n2o_value,
        co2_eq_value=co2_eq_value,
    )

OrganicSoilDrainageEmissionFactor.objects.all().delete()

ModuleType.objects.get_or_create(name="Plantation", class_name="Plantation")
ModuleType.objects.get_or_create(name="OtherLandUse", class_name="OtherLandUse")

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "OrganicSoilDrainageEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    print(row)
    site_location_type = SiteLocationType.objects.get(name__iexact=row["site_location_type"])
    peat_type = PeatType.objects.get(name__iexact=row["peat_type"])
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])
    module_type = ModuleType.objects.get(class_name__iexact=row["module_type"])
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

    OrganicSoilDrainageEmissionFactor.objects.create(
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

PeatExtractionEmissionFactor.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PeatExtractionEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    peat_type = PeatType.objects.get(name__iexact=row["peat_type"])
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])
    site_location_type = SiteLocationType.objects.get(name__iexact=row["site_location_type"])
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

    PeatExtractionEmissionFactor.objects.create(
        peat_type=peat_type,
        climate=climate,
        moisture=moisture,
        site_location_type=site_location_type,
        co2=co2,
        ch4=ch4,
        doc=doc,
        n2o=n2o,
    )

OrganicSoilFuelConsumption.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "OrganicSoilFuelConsumption.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(df_headers2, start=2):

        if j == len(df_headers2):
            break

        fire_type = FireType.objects.get(name__iexact=df_headers2[j])

        print(
            climate,
            moisture,
            fire_type,
            row[df_headers2[j]],
        )

        OrganicSoilFuelConsumption.objects.create(
            climate=climate,
            moisture=moisture,
            fire_type=fire_type,
            value=parse_csv_number(row[df_headers2[j]]),
        )

OrganicSoilRewettingEmissionFactor.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "OrganicSoilRewettingEmissionFactor.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    peat_type = PeatType.objects.get(name__iexact=row["peat_type"])
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])
    module_type = ModuleType.objects.get(class_name__iexact=row["module_type"])
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

    OrganicSoilRewettingEmissionFactor.objects.create(
        peat_type=peat_type,
        climate=climate,
        moisture=moisture,
        module_type=module_type,
        co2=co2,
        ch4=ch4,
        doc=doc,
        n2o=n2o,
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
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        lut = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])

        print(
            lut,
            climate,
            moisture,
            value,
        )

        CoastalDeadwood.objects.create(
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
    print(row)
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    salinity = SalinityType.objects.get(value=sanitize(row["salinity_type"]))

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])

        print(
            land_use_type,
            climate,
            moisture,
            salinity,
            value,
        )

        RewettingMethaneFactor.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            salinity=salinity,
            value=value,
        )

DrainageEmissionFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "DrainageEmissionFactors.csv"),
    header=[0],
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])

        if pd.isna(value):
            continue

        print(
            land_use_type,
            climate,
            moisture,
            value,
        )

        DrainageEmissionFactor.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            value=value,
        )


SoilOrganicCarbon.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "SoilOrganicCarbon.csv"),
    header=0,
    sep=",",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        soil_type = SoilType.objects.get(name__iexact=headers[j])
        value = row[headers[j]]

        if not value or value in ["", "N/A", "NO"] or pd.isna(value):
            continue

        print(
            climate,
            moisture,
            soil_type,
            value,
        )

        SoilOrganicCarbon.objects.create(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            value=value,
        )

IrrigationPressureRequirement.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "IrrigationPressureRequirements.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

irrigation_system_types = df["irrigation_system_type"].unique()
irrigation_system_types = irrigation_system_types[irrigation_system_types != "Other"]

for i, row in enumerate(df_dict):
    irrigation_system_type = IrrigationSystemType.objects.get(name__iexact=sanitize(row["irrigation_system_type"]))

    print(
        irrigation_system_type,
        row["bar"],
        row["avg_pressure"],
        row["head"],
    )

    if irrigation_system_type.name == "Other":
        bar_start = None
        bar_end = None

        for system in IrrigationSystemType.objects.all().exclude(name__in=irrigation_system_types):
            IrrigationPressureRequirement.objects.create(
                irrigation_system_type=system,
                bar_start=bar_start,
                bar_end=bar_end,
                avg_pressure=parse_csv_number(row["avg_pressure"], nan_value=None),
                head=parse_csv_number(row["head"], nan_value=None),
            )

    else:
        try:
            bar_ranges = row["bar"].split("-")
        except AttributeError:
            bar_ranges = [row["bar"], row["bar"]]

        bar_start = parse_csv_number(bar_ranges[0], nan_value=None)
        bar_end = parse_csv_number(bar_ranges[1], nan_value=None)

        IrrigationPressureRequirement.objects.create(
            irrigation_system_type=irrigation_system_type,
            bar_start=bar_start,
            bar_end=bar_end,
            avg_pressure=parse_csv_number(row["avg_pressure"], nan_value=None),
            head=parse_csv_number(row["head"], nan_value=None),
        )

FMGData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FMG.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    grassland_management_type = None
    tillage_management_type = None

    if not pd.isna(row["grassland_management_type"]):
        grassland_management_type = GrasslandManagementType.objects.get(name__iexact=row["grassland_management_type"])

    if not pd.isna(row["tillage_management_type"]):
        tillage_management_type = TillageManagementType.objects.get(name__iexact=row["tillage_management_type"])

    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        tillage_management_type,
        grassland_management_type,
        value,
    )

    FMGData.objects.create(
        climate=climate,
        moisture=moisture,
        tillage_management_type=tillage_management_type,
        grassland_management_type=grassland_management_type,
        value=value,
    )

FIData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FI.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    grassland_management_type = None
    organic_input_type = None

    if not pd.isna(row["grassland_management_type"]):
        grassland_management_type = GrasslandManagementType.objects.get(name__iexact=row["grassland_management_type"])

    if not pd.isna(row["organic_input_type"]):
        organic_input_type = OrganicInputType.objects.get(name__iexact=row["organic_input_type"])

    value = parse_csv_number(row["value"])

    print(
        climate,
        moisture,
        organic_input_type,
        grassland_management_type,
        value,
    )

    FIData.objects.create(
        climate=climate,
        moisture=moisture,
        organic_input_type=organic_input_type,
        grassland_management_type=grassland_management_type,
        value=value,
    )

    if i == len(df) - 1:
        break

FLUData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "FLU.csv"),
    header=[0],
    sep=";",
)

annualcropland = LandUseType.objects.get(name__iexact="Annual Cropland")
crops = LandUseType.objects.filter(module_types__class_name__iexact="AnnualCropland").all()
perennials = LandUseType.objects.filter(module_types__class_name__iexact="PerennialCropland").all()
perennials = perennials.exclude(name__in=["Agroforestry - Default", "Alley Cropping", "Perennial Fallow", "Hedgerow", "Multistrata", "Parkland", "Shaded Perennial", "Silvoarable", "Silvopasture", "Oil Palm", "Rubber", "Tea", "Olive", "Orchard", "Short Rotation Coppice", "Vine"])
for i, row in df.iterrows():
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])
    land_use_type = None
    if not pd.isna(row["land_use_type"]) and row["land_use_type"] != "Perennial Cropland":
        land_use_type = LandUseType.objects.get(name__iexact=row["land_use_type"])
    value = parse_csv_number(row["value"])

    if land_use_type == annualcropland:
        for crop in crops:
            print(
                climate,
                moisture,
                crop,
                value,
            )
            FLUData.objects.create(
                climate=climate,
                moisture=moisture,
                land_use_type=crop,
                value=value,
            )
    elif row["land_use_type"] == "Perennial Cropland":
        for perennial in perennials:
            print(
                climate,
                moisture,
                perennial,
                value,
            )
            FLUData.objects.create(
                climate=climate,
                moisture=moisture,
                land_use_type=perennial,
                value=value,
            )
    else:
        grassland_management_type = None
        if not pd.isna(row["grassland_management_type"]):
            grassland_management_type = GrasslandManagementType.objects.get(name__iexact=row["grassland_management_type"])

        print(
            climate,
            moisture,
            land_use_type,
            grassland_management_type,
            value,
        )

        FLUData.objects.create(
            climate=climate,
            moisture=moisture,
            land_use_type=land_use_type,
            grassland_management_type=grassland_management_type,
            value=value,
        )


PerennialBGB.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "PerennialBGB.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    continent = Region.objects.get(name__iexact=sanitize(row["region"]))

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=sanitize(headers[j]))
        value = parse_csv_number(row[headers[j]])

        if pd.isna(value):
            continue

        print(
            land_use_type,
            climate,
            moisture,
            continent,
            value,
        )

        PerennialBGB.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            continent=continent,
            value=value,
        )

LivestockManureEF.objects.filter(value=None).all().update(value=0)

IrrigationSystemData.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "IrrigationSystems.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    irrigation_system = IrrigationSystemType.objects.get(name__iexact=sanitize(row["irrigation_system_type"]))
    value = parse_csv_number(row["value"], nan_value=None)

    print(irrigation_system, value)

    IrrigationSystemData.objects.create(
        irrigation_system_type=irrigation_system,
        value=value,
    )

OtherConstructedWaterbodiesEmissionFactor.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "OtherConstructedWaterbodiesEmissionFactors.csv"),
    header=[0],
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

print(headers)

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])

    print(row)

    for j, header in enumerate(headers, start=2):

        if j == len(headers):
            break

        print(header)

        waterbody_type = WaterbodyType.objects.get(name__iexact=headers[j])

        value = parse_csv_number(row[headers[j]])

        print(
            waterbody_type,
            climate,
            moisture,
            value,
        )

        OtherConstructedWaterbodiesEmissionFactor.objects.create(
            waterbody_type=waterbody_type,
            climate=climate,
            moisture=moisture,
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

    gear_type = LargeFisheryGearType.objects.get(name__iexact=gear_type)
    fish_type = FishType.objects.get(name__iexact=fish_type)

    LargeFisheryFUI.objects.create(fish_type=fish_type, gear_type=gear_type, value=value)


SettlementEF.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "SettlementEF.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

climates = Climate.objects.all()
moistures = Moisture.objects.all()

for i, row in enumerate(rows):
    settlement_type = SettlementType.objects.get(name__iexact=row["settlement_type"])
    str_climate = row["climate"]
    str_moisture = row["moisture"]

    print(settlement_type, str_climate, str_moisture, row["flu"], row["fi"], row["fmg"], row["biomass"])

    if str_climate == "All" and str_moisture == "All":
        for climate in climates:
            print(f"\t{climate}")
            for moisture in moistures:
                print(f"\t\t{moisture}")
                SettlementEF.objects.create(
                    settlement_type=settlement_type,
                    climate=climate,
                    moisture=moisture,
                    flu=parse_csv_number(row["flu"]),
                    fi=parse_csv_number(row["fi"]),
                    fmg=parse_csv_number(row["fmg"]),
                    biomass=parse_csv_number(row["biomass"]),
                )
    elif str_climate == "All":
        for climate in climates:
            print(f"\t\t{climate}")
            moisture = Moisture.objects.get(name__iexact=str_moisture)
            SettlementEF.objects.create(
                settlement_type=settlement_type,
                climate=climate,
                moisture=moisture,
                flu=parse_csv_number(row["flu"]),
                fi=parse_csv_number(row["fi"]),
                fmg=parse_csv_number(row["fmg"]),
                biomass=parse_csv_number(row["biomass"]),
            )
    elif str_moisture == "All":
        for moisture in moistures:
            print(f"\t\t{moisture}")
            if str_climate == "Temperate":
                for climate in Climate.objects.filter(name__in=["Warm Temperate", "Cool Temperate"]).all():
                    SettlementEF.objects.create(
                        settlement_type=settlement_type,
                        climate=climate,
                        moisture=moisture,
                        flu=parse_csv_number(row["flu"]),
                        fi=parse_csv_number(row["fi"]),
                        fmg=parse_csv_number(row["fmg"]),
                        biomass=parse_csv_number(row["biomass"]),
                    )
            else:
                climate = Climate.objects.get(name__iexact=str_climate)
                SettlementEF.objects.create(
                    settlement_type=settlement_type,
                    climate=climate,
                    moisture=moisture,
                    flu=parse_csv_number(row["flu"]),
                    fi=parse_csv_number(row["fi"]),
                    fmg=parse_csv_number(row["fmg"]),
                    biomass=parse_csv_number(row["biomass"]),
                )
    else:
        climate = Climate.objects.get(name__iexact=str_climate)
        moisture = Moisture.objects.get(name__iexact=str_moisture)

        SettlementEF.objects.create(
            settlement_type=settlement_type,
            climate=climate,
            moisture=moisture,
            flu=parse_csv_number(row["flu"]),
            fi=parse_csv_number(row["fi"]),
            fmg=parse_csv_number(row["fmg"]),
            biomass=parse_csv_number(row["biomass"]),
        )

ElectricityEmission.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ElectricityEmissions.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
rows = df.to_dict("records")

for row in rows:
    country = row["country"]
    operating_margin = parse_csv_number(row["operating_margin"])
    combined_margin = parse_csv_number(row["combined_margin"])

    print(country, operating_margin, combined_margin)
    country = Country.objects.get(name__iexact=country)

    ElectricityEmission.objects.create(
        country=country,
        operating_margin=operating_margin,
        combined_margin=combined_margin,
    )


log.debug("Updating all GlobalWarmingPotential objects...")
# NOTE: This will delete all projects in review. Change to iexact update

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "GlobalWarmingPotential.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    name = row["name"]
    co2 = parse_csv_number(row["co2"])
    ch4 = parse_csv_number(row["ch4"])
    n2o = parse_csv_number(row["n2o"])
    ch4_fossil = parse_csv_number(row["ch4_fossil"])

    import re

    filter_name = re.search(r"\((.*?)\)", name).group(1)

    print(
        name,
        co2,
        ch4,
        n2o,
        ch4_fossil,
    )

    # Look for existing GWP containing the name

    gwp = GlobalWarmingPotential.objects.filter(name__icontains=filter_name).first()

    if gwp:
        print(f"Updating {gwp.name}")
        gwp.co2 = co2
        gwp.ch4 = ch4
        gwp.n2o = n2o
        gwp.ch4_fossil = ch4_fossil
        gwp.save()
    else:
        print(f"Creating {name}")
        GlobalWarmingPotential.objects.create(
            name=name,
            co2=co2,
            ch4=ch4,
            n2o=n2o,
            ch4_fossil=ch4_fossil,
        )


ForestManagementBGB.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementBGB.csv"),
    header=[0],
    sep=";",
)

for i, row in df.iterrows():
    try:
        climate = Climate.objects.get(name__iexact=row["climate"])
        region = Region.objects.get(name__iexact=row["region"])
        forest_type = ForestType.objects.get(name__iexact=row["forest_type"])
        land_use_type = LandUseType.objects.get(name__iexact=row["land_use_type"])
        threshold = row["threshold"]
        if threshold == "> 125" or threshold == ">75":
            threshold = None
        elif "125" in threshold:
            threshold = 125
        elif "75" in threshold:
            threshold = 75
        value = parse_csv_number(row["value"])

        print(climate, region, forest_type, land_use_type, threshold, value)

        ForestManagementBGB.objects.create(climate=climate, region=region, forest_type=forest_type, land_use_type=land_use_type, threshold=threshold, value=value)
    except Exception as e:
        print(row)
        print(e)

ModuleType.objects.filter(class_name="DegradedLand").update(name="Other Land", class_name="OtherLand")
LandUseType.objects.filter(name="Degraded Land").update(name="Other Land")

ModuleType.objects.filter(class_name="AnnualCropping").update(name="Annual Cropland", class_name="AnnualCropland")
LandUseType.objects.filter(name="Annual Cropping").update(name="Annual Cropland")

ModuleType.objects.filter(class_name="PerennialCropping").update(name="Perennial Cropland", class_name="PerennialCropland")
LandUseType.objects.filter(name="Perennial Cropping").update(name="Perennial Cropland")

# Get all LandUseTypes where module_type__class_name is AnnualCropland
crops = LandUseType.objects.filter(module_types__class_name__iexact="AnnualCropland").all()

# Set all crops to have all climates and moistures
for crop in crops:
    crop.climates.set(Climate.objects.all())
    crop.moistures.set(Moisture.objects.all())
    crop.save()


    
df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ListCountries.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    region = Region.objects.get(name__iexact=sanitize(row["EX-ACT"]))
    gleam_region = GLEAMRegion.objects.get(name__iexact=sanitize(row["GLEAM"]))
    ipcc_region = IPCCRegion.objects.get(name__iexact=sanitize(row["IPCC"]))

    try:
        country = Country.objects.get(name__iexact=sanitize(row["Countries"]))
    except Country.DoesNotExist:
        country = Country.objects.create(name=sanitize(row["Countries"]), region=region, gleam_region=gleam_region, ipcc_region=ipcc_region)

    print(
        region,
        gleam_region,
        ipcc_region,
        country,
    )

    if country:
        country.region = region
        country.gleam_region = gleam_region
        country.ipcc_region = ipcc_region
        country.save()


LivestockManureEF.objects.all().delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewNewLivestockManureEF_N2O_semicolon.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name__iexact=row["emission_type"])
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=row["livestock_category_type"]).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=row["livestock_production_type"]).first()
    climate = Climate.objects.filter(name__iexact=row["climate"]).first()
    moisture = Moisture.objects.filter(name__iexact=row["moisture"]).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=df_headers2[j]).first()

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
    emission_type = EmissionType.objects.get(name__iexact=row["emission_type"])
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=row["livestock_category_type"]).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=row["livestock_production_type"]).first()
    climate = Climate.objects.filter(name__iexact=row["climate"]).first()
    moisture = Moisture.objects.filter(name__iexact=row["moisture"]).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=df_headers2[j]).first()

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
    emission_type = EmissionType.objects.get(name__iexact=row["emission_type"])
    livestock_category = LivestockCategoryType.objects.filter(name__iexact=row["livestock_category_type"]).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=row["livestock_production_type"]).first()
    climate = Climate.objects.filter(name__iexact=row["climate"]).first()
    moisture = Moisture.objects.filter(name__iexact=row["moisture"]).first()

    for j, header in enumerate(df_headers2, start=5):
        if j == len(df_headers2):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=df_headers2[j]).first()

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

# Delete all LivestockManureEF where emission_type is CH4
LivestockManureEF.objects.filter(emission_type__name__iexact="CH4").delete()

df2 = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "NewLivestockManureEF_CH4.csv"),
    header=0,
    sep=";",
)

df_headers2 = df2.columns.values.tolist()
df_dict2 = df2.to_dict("records")

for i, row in enumerate(df_dict2):
    emission_type = EmissionType.objects.get(name__iexact=row["emission_type"])
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

annualcropland = LandUseType.objects.get(name__iexact="Annual Cropland")
crops = LandUseType.objects.filter(module_types__class_name__iexact="AnnualCropland").all()

ForestTotalBiomass.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestTotalBiomass.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
    moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
    region = Region.objects.get(name__iexact=sanitize(row["region"]))

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        land_use_type = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])
        if pd.isna(value):
            continue

        if land_use_type == annualcropland:
            for crop in crops:
                print(f"{crop}, {climate}, {moisture}, {region}, {value}")

                ForestTotalBiomass.objects.create(
                    land_use_type=crop,
                    climate=climate,
                    moisture=moisture,
                    continent=region,
                    value=value,
                )

        print(
            land_use_type,
            climate,
            moisture,
            region,
            value,
        )

        ForestTotalBiomass.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            continent=region,
            value=value,
        )


annualcropland = LandUseType.objects.get(name__iexact="Annual Cropland")
crops = LandUseType.objects.filter(module_types__class_name__iexact="AnnualCropland").all()

TotalBiomassAfterDefo.objects.all().delete()

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "TotalBiomassAfterDefo.csv"),
    header=0,
    sep=";",
)

headers = df.columns.values.tolist()
rows = df.to_dict("records")

for i, row in enumerate(rows):
    climate = Climate.objects.get(name__iexact=row["climate"])
    moisture = Moisture.objects.get(name__iexact=row["moisture"])
    region = Region.objects.get(name__iexact=row["region"])

    for j, header in enumerate(headers, start=3):

        if j == len(headers):
            break

        print(headers[j])
        land_use_type = LandUseType.objects.get(name__iexact=headers[j])
        value = parse_csv_number(row[headers[j]])
        if value is None:
            print(f"Skipping {land_use_type} {climate} {moisture} {region} {value}")
            continue

        if land_use_type == annualcropland:
            for crop in crops:
                print(
                    crop,
                    climate,
                    moisture,
                    region,
                    value,
                )

                TotalBiomassAfterDefo.objects.create(
                    land_use_type=crop,
                    climate=climate,
                    moisture=moisture,
                    continent=region,
                    value=value,
                )

        print(
            land_use_type,
            climate,
            moisture,
            region,
            value,
        )

        TotalBiomassAfterDefo.objects.create(
            land_use_type=land_use_type,
            climate=climate,
            moisture=moisture,
            continent=region,
            value=value,
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

awms_list = []

for i, row in enumerate(df_dict):
    livestock_category_type = LivestockCategoryType.objects.filter(name__iexact=sanitize(row["livestock_category_type"])).first()

    livestock_production_type = LivestockProductionType.objects.filter(name__iexact=sanitize(row["livestock_production_type"])).first()

    ipcc_region = IPCCRegion.objects.filter(name__iexact=sanitize(row["ipcc_region"])).first()

    print(f"{livestock_category_type}, {livestock_production_type}, {ipcc_region}")

    for j, header in enumerate(df_headers, start=3):

        if j == len(df_headers):
            break

        manure_management_type = ManureManagementType.objects.filter(name__iexact=sanitize(df_headers[j])).first()

        print(manure_management_type, row[df_headers[j]])

        awms_list.append(
            LivestockAWMS(
                manure_management_type=manure_management_type,
                livestock_category_type=livestock_category_type,
                livestock_production_type=livestock_production_type,
                ipcc_region=ipcc_region,
                value=parse_csv_number(row[df_headers[j]]),
            )
        )

LivestockAWMS.objects.bulk_create(awms_list)

log.debug("Deleting all InputEmissionFactor models...")
EnergyDefaultEmissionFactor.objects.all().delete()

l = []

df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "ipcc_data", "EnergyDefaultEmissionFactors.csv"),
    header=0,
    sep=";",
)

df_headers = df.columns.values.tolist()
df_dict = df.to_dict("records")

for i, row in enumerate(df_dict):
    fuel_use_type = FuelUseType.objects.get(name__iexact=row["fuel_use_type"])
    fuel_type = FuelType.objects.get(name__iexact=row["fuel_type"])
    co2 = parse_csv_number(row["co2"])
    ch4 = parse_csv_number(row["ch4"])
    n2o = parse_csv_number(row["n2o"])

    print(
        fuel_use_type,
        fuel_type,
        co2,
        ch4,
        n2o,
    )

    l.append(
        EnergyDefaultEmissionFactor(
            fuel_use_type=fuel_use_type,
            fuel_type=fuel_type,
            co2=co2,
            ch4=ch4,
            n2o=n2o,
        )
    )

EnergyDefaultEmissionFactor.objects.bulk_create(l)

"""

# TODO: Run in production

# log.debug("Deleting all GrasslandBiomass objects...")
# ipcc.GrasslandBiomass.objects.all().delete()

# df = pd.read_csv(
#     os.path.join(os.path.dirname(__file__), "ipcc_data", "GrasslandBiomass.csv"),
#     header=0,
#     sep=";",
# )

# for i, row in df.iterrows():
#     climate = Climate.objects.get(name__iexact=row["climate"])
#     moisture = Moisture.objects.get(name__iexact=row["moisture"])
#     agb_t_dm_ha = parse_csv_number(row["agb_t_dm_ha"])
#     agb_t_c_ha = parse_csv_number(row["agb_t_c_ha"])
#     bgb_t_dm_ha = parse_csv_number(row["bgb_t_dm_ha"])
#     bgb_t_c_ha = parse_csv_number(row["bgb_t_c_ha"])

#     print(
#         climate,
#         moisture,
#         agb_t_dm_ha,
#         agb_t_c_ha,
#         bgb_t_dm_ha,
#         bgb_t_c_ha,
#     )

#     ipcc.GrasslandBiomass.objects.create(
#         climate=climate,
#         moisture=moisture,
#         agb_t_dm_ha=agb_t_dm_ha,
#         agb_t_c_ha=agb_t_c_ha,
#         bgb_t_dm_ha=bgb_t_dm_ha,
#         bgb_t_c_ha=bgb_t_c_ha,
#     )

# log.debug("Deleting all ForestCombustionFactor objects...")
# ForestCombustionFactor.objects.all().delete()

# df = pd.read_csv(
#     os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestCombustionFactor.csv"),
#     header=[0],
#     sep=";",
# )

# for i, row in df.iterrows():
#     land_use_type = LandUseType.objects.get(name__iexact=sanitize(row["land_use_type"]))
#     climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
#     forest_type = ForestType.objects.get(name__iexact=sanitize(row["forest_type"]))

#     co2 = parse_csv_number(row["gef_co2"])
#     ch4 = parse_csv_number(row["gef_ch4"])
#     n2o = parse_csv_number(row["gef_n2o"])
#     value = parse_csv_number(row["value"])

#     print(
#         land_use_type,
#         climate,
#         forest_type,
#         co2,
#         ch4,
#         n2o,
#         value,
#     )

#     ForestCombustionFactor.objects.create(
#         land_use_type=land_use_type,
#         climate=climate,
#         forest_type=forest_type,
#         co2=co2,
#         ch4=ch4,
#         n2o=n2o,
#         value=value,
#     )

# log.debug("Deleting all LitteDeadwoodCarbonStock objects...")
# LitterDeadwoodCarbonStock.objects.all().delete()

# df = pd.read_csv(
#     os.path.join(os.path.dirname(__file__), "ipcc_data", "LitterDeadwoodCarbonStock.csv"),
#     header=[0],
#     sep=";",
# )

# for i, row in df.iterrows():
#     try:
#         climate = Climate.objects.get(name__iexact=row["climate"])
#         forest_type = ForestType.objects.get(name__iexact=row["forest_type"])
#         land_use_type = LandUseType.objects.get(name__iexact=row["land_use_type"])
#         litter = parse_csv_number(row["litter"])
#         dw = parse_csv_number(row["deadwood"])

#         print(climate, forest_type, land_use_type, litter, dw)

#         LitterDeadwoodCarbonStock.objects.create(climate=climate, forest_type=forest_type, land_use_type=land_use_type, litter=litter, dw=dw)
#     except Exception as e:
#         print(row)
#         print(e)

# log.debug("Deleting all OrganicSoilGefEmissionFactor...")
# OrganicSoilGefEmissionFactor.objects.all().delete()

# df2 = pd.read_csv(
#     os.path.join(os.path.dirname(__file__), "ipcc_data", "OrganicSoilGefEmissionFactor.csv"),
#     header=0,
#     sep=";",
# )

# df_headers2 = df2.columns.values.tolist()
# df_dict2 = df2.to_dict("records")

# for i, row in enumerate(df_dict2):
#     climate = Climate.objects.get(name__iexact=sanitize(row["climate"]))
#     moisture = Moisture.objects.get(name__iexact=sanitize(row["moisture"]))
#     co2 = parse_csv_number(row["co2"], nan_value=0)
#     ch4 = parse_csv_number(row["ch4"], nan_value=0)
#     co = parse_csv_number(row["co"], nan_value=0)

#     print(
#         climate,
#         moisture,
#         co2,
#         ch4,
#         co,
#     )

#     OrganicSoilGefEmissionFactor.objects.create(
#         climate=climate,
#         moisture=moisture,
#         co2=co2,
#         ch4=ch4,
#         co=co,
#     )

# ForestManagementAGB.objects.all().delete()
# import api.utilities as utils

# df = pd.read_csv(
#     os.path.join(os.path.dirname(__file__), "ipcc_data", "ForestManagementAGB.csv"),
#     header=0,
#     sep=";",
# )

# for i, row in df.iterrows():
#     print(row)

#     # TODO: Clarify with Lorenzo what sub-tropical is in terms of climate. Skip for now.
#     if row["climate"] == "Sub-tropical":
#         continue

#     if row["climate"] == "Tropical":
#         climates = [climate for climate in Climate.objects.filter(name__in=["Tropical"]).all()]
#     elif row["climate"] == "Temperate":
#         climates = [climate for climate in Climate.objects.filter(name__in=["Temperate"]).all()]
#     else:
#         climates = [Climate.objects.get(name__iexact=row["climate"])]

#     print(row["land_use_type"])
#     land_use_type = LandUseType.objects.get(name__iexact=row["land_use_type"])

#     regions = []
#     if "South" in row["region"] and "America" in row["region"]:
#         print("South America")
#         regions += [region for region in Region.objects.filter(name__in=["South America", "Caribbean", "Central America"])]
#     if "North" in row["region"] and "America" in row["region"]:
#         print("North America")
#         regions += [region for region in Region.objects.filter(name__in=["North America"])]
#     if "Asia" in row["region"]:
#         print("Asia")
#         regions += [region for region in Region.objects.filter(name__in=["Southern Asia", "Eastern Asia", "South-Eastern Asia", "Western Asia", "Central Asia"])]
#     if "Africa" in row["region"]:
#         print("Africa")
#         regions += [region for region in Region.objects.filter(name__in=["Northern Africa", "Western Africa", "Central Africa", "Eastern Africa", "Southern Africa"])]

#     if not regions:
#         print("No regions found for ", row["region"])
#         regions += [Region.objects.get(name__iexact=row["region"])]

#     forest_condition_type = ForestConditionType.objects.get(name__iexact=row["forest_condition_type"])

#     forest_types = ForestType.objects.filter(name__in=["Natural", "Plantaion"]).all()

#     agb_range_min = None
#     agb_range_max = None
#     agb_growth_min = None
#     agb_growth_max = None
#     agb_range_min_plantation = None
#     agb_range_max_plantation = None
#     agb_growth_min_plantation = None
#     agb_growth_max_plantation = None

#     if not isinstance(row["agb_range"], float) and len(row["agb_range"].split("-")) == 2:
#         agb_range_min = parse_csv_number(row["agb_range"].split("-")[0])
#         agb_range_max = parse_csv_number(row["agb_range"].split("-")[1])
#     elif row["agb_range"] != "n.a.":
#         agb_range_min = parse_csv_number(row["agb_range"])
#         agb_range_max = parse_csv_number(row["agb_range"])

#     if not row["agb_growth"].startswith("-") and not isinstance(row["agb_growth"], float) and len(row["agb_growth"].split("-")) == 2:
#         agb_growth_min = parse_csv_number(row["agb_growth"].split("-")[0])
#         agb_growth_max = parse_csv_number(row["agb_growth"].split("-")[1])
#     elif row["agb_growth"] != "n.a.":
#         agb_growth_min = parse_csv_number(row["agb_growth"])
#         agb_growth_max = parse_csv_number(row["agb_growth"])

#     if not isinstance(row["agb_range_plantation"], float) and len(row["agb_range_plantation"].split("-")) == 2:
#         agb_range_min_plantation = parse_csv_number(row["agb_range_plantation"].split("-")[0])
#         agb_range_max_plantation = parse_csv_number(row["agb_range_plantation"].split("-")[1])
#     elif row["agb_range_plantation"] != "n.a.":
#         agb_range_min_plantation = parse_csv_number(row["agb_range_plantation"])
#         agb_range_max_plantation = parse_csv_number(row["agb_range_plantation"])

#     if not isinstance(row["agb_growth_plantation"], float) and len(row["agb_growth_plantation"].split("-")) == 2:
#         agb_growth_min_plantation = parse_csv_number(row["agb_growth_plantation"].split("-")[0])
#         agb_growth_max_plantation = parse_csv_number(row["agb_growth_plantation"].split("-")[1])
#     elif row["agb_growth_plantation"] != "n.a.":
#         agb_growth_min_plantation = parse_csv_number(row["agb_growth_plantation"])
#         agb_growth_max_plantation = parse_csv_number(row["agb_growth_plantation"])

#     print("Climates: ", climates)
#     print("Regions: ", regions)
#     print("Forest Types: ", forest_types)

#     for region in regions:
#         for climate in climates:
#             for type in forest_types:
#                 # if type.name == "Plantation" and row["agb_range_plantation"] == "n.a." and row["agb_growth_plantation"] == "n.a.":
#                 #     continue
#                 # if type.name == "Natural" and row["agb_range"] == "n.a." and row["agb_growth"] == "n.a.":
#                 #     continue
#                 if type.name == "Plantation" and forest_condition_type.name == "Primary":
#                     continue

#                 if type.name == "Plantation":
#                     agb_min = agb_range_min_plantation
#                     agb_max = agb_range_max_plantation
#                     agb_growth_min = agb_growth_min_plantation
#                     agb_growth_max = agb_growth_max_plantation

#                 print(
#                     land_use_type,
#                     region,
#                     climate,
#                     forest_condition_type,
#                     type,
#                     agb_range_min,
#                     agb_range_max,
#                     agb_growth_min,
#                     agb_growth_max,
#                     agb_range_min_plantation,
#                     agb_range_max_plantation,
#                     agb_growth_min_plantation,
#                     agb_growth_max_plantation,
#                 )

#                 ForestManagementAGB.objects.create(
#                     land_use_type=land_use_type,
#                     region=region,
#                     climate=climate,
#                     forest_condition_type=forest_condition_type,
#                     from_year=row["from_year"],
#                     forest_type=type,
#                     agb_min=agb_range_min * utils.NON_MANGROVE_FACTOR if agb_range_min else None,
#                     agb_max=agb_range_max * utils.NON_MANGROVE_FACTOR if agb_range_max else None,
#                     agb_growth_min=agb_growth_min * utils.NON_MANGROVE_FACTOR if agb_growth_min else None,
#                     agb_growth_max=agb_growth_max * utils.NON_MANGROVE_FACTOR if agb_growth_max else None,
#                 )


# TODO: Run in review


# TODO: Run in develop
