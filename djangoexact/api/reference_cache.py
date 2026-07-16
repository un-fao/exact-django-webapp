"""Per-process memos over runtime-immutable IPCC reference tables.

Reference data (SoilOrganicCarbon, NitrousEmissionFactor,
ForestCombustionFactor, LitterDeadwoodCarbonStock, ForestManagementRootToShoot)
is immutable at runtime: it is loaded once via load_reference_data and never
mutated by the running application. The helpers below memoize the lookups
per gunicorn-worker process. Reloading reference data requires a process
restart or calling clear_reference_caches().

Helpers cache resolved model instances or None, never lazy querysets, and
never cache exceptions: functools.lru_cache does not store raised exceptions,
so a DoesNotExist miss propagates on every call exactly as a direct query
would. Returned instances are shared across callers and must be treated as
read-only.
"""

from functools import lru_cache

from ipcc import models as ipcc


@lru_cache(maxsize=None)
def get_soil_organic_carbon(climate_id, moisture_id, soil_type_id):
    """Return the SoilOrganicCarbon row for the given climate/moisture/soil type ids."""
    return ipcc.SoilOrganicCarbon.objects.get(
        climate_id=climate_id, moisture_id=moisture_id, soil_type_id=soil_type_id
    )


@lru_cache(maxsize=None)
def get_nitrous_emission_factor(moisture_id):
    """Return the NitrousEmissionFactor row for the given moisture id."""
    return ipcc.NitrousEmissionFactor.objects.get(moisture_id=moisture_id)


@lru_cache(maxsize=None)
def get_forest_combustion_factor(land_use_type_id, climate_id, forest_type_id):
    """Return the ForestCombustionFactor row for the given land use type/climate/forest type ids."""
    return ipcc.ForestCombustionFactor.objects.get(
        land_use_type_id=land_use_type_id, climate_id=climate_id, forest_type_id=forest_type_id
    )


@lru_cache(maxsize=None)
def get_litter_deadwood_carbon_stock(land_use_type_id, climate_id, forest_type_id):
    """Return the LitterDeadwoodCarbonStock row for the given land use type/climate/forest type ids."""
    return ipcc.LitterDeadwoodCarbonStock.objects.get(
        land_use_type_id=land_use_type_id, climate_id=climate_id, forest_type_id=forest_type_id
    )


@lru_cache(maxsize=512)
def get_root_to_shoot_above(climate_id, forest_type_id, region_id, land_use_type_id, threshold):
    """Return the first ForestManagementRootToShoot row above threshold, or None.

    threshold is a user-data-derived float with an unbounded distinct value
    range, hence the bounded maxsize (unlike the other helpers here, which are
    keyed purely by reference-table primitive ids). None results are cached
    since the underlying query is deterministic for a given argument set.
    """
    return ipcc.ForestManagementRootToShoot.objects.get_first_above_threshold(
        climate=climate_id,
        forest_type=forest_type_id,
        region=region_id,
        land_use_type=land_use_type_id,
        threshold=threshold,
    )


def clear_reference_caches():
    """Escape hatch for tests and reference-data reloads.

    Clears every memo defined in this module, plus the ModuleType and READY
    StatusType memos defined in api.models (Task 2), so a process can pick
    up freshly reloaded reference data without a restart.
    """
    get_soil_organic_carbon.cache_clear()
    get_nitrous_emission_factor.cache_clear()
    get_forest_combustion_factor.cache_clear()
    get_litter_deadwood_carbon_stock.cache_clear()
    get_root_to_shoot_above.cache_clear()

    from api.models import module_type_for_class, get_ready_status

    module_type_for_class.cache_clear()
    get_ready_status.cache_clear()
