import pandas as pd
from dataclasses import dataclass
import os
import logging
import itertools
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
import django
import random
import traceback


def get_results(model):
    rows = model.objects.all()
    rows = filter(lambda x: x.get_cached_results(), rows)
    return rows


# TODO: Without must become business as usual, as in without = start
# NOTE: Permutations are NOT inter-module, they are intra-module
# NOTE: Results should be displayed as intra-permutation difference. So for example "high c input - low c input", "high c input - without c input", "low c input - without c input"

errors = 0


@dataclass
class BaseData:
    module: "models.BaseModule"  # noqa: F821
    climate: str = None
    moisture: str = None
    soil_type: str = None
    region: str = None
    total: float = None

    def __post_init__(self):
        self.climate = self.module.activity.climate_t2.name if self.module.activity.climate_t2 else self.module.activity.project.climate.name
        self.moisture = self.module.activity.moisture_t2.name if self.module.activity.moisture_t2 else self.module.activity.project.moisture.name
        self.soil_type = self.module.activity.soil_type_t2.name if self.module.activity.soil_type_t2 else self.module.activity.project.soil_type.name
        self.region = self.module.activity.project.country.region
        self.total = 0

    def to_dict(self):
        return {
            "module": self.module.__class__.__name__,
            "climate": self.climate,
            "moisture": self.moisture,
            "soil_type": self.soil_type,
            "region": self.region,
            "total": self.total,
        }

    def build(self):
        return self.to_dict()


@dataclass
class AnnualCroplandData(BaseData):
    land_use_type_start: str = None
    land_use_type_w: str = None
    land_use_type_wo: str = None
    tillage_management_type_start: str = None
    tillage_management_type_w: str = None
    tillage_management_type_wo: str = None
    organic_input_type_start: str = None
    organic_input_type_w: str = None
    organic_input_type_wo: str = None
    residue_management_type_start: str = None
    residue_management_type_w: str = None
    residue_management_type_wo: str = None

    def __post_init__(self):
        super().__post_init__()
        # self.module: "models.AnnualCropland"
        self.land_use_type_start = self.module.land_use_type_start.name if self.module.land_use_type_start else None
        self.land_use_type_w = self.module.land_use_type_w.name if self.module.land_use_type_w else None
        self.land_use_type_wo = self.module.land_use_type_start.name if self.module.land_use_type_start else None
        self.tillage_management_type_start = self.module.tillage_management_type_start.name if self.module.tillage_management_type_start else None
        self.tillage_management_type_w = self.module.tillage_management_type_w.name if self.module.tillage_management_type_w else None
        self.tillage_management_type_wo = self.module.tillage_management_type_start.name if self.module.tillage_management_type_start else None
        self.organic_input_type_start = self.module.organic_input_type_start.name if self.module.organic_input_type_start else None
        self.organic_input_type_w = self.module.organic_input_type_w.name if self.module.organic_input_type_w else None
        self.organic_input_type_wo = self.module.organic_input_type_start.name if self.module.organic_input_type_start else None
        self.residue_management_type_start = self.module.residue_management_type_start.name if self.module.residue_management_type_start else None
        self.residue_management_type_w = self.module.residue_management_type_w.name if self.module.residue_management_type_w else None
        self.residue_management_type_wo = self.module.residue_management_type_start.name if self.module.residue_management_type_start else None

    def to_dict(self):
        return {
            **super().to_dict(),
            "land_use_type_start": self.land_use_type_start,
            "land_use_type_w": self.land_use_type_w,
            "land_use_type_wo": self.land_use_type_wo,
            "tillage_management_type_start": self.tillage_management_type_start,
            "tillage_management_type_w": self.tillage_management_type_w,
            "tillage_management_type_wo": self.tillage_management_type_wo,
            "organic_input_type_start": self.organic_input_type_start,
            "organic_input_type_w": self.organic_input_type_w,
            "organic_input_type_wo": self.organic_input_type_wo,
            "residue_management_type_start": self.residue_management_type_start,
            "residue_management_type_w": self.residue_management_type_w,
            "residue_management_type_wo": self.residue_management_type_wo,
        }


