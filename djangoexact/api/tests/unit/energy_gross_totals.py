"""Energy with/without totals count the baseline consumption once.

Run with:
    python manage.py test api.tests.unit.energy_gross_totals
"""

from rest_framework import status

import api.models as models
from api.calculators import EnergyEntryCalculator

from . import base_module

QUANTITY = 100.0
ELECTRICITY_EF = 0.5


class EnergyGrossTotalsTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Energy
        self.submodule_classes = [models.EnergyEntry]
        super().setUp()
        self.entry = self.submodules[0]
        self.fuels = {
            "fuel": models.FuelType.objects.get(fuel_use_type__name_en="Stationary", name_en="Gasoil/Diesel Oil"),
            "electricity": models.FuelType.objects.filter(name_en="Electricity").first(),
        }

    def _calculate(self, fuel_type, start, w, wo):
        response = self.edit_module(
            self.entry,
            self.user,
            {
                "fuel_type_start": fuel_type.pk,
                "fuel_type_w": fuel_type.pk,
                "fuel_type_wo": fuel_type.pk,
                "quantity_consumed_per_year_start": start,
                "quantity_consumed_per_year_w": w,
                "quantity_consumed_per_year_wo": wo,
                # The factory picks a random country, and not every country has an electricity EF row.
                "electricity_ef_t2_start": ELECTRICITY_EF,
                "electricity_ef_t2_w": ELECTRICITY_EF,
                "electricity_ef_t2_wo": ELECTRICITY_EF,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.entry.refresh_from_db()
        calculator = EnergyEntryCalculator(self.entry)
        total_w, total_wo = calculator.calculate()
        return calculator, total_w.compute_balance(), total_wo.compute_balance()

    def test_unchanged_consumption_is_counted_once(self):
        for name, fuel_type in self.fuels.items():
            with self.subTest(name):
                calculator, total_w, total_wo = self._calculate(fuel_type, QUANTITY, QUANTITY, QUANTITY)
                baseline = calculator.results_start.compute_balance()
                self.assertGreater(baseline, 0)
                self.assertAlmostEqual(total_w, baseline)
                self.assertAlmostEqual(total_wo, baseline)

    def test_stopped_activity_keeps_only_the_phase_out(self):
        for name, fuel_type in self.fuels.items():
            with self.subTest(name):
                calculator, total_w, total_wo = self._calculate(fuel_type, QUANTITY, 0, 0)
                implementation = self.entry.get_activity().implementation_years
                capitalization = self.entry.get_activity().capitalization_years
                phase_out_share = (implementation / 2) / (implementation + capitalization)
                baseline = calculator.results_start.compute_balance()
                self.assertAlmostEqual(total_w, baseline * phase_out_share)
                self.assertAlmostEqual(total_wo, baseline * phase_out_share)

    def test_balance_is_not_changed_by_the_start_series(self):
        for name, fuel_type in self.fuels.items():
            with self.subTest(name):
                calculator, total_w, total_wo = self._calculate(fuel_type, QUANTITY, 0, QUANTITY)
                results_start = calculator.results_start
                with_start = (results_start + calculator.results_w).compute_balance()
                without_start = (results_start + calculator.results_wo).compute_balance()
                self.assertAlmostEqual(total_w - total_wo, with_start - without_start)

    def test_start_inventory_is_kept(self):
        calculator, _, _ = self._calculate(self.fuels["fuel"], QUANTITY, 0, 0)
        self.assertTrue(calculator.math_start.inventory.emissions_by_sector_by_gas)
