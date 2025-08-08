# Emissions Modules Endpoint

## Overview
The `emissions/modules` endpoint provides access to livestock emissions data with filtering and aggregation capabilities. The data is stored in Django models for efficient querying and filtering.

## Endpoint
```
GET /minitool/emissions/modules/livestock/
```

## Query Parameters

### Filter Parameters
- `region` - Filter by region (e.g., "Eastern Africa", "Central Africa")
- `climate` - Filter by climate (e.g., "Warm Temperate", "Tropical", "Boreal")
- `moisture` - Filter by moisture (e.g., "Dry", "Moist")
- `soil_type` - Filter by soil type (e.g., "Wetland", "High Activity Clay", "Sandy")
- `livestock_category_type` - Filter by livestock category (e.g., "Dairy Cattle", "Other Cattle")
- `field` - Filter by change field (e.g., "livestock_production_type")

## Response Format

```json
{
  "filters_applied": {
    "region": "Eastern Africa",
    "climate": "Warm Temperate"
  },
  "total_records_analyzed": 72,
  "aggregated_results": {
    "livestock_production_type": {
      "field": "livestock_production_type",
      "changes": [
        {
          "from": "Default",
          "to": "High-Productivity",
          "statistics": {
            "count": 12,
            "sum": 81.0239,
            "mean": 6.7520,
            "median": 5.8186,
            "min": 4.7768,
            "max": 9.3984,
            "q1": 5.4977,
            "q3": 8.9712
          }
        }
      ]
    }
  }
}
```

## Statistics Fields
For each change, the following statistical measures are provided:
- `count` - Number of records with this change
- `sum` - Sum of all total values for this change
- `mean` - Average total value
- `median` - Median total value
- `min` - Minimum total value
- `max` - Maximum total value
- `q1` - First quartile (25th percentile)
- `q3` - Third quartile (75th percentile)

## Example Usage

### Get all livestock data
```
GET /minitool/emissions/modules/livestock/
```

### Filter by region
```
GET /minitool/emissions/modules/livestock/?region=Eastern%20Africa
```

### Filter by multiple criteria
```
GET /minitool/emissions/modules/livestock/?region=Eastern%20Africa&climate=Warm%20Temperate&moisture=Dry
```

### Filter by livestock category
```
GET /minitool/emissions/modules/livestock/?livestock_category_type=Dairy%20Cattle
```

### Filter by specific field
```
GET /minitool/emissions/modules/livestock/?field=livestock_production_type
```

## Data Models

The endpoint uses two Django models:

### LivestockChange
Stores individual livestock change records with all metadata and the change details.

### LivestockChangeAggregate
Stores pre-aggregated statistics for each change type, enabling fast querying and filtering.

## Data Import

To import data from the JSON file into the database models, use the management command:

```bash
# Import all data (clears existing data first)
python manage.py import_livestock_changes --clear

# Import with custom file path
python manage.py import_livestock_changes --file path/to/livestock_changes.json

# Import only aggregated data (skip individual records)
python manage.py import_livestock_changes --aggregate-only
```

## Performance

The endpoint uses database queries and pre-aggregated statistics for optimal performance:
- Filtering is done at the database level
- Statistics are pre-calculated and stored
- Queries are optimized with database indexes
- Results are returned in a structured format for easy consumption