@dataclass
class LivestockData(BaseData):
    livestock_category_type: str = None
    livestock_production_type_start: str = None
    livestock_production_type_w: str = None
    livestock_production_type_wo: str = None
    heads_number_start: float = None
    heads_number_w: float = None
    heads_number_wo: float = None
    complementary_manure_management_type_start: str = None
    complementary_manure_management_type_w: str = None
    complementary_manure_management_type_wo: str = None

    def __post_init__(self):
        super().__post_init__()
        # self.module: "models.Livestock"
        self.livestock_category_type = self.module.livestock_category_type.name
        self.livestock_production_type_start = self.module.livestock_production_type_start.name if self.module.livestock_production_type_start else None
        self.livestock_production_type_w = self.module.livestock_production_type_w.name if self.module.livestock_production_type_w else None
        self.livestock_production_type_wo = self.livestock_production_type_start
        self.heads_number_start = self.module.heads_number_start
        self.heads_number_w = self.module.heads_number_w
        self.heads_number_wo = self.heads_number_start
        self.complementary_manure_management_type_start = self.module.complementary_manure_management_type_start.name if self.module.complementary_manure_management_type_start else None
        self.complementary_manure_management_type_w = self.module.complementary_manure_management_type_w.name if self.module.complementary_manure_management_type_w else None
        self.complementary_manure_management_type_wo = self.complementary_manure_management_type_start

    def to_dict(self):
        return {
            **super().to_dict(),
            "livestock_category_type": self.livestock_category_type,
            "livestock_production_type_start": self.livestock_production_type_start,
            "livestock_production_type_w": self.livestock_production_type_w,
            "livestock_production_type_wo": self.livestock_production_type_wo,
            "heads_number_start": self.heads_number_start,
            "heads_number_w": self.heads_number_w,
            "heads_number_wo": self.heads_number_wo,
            "complementary_manure_management_type_start": self.complementary_manure_management_type_start,
            "complementary_manure_management_type_w": self.complementary_manure_management_type_w,
            "complementary_manure_management_type_wo": self.complementary_manure_management_type_wo,
        }


@dataclass
class GrasslandData(BaseData):
    grassland_management_type_start: str = None
    grassland_management_type_w: str = None
    grassland_management_type_wo: str = None

    is_fire_used_start: bool = None
    is_fire_used_w: bool = None
    is_fire_used_wo: bool = None

    fire_periodicity_start: float = None
    fire_periodicity_w: float = None
    fire_periodicity_wo: float = None

    fire_impact_start: float = None
    fire_impact_w: float = None
    fire_impact_wo: float = None

    yield_start: float = None
    yield_w: float = None
    yield_wo: float = None

    def __post_init__(self):
        super().__post_init__()
        # self.module: "models.Grassland"
        self.grassland_management_type_start = self.module.grassland_management_type_start.name if self.module.grassland_management_type_start else None
        self.grassland_management_type_w = self.module.grassland_management_type_w.name if self.module.grassland_management_type_w else None
        self.grassland_management_type_wo = self.grassland_management_type_start

        self.is_fire_used_start = self.module.is_fire_used_start
        self.is_fire_used_w = self.module.is_fire_used_w
        self.is_fire_used_wo = self.is_fire_used_start

        self.fire_periodicity_start = self.module.fire_periodicity_start
        self.fire_periodicity_w = self.module.fire_periodicity_w
        self.fire_periodicity_wo = self.fire_impact_start

        self.fire_impact_start = self.module.fire_impact_start
        self.fire_impact_w = self.module.fire_impact_w
        self.fire_impact_wo = self.fire_impact_start

        self.yield_start = self.module.yield_start
        self.yield_w = self.module.yield_w
        self.yield_wo = self.yield_start

    def to_dict(self):
        return {
            **super().to_dict(),
            "grassland_management_type_start": self.grassland_management_type_start,
            "grassland_management_type_w": self.grassland_management_type_w,
            "grassland_management_type_wo": self.grassland_management_type_wo,
            "is_fire_used_start": self.is_fire_used_start,
            "is_fire_used_w": self.is_fire_used_w,
            "is_fire_used_wo": self.is_fire_used_wo,
            "fire_periodicity_start": self.fire_periodicity_start,
            "fire_periodicity_w": self.fire_periodicity_w,
            "fire_periodicity_wo": self.fire_periodicity_wo,
            "fire_impact_start": self.fire_impact_start,
            "fire_impact_w": self.fire_impact_w,
            "fire_impact_wo": self.fire_impact_wo,
            "yield_start": self.yield_start,
            "yield_w": self.yield_w,
            "yield_wo": self.yield_wo,
        }


