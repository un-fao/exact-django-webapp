"""The perennial cropland "agroforestry system" choices come from the land use types linked to its module type.

`SimpleTestCase` on purpose: it reads the committed fixtures, no database. Both copies are checked because
load_reference_data reads landusetype.json and dump_reference_data writes all_reference_data.json.
"""

import json
from pathlib import Path

from django.test import SimpleTestCase

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# The agroforestry and perennial crop systems EX-ACT has factors for, plus the generic and default rows.
PERENNIAL_SYSTEMS = {
    "Alley Cropping",
    "Perennial Fallow",
    "Hedgerow",
    "Multistrata",
    "Parkland",
    "Shaded Perennial",
    "Silvoarable",
    "Silvopasture",
    "Olive",
    "Orchard",
    "Short Rotation Coppice",
    "Tea",
    "Vine",
    "Oil Palm",
    "Rubber",
    "Generic Value",
    "Agroforestry - Default",
}


def _rows(name, model):
    return [row for row in json.loads((FIXTURES / name).read_text(encoding="utf-8")) if row["model"] == model]


class PerennialLandUseTypesTests(SimpleTestCase):
    def test_perennial_cropland_offers_only_its_systems(self):
        (perennial,) = [row["pk"] for row in _rows("moduletype.json", "api.moduletype") if row["fields"]["class_name"] == "PerennialCropland"]
        for name in ("landusetype.json", "all_reference_data.json"):
            with self.subTest(fixture=name):
                linked = {row["fields"]["name"] for row in _rows(name, "api.landusetype") if perennial in row["fields"]["module_types"]}
                self.assertEqual(linked, PERENNIAL_SYSTEMS)
