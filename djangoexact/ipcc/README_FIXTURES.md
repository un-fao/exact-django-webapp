# IPCC Fixtures Import Guide

This document explains the proper order for importing IPCC fixtures and their dependencies on API models.

## Overview

The IPCC app contains 80+ models that depend on various API models through foreign key relationships. When importing fixtures, it's crucial to follow the correct order to avoid foreign key constraint violations.

## Fixture Management

The IPCC app provides two main management commands for handling fixtures:

### 1. Fixture Generation

Use the provided management command to generate fixtures for all IPCC models and their dependencies:

```bash
# Generate all IPCC fixtures
python manage.py generate_ipcc_fixtures

# Generate IPCC fixtures AND dump latest API dependencies
python manage.py generate_ipcc_fixtures --include-dependencies

# Generate fixtures for specific models
python manage.py generate_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon

# Generate fixtures in custom directories
python manage.py generate_ipcc_fixtures --output-dir /path/to/ipcc/fixtures --api-output-dir /path/to/api/fixtures

# Dry run to see what would be generated
python manage.py generate_ipcc_fixtures --include-dependencies --dry-run

# Generate with different output format
python manage.py generate_ipcc_fixtures --format xml --indent 4
```

### Command Options

- `--include-dependencies`: Also dump the latest API dependency fixtures from the database
- `--output-dir`: Directory for IPCC fixtures (default: `ipcc/fixtures`)
- `--api-output-dir`: Directory for API dependency fixtures (default: `api/fixtures`)
- `--models`: Comma-separated list of specific IPCC models to generate
- `--format`: Output format - json, xml, or yaml (default: json)
- `--indent`: JSON indentation level (default: 2)
- `--dry-run`: Show what would be generated without creating files

### 2. Fixture Loading

Use the provided management command to load fixtures in the correct dependency order:

```bash
# Load all IPCC fixtures
python manage.py load_ipcc_fixtures

# Load IPCC fixtures with API dependencies
python manage.py load_ipcc_fixtures --include-dependencies

# Load specific models only
python manage.py load_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon

# Load with custom fixture directories
python manage.py load_ipcc_fixtures --fixtures-dir /path/to/ipcc/fixtures --api-fixtures-dir /path/to/api/fixtures

# Dry run to see what would be loaded
python manage.py load_ipcc_fixtures --include-dependencies --dry-run

# Load with different format
python manage.py load_ipcc_fixtures --format xml

# Continue loading even if some fixtures fail
python manage.py load_ipcc_fixtures --continue-on-error

# Skip pre-load validation
python manage.py load_ipcc_fixtures --skip-validation
```

#### Loading Command Options

- `--include-dependencies`: Also load API dependency fixtures before IPCC fixtures
- `--fixtures-dir`: Directory containing IPCC fixture files (default: `ipcc/fixtures`)
- `--api-fixtures-dir`: Directory containing API fixture files (default: `api/fixtures`)
- `--models`: Comma-separated list of specific IPCC models to load
- `--dry-run`: Show what would be loaded without actually loading fixtures
- `--skip-validation`: Skip pre-load validation checks
- `--continue-on-error`: Continue loading other fixtures if one fails
- `--format`: Expected fixture format - json, xml, or yaml (default: json)

## Import Order

### 1. API Models (Prerequisites)

**CRITICAL**: All API models must be imported before any IPCC models. The following API models are required:

#### Core Reference Models (Import First)
- `Climate` - Climate zones
- `Moisture` - Moisture levels  
- `Region` - Geographic regions
- `Country` - Countries
- `SoilType` - Soil classifications
- `LandUseType` - Land use categories
- `ForestType` - Forest classifications
- `ModuleType` - Module types

#### Management Type Models
- `TillageManagementType` - Tillage practices
- `OrganicInputType` - Organic input types
- `GrasslandManagementType` - Grassland management
- `ManureManagementType` - Manure management
- `WaterRegimeType` - Water regime types
- `IrrigationSystemType` - Irrigation systems

