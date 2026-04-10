"""Module report registry replacing ReportFactory's 30+ elif isinstance() chain."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import api.models as api_models

if TYPE_CHECKING:
    from .base import BaseModuleReport


@functools.lru_cache(maxsize=None)
def _build_registry() -> dict[type, type]:
    """Build and cache the module-type → report-class registry.

    Deferred import avoids circular imports at module load time. The result is
    cached after the first call so the registry dict is constructed exactly once,
    regardless of concurrency (CPython GIL guarantees lru_cache atomicity).
    """
    from .land import (
        AnnualCroplandReport,
        CoastalWetlandReport,
        FloodedRiceReport,
        ForestManagementReport,
        GrasslandReport,
        LandUseChangeReport,
        OtherLandReport,
        PerennialCroplandReport,
        SetAsideReport,
        SettlementReport,
    )
    from .modules import (
        AquacultureReport,
        EnergyReport,
        InputReport,
        IrrigationReport,
        LargeFisheryReport,
        LivestockReport,
        OrganicSoilReport,
        PackagingReport,
        ProcessingReport,
        SmallFisheryReport,
        StorageReport,
        TransportReport,
        WaterbodyReport,
    )

    return {
        api_models.PerennialCropland: PerennialCroplandReport,
        api_models.AnnualCropland: AnnualCroplandReport,
        api_models.FloodedRice: FloodedRiceReport,
        api_models.LandUseChange: LandUseChangeReport,
        api_models.SetAside: SetAsideReport,
        api_models.Grassland: GrasslandReport,
        api_models.OtherLand: OtherLandReport,
        api_models.Waterbody: WaterbodyReport,
        api_models.Aquaculture: AquacultureReport,
        api_models.SmallFishery: SmallFisheryReport,
        api_models.LargeFishery: LargeFisheryReport,
        api_models.Livestock: LivestockReport,
        api_models.ForestManagement: ForestManagementReport,
        api_models.Energy: EnergyReport,
        api_models.Input: InputReport,
        api_models.Irrigation: IrrigationReport,
        api_models.Settlement: SettlementReport,
        api_models.CoastalWetland: CoastalWetlandReport,
        api_models.OrganicSoil: OrganicSoilReport,
        api_models.Transport: TransportReport,
        api_models.Packaging: PackagingReport,
        api_models.Processing: ProcessingReport,
        api_models.Storage: StorageReport,
    }


def get_report_class(module) -> type | None:
    """Return the report class for a module instance, or None if not registered."""
    cls = _build_registry().get(type(module))
    if cls is None:
        import logging
        logging.warning(f"No report class registered for {type(module).__name__}")
    return cls
