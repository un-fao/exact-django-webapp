"""Pure-Python data contracts for the report computation layer.

No Django ORM, no Excel library imports. These dataclasses are the single
source of truth passed from the calculation layer to any renderer (Excel, PDF).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Any


@dataclass
class MetadataWrite:
    """A single cell to write in the Metadata worksheet.

    ``row_offset`` is relative to the section start row (after the section title row).
    ``col`` is 1-indexed (1=label, 2=start, 3=with, 4=without, 5=tier2, 6=comment).
    Using raw cell-level writes gives full flexibility for complex layouts
    (e.g. OrganicSoil, Energy submodule loops) while keeping zero Excel imports here.
    """

    row_offset: int
    col: int
    value: Any
    fill: str | None = None  # e.g. "LIGHT_BLUE", "LIGHT_RED", "LIGHT_ORANGE"


@dataclass
class ResultRow:
    """A single emission row in the Results worksheet (one row per gas/source)."""

    label: str
    yearly_values: list[float]


@dataclass
class ModuleResult:
    """All computed data for a single module report."""

    # Module type name – written as the title row in Results (with LIGHT_BLUE fill)
    title: str

    # Metadata section title (same as title in most cases, with LIGHT_BLUE fill)
    metadata_section_title: str

    # Emission rows written below the module title in the Results sheet
    result_rows: list[ResultRow]

    # Raw cell writes for the Metadata sheet (relative to section start row)
    metadata_writes: list[MetadataWrite]

    # Additional Indicators rows: (label, yearly_values)
    additional_indicator_rows_w: list[tuple[str, list[float]]] = field(default_factory=list)
    additional_indicator_rows_wo: list[tuple[str, list[float]]] = field(default_factory=list)

    # Aggregated total emissions (balance) for this module – used by activity totals
    total_emissions: list[float] = field(default_factory=list)

    # Hectares breakdown for Additional Indicators and cumulative hectares tracking
    units_breakdown_w: list[float] = field(default_factory=list)
    units_breakdown_wo: list[float] = field(default_factory=list)

    # Raw inventory object for the Inventory sheet (or None)
    inventory: Any = None

    # Scenario flags – used by activity report for hectare accumulation
    is_with: bool = False
    is_without: bool = False

    # Internal: raw emissions sets kept for project-level aggregation in
    # BaseProjectReport._build_aggregated_from_module_emissions().
    # Not used by renderers.
    _emissions_set: list = field(default_factory=list, repr=False)
    _emissions_set_w: list = field(default_factory=list, repr=False)
    _emissions_set_wo: list = field(default_factory=list, repr=False)
    _inventory_items: list = field(default_factory=list, repr=False)  # list[InventoryItem]


@dataclass
class T2Override:
    """A Tier-2 override row shown under the activity title in the Metadata sheet."""

    label: str
    value: Any


@dataclass
class ActivityResult:
    """Aggregated results for one activity."""

    title: str
    module_results: list[ModuleResult]
    total_emissions: list[float]
    total_hectares_yearly: list[float]
    t2_overrides: list[T2Override] = field(default_factory=list)


@dataclass
class EmissionsAggregator:
    """Aggregated project-level yearly emissions by gas type and scenario.

    Replaces the 18+ parallel lists in BaseProjectReport.finalize_report().
    """

    duration: int

    biomass_co2: list[float] = field(default_factory=list)
    soil_co2: list[float] = field(default_factory=list)
    other_co2: list[float] = field(default_factory=list)
    ch4: list[float] = field(default_factory=list)
    n2o: list[float] = field(default_factory=list)
    other_ghgs: list[float] = field(default_factory=list)

    biomass_co2_w: list[float] = field(default_factory=list)
    soil_co2_w: list[float] = field(default_factory=list)
    other_co2_w: list[float] = field(default_factory=list)
    ch4_w: list[float] = field(default_factory=list)
    n2o_w: list[float] = field(default_factory=list)
    other_ghgs_w: list[float] = field(default_factory=list)

    biomass_co2_wo: list[float] = field(default_factory=list)
    soil_co2_wo: list[float] = field(default_factory=list)
    other_co2_wo: list[float] = field(default_factory=list)
    ch4_wo: list[float] = field(default_factory=list)
    n2o_wo: list[float] = field(default_factory=list)
    other_ghgs_wo: list[float] = field(default_factory=list)

    def __post_init__(self):
        zeros = [0.0] * self.duration
        for attr in (
            "biomass_co2", "soil_co2", "other_co2", "ch4", "n2o", "other_ghgs",
            "biomass_co2_w", "soil_co2_w", "other_co2_w", "ch4_w", "n2o_w", "other_ghgs_w",
            "biomass_co2_wo", "soil_co2_wo", "other_co2_wo", "ch4_wo", "n2o_wo", "other_ghgs_wo",
        ):
            if not getattr(self, attr):
                setattr(self, attr, list(zeros))

    @property
    def yearly_balance(self) -> list[float]:
        return list(map(sum, zip_longest(
            self.biomass_co2, self.soil_co2, self.other_co2,
            self.ch4, self.n2o, self.other_ghgs,
            fillvalue=0,
        )))

    @property
    def yearly_balance_w(self) -> list[float]:
        return list(map(sum, zip_longest(
            self.biomass_co2_w, self.soil_co2_w, self.other_co2_w,
            self.ch4_w, self.n2o_w, self.other_ghgs_w,
            fillvalue=0,
        )))

    @property
    def yearly_balance_wo(self) -> list[float]:
        return list(map(sum, zip_longest(
            self.biomass_co2_wo, self.soil_co2_wo, self.other_co2_wo,
            self.ch4_wo, self.n2o_wo, self.other_ghgs_wo,
            fillvalue=0,
        )))


@dataclass
class ShadowPriceRow:
    """One year of Shadow Price of Carbon data."""

    year: int
    yearly_balance_wo: float
    yearly_balance_w: float
    sp_wo_min: float | None
    sp_wo_max: float | None
    sp_w_min: float | None
    sp_w_max: float | None
    is_extrapolated: bool = False
    sp_min_value: float | None = None  # For the nominal table row
    sp_max_value: float | None = None  # For the nominal table row


@dataclass
class InventoryItem:
    """One row in the Inventory worksheet."""

    activity_name: str
    module_name: str
    ipcc_category: str
    gas_type: str
    value: float


@dataclass
class ProjectResult:
    """The complete computed result for a project – single source of truth
    passed to any renderer or template context builder.
    """

    project: Any  # api_models.Project (renderers read .name, .country, etc.)

    start_year: int
    last_year: int
    duration: int

    activity_results: list[ActivityResult]
    aggregated: EmissionsAggregator
    cumulative_hectares_yearly: list[float]

    shadow_price_rows: list[ShadowPriceRow]
    nominal_shadow_prices: list[Any]   # ipcc_models.ShadowPriceOfCarbon instances
    extra_shadow_prices: list[Any]     # Extrapolated SPC instances

    inventory_items: list[InventoryItem]