#### Specialized Type Models
- `LivestockCategoryType` - Livestock categories
- `LivestockProductionType` - Production types
- `IPCCRegion` - IPCC regions
- `FuelType` - Fuel types
- `InputType` - Input types
- `BuildingType` - Building types
- `RoadType` - Road types
- `SalinityType` - Salinity levels
- `WaterbodyType` - Water body types
- `TrophicType` - Trophic types
- `FisheryType` - Fishery types
- `FishType` - Fish types
- `GearType` models - Fishing gear types
- `PeatType` - Peat types
- `FireType` - Fire types
- `SiteLocationType` - Site locations
- `OrganicAmendmentType` - Organic amendments
- `WaterManagementType` models - Water management
- `PackagingMaterialType` - Packaging materials
- `RefrigerantType` - Refrigerant types

### 2. IPCC Models (Import Order)

#### Tier 1: No Dependencies (Import First)
```bash
python manage.py loaddata ipcc/fixtures/globalwarmingpotential.json
python manage.py loaddata ipcc/fixtures/emissionfactorcategory.json
python manage.py loaddata ipcc/fixtures/emissiontype.json
```

#### Tier 2: API Dependencies Only
```bash
# Climate and Moisture dependent models
python manage.py loaddata ipcc/fixtures/dataonmangrove.json
python manage.py loaddata ipcc/fixtures/soilorganiccarbon.json
python manage.py loaddata ipcc/fixtures/grasslandbiomass.json
python manage.py loaddata ipcc/fixtures/grasslandsoc.json
python manage.py loaddata ipcc/fixtures/grasslandstockexchangefactor.json

# Land use dependent models
python manage.py loaddata ipcc/fixtures/forestcombustionfactor.json
python manage.py loaddata ipcc/fixtures/afforestationcombustionfactor.json
python manage.py loaddata ipcc/fixtures/litterdeadwoodcarbonstock.json
python manage.py loaddata ipcc/fixtures/landusecarbonstockexchangefactor.json
python manage.py loaddata ipcc/fixtures/soilorcaniccarboncnratio.json
python manage.py loaddata ipcc/fixtures/foresttotalbiomass.json
python manage.py loaddata ipcc/fixtures/afforestationlandusestockexchangefactor.json
python manage.py loaddata ipcc/fixtures/coastalagb.json
python manage.py loaddata ipcc/fixtures/coastalbgb.json
python manage.py loaddata ipcc/fixtures/coastallitter.json
python manage.py loaddata ipcc/fixtures/coastaldeadwood.json
python manage.py loaddata ipcc/fixtures/perennialagb.json
python manage.py loaddata ipcc/fixtures/perennialbgb.json
python manage.py loaddata ipcc/fixtures/perennialmaxagb.json
python manage.py loaddata ipcc/fixtures/croplandflu.json
python manage.py loaddata ipcc/fixtures/afforestationflu.json
python manage.py loaddata ipcc/fixtures/defaultsoilcarbonstock.json
python manage.py loaddata ipcc/fixtures/drainageemissionfactor.json
python manage.py loaddata ipcc/fixtures/cropyieldstat.json
python manage.py loaddata ipcc/fixtures/totalbiomassafterdefo.json

# Forest dependent models
python manage.py loaddata ipcc/fixtures/forestmanagementbgb.json
python manage.py loaddata ipcc/fixtures/forestmanagementagbgrowth.json
python manage.py loaddata ipcc/fixtures/forestmanagementagb.json

# Tillage and organic input dependent models
python manage.py loaddata ipcc/fixtures/tillagecarbonstockexchangefactor.json
python manage.py loaddata ipcc/fixtures/organicinputcarbonstockexchangefactor.json
python manage.py loaddata ipcc/fixtures/croplandfmg.json
python manage.py loaddata ipcc/fixtures/croplandfi.json

# Soil dependent models
python manage.py loaddata ipcc/fixtures/rewettingcarbonfactor.json
python manage.py loaddata ipcc/fixtures/rewettingmethanefactor.json

# Water body dependent models
python manage.py loaddata ipcc/fixtures/otherconstructedwaterbodiesemissionfactor.json

# Country dependent models
python manage.py loaddata ipcc/fixtures/atwood.json
python manage.py loaddata ipcc/fixtures/electricityemission.json

# Fishery dependent models
python manage.py loaddata ipcc/fixtures/largefisheryfui.json
python manage.py loaddata ipcc/fixtures/smallfisheryfui.json

# Input dependent models
python manage.py loaddata ipcc/fixtures/inputreference.json
python manage.py loaddata ipcc/fixtures/inputemissionfactor.json

# Building and road dependent models
python manage.py loaddata ipcc/fixtures/buildingemissionfactor.json
python manage.py loaddata ipcc/fixtures/roademissionfactor.json

# Livestock dependent models
python manage.py loaddata ipcc/fixtures/livestockentericef.json
python manage.py loaddata ipcc/fixtures/livestockmanureef.json
python manage.py loaddata ipcc/fixtures/livestocktam.json
python manage.py loaddata ipcc/fixtures/livestockvser.json
python manage.py loaddata ipcc/fixtures/livestockawms.json
python manage.py loaddata ipcc/fixtures/livestockner.json
python manage.py loaddata ipcc/fixtures/methaneentericfermentationfactor.json
python manage.py loaddata ipcc/fixtures/manuremanagementvolatilizationmultiplier.json

# Energy dependent models
python manage.py loaddata ipcc/fixtures/energydefaultemissionfactor.json
python manage.py loaddata ipcc/fixtures/irrigationsystemdata.json
python manage.py loaddata ipcc/fixtures/irrigationphasedata.json
python manage.py loaddata ipcc/fixtures/irrigationpressurerequirement.json

# Rice dependent models
python manage.py loaddata ipcc/fixtures/ricedefaultemissionfactor.json
python manage.py loaddata ipcc/fixtures/ricesfo.json
python manage.py loaddata ipcc/fixtures/ricesfp.json
python manage.py loaddata ipcc/fixtures/ricesfw.json
python manage.py loaddata ipcc/fixtures/riceyield.json

# Trophic dependent models
python manage.py loaddata ipcc/fixtures/trophicstatefactor.json

# Organic soil dependent models
python manage.py loaddata ipcc/fixtures/organicsoildrainageemissionfactor.json
python manage.py loaddata ipcc/fixtures/peatextractionemissionfactor.json
python manage.py loaddata ipcc/fixtures/peatextractionconversionfactor.json
python manage.py loaddata ipcc/fixtures/organicsoilfuelconsumption.json
python manage.py loaddata ipcc/fixtures/organicsoilgefemissionfactor.json
python manage.py loaddata ipcc/fixtures/organicsoilrewettingemissionfactor.json

# Settlement dependent models
python manage.py loaddata ipcc/fixtures/settlementef.json

# Nitrous dependent models
python manage.py loaddata ipcc/fixtures/nitrousemissionfactor.json
python manage.py loaddata ipcc/fixtures/inputsnitrousemissionfactor.json

# Value chain dependent models
python manage.py loaddata ipcc/fixtures/valuechainpackagingemissionfactor.json
python manage.py loaddata ipcc/fixtures/valuechainrefrigerantemissionfactor.json

# Shadow price dependent models
python manage.py loaddata ipcc/fixtures/shadowpriceofcarbon.json

# FRA dependent models
python manage.py loaddata ipcc/fixtures/fracarbonstock.json

# Emission factor dependent models
python manage.py loaddata ipcc/fixtures/burningemissionfactor.json
python manage.py loaddata ipcc/fixtures/firescombustionfactor.json
python manage.py loaddata ipcc/fixtures/cropnitrousestimationdefaultfactor.json

# FMG, FI, FLU data models
python manage.py loaddata ipcc/fixtures/fmgdata.json
python manage.py loaddata ipcc/fixtures/fidata.json
python manage.py loaddata ipcc/fixtures/fludata.json
```

