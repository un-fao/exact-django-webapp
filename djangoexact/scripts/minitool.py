import pandas as pd
from dataclasses import dataclass
import os

import api.models as models


def get_results(model: models.Module):
    rows = model.objects.all()
    rows = filter(lambda x: x.get_cached_results(), rows)
    return rows


@dataclass
class BaseData:
    module: models.Module
    climate: str = None
    moisture: str = None
    soil_type: str = None
    total: float = None

    def __post_init__(self):
        self.climate = self.module.activity.climate_t2.name if self.module.activity.climate_t2 else self.module.activity.project.climate.name
        self.moisture = self.module.activity.moisture_t2.name if self.module.activity.moisture_t2 else self.module.activity.project.moisture.name
        self.soil_type = self.module.activity.soil_type_t2.name if self.module.activity.soil_type_t2 else self.module.activity.project.soil_type.name
        self.total = self.module.get_cached_results().get("total_w", 0) + self.module.get_cached_results().get("total_wo", 0)

    def to_dict(self):
        return {
            "climate": self.climate,
            "moisture": self.moisture,
            "soil_type": self.soil_type,
            "total": self.total,
        }


@dataclass
class AnnualCroplandData(BaseData):
    tillage_management_start: str = None
    tillage_management_w: str = None
    tillage_management_wo: str = None
    organic_input_type_start: str = None
    organic_input_type_w: str = None
    organic_input_type_wo: str = None
    residue_management_type_start: str = None
    residue_management_type_w: str = None
    residue_management_type_wo: str = None

    def __post_init__(self):
        super().__post_init__()
        self.module: models.AnnualCropland
        self.tillage_management_start = self.module.tillage_management_type_start.name if self.module.tillage_management_type_start else None
        self.tillage_management_w = self.module.tillage_management_type_w.name if self.module.tillage_management_type_w else None
        self.tillage_management_wo = self.module.tillage_management_type_wo.name if self.module.tillage_management_type_wo else None
        self.organic_input_type_start = self.module.organic_input_type_start.name if self.module.organic_input_type_start else None
        self.organic_input_type_w = self.module.organic_input_type_w.name if self.module.organic_input_type_w else None
        self.organic_input_type_wo = self.module.organic_input_type_wo.name if self.module.organic_input_type_wo else None
        self.residue_management_type_start = self.module.residue_management_type_start.name if self.module.residue_management_type_start else None
        self.residue_management_type_w = self.module.residue_management_type_w.name if self.module.residue_management_type_w else None
        self.residue_management_type_wo = self.module.residue_management_type_wo.name if self.module.residue_management_type_wo else None

    def to_dict(self):
        return {
            **super().to_dict(),
            "tillage_management_start": self.tillage_management_start,
            "tillage_management_w": self.tillage_management_w,
            "tillage_management_wo": self.tillage_management_wo,
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
    production_start: float = None
    production_w: float = None
    production_wo: float = None
    heads_number_start: float = None
    heads_number_w: float = None
    heads_number_wo: float = None
    complementary_manure_management_type_start: str = None
    complementary_manure_management_type_w: str = None
    complementary_manure_management_type_wo: str = None

    def __post_init__(self):
        super().__post_init__()
        self.module: models.Livestock
        self.livestock_category_type = self.module.livestock_category_type.name
        self.livestock_production_type_start = self.module.livestock_production_type_start.name if self.module.livestock_production_type_start else None
        self.livestock_production_type_w = self.module.livestock_production_type_w.name if self.module.livestock_production_type_w else None
        self.livestock_production_type_wo = self.module.livestock_production_type_wo.name if self.module.livestock_production_type_wo else None
        self.production_start = self.module.production_start
        self.production_w = self.module.production_w
        self.production_wo = self.module.production_wo
        self.heads_number_start = self.module.heads_number_start
        self.heads_number_w = self.module.heads_number_w
        self.heads_number_wo = self.module.heads_number_wo
        self.complementary_manure_management_type_start = self.module.complementary_manure_management_type_start.name if self.module.complementary_manure_management_type_start else None
        self.complementary_manure_management_type_w = self.module.complementary_manure_management_type_w.name if self.module.complementary_manure_management_type_w else None
        self.complementary_manure_management_type_wo = self.module.complementary_manure_management_type_wo.name if self.module.complementary_manure_management_type_wo else None

    def to_dict(self):
        return {
            **super().to_dict(),
            "livestock_category_type": self.livestock_category_type,
            "livestock_production_type_start": self.livestock_production_type_start,
            "livestock_production_type_w": self.livestock_production_type_w,
            "livestock_production_type_wo": self.livestock_production_type_wo,
            "production_start": self.production_start,
            "production_w": self.production_w,
            "production_wo": self.production_wo,
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
        self.module: models.Grassland
        self.grassland_management_type_start = self.module.grassland_management_type_start.name if self.module.grassland_management_type_start else None
        self.grassland_management_type_w = self.module.grassland_management_type_w.name if self.module.grassland_management_type_w else None
        self.grassland_management_type_wo = self.module.grassland_management_type_wo.name if self.module.grassland_management_type_wo else None

        self.is_fire_used_start = self.module.is_fire_used_start
        self.is_fire_used_w = self.module.is_fire_used_w
        self.is_fire_used_wo = self.module.is_fire_used_wo

        self.fire_periodicity_start = self.module.fire_periodicity_start
        self.fire_periodicity_w = self.module.fire_periodicity_w
        self.fire_periodicity_wo = self.module.fire_periodicity_wo

        self.fire_impact_start = self.module.fire_impact_start
        self.fire_impact_w = self.module.fire_impact_w
        self.fire_impact_wo = self.module.fire_impact_wo

        self.yield_start = self.module.yield_start
        self.yield_w = self.module.yield_w
        self.yield_wo = self.module.yield_wo

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
    if isinstance(module, models.AnnualCropland):
        return AnnualCroplandData(module).to_dict()
    elif isinstance(module, models.Livestock):
        return LivestockData(module).to_dict()
    elif isinstance(module, models.Grassland):
        return GrasslandData(module).to_dict()
    else:
        raise ValueError(f"Unsupported module type: {type(module)}")


def run():
    for model in [models.AnnualCropland, models.Livestock, models.Grassland]:
        data = [build_data(row) for row in get_results(model)]
        print(f"Total {model.__name__} rows: {len(data)}")

        df, result = compute_data(data)
        print(result)

        # Save the data to a csv file
        df.to_csv(os.path.join(os.path.dirname(__file__), "minitool", f"{model.__name__}.csv"), index=False)

        print("\n\n")