class FloodedRiceData(BaseData):
    """
    water_management_type_before_cultivation_start = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_start", null=True, verbose_name=_("water_management_type_before_cultivation_start"))
    water_management_type_before_cultivation_w = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_w", null=True, verbose_name=_("water_management_type_before_cultivation_w"))
    water_management_type_before_cultivation_wo = models.ForeignKey(WaterManagementTypeBeforeCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_before_cultivation_wo", null=True, verbose_name=_("water_management_type_before_cultivation_wo"))

    water_management_type_after_cultivation_start = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_start", null=True, verbose_name=_("water_management_type_after_cultivation_start"))
    water_management_type_after_cultivation_w = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_w", null=True, verbose_name=_("water_management_type_after_cultivation_w"))
    water_management_type_after_cultivation_wo = models.ForeignKey(WaterManagementTypeAfterCultivation, on_delete=models.CASCADE, related_name="%(class)s_water_management_type_after_cultivation_wo", null=True, verbose_name=_("water_management_type_after_cultivation_wo"))

    organic_amendment_type_start = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_start", null=True)
    organic_amendment_type_w = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_w", null=True)
    organic_amendment_type_wo = models.ForeignKey(OrganicAmendmentType, on_delete=models.CASCADE, related_name="%(class)s_organic_amendment_type_wo", null=True)

    """

    def __post_init__(self):
        super().__post_init__()
        # self.module: "models.FloodedRice"
        self.water_management_type_before_cultivation_start = self.module.water_management_type_before_cultivation_start.name if self.module.water_management_type_before_cultivation_start else None
        self.water_management_type_before_cultivation_w = self.module.water_management_type_before_cultivation_w.name if self.module.water_management_type_before_cultivation_w else None
        self.water_management_type_before_cultivation_wo = self.module.water_management_type_before_cultivation_start.name if self.module.water_management_type_before_cultivation_start else None

        self.water_management_type_after_cultivation_start = self.module.water_management_type_after_cultivation_start.name if self.module.water_management_type_after_cultivation_start else None
        self.water_management_type_after_cultivation_w = self.module.water_management_type_after_cultivation_w.name if self.module.water_management_type_after_cultivation_w else None
        self.water_management_type_after_cultivation_wo = self.module.water_management_type_after_cultivation_start.name if self.module.water_management_type_after_cultivation_start else None

        self.organic_amendment_type_start = self.module.organic_amendment_type_start.name if self.module.organic_amendment_type_start else None
        self.organic_amendment_type_w = self.module.organic_amendment_type_w.name if self.module.organic_amendment_type_w else None
        self.organic_amendment_type_wo = self.module.organic_amendment_type_start.name if self.module.organic_amendment_type_start else None

    def to_dict(self):
        return {
            **super().to_dict(),
            "water_management_type_before_cultivation_start": self.water_management_type_before_cultivation_start,
            "water_management_type_before_cultivation_w": self.water_management_type_before_cultivation_w,
            "water_management_type_before_cultivation_wo": self.water_management_type_before_cultivation_wo,
            "water_management_type_after_cultivation_start": self.water_management_type_after_cultivation_start,
            "water_management_type_after_cultivation_w": self.water_management_type_after_cultivation_w,
            "water_management_type_after_cultivation_wo": self.water_management_type_after_cultivation_wo,
            "organic_amendment_type_start": self.organic_amendment_type_start,
            "organic_amendment_type_w": self.organic_amendment_type_w,
            "organic_amendment_type_wo": self.organic_amendment_type_wo,
        }


