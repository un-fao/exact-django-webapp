import pandas as pd
from api.models import *
from ipcc.models import *
import os
import csv


def capitalize_all(string):
    # Capitalize all words that have a space or a dash or a slash between them
    if " " in string:
        return " ".join([word.capitalize() for word in string.split(" ")])
    if "-" in string:
        return "-".join([word.capitalize() for word in string.split("-")])
    if "/" in string:
        return "/".join([word.capitalize() for word in string.split("/")])

    return string


def parse_csv_number(number):
    if isinstance(number, str):
        return float(number.replace(",", "."))
    elif pd.isna(number):
        return 0
    else:
        return float(number)


def sanitize(s: str):
    return s.replace("ï»¿", "").title().strip()


def run():
    """
    with open("scripts/ipcc_data/AboveGroundBiomass.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip the headers
        data = list(
            reader
        )  # read everything else into a list of rows to iterate multiple times

        for i, head in enumerate(header):
            vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[
                0
            ]
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

            vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[
                0
            ]
            for row in data:
                continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
                BelowGroundBiomass.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    continent=continent,
                    threshold=threshold,
                    value=row[i + 1],
                )

    with open("scripts/ipcc_data/TotalBiomassAfterDefo.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            land_use_type = LandUseType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                climate_name = sanitize(row[0])
                moisture_name = sanitize(row[1])
                continent_name = sanitize(row[2])
                value = row[i + 3] if row[i + 3] != "" else None
                year = 1

                climate = Climate.objects.get_or_create(name=climate_name)[0]
                moisture = Moisture.objects.get_or_create(name=moisture_name)[0]
                continent = Continent.objects.get_or_create(name=continent_name)[0]
                TotalBiomassAfterDefo.objects.get_or_create(
                    land_use_type=land_use_type,
                    climate=climate,
                    moisture=moisture,
                    continent=continent,
                    value=value,
                    year=year,
                )

    with open("scripts/ipcc_data/CombustionFactorValues.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        cf = 1
        co2 = 2
        ch4 = 3
        n2o = 4

        for row in data:
            row[co2] = row[co2] if row[co2] != "" else None
            row[ch4] = row[ch4] if row[ch4] != "" else None
            row[n2o] = row[n2o] if row[n2o] != "" else None

            veg_type = VegetationType.objects.get_or_create(name=sanitize(row[0]))[0]
            CombustionFactorValues.objects.get_or_create(
                vegetation_type=veg_type,
                value=row[cf],
                co2=row[co2],
                ch4=row[ch4],
                n2o=row[n2o],
            )

    with open("scripts/ipcc_data/LitterDeadwoodCarbonStock.csv", "r") as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            vegtype, foo = VegetationType.objects.get_or_create(name=sanitize(row[0]))
            LitterDeadwoodCarbonStock.objects.get_or_create(
                vegetation_type=vegtype, litter=row[1], dw=row[2]
            )

    with open("scripts/ipcc_data/LandUseStockExchangeFactor.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            land_use_type = LandUseType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                value = row[i + 2] if row[i + 2] != "" else None
                LandUseCarbonStockExchangeFactor.objects.get_or_create(
                    climate=climate,
                    moisture=moisture,
                    land_use_type=land_use_type,
                    value=value,
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

    with open("scripts/ipcc_data/DefaultEmissionFactors.csv", "r") as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            if row[1] == "":
                continue  # Skip rows that have no associated data
            input = OrganicInputType.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            DefaultEmissionFactor.objects.get_or_create(
                input=input, moisture=moisture, value=row[2]
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

    with open(
        "scripts/ipcc_data/AfforestationLandUseStockExchangeFactor.csv", "r"
    ) as f:
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
                climate = Climate.objects.get_or_create(
                    name=sanitize(sanitize(row[0]))
                )[0]
                moisture = Moisture.objects.get_or_create(
                    name=sanitize(sanitize(row[1]))
                )[0]
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
            vegetation_type = VegetationType.objects.get_or_create(
                name=sanitize(row[0])
            )[0]
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

    with open("scripts/ipcc_data/FiresCombustionFactors.csv", "r") as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            land_name = sanitize(row[0])
            land_use_type = (
                LandUseType.objects.get_or_create(name=land_name)[0]
                if land_name != "Other"
                else None
            )

            fires_cf = (
                FiresCombustionFactor.objects.get_or_create(
                    land_use_type=land_use_type, value=row[1]
                )
                if land_use_type is not None
                else None
            )

    with open("scripts/ipcc_data/CropNitrousEstimationDefaultFactors.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for row in data:
            crop_type = LandUseType.objects.get_or_create(name=sanitize(row[0]))[0]
            CropNitrousEstimationDefaultFactor.objects.get_or_create(
                land_use_type=crop_type,
                slope=row[1] if row[1] != "NA" else None,
                intercept=row[2] if row[2] != "NA" else None,
                n_ag_residues=row[3],
                rs_t=row[4],
                n_bg_t=row[5],
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

    with open("scripts/ipcc_data/CoastalDeadwood.csv", "r") as f:
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

                CoastalDeadwood.objects.get_or_create(
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

    with open(
        "scripts/ipcc_data/OtherConstructedWaterbodiesEmissionFactors.csv", "r"
    ) as f:
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

    with open("scripts/ipcc_data/DefaultSoilCarbonStockMineralSoil.csv", "r") as f:
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
                soil_type = SoilType.objects.get_or_create(name="Mineral")[0]

                value = row[i + 2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DefaultSoilCarbonStock.objects.get_or_create(
                    vegetation_type=vegetation_type,
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
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == "":
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                soil_type = SoilType.objects.get_or_create(name="Organic")[0]

                value = row[i + 2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DefaultSoilCarbonStock.objects.get_or_create(
                    vegetation_type=vegetation_type,
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
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == "":
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                soil_type = SoilType.objects.get_or_create(name="Aggregated")[0]

                value = row[i + 2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DefaultSoilCarbonStock.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
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

    with open("scripts/ipcc_data/DrainageEmissionFactors.csv", "r") as f:
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

                DrainageEmissionFactor.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value,
                )

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

    with open("scripts/ipcc_data/PerennialAGB.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
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

    with open("scripts/ipcc_data/PerennialMaximumAGB_C.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            land_use_type = LandUseType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == "":
                    continue
                try:
                    # FIXME: This skips rows in PerennialMaximumAGB_C that don't have moisture values. Must be fixed. Ask team.
                    # Some rows in the Excel are only matched to a climate, not climate and moisture.
                    float(row[1])
                    continue
                except ValueError:
                    pass

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                print(f"i = {i}")
                print(f"{land_use_type}, {climate}, {moisture}")

                value = row[i + 2]

                print(f"Value {value}")

                PerennialMaxAGB.objects.get_or_create(
                    land_use_type=land_use_type,
                    climate=climate,
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

    with open("scripts/ipcc_data/PerennialBGB.csv", "r") as f:
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

    with open("scripts/ipcc_data/CroplandFLU.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            land_use_type = LandUseType.objects.get(name=head)
            for row in data:
                if sanitize(row[0]) == "":
                    continue

                climate = Climate.objects.get(name=sanitize(row[0]).title())
                moisture = Moisture.objects.get(name=sanitize(row[1]).title())

                value = row[i + 2]

                print(f"{land_use_type}, {climate}, {moisture}, {value}")

                CroplandFLU.objects.get_or_create(
                    land_use_type=land_use_type,
                    climate=climate,
                    moisture=moisture,
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

    with open("scripts/ipcc_data/AfforestationFLU.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
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

    with open("scripts/ipcc_data/GrasslandAGB.csv", "r") as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            climate = Climate.objects.get_or_create(name=sanitize(row[0]).title())[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]).title())[0]

            value = row[2]

            print(f"{climate}, {moisture}, {value}")

            GrasslandAGB.objects.get_or_create(
                climate=climate, moisture=moisture, value=value
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
    with open("scripts/ipcc_data/SmallFisheryDatabaseFish.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            gear_type = GearType.objects.get_or_create(name=head)[0]
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


    with open("scripts/ipcc_data/ElectricityEmissions.csv", "r") as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            country = Country.objects.get_or_create(name=sanitize(row[0]).title())[0]
            continent = Continent.objects.get_or_create(name=sanitize(row[1]).title())[
                0
            ]

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

    df2 = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockManureEF.csv"),
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
            name=capitalize_all(row["livestock_category"])
        )[0]
        climate = Climate.objects.get_or_create(name=capitalize_all(row["climate"]))[0]
        moisture = Moisture.objects.get_or_create(name=capitalize_all(row["moisture"]))[
            0
        ]

        for j, header in enumerate(df_headers2):
            print(header)
            if j < 4:
                continue

            manure_management_type = ManureManagementType.objects.get_or_create(
                name=capitalize_all(df_headers2[j + 4])
            )[0]

            print(
                emission_type,
                livestock_category,
                climate,
                moisture,
                manure_management_type,
                row[df_headers2[j + 4]],
            )

            LivestockManureEF.objects.get_or_create(
                emission_type=emission_type,
                livestock_category=livestock_category,
                climate=climate,
                moisture=moisture,
                manure_management_type=manure_management_type,
                value=parse_csv_number(row[df_headers2[j + 4]]),
            )

            if j + 4 == len(df_headers2) - 1:
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
        region = Continent.objects.get_or_create(name=capitalize_all(row["region"]))[0]

        for j, header in enumerate(df_headers):
            if j < 2:
                continue

            livestock_category = LivestockCategoryType.objects.get_or_create(
                name=capitalize_all(df_headers[j + 2])
            )[0]

            print(
                production_type,
                livestock_category,
                region,
                row[df_headers[j + 2]],
            )

            LivestockTAM.objects.get_or_create(
                production_type=production_type,
                livestock_category=livestock_category,
                region=region,
                value=parse_csv_number(row[df_headers[j + 2]]),
            )

            if j + 2 == len(df_headers) - 1:
                break

    df = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "ipcc_data", "LivestockVSER.csv"),
        header=0,
        sep=";",
    )

    df_headers = df.columns.values.tolist()
    df_dict = df.to_dict("records")

    for i, row in enumerate(df_dict):
        production_type = LivestockProductionType.objects.get_or_create(
            name=capitalize_all(row["production_type"])
        )[0]
        region = Continent.objects.get_or_create(name=capitalize_all(row["region"]))[0]

        for j, header in enumerate(df_headers):
            if j < 2:
                continue

            livestock_category = LivestockCategoryType.objects.get_or_create(
                name=capitalize_all(df_headers[j + 2])
            )[0]

            print(
                production_type,
                livestock_category,
                region,
                row[df_headers[j + 2]],
            )

            LivestockVSER.objects.get_or_create(
                production_type=production_type,
                livestock_category=livestock_category,
                region=region,
                value=parse_csv_number(row[df_headers[j + 2]]),
            )

            if j + 2 == len(df_headers) - 1:
                break

    with open("scripts/ipcc_data/LargeFisheryFUI.csv", "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            gear_type = GearType.objects.get_or_create(name=head)[0]
            for row in data:
                if row[i + 1] == "":
                    continue

                fish_type = FishType.objects.get_or_create(
                    name=sanitize(row[0]).title()
                )[0]
                value = float(row[i + 1])

                print(f"{fish_type}, {gear_type}, {value}")

                LargeFisheryFUI.objects.get_or_create(
                    fish_type=fish_type, gear_type=gear_type, value=value
                )
    """

    print("AO")
    nsed = LargeFisheryFUI.objects.filter(gear_type__name="Not Specified")
    print(nsed)
    for n in nsed:
        _all = LargeFisheryFUI.objects.filter(fish_type=n.fish_type)
        for a in _all:
            if a.gear_type.name != "Not Specified":
                print(a.value)
                print(n.value)
