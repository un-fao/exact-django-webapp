import csv
import numpy as np
from api.models import *
from ipcc.models import *

def sanitize(s:str):
    return s.replace('ï»¿', '').title().strip()

def run():
    # with(open('scripts\ipcc_data\AboveGroundBiomass.csv', 'rU')) as f:

    #     reader = csv.reader(f)
    #     header = next(reader, None)  # skip the headers
    #     data = list(reader)  # read everything else into a list of rows to iterate multiple times

    #     for i, head in enumerate(header):
    #         vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
    #         for row in data:
    #             continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
    #             ag_biomass = AboveGroundBiomass(vegetation_type=vegetation_type, continent=continent, value=row[i+1])

    #             ag_biomass.save()

    # with(open('scripts\ipcc_data\BelowGroundBiomass.csv', 'rU')) as f:

    #     reader = csv.reader(f)
    #     header = next(reader, None)
    #     thresholds = next(reader, None)
    #     data = list(reader)

    #     for i, head in enumerate(header):
    #         threshold = sanitize(thresholds[i])
    #         if threshold == '> 125' or threshold == '> 75':
    #             threshold = None
    #         elif '125' in threshold:
    #             threshold = 125
    #         elif '75' in threshold:
    #             threshold = 75

    #         vegetation_type = VegetationType.objects.get_or_create(name=sanitize(head))[0]
    #         for row in data:
    #             continent = Continent.objects.get_or_create(name=sanitize(row[0]))[0]
    #             bg_biomass = BelowGroundBiomass.objects.get_or_create(vegetation_type=vegetation_type, continent=continent, threshold=threshold, value=row[i+1])

    # with(open('scripts\ipcc_data\TotalBiomassAfterDefo.csv', 'rU')) as f:
            
    #         reader = csv.reader(f)
    #         header = next(reader, None)
    #         data = list(reader)
    
    #         for i, head in enumerate(header):
    #             head = head.replace('ï»¿', '').title()
    #             for row in data:

    #                 land_use_type_name = head
    #                 climate_name = row[0].replace('ï»¿', '').title()
    #                 moisture_name = row[1].replace('ï»¿', '').title()
    #                 continent_name = row[2].replace('ï»¿', '').title()
    #                 value = row[i+3] if row[i+3] != '' else None
    #                 year = 1

    #                 # print(head, row[0], row[1], row[2], row[i+3])



    #                 land_use_type = LandUseType.objects.get_or_create(name=land_use_type_name)
    #                 climate = Climate.objects.get_or_create(name=climate_name)
    #                 moisture = Moisture.objects.get_or_create(name=moisture_name)
    #                 continent = Continent.objects.get_or_create(name=continent_name)
    #                 total_biomass = TotalBiomassAfterDefo(land_use_type=land_use_type[0], climate=climate[0], moisture=moisture[0], continent=continent[0], value=value, year=year)
    #                 total_biomass.save()


    # with(open('scripts\ipcc_data\CombustionFactorValues.csv', 'rU')) as f:
                
    #             reader = csv.reader(f)
    #             header = next(reader, None)
    #             data = list(reader)

    #             cf = 1
    #             co2 = 2
    #             ch4 = 3
    #             n2o = 4

    #             for row in data:

    #                 if row[co2] == '':
    #                     row[co2] = None
    #                 if row[ch4] == '':
    #                     row[ch4] = None
    #                 if row[n2o] == '':
    #                     row[n2o] = None

    #                 veg_type = VegetationType.objects.get(name=row[0].replace('ï»¿', '').title())
    #                 cf_obj = CombustionFactorValues(vegetation_type=veg_type, value=row[cf], co2=row[co2], ch4=row[ch4], n2o=row[n2o])
    #                 cf_obj.save()
                        
    # with(open('scripts\ipcc_data\LitterDeadwoodCarbonStock.csv', 'rU')) as f:

    #     reader = csv.reader(f)
    #     data = list(reader)

    #     for row in data:

    #         vegtype = VegetationType.objects.get(name=sanitize(row[0]))
    #         ldw = LitterDeadwoodCarbonStock(vegetation_type=vegtype, litter=row[1], dw=row[2])
    #         ldw.save()

    # with(open('scripts\ipcc_data\LandUseStockExchangeFactor.csv', 'rU')) as f:
            
    #         reader = csv.reader(f)
    #         header = next(reader, None)
    #         data = list(reader)
    
    #         for i, head in enumerate(header):

    #             for row in data:

    #                 climate = Climate.objects.get(name=sanitize(row[0]))
    #                 moisture = Moisture.objects.get(name=sanitize(row[1]))
    #                 land_use_type = LandUseType.objects.get(name=sanitize(head))
    #                 value = row[i+2] if row[i+2] != '' else None
    #                 obj = LandUseStockExchangeFactor(climate=climate, moisture=moisture, land_use_type=land_use_type, value=value)
    #                 obj.save()

    # with(open('scripts\ipcc_data\Countries.csv', 'rU')) as f:
                
    #     reader = csv.reader(f)
    #     data = list(reader)

    #     for row in data:

    #         country = Country(name=sanitize(row[0]), continent=Continent.objects.get_or_create(name=sanitize(row[1]))[0])
    #         country.save()

    # with(open('scripts\ipcc_data\SoilOrganicCarbon.csv', 'rU')) as f:
                    
    #     reader = csv.reader(f)
    #     header = next(reader, None)
    #     data = list(reader)

    #     for i, head in enumerate(header):
    #         head = sanitize(head)
    #         soil_type = SoilType.objects.get_or_create(name=sanitize(head))[0]
    #         for row in data:
    #             if sanitize(row[0]) == '':
    #                 continue
    #             climate = Climate.objects.get_or_create(name=sanitize(row[0]))[0]
    #             moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
    #             # FIXME: N/A and NO mean 2 different things. Differentiate them
    #             value = row[i+2] if row[i+2] not in ['','N/A','NO'] else None
    #             obj = SoilOrganicCarbon(climate=climate, moisture=moisture, soil_type=soil_type, value=value)
    #             obj.save()
    
    # with(open('scripts\ipcc_data\DefaultEmissionFactors.csv', 'rU')) as f:

    #     reader = csv.reader(f)
    #     data = list(reader)

    #     for row in data:
    #         if row[1] == '':
    #             row[1] = 'Default'
    #         input = Input.objects.get_or_create(name=sanitize(row[0]))[0]
    #         moisture = Moisture.objects.get_or_create(name=sanitize(row[1]))[0]
    #         emission_factor = DefaultEmissionFactors.objects.get_or_create(input=input, moisture=moisture, value=row[2])[0]

    
    pass