@dataclass
class PerennialCroplandData(BaseData):
    def __post_init__(self):
        super().__post_init__()
        # self.module: "models.PerennialCropland"
        self.land_use_type_start = self.module.land_use_type_start.name if self.module.land_use_type_start else None
        self.land_use_type_w = self.module.land_use_type_w.name if self.module.land_use_type_w else None
        self.land_use_type_wo = self.module.land_use_type_start.name if self.module.land_use_type_start else None
        self.tillage_management_type_start = self.module.tillage_management_type_start.name if self.module.tillage_management_type_start else None
        self.tillage_management_type_w = self.module.tillage_management_type_w.name if self.module.tillage_management_type_w else None
        self.tillage_management_type_wo = self.module.tillage_management_type_start.name if self.module.tillage_management_type_start else None
        self.organic_input_type_start = self.module.organic_input_type_start.name if self.module.organic_input_type_start else None
        self.organic_input_type_w = self.module.organic_input_type_w.name if self.module.organic_input_type_w else None
        self.organic_input_type_wo = self.module.organic_input_type_start.name if self.module.organic_input_type_start else None
        self.is_biomass_burned_start = self.module.is_biomass_burned_start
        self.is_biomass_burned_w = self.module.is_biomass_burned_w
        self.is_biomass_burned_wo = self.module.is_biomass_burned_start
        self.fire_periodicity_t2_start = self.module.fire_periodicity_t2_start
        self.fire_periodicity_t2_w = self.module.fire_periodicity_t2_w
        self.fire_periodicity_t2_wo = self.module.fire_periodicity_t2_start

    def to_dict(self):
        return {
            **super().to_dict(),
            "land_use_type_start": self.land_use_type_start,
            "land_use_type_w": self.land_use_type_w,
            "land_use_type_wo": self.land_use_type_wo,
            "tillage_management_type_start": self.tillage_management_type_start,
            "tillage_management_type_w": self.tillage_management_type_w,
            "tillage_management_type_wo": self.tillage_management_type_wo,
            "organic_input_type_start": self.organic_input_type_start,
            "organic_input_type_w": self.organic_input_type_w,
            "organic_input_type_wo": self.organic_input_type_wo,
            "is_biomass_burned_start": self.is_biomass_burned_start,
            "is_biomass_burned_w": self.is_biomass_burned_w,
            "is_biomass_burned_wo": self.is_biomass_burned_wo,
            "fire_periodicity_t2_start": self.fire_periodicity_t2_start,
            "fire_periodicity_t2_w": self.fire_periodicity_t2_w,
            "fire_periodicity_t2_wo": self.fire_periodicity_t2_wo,
        }


def compute_data(data: list[BaseData]):
    df = pd.DataFrame(data)
    result = df.agg(
        min=("total", "min"),
        max=("total", "max"),
        mean=("total", "mean"),
        median=("total", "median"),
        quantile_1=("total", lambda x: x.quantile(0.25)),
        quantile_3=("total", lambda x: x.quantile(0.75)),
        sum=("total", "sum"),
    )
    return df, result


def build_data(module):
    if module.__class__.__name__ == "AnnualCropland":
        return AnnualCroplandData(module).to_dict()
    elif module.__class__.__name__ == "Livestock":
        return LivestockData(module).to_dict()
    elif module.__class__.__name__ == "Grassland":
        return GrasslandData(module).to_dict()
    elif module.__class__.__name__ == "FloodedRice":
        return FloodedRiceData(module).to_dict()
    elif module.__class__.__name__ == "PerennialCropland":
        return PerennialCroplandData(module).to_dict()
    else:
        raise ValueError(f"Unsupported module type: {module.__class__.__name__}")


# Because "runscript" sets up Django automatically for the parent process,
# we still need to set up each child process. We'll do that in an initializer.
def django_initializer():
    """
    This function is called once in each child process.
    It ensures the Django environment is loaded before any model usage.
    """
    # Make sure the environment variable is set to your project's settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
    logging.getLogger().setLevel(logging.CRITICAL)
    django.setup()

    # Close any existing connections to start fresh
    from django.db import connections

    connections.close_all()


