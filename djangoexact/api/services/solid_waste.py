"""Calculator and defaults for the solid waste module (IPCC 2006 Vol. 5, 2019 Refinement where updated).

Reads the ipcc reference tables, resolves defaults and Tier 2 overrides per scenario and runs
math_model/no_time_dependency_final/solid_waste.py once for start -> with and once for start -> without.
Imported at the bottom of api/calculators.py so CalculatorFactory finds SolidWasteCalculator by name.
"""

import ipcc.models as ipcc
from api import calculators
from api.calculators import BaseCalculator
from api.faostat_exceptions import FAOSTATError
from api.models import SOLID_WASTE_CROP_MODULES, FloodedRice, SolidWaste
from math_model.no_time_dependency_final.solid_waste import (
    ANAEROBIC_DIGESTION,
    COMPOSTING,
    INCINERATION,
    OPEN_BURNING,
    SWDS_ROUTES,
    WASTE_TYPES,
    SolidWaste as MathSolidWaste,
    TreatmentFactors,
    WasteComponentFactors,
)

SCENARIOS = ("start", "w", "wo")

# Tier 2 field prefix -> (treatment code, ipcc.WasteTreatmentEmissionFactor attribute)
T2_EMISSION_FACTORS = {
    "composting_ch4_ef": (COMPOSTING, "ch4"),
    "composting_n2o_ef": (COMPOSTING, "n2o"),
    "ad_ch4_ef": (ANAEROBIC_DIGESTION, "ch4"),
    "incineration_ch4_ef": (INCINERATION, "ch4"),
    "incineration_n2o_ef": (INCINERATION, "n2o"),
    "open_burning_ch4_ef": (OPEN_BURNING, "ch4"),
    "open_burning_n2o_ef": (OPEN_BURNING, "n2o"),
}


def climate_zone(climate, moisture) -> str | None:
    """IPCC Vol. 5 Table 3.3 climate zone for an EX-ACT climate and moisture.

    Tropical montane takes the tropical dry rates: montane sites are cooler and drier than the lowland
    tropics the "moist and wet" column describes.
    """
    if climate is None or moisture is None:
        return None
    if climate.name_en == "Tropical Montane":
        return "tropical_dry"
    belt = "tropical" if climate.name_en == "Tropical" else "boreal_temperate"
    return f"{belt}_{'dry' if moisture.name_en == 'Dry' else 'wet'}"


FOOD_ONLY = {waste: 1.0 if waste == "food" else 0.0 for waste in WASTE_TYPES}


def _default_yield(crop, scenario: str) -> float | None:
    """Yield (t/ha) the crop module itself would use without a Tier 2 value, None when there is none."""
    region = crop.activity.project.country.region if crop.activity.project.country else None
    if isinstance(crop, FloodedRice):
        row = ipcc.RiceYield.objects.filter(continent=region).first()
        return row.value if row else None
    land_use_type = getattr(crop, f"land_use_type_{scenario}")
    if land_use_type is None or region is None:
        return None
    year = getattr(crop, "faostat_year_t2", None) or crop.activity.project.start_year_of_activities
    try:
        return calculators._fetch_faostat_yield(country_name=crop.activity.project.country.name, item_name=land_use_type.name, start_year=year, region=region, land_use_type=land_use_type).average
    except FAOSTATError:
        return None


def crop_sources(module: SolidWaste) -> list[dict]:
    """Per crop module of the activity: crop, area, yield (Tier 2 or default), production and wasted tonnes per scenario."""
    by_class = {class_name: key for key, class_name in SOLID_WASTE_CROP_MODULES.items()}
    sources = []
    for crop in module.activity.modules:
        key = by_class.get(type(crop).__name__)
        if key is None:
            continue
        scenarios = {}
        for scenario in SCENARIOS:
            tier2 = getattr(crop, f"crop_yield_t2_{scenario}")
            value = tier2 if tier2 is not None else _default_yield(crop, scenario)
            production = crop.area * value if value is not None and crop.area is not None else None
            share = getattr(module, f"crop_waste_{key}_{scenario}")
            land_use_type = getattr(crop, f"land_use_type_{scenario}", None)
            scenarios[scenario] = {
                "crop": land_use_type.name if land_use_type else None,
                "yield": value,
                "yield_source": None if value is None else "tier2" if tier2 is not None else "default",
                "production": production,
                "waste_share": share,
                "wasted": (production or 0.0) * (share or 0.0),
            }
        sources.append({"key": key, "module_id": crop.pk, "area": crop.area, "scenarios": scenarios})
    return sources