## Loading Workflow

### Recommended Workflow

1. **Generate Fixtures** (if needed):
   ```bash
   python manage.py generate_ipcc_fixtures --include-dependencies
   ```

2. **Load Fixtures**:
   ```bash
   python manage.py load_ipcc_fixtures --include-dependencies
   ```

### Alternative Loading Methods

#### Method 1: Using the Management Command (Recommended)
```bash
# Complete workflow with validation
python manage.py load_ipcc_fixtures --include-dependencies

# Or with dry run first
python manage.py load_ipcc_fixtures --include-dependencies --dry-run
python manage.py load_ipcc_fixtures --include-dependencies
```

#### Method 2: Using the Shell Script
```bash
# Use the provided shell script
./ipcc/import_ipcc_fixtures.sh
```

#### Method 3: Manual Django loaddata
```bash
# Import API fixtures first
python manage.py loaddata api/fixtures/all_api_dependencies.json

# Import IPCC fixtures
python manage.py loaddata ipcc/fixtures/all_ipcc_fixtures.json
```

## Automated Import Script

The provided shell script (`ipcc/import_ipcc_fixtures.sh`) automatically imports fixtures in the correct order:

```bash
#!/bin/bash
# import_ipcc_fixtures.sh

echo "Importing IPCC fixtures in dependency order..."

# Import API fixtures first (assuming they exist)
echo "Importing API fixtures..."
python manage.py loaddata api/fixtures/climate.json
python manage.py loaddata api/fixtures/moisture.json
python manage.py loaddata api/fixtures/region.json
python manage.py loaddata api/fixtures/country.json
python manage.py loaddata api/fixtures/soiltype.json
python manage.py loaddata api/fixtures/landusetype.json
python manage.py loaddata api/fixtures/foresttype.json
python manage.py loaddata api/fixtures/moduletype.json
# ... (add all required API fixtures)

# Import IPCC fixtures
echo "Importing IPCC fixtures..."
python manage.py loaddata ipcc/fixtures/all_ipcc_fixtures.json

echo "IPCC fixtures imported successfully!"
```

