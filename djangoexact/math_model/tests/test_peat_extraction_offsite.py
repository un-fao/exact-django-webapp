"""Off-site CO2 from extracted peat (IPCC 2006 V4 Ch7 Eq. 7.4), quantity path vs the legacy height path.

Expected numbers are worked by hand from the inputs, not read off the implementation.
"""

import dataclasses
import unittest

from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes
from math_model.no_time_dependency_final.inlands import PeatExtraction


def _peat(**overrides) -> PeatExtraction:
    kwargs = {f.name: None if "tier_2" in f.name else 0.0 for f in dataclasses.fields(PeatExtraction) if f.default is dataclasses.MISSING}
    kwargs.update(
        implementation_time=5,
        capitalization_time=5,
        rate_type="linear",
        delay=0,
        hectares_start=100.0,
        hectares_end=100.0,
        percentage_ditches_start=0.1,
        percentage_ditches_end=0.1,
        methane_constant=28.0,
        nitrous_constant=265.0,
        weight_peat=0.4,
        conversion_factor_volume=0.24,
        c_fraction_ref=1,
        extraction_height_start=2.0,
        extraction_height_end=2.0,
    )
    kwargs.update(overrides)
    module = PeatExtraction(**kwargs)
    module.calculate_emissions()
    return module


def _offsite_baseline(module) -> float:
    return next(row.value for row in module.inventory.emissions_by_sector_by_gas if row.activity == ActivityTypes.OFFSITE_PEAT)


class QuantityPathTests(unittest.TestCase):
    def test_horticulture_peat_by_weight(self):
        # 10 t/ha x 100 ha x (1 - 0.1) = 900 t air-dry; x 0.4 tC/t = 360 tC; x 44/12 = 1320 tCO2
        module = _peat(quantity_unit="weight", quantity_start=10.0, quantity_end=10.0, carbon_fraction_start=0.4, carbon_fraction_end=0.4)
        self.assertAlmostEqual(_offsite_baseline(module), 1320.0)

    def test_horticulture_peat_by_volume(self):
        # 20 m3/ha x 100 ha x 0.9 = 1800 m3; x 0.6 t/m3 = 1080 t; x 0.4 tC/t = 432 tC; x 44/12 = 1584 tCO2
        module = _peat(
            quantity_unit="volume", quantity_start=20.0, quantity_end=20.0,
            carbon_fraction_start=0.4, carbon_fraction_end=0.4, bulk_density_start=0.6, bulk_density_end=0.6,
        )
        self.assertAlmostEqual(_offsite_baseline(module), 1584.0)

    def test_volume_at_default_bulk_density_matches_the_table_7_5_volume_factor(self):
        # Table 7.5 nutrient-rich temperate: 0.24 tC/m3 == 0.4 tC/t x (0.24 / 0.4) t/m3
        module = _peat(
            quantity_unit="volume", quantity_start=20.0, carbon_fraction_start=0.4, bulk_density_start=0.24 / 0.4,
        )
        self.assertAlmostEqual(_offsite_baseline(module), 20.0 * 100 * 0.9 * 0.24 * 44 / 12)

    def test_energy_peat_not_counted_gives_zero_offsite(self):
        module = _peat(
            quantity_unit="weight", quantity_start=10.0, quantity_end=10.0, carbon_fraction_start=0.4, carbon_fraction_end=0.4,
            offsite_counted_start=False, offsite_counted_end=False,
        )
        self.assertEqual(_offsite_baseline(module), 0.0)
        offsite = [s for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == ActivityTypes.OFFSITE_PEAT]
        self.assertTrue(all(e.value == 0 for s in offsite for e in s.emissions))

    def test_quantity_path_ignores_extraction_height(self):
        a = _peat(quantity_unit="weight", quantity_start=10.0, carbon_fraction_start=0.4, extraction_height_start=2.0)
        b = _peat(quantity_unit="weight", quantity_start=10.0, carbon_fraction_start=0.4, extraction_height_start=50.0)
        self.assertEqual(_offsite_baseline(a), _offsite_baseline(b))


class LegacyPathTests(unittest.TestCase):
    def test_legacy_formula_is_unchanged(self):
        # Pre-existing behaviour, kept on purpose: density proxy 0.4 x 0.24 / 1, x 100 ha x 2 x 100, carbon fraction 1
        module = _peat()
        self.assertAlmostEqual(_offsite_baseline(module), 0.4 * 0.24 * 100 * 2.0 * 100 * 1 * 44 / 12)
        self.assertAlmostEqual(module.peat_density_tier_2_default, 0.4 * 0.24)


if __name__ == "__main__":
    unittest.main()
