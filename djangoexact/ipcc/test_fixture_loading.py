#!/usr/bin/env python3
"""
Test script to demonstrate the IPCC fixture loading functionality.

This script shows how to use the fixture loading command with different options.
"""

import os
import subprocess
import sys


def run_command(cmd, description):
    """Run a command and display the result."""
    print(f"\n{'=' * 60}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def main():
    """Run various tests of the fixture loading command."""

    # Change to Django project directory
    django_dir = "/Users/claudiolavacca/Developer/FAO/exact-django-webapp/djangoexact"
    os.chdir(django_dir)

    print("IPCC Fixture Loading Test Suite")
    print("=" * 60)

    # Test 1: Dry run with dependencies
    success1 = run_command("python manage.py load_ipcc_fixtures --include-dependencies --dry-run", "Dry run with API dependencies")

    # Test 2: Load specific models only
    success2 = run_command("python manage.py load_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon --dry-run", "Load specific models only")

    # Test 3: Load with custom fixture directories
    success3 = run_command("python manage.py load_ipcc_fixtures --include-dependencies --fixtures-dir /tmp/ipcc_test --api-fixtures-dir /tmp/api_test --dry-run", "Custom fixture directories")

    # Test 4: Load with XML format
    success4 = run_command("python manage.py load_ipcc_fixtures --format xml --dry-run", "XML format fixtures")

    # Test 5: Load with continue on error
    success5 = run_command("python manage.py load_ipcc_fixtures --continue-on-error --dry-run", "Continue on error mode")

    # Test 6: Help command
    success6 = run_command("python manage.py load_ipcc_fixtures --help", "Help command")

    # Test 7: Skip validation
    success7 = run_command("python manage.py load_ipcc_fixtures --skip-validation --dry-run", "Skip validation mode")

    # Test 8: Clean slate
    success8 = run_command("python manage.py load_ipcc_fixtures --clean-slate --dry-run", "Clean slate mode")

    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print("=" * 60)
    tests = [
        ("Dry run with dependencies", success1),
        ("Specific models only", success2),
        ("Custom fixture directories", success3),
        ("XML format fixtures", success4),
        ("Continue on error mode", success5),
        ("Help command", success6),
        ("Skip validation mode", success7),
        ("Clean slate mode", success8),
    ]

    for test_name, success in tests:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")

    total_tests = len(tests)
    passed_tests = sum(1 for _, success in tests if success)

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("All tests passed! ✅")
        return 0
    else:
        print("Some tests failed! ❌")
        return 1


if __name__ == "__main__":
    sys.exit(main())
