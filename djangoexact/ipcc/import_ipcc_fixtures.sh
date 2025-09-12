#!/bin/bash
# Import IPCC fixtures in the correct dependency order

set -e  # Exit on any error

echo "Starting IPCC fixtures import..."

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "Error: manage.py not found. Please run this script from the Django project root."
    exit 1
fi

# Function to import fixture with error handling
import_fixture() {
    local fixture_path="$1"
    local description="$2"
    
    if [ -f "$fixture_path" ]; then
        echo "Importing $description..."
        python manage.py loaddata "$fixture_path" || {
            echo "Error importing $fixture_path"
            exit 1
        }
    else
        echo "Warning: $fixture_path not found, skipping..."
    fi
}

# Import API fixtures first (prerequisites)
echo "Importing API fixtures (prerequisites)..."

# Core reference models
import_fixture "api/fixtures/climate.json" "Climate data"
import_fixture "api/fixtures/moisture.json" "Moisture data"
import_fixture "api/fixtures/region.json" "Region data"
import_fixture "api/fixtures/country.json" "Country data"
import_fixture "api/fixtures/soiltype.json" "Soil type data"
import_fixture "api/fixtures/landusetype.json" "Land use type data"
import_fixture "api/fixtures/foresttype.json" "Forest type data"
import_fixture "api/fixtures/moduletype.json" "Module type data"

# Management type models
import_fixture "api/fixtures/tillagemanagementtype.json" "Tillage management type data"
import_fixture "api/fixtures/organicinputtype.json" "Organic input type data"
import_fixture "api/fixtures/grasslandmanagementtype.json" "Grassland management type data"
import_fixture "api/fixtures/manuremanagementtype.json" "Manure management type data"
import_fixture "api/fixtures/waterregimetype.json" "Water regime type data"
import_fixture "api/fixtures/irrigationsystemtype.json" "Irrigation system type data"

# Specialized type models
import_fixture "api/fixtures/livestockcategorytype.json" "Livestock category type data"
import_fixture "api/fixtures/livestockproductiontype.json" "Livestock production type data"
import_fixture "api/fixtures/ipccregion.json" "IPCC region data"
import_fixture "api/fixtures/fueltype.json" "Fuel type data"
import_fixture "api/fixtures/inputtype.json" "Input type data"
import_fixture "api/fixtures/buildingtype.json" "Building type data"
import_fixture "api/fixtures/roadtype.json" "Road type data"
import_fixture "api/fixtures/salinitytype.json" "Salinity type data"
import_fixture "api/fixtures/waterbodytype.json" "Water body type data"
import_fixture "api/fixtures/trophictype.json" "Trophic type data"
import_fixture "api/fixtures/fisherytype.json" "Fishery type data"
import_fixture "api/fixtures/fishtype.json" "Fish type data"
import_fixture "api/fixtures/largefisherygeartype.json" "Large fishery gear type data"
import_fixture "api/fixtures/smallfisherygeartype.json" "Small fishery gear type data"
import_fixture "api/fixtures/peattype.json" "Peat type data"
import_fixture "api/fixtures/firetype.json" "Fire type data"
import_fixture "api/fixtures/sitelocationtype.json" "Site location type data"
import_fixture "api/fixtures/organicamendmenttype.json" "Organic amendment type data"
import_fixture "api/fixtures/watermanagementtypebeforecultivation.json" "Water management type before cultivation data"
import_fixture "api/fixtures/watermanagementtypeaftercultivation.json" "Water management type after cultivation data"
import_fixture "api/fixtures/packagingmaterialtype.json" "Packaging material type data"
import_fixture "api/fixtures/refrigeranttype.json" "Refrigerant type data"

echo "API fixtures imported successfully!"

# Import IPCC fixtures
echo "Importing IPCC fixtures..."

# Check if combined fixture exists
if [ -f "ipcc/fixtures/all_ipcc_fixtures.json" ]; then
    echo "Importing combined IPCC fixtures..."
    import_fixture "ipcc/fixtures/all_ipcc_fixtures.json" "All IPCC fixtures"
elif [ -f "api/fixtures/all_api_dependencies.json" ]; then
    echo "Importing combined API dependencies first..."
    import_fixture "api/fixtures/all_api_dependencies.json" "All API dependencies"
    echo "Importing combined IPCC fixtures..."
    import_fixture "ipcc/fixtures/all_ipcc_fixtures.json" "All IPCC fixtures"