def process_combinations_grassland(combo):
    """
    This function does the actual work for a single combination.
    It will be executed in the child processes.
    """
    # Import your models/factories/calculators inside the function
    # (or at least after django.setup() has been called):
    import api.tests.factories as factories
    import api.calculators as calculators
    import api.models as models

    logging.getLogger().setLevel(logging.CRITICAL)

    (
        grassland_management_type_start,
        grassland_management_type_w,
        is_fire_used_start,
        is_fire_used_w,
        fire_periodicity_start,
        fire_periodicity_w,
        fire_impact_start,
        fire_impact_w,
        yield_start,
        yield_w,
        climate_moisture,
        soil_type,
        region,
    ) = combo
    climate, moisture = climate_moisture

    p = factories.ProjectFactory.build(
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
        country=region.countries.order_by("?").first(),
    )
    a = factories.ActivityFactory.build(project=p)
    module = factories.GrasslandFactory.build(
        activity=a,
        area=1,
        grassland_management_type_start=grassland_management_type_start,
        grassland_management_type_w=grassland_management_type_w,
        grassland_management_type_wo=grassland_management_type_start,
        is_fire_used_start=is_fire_used_start,
        is_fire_used_w=is_fire_used_w,
        is_fire_used_wo=is_fire_used_start,
        fire_periodicity_start=fire_periodicity_start,
        fire_periodicity_w=fire_periodicity_w,
        fire_periodicity_wo=fire_periodicity_start,
        fire_impact_start=fire_impact_start,
        fire_impact_w=fire_impact_w,
        fire_impact_wo=fire_impact_start,
        yield_start=yield_start,
        yield_w=yield_w,
        yield_wo=yield_start,
        land_use_type_start=models.LandUseType.objects.get(name="Grassland"),
        land_use_type_w=models.LandUseType.objects.get(name="Grassland"),
        land_use_type_wo=models.LandUseType.objects.get(name="Grassland"),
    )

    try:
        balance = calculators.CalculatorFactory().calculate_result(module)[0][2]
    except Exception as e:
        globals()["errors"] += 1
        # Return error information instead of None
        error_info = {"error_type": type(e).__name__, "error_message": str(e), "traceback": traceback.format_exc(), "combination": combo}
        return {"error": error_info}

    # Suppose "build_data" is a helper that modifies the module into a dict
    module = build_data(module)
    module["total"] = balance
    return module


def process_combinations_livestock(combo):
    import api.tests.factories as factories
    import api.calculators as calculators

    logging.getLogger().setLevel(logging.CRITICAL)

    (
        livestock_category_type,
        livestock_production_type_start,
        livestock_production_type_w,
        heads_number_start,
        heads_number_w,
        climate_moisture,
        soil_type,
        region,
    ) = combo
    climate, moisture = climate_moisture

    p = factories.ProjectFactory.build(
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
        country=region.countries.order_by("?").first(),
    )
    a = factories.ActivityFactory.build(project=p)
    module = factories.LivestockFactory.build(
        activity=a,
        livestock_category_type=livestock_category_type,
        livestock_production_type_start=livestock_production_type_start,
        livestock_production_type_w=livestock_production_type_w,
        livestock_production_type_wo=livestock_production_type_start,
        heads_number_start=heads_number_start,
        heads_number_w=heads_number_w,
        heads_number_wo=heads_number_start,
    )

    try:
        balance = calculators.CalculatorFactory().calculate_result(module)[0][2]
    except Exception as e:
        # Return error information instead of None
        error_info = {"error_type": type(e).__name__, "error_message": str(e), "traceback": traceback.format_exc(), "combination": combo}
        return {"error": error_info}

    # Suppose "build_data" is a helper that modifies the module into a dict
    module = build_data(module)
    module["total"] = balance
    return module


def chunked_iterable(iterable, size):
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def process_combinations_annualcropland(combo):
    import api.tests.factories as factories
    import api.calculators as calculators

    logging.getLogger().setLevel(logging.CRITICAL)

    (
        land_use_type_start,
        land_use_type_w,
        tillage_management_start,
        tillage_management_w,
        organic_input_type_start,
        organic_input_type_w,
        residue_management_type_start,
        residue_management_type_w,
        climate_moisture,
        soil_type,
        region,
    ) = combo
    climate, moisture = climate_moisture

    p = factories.ProjectFactory.build(
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
        country=region.countries.order_by("?").first(),
    )
    a = factories.ActivityFactory.build(project=p)
    module = factories.AnnualCroplandFactory.build(
        activity=a,
        area=1,
        land_use_type_start=land_use_type_start,
        land_use_type_w=land_use_type_w,
        land_use_type_wo=land_use_type_start,
        tillage_management_type_start=tillage_management_start,
        tillage_management_type_w=tillage_management_w,
        tillage_management_type_wo=tillage_management_start,
        organic_input_type_start=organic_input_type_start,
        organic_input_type_w=organic_input_type_w,
        organic_input_type_wo=organic_input_type_start,
        residue_management_type_start=residue_management_type_start,
        residue_management_type_w=residue_management_type_w,
        residue_management_type_wo=residue_management_type_start,
    )

    try:
        balance = calculators.CalculatorFactory().calculate_result(module)[0][2]
    except Exception as e:
        # Return error information instead of None
        error_info = {"error_type": type(e).__name__, "error_message": str(e), "traceback": traceback.format_exc(), "combination": combo}
        return {"error": error_info}

    module = build_data(module)
    module["total"] = balance
    return module


