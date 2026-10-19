"""Flooded rice with several seasons per year (NEXT port, feature rice-seasons).

Run with:
    python manage.py test api.tests.unit.flooded_rice_seasons
"""

import json

from django.test import modify_settings

from rest_framework import status
from rest_framework.test import APIClient, force_authenticate

import api.models as models
import ipcc.models as ipcc_models
from api.calculators import FloodedRiceCalculator, FloodedRiceSeasonCalculator
from api.views import generic_module_viewset
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes

from . import base_module

SCENARIOS = ("start", "w", "wo")

# Tier 2 inputs per season: EFc (kg CH4/ha/day), SFw, SFp, SFo, cultivation days.
MAIN = {"efc": 1.19, "sfw": 0.60, "sfp": 1.00, "sfo": 1.50, "days": 120}
SEASON_2 = {"efc": 1.19, "sfw": 0.52, "sfp": 0.68, "sfo": 1.00, "days": 100}
SEASON_3 = {"efc": 1.19, "sfw": 1.00, "sfp": 1.22, "sfo": 2.00, "days": 90}


def _t2_payload(season):
    data = {}
    for sfx in SCENARIOS:
        data.update(
            {
                f"efc_t2_{sfx}": season["efc"],
                f"sfw_t2_{sfx}": season["sfw"],
                f"sfp_t2_{sfx}": season["sfp"],
                f"sfo_t2_{sfx}": season["sfo"],
                f"cultivation_period_t2_{sfx}": season["days"],
                f"crop_yield_t2_{sfx}": 4.0,
                f"rice_straw_t2_{sfx}": 5.0,
            }
        )
    return data


def _seasonal_ch4_kg_per_ha(season):
    # IPCC 2019 Vol 4 ch.5 eq. 5.2 (EF_i = EF_c x SF_w x SF_p x SF_o) times
    # the cultivation period t_i of eq. 5.1.
    return season["efc"] * season["sfw"] * season["sfp"] * season["sfo"] * season["days"]


def _rice_ch4(result):
    return sum(e.value for s in result.yearly_emissions_by_sector_by_gas if s.activity == ActivityTypes.CH4_EMITTED_RICE for e in s.emissions)


class FloodedRiceSeasonsTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.FloodedRice
        super().setUp()

        self.fk_payload = {}
        before = models.WaterManagementTypeBeforeCultivation.objects.order_by("id").first().id
        after = models.WaterManagementTypeAfterCultivation.objects.order_by("id").first().id
        amendment = models.OrganicAmendmentType.objects.exclude(name_en="Straw Burnt").order_by("id").first().id
        for sfx in SCENARIOS:
            self.fk_payload[f"water_management_type_before_cultivation_{sfx}"] = before
            self.fk_payload[f"water_management_type_after_cultivation_{sfx}"] = after
            self.fk_payload[f"organic_amendment_type_{sfx}"] = amendment

        response = self.edit_module(self.module, self.user, {**self.fk_payload, **_t2_payload(MAIN)})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        self.assertTrue(self.module.is_ready())

        self.season_view = generic_module_viewset(models.MinorSeasonFloodedRice).as_view({"post": "create"})

    def _add_season(self, season):
        request = self.request_factory.post("/api/flooded-rices-minor-seasons/", {"parent": self.module.id, **self.fk_payload, **_t2_payload(season)}, format="json")
        force_authenticate(request, user=self.user)
        return self.season_view(request)

    def _hectare_years(self):
        # Hectare-years over the accounting period are the same for every season
        # because additional seasons use the parent's area.
        calc = FloodedRiceSeasonCalculator(self.module)
        calc.calculate()
        return {
            "w": sum(sum(m.hectares_total) for m in (calc.math_start_w, calc.math_w) if m),
            "wo": sum(sum(m.hectares_total) for m in (calc.math_start_wo, calc.math_wo) if m),
        }

    def _expected(self, seasons):
        gwp = self.project.gwp.ch4
        kg_per_ha = sum(_seasonal_ch4_kg_per_ha(s) for s in seasons)
        return {k: kg_per_ha * hy * gwp / 1000 for k, hy in self._hectare_years().items()}

    def _assert_matches_hand_calc(self, seasons):
        results_w, results_wo = FloodedRiceCalculator(self.module).calculate()
        expected = self._expected(seasons)
        self.assertGreater(expected["w"], 0)
        self.assertAlmostEqual(_rice_ch4(results_w), expected["w"], places=6)
        self.assertAlmostEqual(_rice_ch4(results_wo), expected["wo"], places=6)

    def test_main_season_only_unchanged(self):
        self._assert_matches_hand_calc([MAIN])

    def test_single_minor_season_unchanged(self):
        """A pre-existing one-minor-season project keeps computing main + season."""
        self.assertEqual(self._add_season(SEASON_2).status_code, status.HTTP_201_CREATED)
        self._assert_matches_hand_calc([MAIN, SEASON_2])

    def test_three_seasons_sum_to_hand_calc(self):
        for season in (SEASON_2, SEASON_3):
            response = self._add_season(season)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            self.assertTrue(models.MinorSeasonFloodedRice.objects.get(pk=response.data["id"]).is_ready())
        self._assert_matches_hand_calc([MAIN, SEASON_2, SEASON_3])

    def test_country_without_ipcc_rice_yield_uses_tier_2_yield(self):
        # North America has a RiceDefaultEmissionFactor but no RiceYield row.
        self.project.country = models.Country.objects.filter(region__name_en="North America").order_by("id").first()
        self.project.save()
        self.assertFalse(ipcc_models.RiceYield.objects.filter(continent=self.project.country.region).exists())
        self.module = models.FloodedRice.objects.get(pk=self.module.pk)

        self.assertEqual(self.get_module_defaults(self.module, self.user).status_code, status.HTTP_200_OK)
        self._assert_matches_hand_calc([MAIN])

        self.module.crop_yield_t2_w = None
        self.module.save()
        with self.assertRaisesMessage(Exception, "Please provide Tier 2 values for scenarios: w"):
            FloodedRiceSeasonCalculator(self.module).get_defaults()

    def test_seasons_keep_creation_order(self):
        for season in (SEASON_3, SEASON_2, SEASON_3):
            self._add_season(season)
        days = [s.cultivation_period_t2_w for s in self.module.submodules]
        self.assertEqual(days, [90, 100, 90])

    def test_additional_season_cap(self):
        for _ in range(models.MAX_ADDITIONAL_RICE_SEASONS):
            self.assertEqual(self._add_season(SEASON_2).status_code, status.HTTP_201_CREATED)

        response = self._add_season(SEASON_2)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent", response.data)
        self.assertEqual(self.module.minor_seasons.count(), models.MAX_ADDITIONAL_RICE_SEASONS)

        season = self.module.minor_seasons.first()
        view = generic_module_viewset(models.MinorSeasonFloodedRice).as_view({"patch": "partial_update"})
        request = self.request_factory.patch(f"/api/flooded-rices-minor-seasons/{season.pk}/", {"cultivation_period_t2_w": 80}, format="json")
        force_authenticate(request, user=self.user)
        self.assertEqual(view(request, pk=season.pk).status_code, status.HTTP_200_OK)

    # The connection-cleanup middleware closes the shared test connection.
    @modify_settings(MIDDLEWARE={"remove": "minitool.middleware.DatabaseConnectionMiddleware"})
    def test_export_import_round_trip_keeps_seasons(self):
        for season in (SEASON_2, SEASON_3):
            self._add_season(season)

        client = APIClient()
        client.force_authenticate(user=self.user)
        export = client.get(f"/api/projects/{self.project.id}/export/")
        self.assertEqual(export.status_code, status.HTTP_200_OK)
        response = client.post("/api/projects/import_project/?forceCopy=true", data=json.loads(export.content), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, getattr(response, "data", None))

        imported = models.FloodedRice.objects.get(activity__project_id=response.data["projectId"])
        self.assertEqual([s.cultivation_period_t2_w for s in imported.submodules], [100, 90])
