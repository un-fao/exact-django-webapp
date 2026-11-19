"""A settlement's balance includes the emissions of its other infrastructure.

Buildings and roads were summed into the settlement, other infrastructure was not, so the area and
tier 2 emission factor an analyst entered for it never reached the settlement, activity or project totals.

Run with:
    python manage.py test api.tests.unit.settlement_other_infrastructure
"""

from importlib import import_module

from django.apps import apps
from rest_framework import status

import api.models as models
from api.calculators import SettlementCalculator

from . import base_module

cache_migration = import_module("api.migrations.0325_invalidate_settlement_other_infrastructure_caches")

AREA_M2_W = 1000.0
AREA_M2_WO = 200.0
EF_KG_CO2_PER_M2 = 50.0
KG_PER_TONNE = 1000
CACHED = {"x": 1}


class SettlementOtherInfrastructureTestCase(base_module.BaseModuleWithSubmoduleTestCase):
    def setUp(self):
        self.ModuleClass = models.Settlement
        self.submodule_classes = [models.OtherInfrastructure]
        super().setUp()

        settlement_type = models.SettlementType.objects.order_by("pk").first().pk
        response = self.edit_module(self.module, self.user, {f"settlement_type_{s}": settlement_type for s in ("start", "w", "wo")})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        self.infrastructure = self.submodules[0]

    def _set_infrastructure(self, ef_t2: float):
        response = self.edit_module(
            self.infrastructure,
            self.user,
            {
                "area_m2_start": 0,
                "area_m2_w": AREA_M2_W,
                "area_m2_wo": AREA_M2_WO,
                "ef_t2_start": ef_t2,
                "ef_t2_w": ef_t2,
                "ef_t2_wo": ef_t2,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def _settlement_balances(self) -> tuple[float, float]:
        results_w, results_wo = SettlementCalculator(self.module).calculate()
        return results_w.compute_balance(), results_wo.compute_balance()

    def test_other_infrastructure_adds_area_times_emission_factor_to_the_settlement(self):
        self._set_infrastructure(EF_KG_CO2_PER_M2)
        total_w, total_wo = self._settlement_balances()
        self.infrastructure.delete()
        land_only_w, land_only_wo = self._settlement_balances()

        self.assertAlmostEqual(total_w - land_only_w, AREA_M2_W * EF_KG_CO2_PER_M2 / KG_PER_TONNE)
        self.assertAlmostEqual(total_wo - land_only_wo, AREA_M2_WO * EF_KG_CO2_PER_M2 / KG_PER_TONNE)

    def test_zero_emission_factor_adds_nothing(self):
        self._set_infrastructure(0)
        total_w, total_wo = self._settlement_balances()
        self.infrastructure.delete()
        land_only_w, land_only_wo = self._settlement_balances()

        self.assertAlmostEqual(total_w, land_only_w)
        self.assertAlmostEqual(total_wo, land_only_wo)

    def test_cache_migration_clears_only_open_settlements_with_other_infrastructure(self):
        def cached_after_migration():
            models.Settlement.objects.filter(pk=self.module.pk).update(cached_results_total=CACHED)
            cache_migration.invalidate_caches(apps, None)
            return models.Settlement.objects.get(pk=self.module.pk).cached_results_total

        self.assertIsNone(cached_after_migration())

        models.Project.objects.filter(pk=self.project.pk).update(is_finalized=True)
        self.assertEqual(cached_after_migration(), CACHED)

        models.Project.objects.filter(pk=self.project.pk).update(is_finalized=False)
        models.OtherInfrastructure.objects.filter(pk=self.infrastructure.pk).delete()
        self.assertEqual(cached_after_migration(), CACHED)
