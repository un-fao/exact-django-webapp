"""Harvested wood products module (HarvestedWoodProducts): one pool per activity fed by every source module."""

import json
from itertools import zip_longest
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
from api import calculators
from api.reports.base import BaseActivityReport, BaseProjectReport
from api.reports.modules import HarvestedWoodProductsReport
from api.utilities import copy_activity
from api.views import ActivityViewSet, generic_module_viewset
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes
from math_model.no_time_dependency_final.hwp_decay import hwp_pool_line

from . import base_module, land_use_change

ROTATION = {
    "rotation_start_year_t2_w": 2,
    "rotation_start_year_t2_wo": 0,
    "rotation_length_yrs_w": 2,
    "rotation_length_yrs_wo": 2,
    "rotation_percentage_biomass_for_energy_w": 0.2,
    "rotation_percentage_biomass_for_energy_wo": 0.2,
}
# Tier 2 growth pins the forest so the random test project climate cannot break the rotation math.
GROWTH_T2 = {
    f"{field}_{scenario}": value
    for scenario in ("w", "wo")
    for field, value in (("agb_max_t2", 150.0), ("bgb_max_t2", 40.0), ("agb_growth_rate_le_20_yrs_t2", 5.0), ("agb_growth_rate_gt_20_yrs_t2", 3.0))
}
SHARES = {"sawnwood": 0.5, "panels": 0.2, "paper": 0.1}
HWP_VALUES = {f"share_{product}_{scenario}": share for product, share in SHARES.items() for scenario in ("start", "w", "wo")}


def _sum(rows):
    return [sum(values) for values in zip_longest(*rows, fillvalue=0.0)]


def expected_pool(source, hwp) -> dict[str, list[float]]:
    """The HWP_POOL line each scenario should get from one source, built straight from the source calculator's math."""
    source = type(source).objects.get(pk=source.pk)
    calculator = calculators.CalculatorFactory().get_calculator(source)(source)
    calculator.calculate()
    luc = getattr(calculator, "luc_calculator", None)
    if luc is not None:
        entries = [(scenario, math, (scenario,)) for scenario, math in luc.hwp_math.items()]
    else:
        entries = [
            ("start", calculator.math_start, ("w", "wo")),
            ("w", calculator.math_start_w, ("w",)),
            ("wo", calculator.math_start_wo, ("wo",)),
            ("w", calculator.math_w, ("w",)),
            ("wo", calculator.math_wo, ("wo",)),
        ]
    lines = {"w": [], "wo": []}
    for scenario, math, targets in entries:
        inflow = getattr(math, "hwp_inflow_co2", None)
        if inflow is None:
            continue
        line, _stock = hwp_pool_line([float(v) for v in inflow], hwp.shares(scenario), hwp.half_lives_t2(scenario), math.HWP_INFLOW_ALREADY_EMITTED)
        for target in targets:
            lines[target].append(line)
    return {scenario: _sum(rows) for scenario, rows in lines.items()}