def process_combinations_floodedrice(combo):
    import api.tests.factories as factories
    import api.calculators as calculators
    import api.models as models

    logging.getLogger().setLevel(logging.CRITICAL)

    (
        water_management_type_before_cultivation_start,
        water_management_type_before_cultivation_w,
        water_management_type_after_cultivation_start,
        water_management_type_after_cultivation_w,
        organic_amendment_type_start,
        organic_amendment_type_w,
        climate_moisture,
        soil_type,
        region,
    ) = combo
    climate, moisture = climate_moisture

    p = factories.ProjectFactory.build(
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
        country=region.countries.order_by("?").first(),
    )
    a = factories.ActivityFactory.build(project=p)
    module = factories.FloodedRiceFactory.build(
        activity=a,
        area=1,
        water_management_type_before_cultivation_start=water_management_type_before_cultivation_start,
        water_management_type_before_cultivation_w=water_management_type_before_cultivation_w,
        water_management_type_before_cultivation_wo=water_management_type_before_cultivation_start,
        water_management_type_after_cultivation_start=water_management_type_after_cultivation_start,
        water_management_type_after_cultivation_w=water_management_type_after_cultivation_w,
        water_management_type_after_cultivation_wo=water_management_type_after_cultivation_start,
        organic_amendment_type_start=organic_amendment_type_start,
        organic_amendment_type_w=organic_amendment_type_w,
        organic_amendment_type_wo=organic_amendment_type_start,
    )

    try:
        balance = calculators.CalculatorFactory().calculate_result(module)[0][2]
    except Exception as e:
        # Return error information instead of None
        error_info = {"error_type": type(e).__name__, "error_message": str(e), "traceback": traceback.format_exc(), "combination": combo}
        return {"error": error_info}

    module = build_data(module)
    module["total"] = balance
    return module


def process_combinations_perennialcropland(combo):
    import api.tests.factories as factories
    import api.calculators as calculators
    import api.models as models

    logging.getLogger().setLevel(logging.CRITICAL)

    # organic_input_type
    # tillage_management_type

    (
        land_use_type_start,
        land_use_type_w,
        organic_input_type_start,
        organic_input_type_w,
        tillage_management_type_start,
        tillage_management_type_w,
        is_biomass_burned_start,
        is_biomass_burned_w,
        fire_periodicity_t2_start,
        fire_periodicity_t2_w,
        climate_moisture,
        soil_type,
        region,
    ) = combo
    climate, moisture = climate_moisture

    p = factories.ProjectFactory.build(
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
        country=region.countries.order_by("?").first(),
        implementation_years=0,
        start_year_of_activities=2025,
        last_year_of_accounting=2026,
    )
    a = factories.ActivityFactory.build(project=p, change_rate=models.ChangeRate.objects.get(name="immediate"))
    module = factories.PerennialCroplandFactory.build(
        activity=a,
        area=1,
        land_use_type_start=land_use_type_start,
        land_use_type_w=land_use_type_w,
        land_use_type_wo=land_use_type_start,
        organic_input_type_start=organic_input_type_start,
        organic_input_type_w=organic_input_type_w,
        organic_input_type_wo=organic_input_type_start,
        tillage_management_type_start=tillage_management_type_start,
        tillage_management_type_w=tillage_management_type_w,
        tillage_management_type_wo=tillage_management_type_start,
        is_biomass_burned_start=is_biomass_burned_start,
        is_biomass_burned_w=is_biomass_burned_w,
        is_biomass_burned_wo=is_biomass_burned_start,
        fire_periodicity_t2_start=fire_periodicity_t2_start,
        fire_periodicity_t2_w=fire_periodicity_t2_w,
        fire_periodicity_t2_wo=fire_periodicity_t2_start,
    )

    try:
        balance = calculators.CalculatorFactory().calculate_result(module)[0][2]
    except Exception as e:
        # Return error information instead of None
        error_info = {"error_type": type(e).__name__, "error_message": str(e), "traceback": traceback.format_exc(), "combination": combo}
        return {"error": error_info}

    module = build_data(module)
    module["total"] = balance
    return module


def chunked_product(*iterables, chunk_size=1000):
    """
    Yields chunks (lists) of the Cartesian product of `iterables`
    in increments of `chunk_size`.
    """
    it = itertools.product(*iterables)
    while True:
        chunk = list(itertools.islice(it, chunk_size))
        if not chunk:
            break
        yield chunk


