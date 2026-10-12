import csv
import io
import json
import re
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, Client, override_settings

from admin_scripts.fra_carbon_stock import parse_payload, replace_carbon_stock
from admin_scripts.tests.test_views import MIDDLEWARE_WITHOUT_DB_CLEANUP
from api.models import Country, CustomUser
from ipcc.models import FRACarbonStock

DJANGOEXACT_DIR = Path(__file__).resolve().parents[2]
MAPPING_CSV = DJANGOEXACT_DIR / "api" / "data" / "country_iso3.csv"
COUNTRY_FIXTURE = DJANGOEXACT_DIR / "api" / "fixtures" / "country.json"
FRA_CSV = DJANGOEXACT_DIR / "scripts" / "ipcc_data" / "FRACarbonStock2025.csv"

# The two known cross-source aliases plus the curly-apostrophe variant: FRA's
# country list and api.Country's fixture names disagree on these three strings.
FRA_NAME_ALIASES = {
    "Ascension, Saint Helena and Tristan da Cunha": "Saint Helena",
    "Naoero": "Nauru",
    "Côte d'Ivoire": "Côte d’Ivoire",
}

SPOT_CHECKS = {
    "AFG": "Afghanistan",
    "DZA": "Algeria",
    "CIV": "Côte d’Ivoire",
    "PRK": "Democratic People's Republic Of Korea",
    "KOR": "Republic Of Korea",
    "RUS": "Russian Federation",
    "VNM": "Viet Nam",
    "USA": "United States Of America",
    "GBR": "United Kingdom Of Great Britain And Northern Ireland",
    "TUR": "Türkiye",
    "SWZ": "Eswatini",
    "CPV": "Cabo Verde",
    "TLS": "Timor-Leste",
    "CZE": "Czechia",
    "HKG": "China, Hong Kong SAR",
    "MAC": "China, Macao SAR",
}


