"""DB-free guard: FAOSTAT crops must not be linked to the Perennial Cropland module.

Fixtures are regenerated from live databases, so a DB that still carries the old
links would silently bring them back on the next regeneration. This test fails
when that happens.
"""

import json
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)
FAOSTAT_SHEET = BASE_DIR / "scripts" / "ipcc_data" / "FAOSTAT_Crop_Types_20260813.xlsx"
FIXTURES = (
    BASE_DIR / "api" / "fixtures" / "landusetype.json",
    BASE_DIR / "api" / "fixtures" / "all_reference_data.json",
)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


class FaostatCropsNotPerennialGuardTests(SimpleTestCase):
    def test_no_faostat_crop_is_linked_to_perennial_cropland(self):
        sheet = pd.read_excel(FAOSTAT_SHEET, sheet_name="Annualsperennials")
        faostat_items = {
            str(item).replace("ï»¿", "").replace("﻿", "").strip() for item in sheet["ITEM"].dropna()
        }
        module_types = _load(BASE_DIR / "api" / "fixtures" / "moduletype.json")
        perennial_pk = next(m["pk"] for m in module_types if m["fields"]["class_name"] == "PerennialCropland")

        for fixture in FIXTURES:
            offending = sorted(
                row["fields"]["name"]
                for row in _load(fixture)
                if row["model"] == "api.landusetype"
                and row["fields"].get("name") in faostat_items
                and perennial_pk in row["fields"].get("module_types", [])
            )
            with self.subTest(fixture=fixture.name):
                self.assertEqual(offending, [], f"FAOSTAT crops linked to PerennialCropland in {fixture.name}")