else
    echo "Combined fixtures not found, importing individual fixtures..."
    
    # Import individual IPCC fixtures in dependency order
    import_fixture "ipcc/fixtures/globalwarmingpotential.json" "Global warming potential data"
    import_fixture "ipcc/fixtures/emissionfactorcategory.json" "Emission factor category data"
    import_fixture "ipcc/fixtures/emissiontype.json" "Emission type data"
    
    # Climate and moisture dependent models
    import_fixture "ipcc/fixtures/dataonmangrove.json" "Data on mangrove"
    import_fixture "ipcc/fixtures/soilorganiccarbon.json" "Soil organic carbon data"
    import_fixture "ipcc/fixtures/grasslandbiomass.json" "Grassland biomass data"
    import_fixture "ipcc/fixtures/grasslandsoc.json" "Grassland SOC data"
    import_fixture "ipcc/fixtures/grasslandstockexchangefactor.json" "Grassland stock exchange factor data"
    
    # Land use dependent models
    import_fixture "ipcc/fixtures/forestcombustionfactor.json" "Forest combustion factor data"
    import_fixture "ipcc/fixtures/afforestationcombustionfactor.json" "Afforestation combustion factor data"
    import_fixture "ipcc/fixtures/litterdeadwoodcarbonstock.json" "Litter deadwood carbon stock data"
    import_fixture "ipcc/fixtures/landusecarbonstockexchangefactor.json" "Land use carbon stock exchange factor data"
    import_fixture "ipcc/fixtures/soilorcaniccarboncnratio.json" "Soil organic carbon CN ratio data"
    import_fixture "ipcc/fixtures/foresttotalbiomass.json" "Forest total biomass data"
    import_fixture "ipcc/fixtures/afforestationlandusestockexchangefactor.json" "Afforestation land use stock exchange factor data"
    import_fixture "ipcc/fixtures/coastalagb.json" "Coastal AGB data"
    import_fixture "ipcc/fixtures/coastalbgb.json" "Coastal BGB data"
    import_fixture "ipcc/fixtures/coastallitter.json" "Coastal litter data"
    import_fixture "ipcc/fixtures/coastaldeadwood.json" "Coastal deadwood data"
    import_fixture "ipcc/fixtures/perennialagb.json" "Perennial AGB data"
    import_fixture "ipcc/fixtures/perennialbgb.json" "Perennial BGB data"
    import_fixture "ipcc/fixtures/perennialmaxagb.json" "Perennial max AGB data"
    import_fixture "ipcc/fixtures/croplandflu.json" "Cropland FLU data"
    import_fixture "ipcc/fixtures/afforestationflu.json" "Afforestation FLU data"
    import_fixture "ipcc/fixtures/defaultsoilcarbonstock.json" "Default soil carbon stock data"
    import_fixture "ipcc/fixtures/drainageemissionfactor.json" "Drainage emission factor data"
    import_fixture "ipcc/fixtures/cropyieldstat.json" "Crop yield stat data"
    import_fixture "ipcc/fixtures/totalbiomassafterdefo.json" "Total biomass after deforestation data"
    
    # Forest dependent models
    import_fixture "ipcc/fixtures/forestmanagementbgb.json" "Forest management BGB data"
    import_fixture "ipcc/fixtures/forestmanagementagbgrowth.json" "Forest management AGB growth data"
    import_fixture "ipcc/fixtures/forestmanagementagb.json" "Forest management AGB data"
    
    # Tillage and organic input dependent models
    import_fixture "ipcc/fixtures/tillagecarbonstockexchangefactor.json" "Tillage carbon stock exchange factor data"
    import_fixture "ipcc/fixtures/organicinputcarbonstockexchangefactor.json" "Organic input carbon stock exchange factor data"
    import_fixture "ipcc/fixtures/croplandfmg.json" "Cropland FMG data"
    import_fixture "ipcc/fixtures/croplandfi.json" "Cropland FI data"
    
    # Soil dependent models
    import_fixture "ipcc/fixtures/rewettingcarbonfactor.json" "Rewetting carbon factor data"
    import_fixture "ipcc/fixtures/rewettingmethanefactor.json" "Rewetting methane factor data"
    
    # Water body dependent models
    import_fixture "ipcc/fixtures/otherconstructedwaterbodiesemissionfactor.json" "Other constructed waterbodies emission factor data"
    
    # Country dependent models
    import_fixture "ipcc/fixtures/atwood.json" "Atwood data"
    import_fixture "ipcc/fixtures/electricityemission.json" "Electricity emission data"
    
    # Fishery dependent models
    import_fixture "ipcc/fixtures/largefisheryfui.json" "Large fishery FUI data"
    import_fixture "ipcc/fixtures/smallfisheryfui.json" "Small fishery FUI data"
    
    # Input dependent models
    import_fixture "ipcc/fixtures/inputreference.json" "Input reference data"
    import_fixture "ipcc/fixtures/inputemissionfactor.json" "Input emission factor data"
    
    # Building and road dependent models
    import_fixture "ipcc/fixtures/buildingemissionfactor.json" "Building emission factor data"
    import_fixture "ipcc/fixtures/roademissionfactor.json" "Road emission factor data"
    
    # Livestock dependent models
    import_fixture "ipcc/fixtures/livestockentericef.json" "Livestock enteric EF data"
    import_fixture "ipcc/fixtures/livestockmanureef.json" "Livestock manure EF data"
    import_fixture "ipcc/fixtures/livestocktam.json" "Livestock TAM data"
    import_fixture "ipcc/fixtures/livestockvser.json" "Livestock VSER data"
    import_fixture "ipcc/fixtures/livestockawms.json" "Livestock AWMS data"
    import_fixture "ipcc/fixtures/livestockner.json" "Livestock NER data"
    import_fixture "ipcc/fixtures/methaneentericfermentationfactor.json" "Methane enteric fermentation factor data"
    import_fixture "ipcc/fixtures/manuremanagementvolatilizationmultiplier.json" "Manure management volatilization multiplier data"
    
    # Energy dependent models
    import_fixture "ipcc/fixtures/energydefaultemissionfactor.json" "Energy default emission factor data"
    import_fixture "ipcc/fixtures/irrigationsystemdata.json" "Irrigation system data"
    import_fixture "ipcc/fixtures/irrigationphasedata.json" "Irrigation phase data"
    import_fixture "ipcc/fixtures/irrigationpressurerequirement.json" "Irrigation pressure requirement data"
    
    # Rice dependent models
    import_fixture "ipcc/fixtures/ricedefaultemissionfactor.json" "Rice default emission factor data"
    import_fixture "ipcc/fixtures/ricesfo.json" "Rice SFO data"
    import_fixture "ipcc/fixtures/ricesfp.json" "Rice SFP data"
    import_fixture "ipcc/fixtures/ricesfw.json" "Rice SFW data"
    import_fixture "ipcc/fixtures/riceyield.json" "Rice yield data"
    
    # Trophic dependent models
    import_fixture "ipcc/fixtures/trophicstatefactor.json" "Trophic state factor data"
    
    # Organic soil dependent models
    import_fixture "ipcc/fixtures/organicsoildrainageemissionfactor.json" "Organic soil drainage emission factor data"
    import_fixture "ipcc/fixtures/peatextractionemissionfactor.json" "Peat extraction emission factor data"
    import_fixture "ipcc/fixtures/peatextractionconversionfactor.json" "Peat extraction conversion factor data"
    import_fixture "ipcc/fixtures/organicsoilfuelconsumption.json" "Organic soil fuel consumption data"
    import_fixture "ipcc/fixtures/organicsoilgefemissionfactor.json" "Organic soil GEF emission factor data"
    import_fixture "ipcc/fixtures/organicsoilrewettingemissionfactor.json" "Organic soil rewetting emission factor data"
    
    # Settlement dependent models
    import_fixture "ipcc/fixtures/settlementef.json" "Settlement EF data"
    
    # Nitrous dependent models
    import_fixture "ipcc/fixtures/nitrousemissionfactor.json" "Nitrous emission factor data"
    import_fixture "ipcc/fixtures/inputsnitrousemissionfactor.json" "Inputs nitrous emission factor data"
    
    # Value chain dependent models
    import_fixture "ipcc/fixtures/valuechainpackagingemissionfactor.json" "Value chain packaging emission factor data"
    import_fixture "ipcc/fixtures/valuechainrefrigerantemissionfactor.json" "Value chain refrigerant emission factor data"
    
    # Shadow price dependent models
    import_fixture "ipcc/fixtures/shadowpriceofcarbon.json" "Shadow price of carbon data"
    
    # FRA dependent models
    import_fixture "ipcc/fixtures/fracarbonstock.json" "FRA carbon stock data"
    
    # Emission factor dependent models
    import_fixture "ipcc/fixtures/burningemissionfactor.json" "Burning emission factor data"
    import_fixture "ipcc/fixtures/firescombustionfactor.json" "Fires combustion factor data"
    import_fixture "ipcc/fixtures/cropnitrousestimationdefaultfactor.json" "Crop nitrous estimation default factor data"
    
    # FMG, FI, FLU data models
    import_fixture "ipcc/fixtures/fmgdata.json" "FMG data"
    import_fixture "ipcc/fixtures/fidata.json" "FI data"
    import_fixture "ipcc/fixtures/fludata.json" "FLU data"
fi

echo "IPCC fixtures imported successfully!"
echo "All fixtures have been imported in the correct dependency order."
