# Minitool Database Migration to GCP Cloud SQL

## Current State Analysis
- **Database**: SQLite with ~9.9M records
- **Modules**: Livestock (1M), Annual Cropland (168K), Flooded Rice (150K), Grassland (8.5M)
- **Query Patterns**: Complex aggregations, JSON filtering, statistical calculations
- **Performance Issues**: Connection pool exhaustion, slow complex queries

## Recommended Solution: Cloud SQL PostgreSQL

### Why PostgreSQL?
1. **JSONB Performance**: Superior handling of your `custom_filters` JSONField
2. **Advanced Indexing**: Better for complex filtering patterns
3. **Aggregation Optimization**: Excellent for statistical calculations
4. **Connection Pooling**: Built-in PgBouncer support
5. **Cost-Effective**: Better price/performance than Spanner for your scale

### Instance Configuration
```yaml
Instance Type: db-custom-8-32
- 8 vCPU cores
- 32GB RAM
- SSD storage (100GB+)

PostgreSQL Version: 15 or 16
Connection Pool: PgBouncer enabled
Backup: Automated daily backups
High Availability: Enabled (optional)
```

## Migration Steps

### 1. Data Export from SQLite
```bash
# Export current data to JSON format
python manage.py dumpdata minitool --indent=2 > minitool_data.json

# Or use Django's serialization
python manage.py shell
>>> from django.core import serializers
>>> from minitool.models import *
>>> data = serializers.serialize('json', ChangeAggregate.objects.all())
>>> with open('change_aggregate_data.json', 'w') as f:
...     f.write(data)
```

### 2. Cloud SQL Setup
```bash
# Create Cloud SQL instance
gcloud sql instances create minitool-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-8-32 \
  --storage-type=SSD \
  --storage-size=100GB \
  --region=us-central1 \
  --backup-start-time=02:00 \
  --enable-bin-log

# Create database
gcloud sql databases create minitool --instance=minitool-db

# Create user
gcloud sql users create minitool_user \
  --instance=minitool-db \
  --password=YOUR_SECURE_PASSWORD
```

### 3. Django Settings Update
```python
# settings.py
DATABASES = {
    'default': {
        # ... existing default database
    },
    'minitool': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'minitool',
        'USER': 'minitool_user',
        'PASSWORD': 'YOUR_SECURE_PASSWORD',
        'HOST': '/cloudsql/PROJECT_ID:REGION:minitool-db',
        'PORT': '5432',
        'OPTIONS': {
            'application_name': 'djangoexact_minitool',
            'connect_timeout': 30,
        },
        'CONN_MAX_AGE': 0,
        'ATOMIC_REQUESTS': False,
    }
}
```

### 4. Database Optimization
```sql
-- Create optimized indexes for your query patterns
CREATE INDEX CONCURRENTLY idx_change_aggregate_module_type ON minitool_changeaggregate(module_type);
CREATE INDEX CONCURRENTLY idx_change_aggregate_region ON minitool_changeaggregate(region);
CREATE INDEX CONCURRENTLY idx_change_aggregate_climate ON minitool_changeaggregate(climate);
CREATE INDEX CONCURRENTLY idx_change_aggregate_moisture ON minitool_changeaggregate(moisture);
CREATE INDEX CONCURRENTLY idx_change_aggregate_soil_type ON minitool_changeaggregate(soil_type);
CREATE INDEX CONCURRENTLY idx_change_aggregate_field ON minitool_changeaggregate(field);

-- JSONB indexes for custom_filters
CREATE INDEX CONCURRENTLY idx_change_aggregate_custom_filters_gin ON minitool_changeaggregate USING GIN (custom_filters);

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY idx_change_aggregate_module_region ON minitool_changeaggregate(module_type, region);
CREATE INDEX CONCURRENTLY idx_change_aggregate_module_field ON minitool_changeaggregate(module_type, field);

-- Partial indexes for specific modules
CREATE INDEX CONCURRENTLY idx_livestock_changes ON minitool_changeaggregate(module_type, field, from_value, to_value) 
WHERE module_type = 'Livestock';
```

### 5. Performance Monitoring
```python
# Add to your views for query monitoring
from django.db import connection
import time

def monitor_query_performance(view_func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = view_func(*args, **kwargs)
        end_time = time.time()
        
        # Log query performance
        logger.info(f"Query took {end_time - start_time:.2f} seconds")
        
        # Log actual SQL queries
        for query in connection.queries:
            logger.debug(f"SQL: {query['sql']} - Time: {query['time']}")
            
        return result
    return wrapper
```

## Expected Performance Improvements

### Query Performance
- **Complex aggregations**: 5-10x faster with proper indexing
- **JSON filtering**: 3-5x faster with GIN indexes
- **Statistical calculations**: 2-3x faster with optimized queries

### Connection Management
- **Connection pooling**: Eliminates connection exhaustion
- **Better resource utilization**: More efficient memory usage
- **Scalability**: Can handle 10x more concurrent users

### Cost Estimation
- **Cloud SQL db-custom-8-32**: ~$1,200/month
- **Storage (100GB SSD)**: ~$17/month
- **Backup storage**: ~$5/month
- **Total**: ~$1,222/month

## Alternative: Cloud Spanner (For Extreme Scale)

If you expect >100M records or need global distribution:

```yaml
Instance Configuration:
- Processing Units: 1000 (minimum)
- Storage: Automatic scaling
- Multi-region: us-central1, europe-west1

Cost: ~$3,000/month (minimum)
```

## Migration Timeline

1. **Week 1**: Setup Cloud SQL instance and test connectivity
2. **Week 2**: Migrate data and test performance
3. **Week 3**: Optimize indexes and queries
4. **Week 4**: Deploy to production with monitoring

## Monitoring and Maintenance

### Cloud Monitoring
```yaml
Metrics to Monitor:
- Query performance (avg response time)
- Connection pool utilization
- CPU and memory usage
- Storage growth
- Error rates
```

### Regular Maintenance
- Weekly: Review slow query logs
- Monthly: Analyze index usage
- Quarterly: Review and optimize query patterns