class HwpModuleMixin:
    def results(self, module, aggregate="total", cached="false"):
        view = generic_module_viewset(module.__class__).as_view({"get": "results"})
        url = reverse(f"{module.__class__.__name__.lower()}-results", args=[module.pk]) + f"?cached={cached}&aggregate={aggregate}"
        request = self.request_factory.get(url, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def pool(self, hwp) -> dict[str, list[float]]:
        data = self.results(hwp, "activity")
        out = {}
        for key, scenario in (("total_w", "w"), ("total_wo", "wo")):
            rows = [row for row in data[key] if row["activity"] == str(ActivityTypes.HWP_POOL)]
            out[scenario] = _sum([[emission["value"] for emission in row["emissions"]] for row in rows])
        return out

    def add_hwp(self, activity, **values):
        activity.module_types.add(models.ModuleType.objects.get(class_name="HarvestedWoodProducts"))
        return self.create_submodule(models.HarvestedWoodProducts, self.user, {"activity": activity.pk, **HWP_VALUES, **values})

    def hwp_of(self, activity):
        return models.HarvestedWoodProducts.objects.get(activity=activity)

    def assert_sources_unchanged_and_pool_matches(self, sources):
        """Adding the module leaves every source's own results exactly as they were; its line is the sources' pools."""
        activity = sources[0].activity
        before = {source.pk: self.results(source) for source in sources}

        response = self.add_hwp(activity)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        hwp = self.hwp_of(activity)

        for source in sources:
            self.assertEqual(self.results(source), before[source.pk], type(source).__name__)

        expected = {"w": [], "wo": []}
        for source in sources:
            for scenario, line in expected_pool(source, hwp).items():
                expected[scenario] = _sum([expected[scenario], line])
        actual = self.pool(hwp)
        for scenario in ("w", "wo"):
            self.assertEqual(len(actual[scenario]), len(expected[scenario]), scenario)
            for got, want in zip(actual[scenario], expected[scenario]):
                self.assertAlmostEqual(got, want, places=4)

        breakdown = self.results(hwp)["hwp"]
        self.assertEqual({entry["class_name"] for entry in breakdown["sources"]}, {type(source).__name__ for source in sources})
        self.assertAlmostEqual(sum(entry["balance"] for entry in breakdown["sources"]), self.results(hwp)["balance"], places=4)
        self.assertIsNone(breakdown["warning"])
        return hwp


class ForestHwpModuleTestCase(HwpModuleMixin, base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.ForestManagement
        # The base class builds a random project; some climate / land-use pairs lack IPCC forest rows.
        for _ in range(5):
            super().setUp()
            if self.configure_computable_forest():
                return
        self.fail("No land-use type with IPCC forest data found for the random test projects")

    def configure_computable_forest(self) -> bool:
        for land_use_type in self.land_use_types.order_by("id"):
            response = self.edit_module(
                self.module,
                self.user,
                {
                    "land_use_type_start": land_use_type.id,
                    "forest_type": models.ForestType.objects.get(name_en="Natural").id,
                    "forest_condition_type": models.ForestConditionType.objects.get(name_en="Primary").id,
                    **ROTATION,
                    **GROWTH_T2,
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.module.refresh_from_db()
            if self.get_results(cached="false").status_code == status.HTTP_200_OK:
                return True
        return False

    def test_forest_alone_feeds_a_removal(self):
        hwp = self.assert_sources_unchanged_and_pool_matches([self.module])
        self.assertLess(self.results(hwp)["total_w"], 0)

    def test_module_is_listed_and_counted_in_activity_totals_and_report(self):
        modules_before = self.calculate_activity_results(self.activity, self.user).data["modules"]
        self.add_hwp(self.activity)
        hwp = self.hwp_of(self.activity)
        # The builder breadcrumb reads this endpoint.
        view = ActivityViewSet.as_view({"get": "modules"})
        request = self.request_factory.get(reverse("activities-modules", args=[self.activity.pk]))
        force_authenticate(request, user=self.user)
        listed = view(request, pk=self.activity.pk).data
        listed = listed.get("results", listed) if isinstance(listed, dict) else listed
        self.assertIn(hwp.module_type.pk, [module["module_type"] for module in listed])

        # A module only joins activity totals once READY, which the module page's save sets.
        self.assertEqual(self.edit_module(hwp, self.user, {}).status_code, status.HTTP_200_OK)
        hwp.refresh_from_db()
        response = self.calculate_activity_results(self.activity, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        [hwp_data] = [m for m in response.data["modules"] if m["id"] == hwp.pk and "share_sawnwood_w" in m]
        self.assertAlmostEqual(hwp_data["results"]["balance"], self.results(hwp)["balance"], places=4)
        self.assertEqual(len(response.data["modules"]), len(modules_before) + 1)

        project_report = BaseProjectReport(self.project)
        report = HarvestedWoodProductsReport(module=hwp, activity_report=Mock(project_report=project_report)).compute()
        [row] = [row for row in report.result_rows if row.label == "CO2 from HWP pool (CRT 4.G)"]
        self.assertAlmostEqual(sum(row.yearly_values), self.results(hwp)["balance"], places=2)

        activity_result = BaseActivityReport(project_report, models.Activity.objects.get(pk=self.activity.pk)).compute()
        totals = [sum(module_result.total_emissions) for module_result in activity_result.module_results]
        self.assertAlmostEqual(sum(activity_result.total_emissions), sum(totals), places=2)
        self.assertIn("Harvested Wood Products", [module_result.metadata_section_title for module_result in activity_result.module_results])

    def test_source_edit_invalidates_the_cached_pool(self):
        self.add_hwp(self.activity)
        hwp = self.hwp_of(self.activity)
        self.edit_module(hwp, self.user, {})
        first = self.results(hwp, cached="true")["balance"]
        self.assertEqual(self.results(hwp, cached="true")["balance"], first)

        self.edit_module(self.module, self.user, {"rotation_percentage_biomass_for_energy_w": 0.6})
        self.assertNotAlmostEqual(self.results(hwp, cached="true")["balance"], first, places=4)

    def cached_pool(self):
        self.add_hwp(self.activity)
        hwp = self.hwp_of(self.activity)
        self.edit_module(hwp, self.user, {})
        self.results(hwp, cached="true")
        hwp.refresh_from_db()
        self.assertTrue(hwp.is_cached_results_valid())
        return hwp

    def test_pool_cache_does_not_depend_on_the_sources_being_cached(self):
        # An unedited source without a cache (never read, or cleared by a migration that changed nothing here) leaves the pool valid.
        hwp = self.cached_pool()
        models.ForestManagement.objects.filter(pk=self.module.pk).update(last_cached_at=None, cached_results_total=None)
        hwp.refresh_from_db()
        self.assertTrue(hwp.is_cached_results_valid())

    def test_invalidating_a_source_cache_invalidates_the_pool(self):
        # The path a disturbance edit or deletion takes: it clears the forest cache without touching last_modified.
        hwp = self.cached_pool()
        models.ForestManagement.objects.get(pk=self.module.pk).invalidate_cached_results()
        hwp.refresh_from_db()
        self.assertFalse(hwp.is_cached_results_valid())

    def test_without_sources_the_module_computes_zero_and_warns(self):
        self.add_hwp(self.activity)
        hwp = self.hwp_of(self.activity)
        self.assertNotEqual(self.results(hwp)["balance"], 0)

        self.activity.module_types.remove(self.module_type)
        self.module.delete()
        data = self.results(hwp)
        self.assertEqual(data["balance"], 0)
        self.assertEqual(data["hwp"]["warning"], "no_sources")
        self.assertEqual(data["hwp"]["sources"], [])

    def test_deleting_a_source_invalidates_the_cached_pool(self):
        self.add_hwp(self.activity)
        hwp = self.hwp_of(self.activity)
        self.edit_module(hwp, self.user, {})
        self.assertNotEqual(self.results(hwp, cached="true")["balance"], 0)

        self.activity.module_types.remove(self.module_type)
        self.module.delete()
        data = self.results(hwp, cached="true")
        self.assertEqual(data["balance"], 0)
        self.assertEqual(data["hwp"]["warning"], "no_sources")

    def test_validation(self):
        too_much = self.add_hwp(self.activity, share_sawnwood_wo=0.8)
        self.assertEqual(too_much.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.add_hwp(self.activity).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.add_hwp(self.activity).status_code, status.HTTP_400_BAD_REQUEST)

    @skipUnless(hasattr(models.ForestManagement, "is_stock_difference"), "needs the stock-difference approach (#346)")
    def test_stock_difference_forest_is_not_a_source(self):
        self.edit_module(self.module, self.user, {"approach": "stock_difference"})
        self.assertEqual(self.add_hwp(self.activity).status_code, status.HTTP_400_BAD_REQUEST)

    def test_defaults_are_ipcc_half_lives(self):
        self.add_hwp(self.activity)
        data = self.get_module_defaults(self.hwp_of(self.activity), self.user).data
        for scenario in ("start", "w", "wo"):
            self.assertEqual(data[f"half_life_sawnwood_t2_{scenario}_default"], 35.0)
            self.assertEqual(data[f"half_life_panels_t2_{scenario}_default"], 25.0)
            self.assertEqual(data[f"half_life_paper_t2_{scenario}_default"], 2.0)

    def test_copy_activity_copies_the_module(self):
        self.add_hwp(self.activity)
        copied = copy_activity(self.activity, owner=self.user)
        self.assertEqual(copied.harvestedwoodproducts.get().share_sawnwood_w, 0.5)

    # The test client goes through DatabaseConnectionMiddleware, which closes the test transaction's connection.
    @override_settings(MIDDLEWARE=[m for m in settings.MIDDLEWARE if not m.endswith("DatabaseConnectionMiddleware")])
    def test_export_import_keeps_the_module(self):
        self.add_hwp(self.activity)
        self.client.force_authenticate(user=self.user)
        export = self.client.get(f"/api/projects/{self.project.id}/export/")
        self.assertEqual(export.status_code, status.HTTP_200_OK)
        response = self.client.post("/api/projects/import_project/?forceCopy=true", data=json.loads(export.content), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, getattr(response, "data", None))
        imported = models.HarvestedWoodProducts.objects.get(activity__project_id=response.data["projectId"])
        self.assertEqual(imported.share_sawnwood_w, 0.5)


class BuilderHwpModuleTestCase(HwpModuleMixin, base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.Waterbody
        super().setUp()
        self.hwp_type = models.ModuleType.objects.get(class_name="HarvestedWoodProducts")

    def test_no_source_is_rejected_by_the_builder_and_the_module_endpoint(self):
        response = self.create_activity(self.project, self.user, [self.module_type, self.hwp_type])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.add_hwp(self.activity)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.HarvestedWoodProducts.objects.filter(activity=self.activity).exists())

    def test_builder_creates_the_module_next_to_a_source(self):
        forest = models.ModuleType.objects.get(class_name="ForestManagement")
        response = self.create_activity(self.project, self.user, [forest, self.hwp_type])
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        activity = models.Activity.objects.get(pk=response.data["id"])
        self.assertTrue(activity.harvestedwoodproducts.exists())
        self.assertEqual([type(source).__name__ for source in self.hwp_of(activity).sources], ["ForestManagement"])


class PerennialHwpModuleTestCase(HwpModuleMixin, base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.PerennialCropland
        for _ in range(5):
            super().setUp()
            if self.configure_renewal():
                return
        self.fail("No perennial land-use type with IPCC data found for the random test projects")

    def configure_renewal(self) -> bool:
        trees = models.LandUseType.objects.filter(module_types__class_name="PerennialCropland", climates=self.project.climate, moistures=self.project.moisture, is_active=True)
        tillage = models.TillageManagementType.objects.order_by("id").first().id
        organic_input = models.OrganicInputType.objects.order_by("id").first().id
        for tree in trees.order_by("id"):
            self.edit_module(
                self.module,
                self.user,
                {
                    **{f"land_use_type_{scenario}": tree.id for scenario in ("start", "w", "wo")},
                    **{f"tillage_management_type_{scenario}": tillage for scenario in ("start", "w", "wo")},
                    **{f"organic_input_type_{scenario}": organic_input for scenario in ("start", "w", "wo")},
                    "is_complete_renewal_w": True,
                },
            )
            self.module.refresh_from_db()
            if self.get_results(cached="false").status_code == status.HTTP_200_OK:
                return True
        return False

    def test_perennial_alone_defers_the_renewal_emission(self):
        hwp = self.assert_sources_unchanged_and_pool_matches([self.module])
        [source] = self.results(hwp)["hwp"]["sources"]
        self.assertGreater(source["inflow_w"], 0)
        # The removed trees are already in the BIOMASS loss line, so the pool can only defer them: a removal.
        self.assertLess(source["pool_w"], 0)
        self.assertGreater(source["pool_w"], -source["inflow_w"])
        self.assertEqual(source["inflow_wo"], 0)

    def test_change_of_system_feeds_the_trees_removed(self):
        other_trees = models.LandUseType.objects.filter(
            module_types__class_name="PerennialCropland", climates=self.project.climate, moistures=self.project.moisture, is_active=True
        ).exclude(pk=self.module.land_use_type_start_id)
        for tree in other_trees.order_by("id"):
            self.edit_module(self.module, self.user, {"land_use_type_w": tree.id, "is_complete_renewal_w": False})
            if self.get_results(cached="false").status_code == status.HTTP_200_OK:
                break
        else:
            self.skipTest("Only one perennial land-use type with IPCC data in this random test project")

        hwp = self.assert_sources_unchanged_and_pool_matches([self.module])
        [source] = self.results(hwp)["hwp"]["sources"]
        self.assertGreater(source["inflow_w"], 0)
        self.assertLess(source["pool_w"], 0)
        self.assertEqual(source["inflow_wo"], 0)


class DeforestationHwpModuleTestCase(HwpModuleMixin, base_module.AnyToAnyLandUseChangeTestCase):
    def setUp(self):
        for _ in range(5):
            super().setUp()
            self.setup_scenario(start_module="ForestManagement", w_module="AnnualCropland", wo_module="ForestManagement")
            if self.configure_deforestation():
                break
        else:
            self.fail("No IPCC forest and cropland data for deforestation in the random test projects")
        self.edit_module(self.land_use_change, self.user, {"dry_matter_w": 40.0})
        self.land_use_change.refresh_from_db()

    def configure_deforestation(self) -> bool:
        def land_use_types(class_name):
            return models.LandUseType.objects.filter(module_types__class_name=class_name, climates=self.project.climate, moistures=self.project.moisture, is_active=True).order_by("id")

        crop = land_use_types("AnnualCropland").first()
        if crop is None:
            return False
        self.edit_module(
            self.module_w,
            self.user,
            {
                **{f"land_use_type_{scenario}": crop.id for scenario in ("start", "w", "wo")},
                **{f"tillage_management_type_{scenario}": models.TillageManagementType.objects.order_by("id").first().id for scenario in ("start", "w", "wo")},
                **{f"organic_input_type_{scenario}": models.OrganicInputType.objects.order_by("id").first().id for scenario in ("start", "w", "wo")},
                **{f"residue_management_type_{scenario}": models.ResidueManagementType.objects.order_by("id").first().id for scenario in ("start", "w", "wo")},
            },
        )
        for forest in land_use_types("ForestManagement"):
            self.edit_module(
                self.module_start,
                self.user,
                {
                    "land_use_type_start": forest.id,
                    "forest_type": models.ForestType.objects.get(name_en="Natural").id,
                    "forest_condition_type": models.ForestConditionType.objects.get(name_en="Primary").id,
                },
            )
            if self.get_land_use_change_results(cached="false").status_code == status.HTTP_200_OK:
                return True
        return False

    def test_deforestation_emits_the_wood_harvested_before_clearing(self):
        # Forest start module and land use change are both sources; only the land use change harvests here.
        hwp = self.assert_sources_unchanged_and_pool_matches([self.module_start, self.land_use_change])
        [luc] = [entry for entry in self.results(hwp)["hwp"]["sources"] if entry["class_name"] == "LandUseChange"]
        # At most the whole harvested dry matter: the yearly spread follows the hectares converted within the horizon.
        self.assertGreater(luc["inflow_w"], 0)
        self.assertLessEqual(luc["inflow_w"], 40.0 * 0.47 * self.land_use_change.area * 44 / 12 + 1e-6)
        # Never emitted before: over the project the line emits the unshared 20% at once plus the decay of the rest.
        self.assertGreater(luc["pool_w"], 0.2 * luc["inflow_w"])
        self.assertLess(luc["pool_w"], luc["inflow_w"])

    def test_forest_read_by_the_deforestation_invalidates_the_cached_pool_even_when_not_a_source(self):
        # A stock-difference forest feeds no wood itself, but the deforestation calculator still reads it.
        with patch.object(models.ForestManagement, "is_stock_difference", create=True, new=lambda module: True):
            self.add_hwp(self.activity)
            hwp = self.hwp_of(self.activity)
            self.assertEqual([type(source).__name__ for source in hwp.sources], ["LandUseChange"])
            self.results(hwp, cached="true")
            hwp.refresh_from_db()
            self.assertTrue(hwp.is_cached_results_valid())

            forest = models.ForestManagement.objects.get(pk=self.module_start.pk)
            forest.rotation_length_yrs_w = (forest.rotation_length_yrs_w or 0) + 1
            forest.save()
            hwp.refresh_from_db()
            self.assertFalse(hwp.is_cached_results_valid())


class PerennialLandUseChangeHwpModuleTestCase(HwpModuleMixin, base_module.AnyToAnyLandUseChangeTestCase):
    def setUp(self):
        for _ in range(5):
            super().setUp()
            self.setup_scenario(start_module="PerennialCropland", w_module="AnnualCropland", wo_module="PerennialCropland")
            if self.configure():
                break
        else:
            self.fail("No IPCC perennial and cropland data in the random test projects")
        self.edit_module(self.land_use_change, self.user, {"dry_matter_w": 30.0})
        self.land_use_change.refresh_from_db()

    def configure(self) -> bool:
        def first(model):
            return model.objects.order_by("id").first().id

        def land_use_types(class_name):
            return models.LandUseType.objects.filter(module_types__class_name=class_name, climates=self.project.climate, moistures=self.project.moisture, is_active=True).order_by("id")

        crop = land_use_types("AnnualCropland").first()
        if crop is None:
            return False
        common = {
            **{f"tillage_management_type_{scenario}": first(models.TillageManagementType) for scenario in ("start", "w", "wo")},
            **{f"organic_input_type_{scenario}": first(models.OrganicInputType) for scenario in ("start", "w", "wo")},
        }
        self.edit_module(
            self.module_w,
            self.user,
            {
                **common,
                **{f"land_use_type_{scenario}": crop.id for scenario in ("start", "w", "wo")},
                **{f"residue_management_type_{scenario}": first(models.ResidueManagementType) for scenario in ("start", "w", "wo")},
            },
        )
        for tree in land_use_types("PerennialCropland"):
            self.edit_module(self.module_start, self.user, {**common, **{f"land_use_type_{scenario}": tree.id for scenario in ("start", "w", "wo")}, "is_complete_renewal_wo": True})
            if self.get_land_use_change_results(cached="false").status_code == status.HTTP_200_OK and self.get_module_results(self.module_start, cached="false").status_code == status.HTTP_200_OK:
                return True
        return False

    def test_land_use_change_and_perennial_sum(self):
        hwp = self.assert_sources_unchanged_and_pool_matches([self.module_start, self.land_use_change])
        sources = {entry["class_name"]: entry for entry in self.results(hwp)["hwp"]["sources"]}
        self.assertEqual(set(sources), {"PerennialCropland", "LandUseChange"})
        self.assertGreater(sources["LandUseChange"]["inflow_w"], 0)

    def test_conversion_from_perennial_counts_the_wood_once(self):
        # The perennial module is part of the land use change, so it is a source too. With project the trees are
        # converted: only the land use change computes them (harvest before conversion), even with a renewal flag left
        # on the perennial module. Without project they stay perennial and are renewed: only the perennial module does.
        self.edit_module(self.module_start, self.user, {"is_complete_renewal_w": True})
        self.add_hwp(self.activity)
        sources = {entry["class_name"]: entry for entry in self.results(self.hwp_of(self.activity))["hwp"]["sources"]}
        self.assertEqual(sources["PerennialCropland"]["inflow_w"], 0)
        self.assertGreater(sources["PerennialCropland"]["inflow_wo"], 0)
        self.assertGreater(sources["LandUseChange"]["inflow_w"], 0)
        self.assertEqual(sources["LandUseChange"]["inflow_wo"], 0)

    def test_wood_harvested_before_conversion_is_reported_in_dry_matter(self):
        self.add_hwp(self.activity)
        [luc] = [entry for entry in self.results(self.hwp_of(self.activity))["hwp"]["sources"] if entry["class_name"] == "LandUseChange"]
        # At most the dry matter entered per hectare times the area: the spread follows the hectares converted in time.
        self.assertGreater(luc["inflow_dm_w"], 0)
        self.assertLessEqual(luc["inflow_dm_w"], 30.0 * self.land_use_change.area + 1e-6)
        self.assertAlmostEqual(luc["inflow_dm_w"], luc["inflow_w"] * 12 / 44 / 0.47, places=6)
        self.assertEqual(luc["inflow_dm_wo"], 0)


class NonWoodLandUseChangeHwpTestCase(HwpModuleMixin, base_module.BaseLandUseChangeTestCase):
    """Annual cropland to other land: no wood, so the harvest before conversion neither feeds the pool nor vanishes."""

    def setUp(self):
        # The base class builds a random project; some lack IPCC rows for the factory's cropland.
        for _ in range(5):
            super().setUp()
            self.setup_land_use_change(module_type_start_name="AnnualCropland", module_type_w_name="OtherLand", module_type_wo_name="AnnualCropland")
            # Unbound call: subclassing that case would also run its own tests here.
            land_use_change.AnnualToOtherLandTestCase.configure_annual_cropland_modules(self)
            self.edit_module(self.module_w, self.user, {"land_use_type_start": models.LandUseType.objects.get(name_en="Other Land").id})
            if self.get_land_use_change_results(cached="false").status_code == status.HTTP_200_OK:
                return
        self.fail("No IPCC cropland data for the random test projects")

    def luc_balance(self):
        response = self.get_land_use_change_results(cached="false")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data["balance"]

    def test_harvest_before_conversion_is_ignored(self):
        without_harvest = self.luc_balance()
        self.edit_module(self.land_use_change, self.user, {"dry_matter_w": 2.0})
        self.assertAlmostEqual(self.luc_balance(), without_harvest, places=6)

    def test_land_use_change_from_non_wood_land_is_not_a_source(self):
        self.assertEqual(models.HarvestedWoodProducts.sources_of(self.activity), [])
        self.assertEqual(self.add_hwp(self.activity).status_code, status.HTTP_400_BAD_REQUEST)
