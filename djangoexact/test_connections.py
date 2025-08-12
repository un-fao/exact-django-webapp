#!/usr/bin/env python
"""
Test script to verify database connection management.
Run this to test if the connection pool exhaustion issue is resolved.
"""

import os
import sys
import django
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
django.setup()

from django.db import connection, connections
from minitool.db_manager import get_connection_info, cleanup_connections


def test_connection():
    """Test a single database connection."""
    try:
        info = get_connection_info()
        print(f"Connection test: {info}")
        return info.get("connection_healthy", False)
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


def test_multiple_connections(num_connections=10):
    """Test multiple concurrent connections."""
    print(f"Testing {num_connections} concurrent connections...")

    def single_connection_test():
        return test_connection()

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: single_connection_test(), range(num_connections)))

    successful = sum(results)
    print(f"Successful connections: {successful}/{num_connections}")
    return successful == num_connections


def test_minitool_views():
    """Test minitool view endpoints."""
    print("Testing minitool view endpoints...")

    # Import here to avoid circular imports
    from django.test import RequestFactory
    from minitool.views import EmissionsModulesViewSet

    factory = RequestFactory()
    viewset = EmissionsModulesViewSet()

    # Test db-status endpoint
    request = factory.get("/api/minitool/db-status/")
    try:
        response = viewset.db_status(request)
        print(f"DB status endpoint: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"DB status endpoint failed: {e}")
        return False


def main():
    """Main test function."""
    print("Testing database connection management...")

    # Test 1: Single connection
    print("\n1. Testing single connection...")
    if test_connection():
        print("✓ Single connection test passed")
    else:
        print("✗ Single connection test failed")
        return False

    # Test 2: Multiple connections
    print("\n2. Testing multiple connections...")
    if test_multiple_connections(20):
        print("✓ Multiple connections test passed")
    else:
        print("✗ Multiple connections test failed")
        return False

    # Test 3: Minitool views
    print("\n3. Testing minitool views...")
    if test_minitool_views():
        print("✓ Minitool views test passed")
    else:
        print("✗ Minitool views test failed")
        return False

    # Test 4: Connection cleanup
    print("\n4. Testing connection cleanup...")
    cleanup_connections()

    # Test 5: Direct connections cleanup
    print("\n5. Testing direct connections cleanup...")
    try:
        connections.close_all()
        print("✓ Direct connections cleanup test passed")
    except Exception as e:
        print(f"✗ Direct connections cleanup test failed: {e}")
        return False

    print("✓ Connection cleanup test passed")

    print("\n🎉 All tests passed! Connection management is working properly.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