## Dependency Validation

The fixture generation script automatically validates that all required API models exist and have data before generating IPCC fixtures. This helps prevent import failures due to missing dependencies.

### Validation Features

- **Missing Model Detection**: Identifies API models that don't exist in the database
- **Empty Model Detection**: Identifies API models that exist but have no data
- **Dependency Warnings**: Provides clear warnings about potential import issues
- **Automatic Suggestions**: Recommends using `--include-dependencies` to dump latest API data

### Example Validation Output

```
Warning: Empty API models (no data): Climate, Moisture, Region
Warning: Some API dependencies are missing or empty. IPCC fixtures may fail to import.
Warning: Consider running with --include-dependencies to dump latest API data.
```

## Troubleshooting

### Common Issues

1. **Foreign Key Constraint Violations**
   - Ensure API models are imported before IPCC models
   - Check that referenced records exist in the database
   - Use `--include-dependencies` to ensure latest API data is available

2. **Missing Dependencies**
   - Verify all required API models have data
   - Check fixture file paths and names
   - Run the script with `--include-dependencies` to dump current API data

3. **Data Integrity Issues**
   - Validate fixture data before import
   - Use `--dry-run` flag to test the generation process
   - Check validation warnings for missing or empty models

4. **API App Not Found**
   - Ensure the API app is properly configured in Django settings
   - Verify the API app is installed and accessible

### Validation Commands

```bash
# Check for missing foreign key references
python manage.py shell -c "
from ipcc.models import *
from django.db import IntegrityError
for model in [GlobalWarmingPotential, SoilOrganicCarbon, ForestTotalBiomass]:
    try:
        model.objects.first()
        print(f'{model.__name__}: OK')
    except Exception as e:
        print(f'{model.__name__}: {e}')
"

# Verify fixture data integrity
python manage.py validate
```

## Notes

- The fixture generation script automatically handles the dependency order
- Individual fixture files are created for each model for granular control
- A combined fixture file is also generated for bulk import
- Always test imports in a development environment first
- Consider using database transactions for large imports

## Model Dependencies Summary

| IPCC Model | API Dependencies |
|------------|------------------|
| Most models | Climate, Moisture |
| Forest models | ForestType, Region |
| Land use models | LandUseType |
| Soil models | SoilType |
| Livestock models | LivestockCategoryType, LivestockProductionType, IPCCRegion |
| Fishery models | FisheryType, FishType, GearType models |
| Energy models | FuelType, InputType |
| Building models | BuildingType, RoadType |
| Water models | WaterbodyType, SalinityType |
| Organic soil models | PeatType, FireType, SiteLocationType |

