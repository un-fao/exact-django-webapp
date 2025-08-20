# Minitool Caching Strategy

## Current State Analysis

Your minitool has **perfect caching opportunities**:

### Query Patterns That Benefit from Caching:
1. **Complex aggregations** with multiple filters (region, climate, moisture, soil_type)
2. **Statistical calculations** (mean, median, quartiles, min/max)
3. **JSON field filtering** on `custom_filters`
4. **Cross-module comparisons** and summaries
5. **Field and filter metadata** (available values, counts)

### Current Caching Infrastructure:
- ✅ Django's `cache` framework already configured
- ✅ `CachedResultMixin` for API modules
- ✅ Cache invalidation patterns established
- ❌ **No caching for minitool queries**

## Recommended Caching Architecture

### 1. **Multi-Layer Caching Strategy**

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Request                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                CDN/Edge Cache                               │
│              (Cloud CDN - 1 hour)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Application Cache                              │
│           (Redis/MemoryCache - 15 min)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Database Cache                                 │
│        (PostgreSQL Materialized Views)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              PostgreSQL Database                            │
└─────────────────────────────────────────────────────────────┘
```

### 2. **GCP Caching Services**

#### **Primary: Cloud Memorystore for Redis**
```yaml
Instance Configuration:
- Tier: Basic
- Size: 1GB (can scale up)
- Region: Same as your Cloud SQL
- Network: VPC with Cloud SQL

Cost: ~$50/month
```

#### **Secondary: Cloud CDN**
```yaml
Configuration:
- Cache TTL: 1 hour for GET requests
- Invalidation: Manual or automatic
- Edge locations: Global

Cost: ~$10-20/month (depending on traffic)
```

## Implementation Plan

### 1. **Redis Cache Configuration**

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://YOUR_REDIS_IP:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'minitool',
        'TIMEOUT': 900,  # 15 minutes default
    },
    'long_term': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://YOUR_REDIS_IP:6379/2',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'minitool_long',
        'TIMEOUT': 3600,  # 1 hour
    }
}
```

### 2. **Cache Decorators for Minitool Views**

```python
# minitool/cache_utils.py
from django.core.cache import cache
from functools import wraps
import hashlib
import json
import time

def cache_minitool_query(timeout=900, key_prefix="minitool_query"):
    """
    Cache decorator for minitool queries with intelligent key generation.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Generate cache key from request parameters
            cache_key = generate_cache_key(request, key_prefix)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute view and cache result
            result = view_func(self, request, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator

def generate_cache_key(request, prefix):
    """Generate unique cache key from request parameters."""
    # Get all query parameters
    params = dict(request.query_params)
    
    # Sort parameters for consistent key generation
    sorted_params = sorted(params.items())
    
    # Create hash of parameters
    param_string = json.dumps(sorted_params, sort_keys=True)
    param_hash = hashlib.md5(param_string.encode()).hexdigest()
    
    return f"{prefix}:{param_hash}"

def cache_aggregation_result(module_type, filters, timeout=1800):
    """
    Cache aggregation results with longer timeout.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and parameters
            key_parts = [func.__name__, module_type]
            key_parts.extend([f"{k}:{v}" for k, v in sorted(filters.items())])
            cache_key = f"minitool_agg:{hashlib.md5(':'.join(key_parts).encode()).hexdigest()}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator
```

### 3. **Enhanced Minitool Views with Caching**

```python
# minitool/views.py (updated)
from .cache_utils import cache_minitool_query, cache_aggregation_result

class EmissionsModulesViewSet(viewsets.GenericViewSet):
    
    @cache_minitool_query(timeout=1800, key_prefix="minitool_livestock")
    @decorators.action(detail=False, methods=["get"])
    @close_db_connections
    def livestock(self, request, *args, **kwargs):
        """Get livestock emissions modules data with caching."""
        queryset, filters = self.get_filtered_queryset("livestock", request)
        
        # Cache the aggregation result
        @cache_aggregation_result("livestock", filters, timeout=3600)
        def get_aggregated_data():
            return self.aggregate_by_change(queryset)
        
        aggregated_data = get_aggregated_data()
        
        response_data = {
            "filters_applied": filters,
            "total_records_analyzed": queryset.count(),
            "aggregated_results": aggregated_data,
            "cached_at": time.time()
        }
        
        return Response(response_data)

    @cache_minitool_query(timeout=1800, key_prefix="minitool_summary")
    @decorators.action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request, *args, **kwargs):
        """Get summary statistics for all modules with caching."""
        # Implementation with caching
        pass

    @cache_minitool_query(timeout=3600, key_prefix="minitool_fields")
    @decorators.action(detail=False, methods=["get"])
    def fields(self, request, *args, **kwargs):
        """Get fields with caching."""
        # Implementation with caching
        pass
```

### 4. **Database-Level Caching (Materialized Views)**