def _load_mapping():
    with io.open(MAPPING_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Iso3MappingTest(SimpleTestCase):
    """Offline correctness gate on the hand-authored ISO3 mapping."""

    def test_format_uniqueness_and_coverage(self):
        mapping = _load_mapping()
        names = {
            c["fields"]["name"]
            for c in json.load(io.open(COUNTRY_FIXTURE, encoding="utf-8"))
        }

        self.assertTrue(
            all(re.fullmatch(r"[A-Z]{3}", r["iso3"]) for r in mapping),
            "every iso3 must be exactly 3 uppercase letters",
        )
        self.assertEqual(
            len({r["iso3"] for r in mapping}), len(mapping), "duplicate iso3 code",
        )
        self.assertEqual(
            len({r["name"] for r in mapping}), len(mapping), "duplicate name",
        )
        self.assertGreaterEqual(len(mapping), 245)

        missing = [r["name"] for r in mapping if r["name"] not in names]
        self.assertEqual(missing, [], "mapping name not found in country.json fixture")

    def test_all_fra_country_names_covered(self):
        mapping_names = {r["name"].lower() for r in _load_mapping()}

        with io.open(FRA_CSV, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        fra_names = [r["country"] for r in rows if r["country"] != "© FRA 2026"]

        self.assertEqual(len(fra_names), 236)

        missing = []
        for name in fra_names:
            mapped_name = FRA_NAME_ALIASES.get(name, name)
            if mapped_name.lower() not in mapping_names:
                missing.append(name)
        self.assertEqual(missing, [], "FRA country name with no ISO3 mapping entry")

    def test_spot_check_codes(self):
        mapping = {r["iso3"]: r["name"] for r in _load_mapping()}
        for iso3, expected_name in SPOT_CHECKS.items():
            self.assertEqual(mapping.get(iso3), expected_name, f"iso3={iso3}")


class Iso3FixtureTest(SimpleTestCase):
    """country.json rows carry the mapped iso3, and only the mapped ones."""

    def test_fixture_iso3_matches_mapping(self):
        mapping = {r["name"]: r["iso3"] for r in _load_mapping()}
        fixture = json.load(io.open(COUNTRY_FIXTURE, encoding="utf-8"))

        for obj in fixture:
            if obj.get("model") != "api.country":
                continue
            name = obj["fields"]["name"]
            expected = mapping.get(name)
            self.assertEqual(
                obj["fields"].get("iso3"), expected,
                f"fixture iso3 mismatch for {name!r}",
            )


class ParsePayloadTest(SimpleTestCase):
    def test_parses_full_null_calculated_and_missing_variable(self):
        payload = {
            "fra": {
                "2025": {
                    "ITA": {
                        "carbonStockAvg": {
                            "2025": {
                                "carbon_forest_above_ground": {"raw": "50.60"},
                                "carbon_forest_below_ground": {"raw": "10.20"},
                                "carbon_forest_deadwood": {"raw": "0.80"},
                                "carbon_forest_litter": {"raw": "1.40"},
                            }
                        }
                    },
                    "AFG": {
                        "carbonStockAvg": {
                            "2025": {
                                "carbon_forest_above_ground": {"raw": "41.08"},
                                "carbon_forest_below_ground": {"raw": "10.84"},
                                "carbon_forest_deadwood": {"raw": None},
                                "carbon_forest_litter": {"raw": "0.50"},
                            }
                        }
                    },
                    "BRA": {
                        "carbonStockAvg": {
                            "2025": {
                                "carbon_forest_above_ground": {"raw": "120.00", "calculated": True},
                                "carbon_forest_below_ground": {"raw": "30.00"},
                                "carbon_forest_deadwood": {"raw": "5.00"},
                                "carbon_forest_litter": {"raw": "2.00"},
                            }
                        }
                    },
                    "XYZ": {
                        "carbonStockAvg": {
                            "2025": {
                                "carbon_forest_above_ground": {"raw": "1.00"},
                                # carbon_forest_below_ground missing entirely
                                "carbon_forest_deadwood": {"raw": "0.10"},
                                "carbon_forest_litter": {"raw": "0.20"},
                            }
                        }
                    },
                }
            }
        }

        result = parse_payload(payload, "2025")

        self.assertEqual(
            result["ITA"],
            {"agb": 50.60, "bgb": 10.20, "deadwood": 0.80, "litter": 1.40},
        )
        self.assertEqual(result["AFG"]["deadwood"], None)
        self.assertEqual(result["AFG"]["agb"], 41.08)
        self.assertEqual(result["BRA"]["agb"], 120.00)
        # missing variable key -> None, no KeyError
        self.assertEqual(result["XYZ"]["bgb"], None)
        self.assertEqual(result["XYZ"]["agb"], 1.00)


class ReplaceCarbonStockTest(TestCase):
    def setUp(self):
        self.italy = Country.objects.create(name="Italy", iso3="ITA")
        self.france = Country.objects.create(name="France", iso3="FRA")
        self.no_iso = Country.objects.create(name="No ISO Country")
        # Stale row for a different year and a different country.
        FRACarbonStock.objects.create(
            country=self.no_iso, year=2020, agb=1.0, bgb=1.0, deadwood=1.0, litter=1.0,
        )

    def test_replace_deletes_stale_and_writes_single_year(self):
        by_iso = {
            "ITA": {"agb": 50.6, "bgb": 10.2, "deadwood": 0.8, "litter": 1.4},
            "FRA": {"agb": None, "bgb": None, "deadwood": None, "litter": None},
            "ZZZ": {"agb": 9.0, "bgb": 9.0, "deadwood": 9.0, "litter": 9.0},
        }

        result = replace_carbon_stock("2020", by_iso)

        self.assertEqual(result["year"], 2020)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["unmapped"], ["ZZZ"])

        # Stale row for the unrelated country/year is gone.
        self.assertFalse(
            FRACarbonStock.objects.filter(country=self.no_iso).exists()
        )

        italy_row = FRACarbonStock.objects.get(country=self.italy)
        self.assertEqual(italy_row.year, 2020)
        self.assertEqual(italy_row.agb, 50.6)
        self.assertEqual(italy_row.bgb, 10.2)

        france_row = FRACarbonStock.objects.get(country=self.france)
        self.assertIsNone(france_row.agb)

        # The invariant calculators.py:7289 depends on: exactly one year exists.
        self.assertEqual(
            FRACarbonStock.objects.values_list("year", flat=True).distinct().count(),
            1,
        )


@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_DB_CLEANUP)
class FraCarbonStockViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = CustomUser.objects.create_user(
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
            firebase_uid="staff_uid",
        )
        self.regular_user = CustomUser.objects.create_user(
            email="user@example.com",
            password="testpass123",
            is_staff=False,
            firebase_uid="user_uid",
        )
        self.italy = Country.objects.create(name="Italy", iso3="ITA")

    def test_anonymous_get_redirects_to_login(self):
        response = self.client.get("/api/admin-scripts/fra-carbon-stock/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_non_staff_get_forbidden(self):
        self.client.login(email="user@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/fra-carbon-stock/")
        self.assertEqual(response.status_code, 403)

    @patch("admin_scripts.views.fetch_years")
    def test_staff_get_shows_years_with_latest_selected(self, mock_fetch_years):
        mock_fetch_years.return_value = ["1990", "2020", "2025"]
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/fra-carbon-stock/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_year"], "2025")
        self.assertFalse(FRACarbonStock.objects.exists())

    @patch("admin_scripts.views.fetch_years")
    def test_staff_post_invalid_year_rejected(self, mock_fetch_years):
        mock_fetch_years.return_value = ["1990", "2020", "2025"]
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/fra-carbon-stock/", {"year": "1999"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid or stale assessment year")
        self.assertFalse(FRACarbonStock.objects.exists())

    @patch("admin_scripts.views.fetch_data")
    @patch("admin_scripts.views.fetch_years")
    def test_staff_post_valid_year_creates_rows(self, mock_fetch_years, mock_fetch_data):
        mock_fetch_years.return_value = ["2025"]
        mock_fetch_data.return_value = {
            "fra": {
                "2025": {
                    "ITA": {
                        "carbonStockAvg": {
                            "2025": {
                                "carbon_forest_above_ground": {"raw": "50.60"},
                                "carbon_forest_below_ground": {"raw": "10.20"},
                                "carbon_forest_deadwood": {"raw": "0.80"},
                                "carbon_forest_litter": {"raw": "1.40"},
                            }
                        }
                    },
                }
            }
        }
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/fra-carbon-stock/", {"year": "2025"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(FRACarbonStock.objects.filter(country=self.italy, year=2025).exists())