This dependency structure ensures that all referenced records exist before importing IPCC data.

## New Features

### Automatic Dependency Dumping

The enhanced fixture generation script now includes the ability to automatically dump the latest API dependency fixtures from the database:

```bash
# Generate IPCC fixtures and dump latest API dependencies
python manage.py generate_ipcc_fixtures --include-dependencies
```

This ensures that:
- All required API models are up-to-date
- No missing dependencies when importing IPCC fixtures
- Consistent data across different environments

### Dependency Validation

The script automatically validates API dependencies before generating IPCC fixtures:

- **Pre-flight Checks**: Validates all required API models exist
- **Data Validation**: Checks that API models contain data
- **Clear Warnings**: Provides specific guidance on missing dependencies
- **Automatic Suggestions**: Recommends solutions for common issues

### Enhanced Output Options

- **Multiple Formats**: Support for JSON, XML, and YAML output
- **Custom Directories**: Separate output directories for API and IPCC fixtures
- **Combined Fixtures**: Automatic generation of combined fixture files
- **Dry Run Mode**: Test generation without creating files

### Testing

Test scripts are provided to validate both fixture generation and loading functionality:

```bash
# Test fixture generation
python ipcc/test_fixture_generation.py

# Test fixture loading
python ipcc/test_fixture_loading.py
```

These test suites validate various command options and ensure the processes work correctly.

## Loading Features

### Comprehensive Validation

The loading command includes extensive validation:

- **Pre-load Checks**: Validates API dependencies before loading IPCC fixtures
- **Directory Validation**: Ensures fixture directories exist
- **Model Validation**: Checks that required API models have data
- **Interactive Prompts**: Asks for confirmation when dependencies are missing

### Error Handling

- **Continue on Error**: Option to continue loading other fixtures if one fails
- **Detailed Error Messages**: Clear indication of what went wrong
- **Graceful Degradation**: Handles missing fixtures gracefully
- **Transaction Safety**: Uses Django's built-in transaction handling

### Flexible Loading Options

- **Combined Fixtures**: Automatically detects and uses combined fixture files
- **Individual Fixtures**: Falls back to individual fixture files if combined files don't exist
- **Specific Models**: Load only specific IPCC models
- **Multiple Formats**: Support for JSON, XML, and YAML fixtures
- **Custom Directories**: Specify custom fixture directories

### Loading Order Management

The command automatically handles the correct loading order:

1. **API Dependencies First** (if `--include-dependencies` is used)
2. **IPCC Models in Dependency Order**
3. **Validation Between Steps**
4. **Error Recovery Options**

## Complete Workflow

### Automated Workflow Script

A complete workflow script is provided that demonstrates the entire process:

```bash
# Run the complete workflow in test mode
python ipcc/complete_fixture_workflow.py --test-mode

# Run the complete workflow in production mode
python ipcc/complete_fixture_workflow.py

# Skip generation step (if fixtures already exist)
python ipcc/complete_fixture_workflow.py --skip-generation

# Skip loading step (if you only want to generate)
python ipcc/complete_fixture_workflow.py --skip-loading
```

### Workflow Steps

The complete workflow includes:

1. **Generate Fixtures**: Create IPCC and API dependency fixtures from database
2. **Validate Fixtures**: Dry-run validation of generated fixtures
3. **Load Fixtures**: Load fixtures in correct dependency order
4. **Verify Loading**: Confirm data was loaded successfully
5. **Test Specific Models**: Test loading individual models
6. **Test Error Handling**: Verify error handling works correctly

### Quick Start

For a quick start with IPCC fixtures:

```bash
# 1. Generate and load all fixtures
python manage.py generate_ipcc_fixtures --include-dependencies
python manage.py load_ipcc_fixtures --include-dependencies

# 2. Or use the complete workflow script
python ipcc/complete_fixture_workflow.py --test-mode  # Test first
python ipcc/complete_fixture_workflow.py             # Then run for real
```
