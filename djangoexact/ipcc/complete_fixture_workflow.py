#!/usr/bin/env python3
"""
Complete IPCC Fixture Workflow Example

This script demonstrates the complete workflow for managing IPCC fixtures:
1. Generate fixtures from the database
2. Load fixtures in the correct order
3. Validate the process

Usage:
    python ipcc/complete_fixture_workflow.py
    python ipcc/complete_fixture_workflow.py --test-mode
"""

import os
import subprocess
import sys
import argparse


def run_command(cmd, description, check=True):
    """Run a command and display the result."""
    print(f"\n{'=' * 60}")
    print(f"Step: {description}")
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

        if check and result.returncode != 0:
            print(f"❌ Command failed: {description}")
            return False
        else:
            print(f"✅ Command completed: {description}")
            return True
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False


def main():
    """Run the complete IPCC fixture workflow."""
    parser = argparse.ArgumentParser(description="Complete IPCC Fixture Workflow")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode (dry-run)")
    parser.add_argument("--skip-generation", action="store_true", help="Skip fixture generation step")
    parser.add_argument("--skip-loading", action="store_true", help="Skip fixture loading step")
    args = parser.parse_args()

    # Change to Django project directory
    django_dir = "/Users/claudiolavacca/Developer/FAO/exact-django-webapp/djangoexact"
    os.chdir(django_dir)

    print("🌍 IPCC Complete Fixture Workflow")
    print("=" * 60)
    print("This script demonstrates the complete workflow for managing IPCC fixtures")
    print("=" * 60)

    # Determine if we're in test mode
    dry_run_flag = "--dry-run" if args.test_mode else ""

    success_count = 0
    total_steps = 0

    # Step 1: Generate IPCC fixtures with dependencies
    if not args.skip_generation:
        total_steps += 1
        cmd = f"python manage.py generate_ipcc_fixtures --include-dependencies {dry_run_flag}"
        if run_command(cmd, "Generate IPCC fixtures with API dependencies"):
            success_count += 1

    # Step 2: Validate generated fixtures
    if not args.skip_generation:
        total_steps += 1
        cmd = f"python manage.py load_ipcc_fixtures --include-dependencies --dry-run"
        if run_command(cmd, "Validate generated fixtures (dry run)"):
            success_count += 1

    # Step 3: Load IPCC fixtures
    if not args.skip_loading:
        total_steps += 1
        cmd = f"python manage.py load_ipcc_fixtures --include-dependencies {dry_run_flag}"
        if run_command(cmd, "Load IPCC fixtures with dependencies"):
            success_count += 1

    # Step 4: Verify loading (if not in test mode)
    if not args.test_mode and not args.skip_loading:
        total_steps += 1
        cmd = "python manage.py shell -c \"from ipcc.models import *; print(f'IPCC models loaded: {GlobalWarmingPotential.objects.count()} GWP, {SoilOrganicCarbon.objects.count()} SOC')\""
        if run_command(cmd, "Verify IPCC data was loaded", check=False):
            success_count += 1

    # Step 5: Test specific model loading
    total_steps += 1
    cmd = f"python manage.py load_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon {dry_run_flag}"
    if run_command(cmd, "Test loading specific models"):
        success_count += 1

    # Step 6: Test error handling
    total_steps += 1
    cmd = f"python manage.py load_ipcc_fixtures --continue-on-error {dry_run_flag}"
    if run_command(cmd, "Test error handling (continue on error)"):
        success_count += 1

    # Summary
    print(f"\n{'=' * 60}")
    print("WORKFLOW SUMMARY")
    print("=" * 60)

    print(f"Mode: {'Test (dry-run)' if args.test_mode else 'Production'}")
    print(f"Steps completed: {success_count}/{total_steps}")

    if success_count == total_steps:
        print("🎉 All steps completed successfully!")
        print("\nNext steps:")
        if args.test_mode:
            print("1. Run without --test-mode to execute the actual workflow")
            print("2. Verify your database has the required API data")
            print("3. Check that fixture files are generated correctly")
        else:
            print("1. Verify IPCC data is loaded in your database")
            print("2. Test your application with the loaded data")
            print("3. Consider backing up your database")
        return 0
    else:
        print("❌ Some steps failed!")
        print("\nTroubleshooting:")
        print("1. Check that your database has the required API data")
        print("2. Verify fixture directories exist and are writable")
        print("3. Run with --test-mode to debug without making changes")
        print("4. Check Django logs for detailed error messages")
        return 1


if __name__ == "__main__":
    sys.exit(main())
