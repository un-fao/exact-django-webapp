"""FRA carbon stock import: fetch from fra-data.fao.org, parse, replace-all write.

Split out of views.py (matching catalog.py / gap_detector.py / scenario_utils.py)
so the network fetch, response parsing, and the destructive DB write are each
testable without HTTP. See .planning/quick/260820-he5-.../260820-he5-CONTEXT.md
for the live-verified API contract this module implements.
"""

from django.db import transaction

import requests

from api.models import Country
from ipcc.models import FRACarbonStock

BASE_URL = "https://fra-data.fao.org/api/explorer"

# Cloudflare returns 403 without a browser-like User-Agent. Not optional.
HEADERS = {"User-Agent": "Mozilla/5.0"}

TIMEOUT = 120

# FRA variable name -> FRACarbonStock field name.
VARIABLES = {
    "carbon_forest_above_ground": "agb",
    "carbon_forest_below_ground": "bgb",
    "carbon_forest_deadwood": "deadwood",
    "carbon_forest_litter": "litter",
}


def fetch_years():
    """Return the available FRA assessment years, sorted ascending (as strings)."""
    response = requests.get(
        f"{BASE_URL}/sections/metadata",
        params={
            "assessmentName": "fra",
            "countryIso": "WO",
            "cycleName": "2025",
            "sectionNames[]": "carbonStock",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    dimensions = payload["carbonStock"]["dimensions"]
    years = [d["name"] for d in dimensions]
    return sorted(years, key=int)


def fetch_data(year, isos):
    """Fetch carbon stock data for ``year`` across the given ISO3 list."""
    response = requests.get(
        f"{BASE_URL}/data",
        params={
            "assessmentName": "fra",
            "columns[]": [year],
            "countryISOs[]": list(isos),
            "tableNames[]": ["carbonStockAvg"],
            "variables[]": list(VARIABLES),
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def parse_payload(payload, year):
    """Walk the FRA response shape into ``{iso: {field_name: float|None, ...}}``.

    ``raw`` is a string or null in the response; null/empty stays None, else
    parsed to float. Entries carrying ``"calculated": true`` are read the same
    way (``raw`` still holds the value).
    """
    result = {}
    countries = payload.get("fra", {}).get(year, {})
    for iso, country_data in countries.items():
        by_field = {}
        year_data = country_data.get("carbonStockAvg", {}).get(year, {})
        for fra_variable, field_name in VARIABLES.items():
            raw = year_data.get(fra_variable, {}).get("raw")
            by_field[field_name] = float(raw) if raw not in (None, "") else None
        result[iso] = by_field
    return result


def replace_carbon_stock(year, by_iso):
    """Delete every FRACarbonStock row and re-create one per mapped ISO3.

    A row is created even when all four values are None, matching the current
    CSV importer's behaviour for countries FRA reports with no data — skipping
    them would flip calculators.py's `.first()` lookup from agb=0 to a raised
    ValueError for those countries.

    Returns a dict with year/deleted/created counts and the sorted list of
    ISO3 codes present in ``by_iso`` that have no mapped Country.
    """
    countries_by_iso = {
        c.iso3: c for c in Country.objects.exclude(iso3__isnull=True)
    }
    unmapped = sorted(set(by_iso) - set(countries_by_iso))

    year_int = int(year)
    with transaction.atomic():
        deleted, _ = FRACarbonStock.objects.all().delete()
        new_rows = [
            FRACarbonStock(
                country=countries_by_iso[iso],
                year=year_int,
                agb=fields.get("agb"),
                bgb=fields.get("bgb"),
                deadwood=fields.get("deadwood"),
                litter=fields.get("litter"),
            )
            for iso, fields in by_iso.items()
            if iso in countries_by_iso
        ]
        FRACarbonStock.objects.bulk_create(new_rows)

    return {
        "year": year_int,
        "deleted": deleted,
        "created": len(new_rows),
        "unmapped": unmapped,
    }
