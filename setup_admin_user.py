#!/usr/bin/env python3
"""
Script to set up the admin user for the Django backend.
Run this script from the backend directory to create the admin user.
"""

import os
import sys
import django

# Add the djangoexact directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "djangoexact"))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
django.setup()

from django.core.management import call_command

if __name__ == "__main__":
    print("Setting up admin user...")
    try:
        call_command("create_admin_user")
        print("Admin user setup completed successfully!")
    except Exception as e:
        print(f"Error setting up admin user: {e}")
        sys.exit(1)