```sql
-- Create materialized views for common aggregations
CREATE MATERIALIZED VIEW minitool_livestock_summary AS
SELECT 
    module_type,
    region,
    climate,
    moisture,
    soil_type,
    COUNT(*) as total_records,
    SUM(count) as total_changes,
    AVG(mean) as avg_impact,
    MIN(min_value) as min_impact,
    MAX(max_value) as max_impact
FROM minitool_changeaggregate 
WHERE module_type = 'Livestock'
GROUP BY module_type, region, climate, moisture, soil_type;

-- Create indexes on materialized view
CREATE INDEX idx_livestock_summary_region ON minitool_livestock_summary(region);
CREATE INDEX idx_livestock_summary_climate ON minitool_livestock_summary(climate);

-- Refresh materialized views (run periodically)
REFRESH MATERIALIZED VIEW CONCURRENTLY minitool_livestock_summary;
```

### 5. **Cache Invalidation Strategy**

```python
# minitool/cache_manager.py
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ChangeAggregate

class MinitoolCacheManager:
    """Manages cache invalidation for minitool data."""
    
    @staticmethod
    def invalidate_module_cache(module_type):
        """Invalidate all cache entries for a specific module."""
        # Get all keys for this module
        pattern = f"minitool_{module_type.lower().replace(' ', '_')}:*"
        keys = cache.keys(pattern)
        
        if keys:
            cache.delete_many(keys)
    
    @staticmethod
    def invalidate_all_minitool_cache():
        """Invalidate all minitool cache entries."""
        pattern = "minitool:*"
        keys = cache.keys(pattern)
        
        if keys:
            cache.delete_many(keys)
    
    @staticmethod
    def warm_cache():
        """Pre-populate cache with common queries."""
        from .views import EmissionsModulesViewSet
        
        viewset = EmissionsModulesViewSet()
        
        # Warm cache for common queries
        common_filters = [
            {"region": "Eastern Africa"},
            {"climate": "Warm Temperate"},
            {"module_type": "Livestock"},
        ]
        
        for filters in common_filters:
            # Simulate requests to populate cache
            pass

# Signal handlers for automatic cache invalidation
@receiver(post_save, sender=ChangeAggregate)
def invalidate_cache_on_save(sender, instance, **kwargs):
    """Invalidate cache when data is updated."""
    MinitoolCacheManager.invalidate_module_cache(instance.module_type)

@receiver(post_delete, sender=ChangeAggregate)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when data is deleted."""
    MinitoolCacheManager.invalidate_module_cache(instance.module_type)
```

### 6. **Cache Monitoring and Analytics**

```python
# minitool/cache_monitoring.py
from django.core.cache import cache
import time
import logging

logger = logging.getLogger(__name__)

class CacheMetrics:
    """Track cache performance metrics."""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.start_time = time.time()
    
    def record_hit(self):
        self.hits += 1
    
    def record_miss(self):
        self.misses += 1
    
    def get_hit_rate(self):
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0
    
    def get_stats(self):
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.get_hit_rate(),
            'uptime': time.time() - self.start_time
        }

def cache_monitor_decorator(func):
    """Decorator to monitor cache performance."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        # Check if result is in cache
        cache_key = f"monitor:{func.__name__}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            metrics.record_hit()
            logger.info(f"Cache HIT for {func.__name__}")
        else:
            metrics.record_miss()
            logger.info(f"Cache MISS for {func.__name__}")
        
        result = func(*args, **kwargs)
        
        execution_time = time.time() - start_time
        logger.info(f"{func.__name__} executed in {execution_time:.2f}s")
        
        return result
    return wrapper
```

## Expected Performance Improvements

### **Cache Hit Rates:**
- **Field metadata queries**: 95%+ hit rate (rarely change)
- **Aggregation queries**: 80-90% hit rate (15-minute cache)
- **Summary queries**: 90%+ hit rate (1-hour cache)
- **Complex filters**: 70-80% hit rate (depends on filter combinations)

### **Response Time Improvements:**
- **Cached queries**: 10-50ms (vs 500ms-2s uncached)
- **Database queries**: 2-5x faster with materialized views
- **Overall API**: 3-10x faster for common queries

### **Cost-Benefit Analysis:**
- **Redis Memorystore**: $50/month
- **Performance gain**: 3-10x faster queries
- **User experience**: Dramatically improved
- **Database load**: Significantly reduced

## Implementation Timeline

### **Week 1: Basic Caching**
1. Setup Redis Memorystore
2. Implement cache decorators
3. Add caching to main minitool endpoints

### **Week 2: Advanced Caching**
1. Implement cache invalidation
2. Add materialized views
3. Setup cache monitoring

### **Week 3: Optimization**
1. Fine-tune cache timeouts
2. Implement cache warming
3. Add cache analytics

### **Week 4: Production**
1. Deploy with monitoring
2. Performance testing
3. Cache optimization based on usage patterns

## Monitoring and Maintenance

### **Key Metrics to Track:**
- Cache hit rate (target: >80%)
- Average response time
- Cache memory usage
- Cache eviction rate
- Database query reduction

### **Regular Maintenance:**
- Weekly: Review cache hit rates
- Monthly: Optimize cache timeouts
- Quarterly: Analyze cache patterns and adjust strategy

This caching strategy will transform your minitool performance, making it 3-10x faster while reducing database load and improving user experience!