def compute_permutations(fields: dict, model, chunk_size=10000, stop_at=None, is_coastal=False):
    import api.models as models
    import math

    # Get land use types for this model
    land_use_types = []
    if "land_use_type_start" in fields:
        land_use_types.extend(fields["land_use_type_start"])
    if "land_use_type_w" in fields:
        land_use_types.extend(fields["land_use_type_w"])

    # Remove duplicates while preserving order
    seen = set()
    unique_land_use_types = []
    for lut in land_use_types:
        if lut.id not in seen:
            seen.add(lut.id)
            unique_land_use_types.append(lut)

    # Get all valid climate-moisture combinations for these land use types
    valid_climate_moistures = set()
    if unique_land_use_types:
        # Filter by land use type constraints
        for land_use_type in unique_land_use_types:
            for climate in land_use_type.climates.all():
                for moisture in climate.moistures.all():
                    valid_climate_moistures.add((climate, moisture))
        print(f"Found {len(valid_climate_moistures)} valid climate-moisture combinations for {len(unique_land_use_types)} land use types")
    else:
        # Fallback: use all active climates and their moistures (for modules without land use types)
        active_climates = models.Climate.objects.filter(is_active=True).all()
        for c in active_climates:
            for m in c.moistures.all():
                valid_climate_moistures.add((c, m))
        print(f"Using all active climate-moisture combinations ({len(valid_climate_moistures)}) for modules without land use type constraints")

    # Convert back to list and sort for consistency
    climate_moistures = sorted(list(valid_climate_moistures), key=lambda x: (x[0].id, x[1].id))

    fields.update(
        {
            "climate_moistures": climate_moistures,
            "soil_types": models.SoilType.objects.filter(is_coastal=is_coastal, active=True).all(),
            "region": models.Region.objects.all(),
        }
    )

    print(f"Computing permutations for {model.__name__}...")
    # print(f"Fields: {json.dumps({k: len(v) for k, v in fields.items()}, indent=2)}")

    combiner_function = globals()[f"process_combinations_{model.__name__.lower()}"]

    # Prepare each dimension
    iterables = []
    for val in fields.values():
        if isinstance(val, int):
            # If you have an integer count
            iterables.append(range(val))
        else:
            # If you have an actual collection, e.g. a QuerySet
            iterables.append(list(val))

    # Compute total permutations
    # (product of the lengths of each iterable)
    total = math.prod(len(x) for x in iterables)
    print(f"Total permutations (theoretical): {total:,}")

    data = []
    errors_data = []
    local_errors = 0

    def save_data():
        """Helper function to save data to CSV"""
        if data:
            df = pd.DataFrame(data)
            filepath = os.path.join(os.path.dirname(__file__), "minitool", f"{model.__name__.lower()}.csv")
            df.to_csv(filepath, index=False)
            print(f"Saved {len(data)} rows to {filepath}")

        if errors_data:
            errors_df = pd.DataFrame(errors_data)
            errors_filepath = os.path.join(os.path.dirname(__file__), "minitool", f"{model.__name__.lower()}_errors.csv")
            errors_df.to_csv(errors_filepath, index=False)
            print(f"Saved {len(errors_data)} errors to {errors_filepath}")

        print(f"Total errors: {globals()['errors']}")

    try:
        with ProcessPoolExecutor(max_workers=4, initializer=django_initializer) as executor:
            pbar = tqdm(total=total, desc=f"Building {model.__name__} permutations")

            for chunk in chunked_product(*iterables, chunk_size=chunk_size):
                results_iter = executor.map(combiner_function, chunk)

                for result in results_iter:
                    if stop_at and len(data) >= stop_at:
                        # Terminate worker processes
                        for proc in executor._processes.values():
                            proc.terminate()
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    if result and "error" in result:
                        # This is an error result
                        errors_data.append(result["error"])
                        local_errors += 1
                    elif result and result.get("total", 0) != 0:
                        # This is a successful result
                        data.append(result)
                    else:
                        # This is a None result (no error info captured)
                        local_errors += 1

                    pbar.update(1)
                else:
                    # If we never broke out of the loop,
                    # proceed to the next chunk
                    continue

                # If we did break due to stop_at,
                # break out of the outer loop
                break

            pbar.close()

    except KeyboardInterrupt:
        print(f"\nKeyboard interrupt detected! Saving {len(data)} computed rows...")
        print(f"Errors encountered so far: {local_errors}")
        # Clean up the progress bar
        try:
            pbar.close()
        except:
            pass
        # Save the data we have so far
        save_data()
        print("Data saved successfully. Exiting gracefully.")
        return

    globals()["errors"] += local_errors

    if not data:
        print(f"No data for {model.__name__}!")
        return

    save_data()


