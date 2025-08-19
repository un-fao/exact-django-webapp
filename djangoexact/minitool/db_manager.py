from django.db import connection, connections
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@contextmanager
def managed_db_connection():
    """
    Context manager to ensure database connections are properly managed.
    This helps prevent connection pool exhaustion.
    """
    try:
        yield connection
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        # Always close connections to prevent pool exhaustion
        connections.close_all()


def cleanup_connections():
    """
    Force cleanup of all database connections.
    Call this after heavy database operations.
    """
    try:
        connections.close_all()
        logger.debug("Database connections cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up connections: {e}")


def get_connection_info():
    """
    Get information about the current database connection.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]

        return {
            "database": connection.settings_dict.get("NAME", "unknown"),
            "host": connection.settings_dict.get("HOST", "unknown"),
            "port": connection.settings_dict.get("PORT", "unknown"),
            "version": version,
            "connection_healthy": True,
        }
    except Exception as e:
        return {"connection_healthy": False, "error": str(e)}
