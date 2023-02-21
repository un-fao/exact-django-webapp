import csv
from api.models import *
from ipcc.models import *

def sanitize(s:str):
    return s.replace('ï»¿', '').title().strip()

def run():
    """
    with(open('scripts\ipcc_data\AboveGroundBiomass.csv', 'r')) as f:

        reader = csv.reader(f)
        header = next(reader, None)  # skip the headers
        data = list(reader)  # read everything else into a list of rows to iterate multiple times

        for i, head in enumerate(header):
            vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
                AboveGroundBiomass.objects.get_or_create(vegetation_type=vegetation_type, continent=continent, value=row[i+1])

    with(open('scripts\ipcc_data\BelowGroundBiomass.csv', 'r')) as f:

        reader = csv.reader(f)
        header = next(reader, None)
        thresholds = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            threshold = sanitize(thresholds[i])
            if threshold == '> 125' or threshold == '>75':
                threshold = None
            elif '125' in threshold:
                threshold = 125
            elif '75' in threshold:
                threshold = 75

            vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
                BelowGroundBiomass.objects.get_or_create(vegetation_type=vegetation_type, continent=continent, threshold=threshold, value=row[i+1])

    with(open('scripts\ipcc_data\TotalBiomassAfterDefo.csv', 'r')) as f:
            
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            land_use_type = LandUseType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:

                climate_name = sanitize(row[0])
                moisture_name = sanitize(row[1])
                continent_name = sanitize(row[2])
                value = row[i+3] if row[i+3] != '' else None
                year = 1

                climate = Climate.objects.get_or_create(name=climate_name)[0]
                moisture = Moisture.objects.get_or_create(name=moisture_name)[0]
                continent = Continent.objects.get_or_create(name=continent_name)[0]
                TotalBiomassAfterDefo.objects.get_or_create(land_use_type=land_use_type, climate=climate, moisture=moisture, continent=continent, value=value, year=year)

    with(open('scripts\ipcc_data\CombustionFactorValues.csv', 'r')) as f:
                
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        cf = 1
        co2 = 2
        ch4 = 3
        n2o = 4

        for row in data:

            row[co2] = row[co2] if row[co2] != '' else None
            row[ch4] = row[ch4] if row[ch4] != '' else None
            row[n2o] = row[n2o] if row[n2o] != '' else None

            veg_type = VegetationType.objects.get_or_create(name=sanitize(row[0]))[0]
            CombustionFactorValues.objects.get_or_create(vegetation_type=veg_type, value=row[cf], co2=row[co2], ch4=row[ch4], n2o=row[n2o])
                        
    with(open('scripts\ipcc_data\LitterDeadwoodCarbonStock.csv', 'r')) as f:

        reader = csv.reader(f)
        data = list(reader)

        for row in data:

            vegtype, foo = VegetationType.objects.get_or_create(name=sanitize(row[0]))
            LitterDeadwoodCarbonStock.objects.get_or_create(vegetation_type=vegtype, litter=row[1], dw=row[2])

    with(open('scripts\ipcc_data\LandUseStockExchangeFactor.csv', 'r')) as f:
            
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            land_use_type = LandUseType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                value = row[i+2] if row[i+2] != '' else None
                LandUseStockExchangeFactor.objects.get_or_create(climate=climate, moisture=moisture, land_use_type=land_use_type, value=value)

    with(open('scripts\ipcc_data\Countries.csv', 'r')) as f:
                
        reader = csv.reader(f)
        data = list(reader)

        for row in data:

            Country.objects.get_or_create(name=sanitize(row[0]), continent=Continent.objects.get_or_create(name=sanitize(row[1]))[0])

    with(open('scripts\ipcc_data\SoilOrganicCarbon.csv', 'r')) as f:
                    
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head)
            soil_type = SoilType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue
                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                # FIXME: N/A and NO mean 2 different things. Differentiate them
                value = row[i+2] if row[i+2] not in ['','N/A','NO'] else None
                SoilOrganicCarbon.objects.get_or_create(climate=climate, moisture=moisture, soil_type=soil_type, value=value)
    
    with(open('scripts\ipcc_data\DefaultEmissionFactors.csv', 'r')) as f:

        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            if row[1] == '':
                continue # Skip rows that have no associated data
            input = OrganicInputType.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            DefaultEmissionFactors.objects.get_or_create(input=input, moisture=moisture, value=row[2])

    with(open('scripts\ipcc_data\ForestTotalBiomass.csv', 'r')) as f:

        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head)
            if head == '': continue
            land_use_type = LandUseType.objects.get_or_create(name=head)[0]
            for row in data:
                if row[i+3] == '': continue
                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                continent = Continent.objects.get_or_create(name=sanitize(row[2]))[0]
                value = row[i+3]
                ForestTotalBiomass.objects.get_or_create(land_use_type=land_use_type, climate=climate, moisture=moisture, continent=continent, value=value)

    with(open('scripts\ipcc_data\AfforestationLandUseStockExchangeFactor.csv', 'r')) as f:

        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head)
            if head == '': continue
            land_use_type = LandUseType.objects.get_or_create(name=head)[0]
            for row in data:
                if row[i+2] == '': continue
                climate = Climate.objects.get_or_create(name=sanitize(sanitize(row[0])))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(sanitize(row[1])))[0]
                value = row[i+2]
                AfforestationLandUseStockExchangeFactor.objects.get_or_create(land_use_type=land_use_type, climate=climate, moisture=moisture, value=value)

    with(open('scripts\ipcc_data\AboveGroundNetBiomassGrowth.csv', 'r')) as f:

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
                value_upto_20_years=value_upto_20_years
            )

    with(open('scripts\ipcc_data\AfforestationCombustionFactorValues.csv', 'r')) as f:
            
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
                n2o=row[n2o]
            )

    with(open('scripts\ipcc_data\BurningEmissionFactors.csv', 'r')) as f:
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

            emission_factor_category = EmissionFactorCategory.objects.get_or_create(name=row[category])[0]
            
            BurningEmissionFactor.objects.get_or_create(
                category = emission_factor_category,
                co2 = row[co2],
                co = row[co],
                ch4 = row[ch4],
                n2o = row[n2o],
                nox = row[nox]
            )
    with(open('scripts\ipcc_data\FiresCombustionFactors.csv', 'r')) as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            land_name = sanitize(row[0])
            land_use_type = LandUseType.objects.get_or_create(name=land_name)[0] if land_name != "Other" else None
            
            fires_cf = FiresCombustionFactor.objects.get_or_create(
                land_use_type = land_use_type,
                value = row[1]
            ) if land_use_type is not None else None

    with(open('scripts\ipcc_data\CropNitrousEstimationDefaultFactors.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for row in data:
            crop_type = LandUseType.objects.get_or_create(name=sanitize(row[0]))[0]
            CropNitrousEstimationDefaultFactor.objects.get_or_create(
                land_use_type = crop_type,
                slope = row[1] if row[1] != 'NA' else None,
                intercept = row[2] if row[2] != 'NA' else None,
                n_ag_residues = row[3],
                rs_t = row[4],
                n_bg_t = row[5]
            )
    with(open('scripts\ipcc_data\CoastalAboveGroundBiomass.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                CoastalAboveGroundBiomass.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )

    with(open('scripts\ipcc_data\CoastalBGAGRatio.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                CoastalBGAGRatio.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )

    with(open('scripts\ipcc_data\CoastalLitter.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                CoastalLitter.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )

    with(open('scripts\ipcc_data\CoastalDeadwood.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                CoastalDeadwood.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )
    
    with(open('scripts\ipcc_data\RewettingEmissionFactors.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                RewettingCarbonFactor.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )

    with(open('scripts\ipcc_data\RewettingMethaneFactors_salinity-lt18.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                salinity = SalinityType.objects.get_or_create(value="<18")[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                RewettingMethaneFactor.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    salinity=salinity,
                    value=value
                )
    with(open('scripts\ipcc_data\OtherConstructedWaterbodiesEmissionFactors.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            waterbody_type = WaterbodyType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                print(f"{waterbody_type}, {climate}, {moisture}, {value}")

                OtherConstructedWaterbodiesEmissionFactor.objects.get_or_create(
                    waterbody_type=waterbody_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )
    with(open('scripts\ipcc_data\DefaultSoilCarbonStockMineralSoil.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                soil_type = SoilType.objects.get_or_create(name="Mineral")[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DefaultSoilCarbonStock.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
                    value=value
                )
    with(open('scripts\ipcc_data\DefaultSoilCarbonStockOrganicSoil.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                soil_type = SoilType.objects.get_or_create(name="Organic")[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DefaultSoilCarbonStock.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
                    value=value
                )

    with(open('scripts\ipcc_data\DefaultSoilCarbonStockAggregatedSoil.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
                soil_type = SoilType.objects.get_or_create(name="Aggregated")[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DefaultSoilCarbonStock.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    soil_type=soil_type,
                    value=value
                )
    with(open('scripts\ipcc_data\Atwood.csv', 'r')) as f:
        reader = csv.reader(f)
        data = list(reader)

        for row in data:

            # FIXME: Some countries have no continent in the database. Link them
            country = Country.objects.get_or_create(name=sanitize(row[0]))[0]

            n = sanitize(row[1])
            area_2014_km2 = sanitize(row[2])
            mg_c_ha = sanitize(row[3])
            sd = sanitize(row[4]) if sanitize(row[4]) != '' else None
            score = sanitize(row[5]) if sanitize(row[5]) != '' else None

            Atwood.objects.get_or_create(
                country = country,
                n = n,
                area_2014_km2 = area_2014_km2,
                mg_c_ha = mg_c_ha,
                sd = sd,
                score = score
            )
    with(open('scripts\ipcc_data\DrainageEmissionFactors.csv', 'r')) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            head = sanitize(head).title()
            vegetation_type = VegetationType.objects.get_or_create(name=head)[0]
            for row in data:
                if sanitize(row[0]) == '':
                    continue

                climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
                moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]

                value = row[i+2]

                print(f"{vegetation_type}, {climate}, {moisture}, {value}")

                DrainageEmissionFactor.objects.get_or_create(
                    vegetation_type=vegetation_type,
                    climate=climate,
                    moisture=moisture,
                    value=value
                )
"""