def run():
    # Suppress log noise
    logging.getLogger().setLevel(logging.CRITICAL)
    print("Running script without noisy logging...")

    # --- Parent process has Django, so we can safely import models here. ---
    import api.models as models

    ANNUAL_CROPLAND = False
    FLOODED_RICE = False
    GRASSLAND = False
    LIVESTOCK = False
    PERENNIAL_CROPLAND = True

    MAX_ROWS = 10000

    try:
        if GRASSLAND:
            compute_permutations(
                {
                    "grassland_management_type_start": models.GrasslandManagementType.objects.all(),
                    "grassland_management_type_w": models.GrasslandManagementType.objects.all(),
                    "is_fire_used_start": [True, False],
                    "is_fire_used_w": [True, False],
                    "fire_periodicity_start": [1],
                    "fire_periodicity_w": [1],
                    "fire_impact_start": [1, 0],
                    "fire_impact_w": [1, 0],
                    "yield_start": [1],
                    "yield_w": [1],
                },
                models.Grassland,
                stop_at=MAX_ROWS,
            )

        if LIVESTOCK:
            compute_permutations(
                {
                    "livestock_category_types": models.LivestockCategoryType.objects.all(),
                    "livestock_production_type_start": models.LivestockProductionType.objects.all(),
                    "livestock_production_type_w": models.LivestockProductionType.objects.all(),
                    "heads_number_start": [1],
                    "heads_number_w": [1],
                },
                models.Livestock,
                stop_at=MAX_ROWS,
            )

        if ANNUAL_CROPLAND:
            compute_permutations(
                {
                    "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Annual Cropland").all(),
                    "land_use_type_w": models.LandUseType.objects.filter(module_types__name="Annual Cropland").all(),
                    "tillage_management_type_start": models.TillageManagementType.objects.all(),
                    "tillage_management_type_w": models.TillageManagementType.objects.all(),
                    "organic_input_type_start": models.OrganicInputType.objects.all(),
                    "organic_input_type_w": models.OrganicInputType.objects.all(),
                    "residue_management_type_start": models.ResidueManagementType.objects.all(),
                    "residue_management_type_w": models.ResidueManagementType.objects.all(),
                },
                models.AnnualCropland,
                stop_at=MAX_ROWS,
            )

        if FLOODED_RICE:
            compute_permutations(
                {
                    "water_management_type_before_cultivation_start": models.WaterManagementTypeBeforeCultivation.objects.all(),
                    "water_management_type_before_cultivation_w": models.WaterManagementTypeBeforeCultivation.objects.all(),
                    "water_management_type_after_cultivation_start": models.WaterManagementTypeAfterCultivation.objects.all(),
                    "water_management_type_after_cultivation_w": models.WaterManagementTypeAfterCultivation.objects.all(),
                    "organic_amendment_type_start": models.OrganicAmendmentType.objects.all(),
                    "organic_amendment_type_w": models.OrganicAmendmentType.objects.all(),
                },
                models.FloodedRice,
                stop_at=MAX_ROWS,
            )

        if PERENNIAL_CROPLAND:
            compute_permutations(
                {
                    "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
                    "land_use_type_w": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
                    "organic_input_type_start": models.OrganicInputType.objects.filter(is_active=True).all(),
                    "organic_input_type_w": models.OrganicInputType.objects.filter(is_active=True).all(),
                    "tillage_management_type_start": models.TillageManagementType.objects.all(),
                    "tillage_management_type_w": models.TillageManagementType.objects.all(),
                    "is_biomass_burned_start": [True, False],
                    "is_biomass_burned_w": [True, False],
                    "fire_periodicity_t2_start": [1],
                    "fire_periodicity_t2_w": [1],
                },
                models.PerennialCropland,
                stop_at=MAX_ROWS,
            )

    except KeyboardInterrupt:
        print(f"\nKeyboard interrupt detected in main run function!")
        print("Script terminated by user. Any completed computations have been saved.")
        return
