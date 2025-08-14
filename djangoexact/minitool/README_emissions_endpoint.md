# Emissions Modules Endpoint

## Overview
The `emissions/modules` endpoint provides access to livestock emissions data with filtering and aggregation capabilities. The data is stored in Django models for efficient querying and filtering.

## Endpoint
```
GET /minitool/emissions/modules/livestock/
```

## Query Parameters

### Standard Filter Parameters
- `region` - Filter by region (e.g., "Eastern Africa", "Central Africa")
- `climate` - Filter by climate (e.g., "Warm Temperate", "Tropical", "Boreal")
- `moisture` - Filter by moisture (e.g., "Dry", "Moist")
- `soil_type` - Filter by soil type (e.g., "Wetland", "High Activity Clay", "Sandy")
- `field` - Filter by change field (e.g., "livestock_production_type")

### Module-Specific Filter Parameters
- `livestock_category_type` - Filter by livestock category (e.g., "Dairy Cattle", "Other Cattle") - **Livestock only**

### Custom Filter Parameters
The system automatically detects custom filter columns based on the data. Any column that is not numerical and doesn't end with "_start", "_w", or "_wo" is treated as a filter. These custom filters are stored in the `custom_filters` JSONField and can be queried directly.

For example, if your data has a custom column like `livestock_category_type`, you can filter by it directly:
```
GET /minitool/emissions/modules/livestock/?livestock_category_type=Dairy%20Cattle
```

## Available Custom Filters

To discover what custom filters are available for each module, use the custom-filters endpoints:

### Livestock
```
GET /minitool/emissions/modules/livestock/custom-filters/
```

### Annual Cropland
```
GET /minitool/emissions/modules/annual-cropland/custom-filters/
```

### Flooded Rice
```
GET /minitool/emissions/modules/flooded-rice/custom-filters/
```

### Grassland
```
GET /minitool/emissions/modules/grassland/custom-filters/
```

These endpoints return a JSON object with available custom filter fields and their possible values:

```json
{
  "livestock_category_type": ["Dairy Cattle", "Other Cattle", "Sheep", "Goats"],
  "production_system": ["Intensive", "Extensive", "Mixed"]
}
```

## Response Format

```json
{
  "filters_applied": {
    "region": "Eastern Africa",
    "climate": "Warm Temperate",
    "livestock_category_type": "Dairy Cattle"
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

### Filter by livestock category (standard field)
```
GET /minitool/emissions/modules/livestock/?livestock_category_type=Dairy%20Cattle
```

### Filter by custom field
```
GET /minitool/emissions/modules/livestock/?production_system=Intensive
```

### Filter by specific field
```
GET /minitool/emissions/modules/livestock/?field=livestock_production_type
```

### Get available custom filters
```
GET /minitool/emissions/modules/livestock/custom-filters/
```

## Data Models

The endpoint uses two Django models:

### LivestockChange
Stores individual livestock change records with all metadata and the change details.

### LivestockChangeAggregate
Stores pre-aggregated statistics for each change type, enabling fast querying and filtering.

Both models include a `custom_filters` JSONField that stores dynamic filter columns.

## Data Import

To import data from the JSON file into the database models, use the management command:

```bash
# Import all data (clears existing data first)
python manage.py import_changes --all --clear

# Import specific module
python manage.py import_changes --file livestock_changes.json --module-type livestock

# Import only aggregated data (skip individual records)
python manage.py import_changes --all --aggregate-only
```

The import command automatically detects custom filter columns based on the rule:
- If a column is not numerical and doesn't end with "_start", "_w", or "_wo", it's treated as a filter
- These custom filters are stored in the `custom_filters` JSONField

## Performance

The endpoint uses database queries and pre-aggregated statistics for optimal performance:
- Filtering is done at the database level
- Statistics are pre-calculated and stored
- Queries are optimized with database indexes
- JSON field filtering is supported for custom filters
- Results are returned in a structured format for easy consumption
