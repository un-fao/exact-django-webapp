import csv
from api.models import *
from ipcc.models import *

def sanitize(s:str):
    return s.replace('ï»¿', '').title().strip()

def run():
    with(open('scripts\ipcc_data\AboveGroundBiomass.csv', 'rU')) as f:

        reader = csv.reader(f)
        header = next(reader, None)  # skip the headers
        data = list(reader)  # read everything else into a list of rows to iterate multiple times

        for i, head in enumerate(header):
            vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
                AboveGroundBiomass.objects.get_or_create(vegetation_type=vegetation_type, continent=continent, value=row[i+1])

    with(open('scripts\ipcc_data\BelowGroundBiomass.csv', 'rU')) as f:

        reader = csv.reader(f)
        header = next(reader, None)
        thresholds = next(reader, None)
        data = list(reader)

        for i, head in enumerate(header):
            threshold = sanitize(thresholds[i])
            if threshold == '> 125' or threshold == '> 75':
                threshold = None
            elif '125' in threshold:
                threshold = 125
            elif '75' in threshold:
                threshold = 75

            vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
            for row in data:
                continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
                BelowGroundBiomass.objects.get_or_create(vegetation_type=vegetation_type, continent=continent, threshold=threshold, value=row[i+1])

    with(open('scripts\ipcc_data\TotalBiomassAfterDefo.csv', 'rU')) as f:
            
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

    with(open('scripts\ipcc_data\CombustionFactorValues.csv', 'rU')) as f:
                
        reader = csv.reader(f)
        data = list(next(reader, None))

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
                        
    with(open('scripts\ipcc_data\LitterDeadwoodCarbonStock.csv', 'rU')) as f:

        reader = csv.reader(f)
        data = list(reader)

        for row in data:

            vegtype = VegetationType.objects.get_or_create(name=sanitize(row[0]))
            LitterDeadwoodCarbonStock.objects.get_or_create(vegetation_type=vegtype, litter=row[1], dw=row[2])

    with(open('scripts\ipcc_data\LandUseStockExchangeFactor.csv', 'rU')) as f:
            
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

    with(open('scripts\ipcc_data\Countries.csv', 'rU')) as f:
                
        reader = csv.reader(f)
        data = list(reader)

        for row in data:

            Country.objects.get_or_create(name=sanitize(row[0]), continent=Continent.objects.get_or_create(name=sanitize(row[1]))[0])

    with(open('scripts\ipcc_data\SoilOrganicCarbon.csv', 'rU')) as f:
                    
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
                obj = SoilOrganicCarbon(climate=climate, moisture=moisture, soil_type=soil_type, value=value)
                obj.save()
    
    with(open('scripts\ipcc_data\DefaultEmissionFactors.csv', 'rU')) as f:

        reader = csv.reader(f)
        data = list(reader)

        for row in data:
            if row[1] == '':
                continue # Skip rows that have no associated data
            input = Input.objects.get_or_create(name=sanitize(row[0]))[0]
            moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
            DefaultEmissionFactors.objects.get_or_create(input=input, moisture=moisture, value=row[2])
    
    pass