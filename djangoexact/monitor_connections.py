#!/usr/bin/env python
"""
Simple monitoring script to track database connection usage.
Run this to monitor connection health during minitool usage.
"""

import os
import sys
import time
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
django.setup()

from django.db import connections
from minitool.db_manager import get_connection_info


def monitor_connections():
    """Monitor database connections in real-time."""
    print("🔍 Database Connection Monitor")
    print("=" * 50)

    try:
        while True:
            # Get connection info
            info = get_connection_info()

            # Get connection count
            connection_count = len(connections.all())

            # Clear screen (works on most terminals)
            os.system("clear" if os.name == "posix" else "cls")

            print("🔍 Database Connection Monitor")
            print("=" * 50)
            print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Connection Health: {'✅ Healthy' if info.get('connection_healthy') else '❌ Unhealthy'}")
            print(f"Active Connections: {connection_count}")

            if info.get("connection_healthy"):
                print(f"Database: {info.get('database', 'unknown')}")
                print(f"Host: {info.get('host', 'unknown')}")
                print(f"Port: {info.get('port', 'unknown')}")
                if info.get("version"):
                    print(f"Version: {info.get('version', 'unknown')}")
            else:
                print(f"Error: {info.get('error', 'Unknown error')}")

            print("\nPress Ctrl+C to stop monitoring...")

            # Wait 5 seconds before next check
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped by user")
        print("Closing all connections...")
        connections.close_all()
        print("✅ All connections closed")


def quick_check():
    """Quick connection health check."""
    print("🔍 Quick Connection Health Check")
    print("=" * 40)

    info = get_connection_info()
    connection_count = len(connections.all())

    print(f"Connection Health: {'✅ Healthy' if info.get('connection_healthy') else '❌ Unhealthy'}")
    print(f"Active Connections: {connection_count}")

    if info.get("connection_healthy"):
        print(f"Database: {info.get('database', 'unknown')}")
        print(f"Host: {info.get('host', 'unknown')}")
        print(f"Port: {info.get('port', 'unknown')}")
        if info.get("version"):
            print(f"Version: {info.get('version', 'unknown')}")
    else:
        print(f"Error: {info.get('error', 'Unknown error')}")

    # Close connections after check
    connections.close_all()
    print("\n✅ Connections closed after check")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        monitor_connections()
    else:
        quick_check()

