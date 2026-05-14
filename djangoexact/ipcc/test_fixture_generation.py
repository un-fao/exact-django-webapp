#!/usr/bin/env python3
"""
Test script to demonstrate the IPCC fixture generation functionality.

This script shows how to use the fixture generation command with different options.
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
        # Local fixture-generation test script; cmd is built from in-script literals, not user input.
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)  # nosemgrep
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
    """Run various tests of the fixture generation command."""

    # Change to Django project directory
    django_dir = "/Users/claudiolavacca/Developer/FAO/exact-django-webapp/djangoexact"
    os.chdir(django_dir)

    print("IPCC Fixture Generation Test Suite")
    print("=" * 60)

    # Test 1: Dry run with dependencies
    success1 = run_command("python manage.py generate_ipcc_fixtures --include-dependencies --dry-run", "Dry run with API dependencies")

    # Test 2: Generate specific models only
    success2 = run_command("python manage.py generate_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon --dry-run", "Generate specific models only")

    # Test 3: Generate with custom output directories
    success3 = run_command("python manage.py generate_ipcc_fixtures --include-dependencies --output-dir /tmp/ipcc_test --api-output-dir /tmp/api_test --dry-run", "Custom output directories")

    # Test 4: Generate with XML format
    success4 = run_command("python manage.py generate_ipcc_fixtures --format xml --dry-run", "XML output format")

    # Test 5: Help command
    success5 = run_command("python manage.py generate_ipcc_fixtures --help", "Help command")

    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print("=" * 60)
    tests = [
        ("Dry run with dependencies", success1),
        ("Specific models only", success2),
        ("Custom output directories", success3),
        ("XML output format", success4),
        ("Help command", success5),
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
