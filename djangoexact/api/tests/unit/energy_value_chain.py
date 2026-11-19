"""Energy value-chain stages.

Run with:
    python manage.py test api.tests.unit.energy_value_chain
"""

from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
from api.calculators import EnergyEntryCalculator
from api.reports.modules import _energy_value_chain_stage_metadata_writes
from math_model.no_time_dependency_final.ghg_emissions_classes import GasTypes

from . import base_module


def _fuel(use_type, name):
    return models.FuelType.objects.get(fuel_use_type__name_en=use_type, name_en=name)


def _start_inventory(entry):
    calculator = EnergyEntryCalculator(entry)
    calculator.calculate()
    return {item.gas_type: item.value for item in calculator.math_start.inventory.emissions_by_sector_by_gas}


class EnergyValueChainTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Energy
        self.submodule_classes = [models.EnergyEntry, models.EnergyEntry, models.EnergyEntry]
        super().setUp()
        self.gwp = self.project.gwp

    def _set(self, entry, fuel_type, quantity, stage=None):
        data = {
            "fuel_type_start": fuel_type.pk,
            "fuel_type_w": fuel_type.pk,
            "fuel_type_wo": fuel_type.pk,
            "quantity_consumed_per_year_start": quantity,
            "quantity_consumed_per_year_w": quantity * 2,
            "quantity_consumed_per_year_wo": quantity,
            "value_chain_stage": stage.pk if stage else None,
        }
        response = self.edit_module(entry, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        entry.refresh_from_db()

    def _results(self, aggregate):
        view = self.module_viewset.as_view({"get": "results"})
        url = reverse("energy-results", args=[self.module.pk]) + f"?aggregate={aggregate}&cached=false"
        request = self.request_factory.get(url, format="json")
        force_authenticate(request, user=self.user)
        self.module.refresh_from_db()
        return view(request, pk=self.module.pk)

    def test_stage_aggregation_splits_the_module_total(self):
        on_farm = models.ValueChainStage.objects.get(name_en="On-farm")
        retail = models.ValueChainStage.objects.get(name_en="Food retail")
        diesel = _fuel("Mobile", "Gasoil/Diesel Oil")
        self._set(self.submodules[0], diesel, 3, on_farm)
        self._set(self.submodules[1], _fuel("Stationary", "Gasoil/Diesel Oil"), 5, retail)
        self._set(self.submodules[2], diesel, 7)

        total = self._results("total")
        by_stage = self._results("value_chain_stage")

        self.assertEqual(total.status_code, status.HTTP_200_OK, total.data)
        self.assertEqual(by_stage.status_code, status.HTTP_200_OK, by_stage.data)
        rows = by_stage.data["value_chain_stages"]
        self.assertEqual([r["id"] for r in rows], [on_farm.pk, retail.pk, None])
        self.assertEqual(rows[0]["name"], "On-farm")
        self.assertAlmostEqual(sum(r["balance"] for r in rows), total.data["balance"], places=6)
        self.assertAlmostEqual(by_stage.data["balance"], total.data["balance"], places=6)
        self.assertGreater(rows[0]["balance"], 0)
        # Same fuel and same with/without ratio, so balances scale with quantity (3 vs 7).
        self.assertAlmostEqual(rows[2]["balance"] / rows[0]["balance"], 7 / 3, places=6)

    def test_stage_is_a_tag_only(self):
        diesel = _fuel("Stationary", "Gasoil/Diesel Oil")
        for entry in self.submodules:
            self._set(entry, diesel, 4)
        untagged = self._results("total").data["balance"]

        self._set(self.submodules[0], diesel, 4, models.ValueChainStage.objects.get(name_en="Food processing"))
        tagged = self._results("total").data["balance"]

        self.assertEqual(untagged, tagged)

    def test_existing_stationary_diesel_result_is_unchanged(self):
        # Pre-existing EF row (2.6669331 tCO2/m3): annual start-year CO2 for 4 m3 is 10.6677324 t.
        entry = self.submodules[0]
        self._set(entry, _fuel("Stationary", "Gasoil/Diesel Oil"), 4)
        self.assertIsNone(entry.value_chain_stage)
        self.assertAlmostEqual(_start_inventory(entry)[GasTypes.CO2], 10.6677324, places=6)


class EnergyValueChainMetadataTestCase(SimpleTestCase):
    def _entry(self, stage_name=None):
        stage = SimpleNamespace(name=stage_name) if stage_name else None
        return SimpleNamespace(value_chain_stage=stage, value_chain_stage_id=1 if stage else None)

    def test_no_rows_without_stages(self):
        writes = _energy_value_chain_stage_metadata_writes([self._entry(), self._entry()], 0, is_start=True, is_with=True, is_without=True)
        self.assertEqual(writes, [])

    def test_one_row_per_entry_once_any_stage_is_set(self):
        writes = _energy_value_chain_stage_metadata_writes([self._entry(), self._entry("On-farm")], 8, is_start=False, is_with=True, is_without=True)
        cells = {(w.row_offset, w.col): w.value for w in writes}
        self.assertEqual(cells[(8, 1)], "Energy entry 1 - value chain stage")
        self.assertEqual(cells[(9, 3)], "On-farm")
        self.assertEqual(cells[(9, 4)], "On-farm")
        self.assertNotIn((9, 2), cells)
