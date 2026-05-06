"""
Back-populate ipcc.CropYieldStat rows for LandUseTypes bound to AnnualCropland.

For every LandUseType whose module_types includes class_name='AnnualCropland'
and that has zero existing CropYieldStat rows, fetch yields from FAOSTAT
for each Region and create one CropYieldStat per (LUT, Region).

Usage:
    python manage.py runscript populate_annual_cropland_yield_stats
    python manage.py runscript populate_annual_cropland_yield_stats --script-args=--apply
"""

from django.db import transaction

from api.faostat_exceptions import (
    FAOSTATInvalidInputError,
    FAOSTATNetworkError,
    FAOSTATNoDataError,
)
from api.faostat_service import get_yield
from api.models import LandUseType, Country
from ipcc.models import CropYieldStat


class _DryRun(Exception):
    """Sentinel raised to roll back the atomic block on dry-run."""


def run(*args):
    apply = "--apply" in args

    luts = LandUseType.objects.filter(
        module_types__class_name="AnnualCropland"
    ).distinct()

    regions = list(Country.objects.all())

    total = luts.count()
    skipped_existing = 0
    processed = 0
    created = 0
    faostat_skipped = 0

    try:
        with transaction.atomic():
            for lut in luts:
                if CropYieldStat.objects.filter(land_use_type=lut).exists():
                    skipped_existing += 1
                    print(f"  skip (has stats): '{lut.name}'")
                    continue

                processed += 1
                print(f"  process: '{lut.name}'")
                for region in regions:
                    try:
                        rec = get_yield(area=region.name, item=lut.name, year=None)
                    except (
                        FAOSTATInvalidInputError,
                        FAOSTATNoDataError,
                        FAOSTATNetworkError,
                    ) as e:
                        faostat_skipped += 1
                        print(
                            f"    skip: region='{region.name}', item='{lut.name}', "
                            f"reason={type(e).__name__}: {e}"
                        )
                        continue

                    value = rec.value
                    CropYieldStat.objects.create(
                        land_use_type=lut,
                        continent=region.region,
                        year_2016=value,
                        year_2017=value,
                        year_2018=value,
                        year_2019=value,
                        year_2020=value,
                        average=value,
                    )
                    created += 1
                    print(
                        f"    create: region='{region.name}', value={value} "
                        f"(year={rec.year}, unit={rec.unit})"
                    )

            if not apply:
                raise _DryRun()
    except _DryRun:
        print(
            f"\nSummary: total={total} skipped_existing={skipped_existing} "
            f"processed={processed} created={created} faostat_skipped={faostat_skipped}"
        )
        print("DRY RUN — no changes committed. Re-run with --apply to persist.")
    else:
        print(
            f"\nSummary: total={total} skipped_existing={skipped_existing} "
            f"processed={processed} created={created} faostat_skipped={faostat_skipped}"
        )
        print("Applied.")
