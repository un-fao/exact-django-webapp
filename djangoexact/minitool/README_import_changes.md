# Import Changes Command

This document describes the generalized import command for importing changes data from JSON files into the database models.

## Overview

The `import_changes` command is a generalized version of the original `import_livestock_changes` command that can handle all module types:
- Livestock
- Annual Cropland  
- Flooded Rice
- Grassland

## Usage

### Import a Single Module Type

```bash
python manage.py import_changes --file <filename> --module-type <module-type>
```

**Parameters:**
- `--file`: Path to the JSON file (relative to the changes directory)
- `--module-type`: One of `livestock`, `annual-cropland`, `flooded-rice`, `grassland`
- `--clear`: (Optional) Clear existing data before importing
- `--aggregate-only`: (Optional) Only create aggregated data, skip individual records

**Examples:**

```bash
# Import livestock changes
python manage.py import_changes --file livestock_changes.json --module-type livestock --clear

# Import annual cropland changes (aggregate only)
python manage.py import_changes --file annualcropland_changes.json --module-type annual-cropland --aggregate-only

# Import flooded rice changes
python manage.py import_changes --file floodedrice_changes.json --module-type flooded-rice

# Import grassland changes
python manage.py import_changes --file grassland_changes.json --module-type grassland --clear
```

### Import All Module Types

```bash
python manage.py import_changes --all [--clear] [--aggregate-only]
```

This will import all module types from their respective files:
- `livestock_changes.json` → Livestock
- `annualcropland_changes.json` → Annual Cropland
- `floodedrice_changes.json` → Flooded Rice
- `grassland_changes.json` → Grassland

**Examples:**

```bash
# Import all modules
python manage.py import_changes --all

# Import all modules with clearing existing data
python manage.py import_changes --all --clear

# Import all modules (aggregate only)
python manage.py import_changes --all --aggregate-only
```

## Data Structure

The command expects JSON files with the following structure:

### Common Structure
```json
[
  {
    "module_type": "Module Name",
    "region": "Region Name",
    "climate": "Climate Type",
    "moisture": "Moisture Level",
    "soil_type": "Soil Type",
    "total": 123.45,
    "changes": [
      {
        "field": "field_name",
        "from": "old_value",
        "to": "new_value"
      }
    ]
  }
]
```

### Module-Specific Fields

#### Livestock
```json
{
  "module_type": "Livestock",
  "region": "Eastern Africa",
  "climate": "Warm Temperate",
  "moisture": "Dry",
  "soil_type": "Wetland",
  "total": 8.97,
  "changes": [...],
  "livestock_category_type": "Dairy Cattle"
}
```

#### Annual Cropland
```json
{
  "module_type": "Annual Cropland",
  "region": "Malawi",
  "climate": "Cool Temperate",
  "moisture": "Dry",
  "soil_type": "High Activity Clay",
  "total": -2.93,
  "changes": [...]
}
```

#### Flooded Rice
```json
{
  "module_type": "Floodedrice",
  "region": "Mayotte",
  "climate": "Cool Temperate",
  "moisture": "Dry",
  "soil_type": "High Activity Clay",
  "total": -6.42,
  "changes": [...]
}
```

#### Grassland
```json
{
  "module_type": "Grassland",
  "region": "Eastern Africa",
  "climate": "Cool Temperate",
  "moisture": "Dry",
  "soil_type": "High Activity Clay",
  "total": -1.82,
  "changes": [...],
  "module": "Grassland"
}
```

## Models Created

The command creates two types of records for each module:

### Individual Change Records
- `LivestockChange`
- `AnnualCroplandChange`
- `FloodedRiceChange`
- `GrasslandChange`

### Aggregated Statistics Records
- `LivestockChangeAggregate`
- `AnnualCroplandChangeAggregate`
- `FloodedRiceChangeAggregate`
- `GrasslandChangeAggregate`

## Testing

Use the test command to verify the import functionality:

```bash
python manage.py test_import_changes --module-type livestock
```

This will create a small test file, run the import, and clean up afterward.

## File Locations

The command automatically looks for files in:
```
djangoexact/minitool/scripts/minitool/changes/
```

Supported files:
- `livestock_changes.json`
- `annualcropland_changes.json`
- `floodedrice_changes.json`
- `grassland_changes.json`

## Error Handling

The command includes comprehensive error handling:
- File not found errors
- JSON parsing errors
- Database transaction rollback on errors
- Detailed progress reporting
- Statistics on created/skipped records

## Performance Considerations

- Uses database transactions for data integrity
- Processes large files efficiently with streaming JSON parsing
- Provides progress updates for long-running imports
- Supports `--aggregate-only` for faster processing when individual records aren't needed