def food_waste(module: SolidWaste, sources: list[dict]) -> dict[str, float]:
    """Total food waste per scenario, t/yr: the direct amount plus the wasted share of each crop's production."""
    return {s: (getattr(module, f"amount_{s}") or 0.0) + sum(source["scenarios"][s]["wasted"] for source in sources) for s in SCENARIOS}


def treatment_defaults() -> dict[str, ipcc.WasteTreatmentEmissionFactor]:
    return {row.code: row for row in ipcc.WasteTreatmentEmissionFactor.objects.all()}


def module_defaults(module: SolidWaste) -> dict:
    """Values the module page shows: Tier 1 emission factors per scenario and the crop sources of the activity."""
    treatments = treatment_defaults()
    activity = module.activity
    values = {
        "climate_zone_default": climate_zone(activity.climate_t2 or activity.project.climate, activity.moisture_t2 or activity.project.moisture),
        "crop_sources": crop_sources(module),
    }
    for scenario in SCENARIOS:
        for prefix, (code, attribute) in T2_EMISSION_FACTORS.items():
            values[f"{prefix}_t2_{scenario}_default"] = getattr(treatments[code], attribute) if code in treatments else None
    return values


class SolidWasteCalculator(BaseCalculator):
    def __init__(self, input) -> None:
        super().__init__(input)
        self.results_extra = {}

    def get_defaults(self, calculate=False) -> dict:
        return module_defaults(self.module)

    def _components(self, zone: str) -> dict[str, WasteComponentFactors]:
        return {
            row.code: WasteComponentFactors(doc=row.doc, dry_matter=row.dry_matter, carbon=row.carbon, fossil_carbon=row.fossil_carbon, k=getattr(row, f"k_{zone}"))
            for row in ipcc.WasteComponent.objects.all()
        }

    def _factors(self, scenario: str, treatments: dict) -> TreatmentFactors:
        def value(prefix):
            code, attribute = T2_EMISSION_FACTORS[prefix]
            override = getattr(self.module, f"{prefix}_t2_{scenario}")
            return override if override is not None else getattr(treatments[code], attribute)

        return TreatmentFactors(
            composting_ch4=value("composting_ch4_ef"),
            composting_n2o=value("composting_n2o_ef"),
            ad_ch4=value("ad_ch4_ef"),
            incineration_ch4=value("incineration_ch4_ef"),
            incineration_n2o=value("incineration_n2o_ef"),
            incineration_of=treatments[INCINERATION].oxidation_factor,
            open_burning_ch4=value("open_burning_ch4_ef"),
            open_burning_n2o=value("open_burning_n2o_ef"),
            open_burning_of=treatments[OPEN_BURNING].oxidation_factor,
        )

    def calculate(self):
        module: SolidWaste = self.module
        zone = climate_zone(self.climate, self.moisture)
        components = self._components(zone)
        sites = {row.code: row for row in ipcc.SolidWasteDisposalSiteType.objects.filter(code__in=SWDS_ROUTES)}
        treatments = treatment_defaults()
        amounts = food_waste(module, crop_sources(module))
        gwp = self.project.gwp

        def run(end: str) -> MathSolidWaste:
            math = MathSolidWaste(
                amount_start=amounts["start"],
                amount_end=amounts[end],
                composition_start=FOOD_ONLY,
                composition_end=FOOD_ONLY,
                routes_start=module.routes("start"),
                routes_end=module.routes(end),
                swds_recovery_start=module.swds_recovery_start or 0.0,
                swds_recovery_end=getattr(module, f"swds_recovery_{end}") or 0.0,
                ad_recovery_start=module.ad_recovery_start or 0.0,
                ad_recovery_end=getattr(module, f"ad_recovery_{end}") or 0.0,
                components=components,
                mcf={code: site.mcf for code, site in sites.items()},
                ox={code: site.ox for code, site in sites.items()},
                factors_start=self._factors("start", treatments),
                factors_end=self._factors(end, treatments),
                gwp_ch4=gwp.ch4,
                gwp_n2o=gwp.n2o,
                implementation_time=self.activity.implementation_years,
                capitalization_time=self.activity.capitalization_years,
                rate_type=self.change_rate.name,
                delay=self.activity.delay,
            )
            math.calculate_emissions()
            return math

        self.math_w = run("w")
        self.math_wo = run("wo")
        self.results_w = self.math_w.result
        self.results_wo = self.math_wo.result
        self.results_extra = {
            "solid_waste": {
                # Index 0 of every series, the activity's own delay included as leading zeros.
                "start_year": self.project.start_year_of_activities,
                "unit": "t wet weight / yr",
                "climate_zone": zone,
                "food_waste": amounts,
                "food_waste_by_route": {"w": self.math_w.food_waste_by_route, "wo": self.math_wo.food_waste_by_route},
            }
        }
        return (self.results_w, self.results_wo)
