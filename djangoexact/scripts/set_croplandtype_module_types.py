"""
Set LandUseType.module_types for annual/perennial cropland from IPCC CSV.

Usage:
    python manage.py runscript set_croplandtype_module_types
    python manage.py runscript set_croplandtype_module_types --script-args=--apply
"""

import csv
from pathlib import Path

from django.db import transaction

from api.models import LandUseType, ModuleType


CSV_PATH = Path(__file__).parent / "ipcc_data" / "CropNitrous-annualperennials.csv"


class _DryRun(Exception):
    """Sentinel raised to roll back the atomic block on dry-run."""


def run(*args):
    apply = "--apply" in args

    try:
        annual = ModuleType.objects.get(class_name="AnnualCropland")
        perennial = ModuleType.objects.get(class_name="PerennialCropland")
    except ModuleType.DoesNotExist as e:
        print(f"ERROR: required ModuleType not found: {e}")
        return

    try:
        with transaction.atomic():
            with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item = row["ITEM"].strip()
                    if item == "Default":
                        continue
                    if "+ (Total)" in item:
                        continue

                    lut = LandUseType.objects.filter(name=item).first()
                    if lut is None:
                        print(f"  skip: LandUseType '{item}' not found")
                        continue

                    lut.module_types.clear()
                    assigned = []
                    if row["ANNUALS"].strip().upper() == "YES":
                        lut.module_types.add(annual)
                        assigned.append("AnnualCropland")
                    if row["PERENNIALS"].strip().upper() == "YES":
                        lut.module_types.add(perennial)
                        assigned.append("PerennialCropland")

                    print(f"  '{item}': {assigned or 'none'}")

            if not apply:
                raise _DryRun()
    except _DryRun:
        print("\nDRY RUN — no changes committed. Re-run with --apply to persist.")
    else:
        print("\nApplied.")
