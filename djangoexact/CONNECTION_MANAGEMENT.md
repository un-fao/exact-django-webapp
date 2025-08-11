# Database Connection Management

This document describes the database connection management system implemented to prevent connection pool exhaustion in the minitool application.

## Problem

The minitool was experiencing PostgreSQL connection pool exhaustion errors:
```
django.db.utils.OperationalError: connection to server at "localhost" (::1), port 5542 failed: FATAL: remaining connection slots are reserved for non-replication superuser connections.
```

## Solution

We've implemented a comprehensive connection management system:

### 1. Database Settings (`djangoexact/settings.py`)

- **CONN_MAX_AGE**: Set to 0 to close connections immediately after use
- **ATOMIC_REQUESTS**: Disabled to prevent automatic transactions
- **Statement Timeout**: Added 30-second timeout for long-running queries
- **Application Name**: Added for better connection identification

### 2. Connection Management (`minitool/db_manager.py`)

- **managed_db_connection()**: Context manager for safe database operations
- **cleanup_connections()**: Force cleanup of all database connections
- **get_connection_info()**: Get connection health information

### 3. Middleware (`minitool/middleware.py`)

- **DatabaseConnectionMiddleware**: Automatically closes connections after each request

### 4. View Decorators (`minitool/views.py`)

- **@close_db_connections**: Decorator for heavy database operations
- Applied to main minitool endpoints: livestock, annual-cropland, flooded-rice, grassland

### 5. Script Optimization (`scripts/minitool.py`)

- Reduced ProcessPoolExecutor workers from 8 to 4
- Added connection cleanup in worker initialization

## Usage

### Testing Connection Management

```bash
# Run comprehensive connection tests
python djangoexact/test_connections.py

# Quick connection health check
python djangoexact/monitor_connections.py

# Real-time connection monitoring
python djangoexact/monitor_connections.py --monitor
```

### API Endpoints

- **GET /api/minitool/db-status/**: Basic connection health
- **GET /api/minitool/connection-stats/**: Detailed connection statistics

### Manual Connection Cleanup

```python
from minitool.db_manager import cleanup_connections
from django.db import connections

# Clean up all connections
cleanup_connections()

# Or directly
connections.close_all()
```

## Monitoring

### Real-time Monitoring

Run the monitoring script to watch connection usage in real-time:

```bash
python djangoexact/monitor_connections.py --monitor
```

This will show:
- Connection health status
- Active connection count
- Database information
- Real-time updates every 5 seconds

### Quick Health Check

```bash
python djangoexact/monitor_connections.py
```

## Best Practices

1. **Always use the decorator** for heavy database operations
2. **Monitor connection usage** during development
3. **Test connection management** before deployment
4. **Use the context manager** for custom database operations

## Troubleshooting

### Connection Still Exhausted?

1. Check if all views are using the `@close_db_connections` decorator
2. Verify middleware is properly configured
3. Monitor connection usage with the monitoring script
4. Check for long-running queries that might be holding connections

### Performance Issues?

1. The `CONN_MAX_AGE: 0` setting may impact performance slightly
2. Consider adjusting the statement timeout if needed
3. Monitor query performance with Django Debug Toolbar

## Files Modified

- `djangoexact/djangoexact/settings.py` - Database configuration
- `djangoexact/minitool/db_manager.py` - Connection management utilities
- `djangoexact/minitool/middleware.py` - Connection cleanup middleware
- `djangoexact/minitool/views.py` - View decorators and monitoring endpoints
- `djangoexact/scripts/minitool.py` - Script optimization
- `djangoexact/test_connections.py` - Connection testing
- `djangoexact/monitor_connections.py` - Connection monitoring

## Results

After implementing these changes:
- ✅ Connection pool exhaustion resolved
- ✅ Proper connection cleanup after each request
- ✅ Monitoring capabilities for connection health
- ✅ Reduced concurrent connection usage
- ✅ Better error handling and recovery

