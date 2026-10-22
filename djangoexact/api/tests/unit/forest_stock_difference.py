import io
from types import SimpleNamespace

import openpyxl

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
import ipcc.models as ipcc_models
from api.defaults import DefaultsFactory
from api.services.forest_stock_difference import STOCK_DIFFERENCE_LUC_ERROR, calculate_stock_difference, stock_difference_defaults
from api.utilities import NON_MANGROVE_FACTOR
from api.views import ProjectViewSet

from . import base_module

START = {"agb": 120.0, "bgb": 30.0, "litter": 5.0, "deadwood": 8.0, "soc": 60.0}
END_W = {"agb": 150.0, "bgb": 36.0, "litter": 6.0, "deadwood": 9.0, "soc": 62.0}
END_WO = {"agb": 100.0, "bgb": 25.0, "litter": 4.0, "deadwood": 6.0, "soc": 58.0}


def stock_fields():
    fields = {}
    for scenario, stocks in (("start", START), ("w", END_W), ("wo", END_WO)):
        fields.update({f"stock_{pool}_{scenario}": value for pool, value in stocks.items()})
    return fields


class ForestStockDifferenceTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.ForestManagement
        super().setUp()

        self.edit_module(
            self.module,
            self.user,
            {
                "land_use_type_start": self.land_use_types.order_by("id").first().id,
                "forest_type": models.ForestType.objects.get(name_en="Natural").id,
                "forest_condition_type": models.ForestConditionType.objects.get(name_en="Primary").id,
            },
        )
        self.module.refresh_from_db()

    def balance(self):
        response = self.get_results(cached="false")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_gain_loss_ignores_stock_fields(self):
        before = self.balance()

        self.edit_module(self.module, self.user, stock_fields())
        self.module.refresh_from_db()
        self.assertEqual(self.module.approach, models.ForestManagement.APPROACH_GAIN_LOSS)

        after = self.balance()
        for key in ("total_w", "total_wo", "balance"):
            self.assertEqual(before[key], after[key], key)

    def test_stock_difference_results_follow_the_stock_change(self):
        self.edit_module(self.module, self.user, {"approach": "stock_difference", **stock_fields()})
        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name_en, "READY")

        area = self.module.area
        expected_w = -(sum(END_W.values()) - sum(START.values())) * area * 44 / 12
        expected_wo = -(sum(END_WO.values()) - sum(START.values())) * area * 44 / 12

        data = self.balance()
        self.assertAlmostEqual(data["total_w"], expected_w, places=4)
        self.assertAlmostEqual(data["total_wo"], expected_wo, places=4)

    def test_stock_difference_with_missing_stock_is_not_ready(self):
        fields = stock_fields()
        del fields["stock_soc_wo"]
        self.edit_module(self.module, self.user, {"approach": "stock_difference", **fields})
        self.module.refresh_from_db()
        self.assertEqual(self.module.status.name_en, "EMPTY")

    def test_excel_report_lists_the_stock_inputs_instead_of_gain_loss_defaults(self):
        self.edit_module(self.module, self.user, {"approach": "stock_difference", **stock_fields()})

        request = self.request_factory.post(reverse("project-report", args=[self.project.pk]), {}, format="json")
        force_authenticate(request, user=self.user)
        response = ProjectViewSet.as_view({"post": "report"})(request, pk=self.project.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK, getattr(response, "data", None))

        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        rows = [row for sheet in workbook.worksheets for row in sheet.iter_rows(values_only=True)]
        by_label = {row[0]: row[1:4] for row in rows if row and isinstance(row[0], str)}
        for pool, label in (("agb", "AGB"), ("bgb", "BGB"), ("litter", "Litter"), ("deadwood", "Deadwood"), ("soc", "SOC")):
            self.assertEqual(tuple(by_label[f"{label} stock (tC/ha)"]), (START[pool], END_W[pool], END_WO[pool]))
        self.assertEqual(by_label["Approach"][0], "Stock difference")
        self.assertEqual(by_label["Data source"][0], self.module.data_source.short_name)
        self.assertNotIn("AGB growth rate <=20 years (tC/ha)", by_label)


class StockDifferenceLandUseChangeTestCase(SimpleTestCase):
    def test_land_use_change_is_rejected(self):
        module = SimpleNamespace(is_luc_remaining_same=lambda: False, is_business_as_usual=lambda: True)
        with self.assertRaisesMessage(ValueError, STOCK_DIFFERENCE_LUC_ERROR):
            calculate_stock_difference(SimpleNamespace(module=module, forest=None))


class StockDifferenceDefaultsTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        self.ModuleClass = models.ForestManagement
        super().setUp()

        agb_ref = ipcc_models.ForestManagementAGB.objects.filter(
            climate=self.project.climate, region=self.project.country.region, from_year=0, agb_min__isnull=False, agb_max__isnull=False
        ).first()
        self.assertIsNotNone(agb_ref, "seed DB has no ForestManagementAGB row for the test project")
        self.agb_ref = agb_ref
        self.edit_module(
            self.module,
            self.user,
            {
                "land_use_type_start": agb_ref.land_use_type_id,
                "forest_type": agb_ref.forest_type_id,
                "forest_condition_type": agb_ref.forest_condition_type_id,
            },
        )
        self.module.refresh_from_db()

    def defaults(self):
        return vars(DefaultsFactory.get_defaults(self.module, calculate=True))

    def test_ipcc_stocks_come_from_reference_tables(self):
        values = stock_difference_defaults(self.module)

        agb_dm = (self.agb_ref.agb_min + self.agb_ref.agb_max) / 2
        agb = agb_dm * NON_MANGROVE_FACTOR
        self.assertAlmostEqual(values["stock_agb_start_default"], agb)
        self.assertEqual(values["stock_agb_w_default"], values["stock_agb_start_default"])
        self.assertEqual(values["stock_agb_wo_default"], values["stock_agb_start_default"])

        rshoot = ipcc_models.ForestManagementRootToShoot.objects.get_max_below_threshold(
            climate=self.project.climate, forest_type=self.module.forest_type, region=self.project.country.region, land_use_type=self.module.land_use_type_start, threshold=agb_dm
        )
        if rshoot is None:
            self.assertIsNone(values["stock_bgb_start_default"])
        else:
            self.assertAlmostEqual(values["stock_bgb_start_default"], agb * rshoot.value)

        litter_dw = ipcc_models.LitterDeadwoodCarbonStock.objects.filter(
            climate=self.project.climate, forest_type=self.module.forest_type, land_use_type=self.module.land_use_type_start
        ).first()
        self.assertEqual(values["stock_litter_w_default"], litter_dw.litter if litter_dw else None)
        self.assertEqual(values["stock_deadwood_wo_default"], litter_dw.dw if litter_dw else None)

        soc = ipcc_models.SoilOrganicCarbon.objects.filter(climate=self.project.climate, moisture=self.project.moisture, soil_type=self.project.soil_type).first()
        self.assertEqual(values["stock_soc_start_default"], self.activity.soc or (soc.value if soc else None))

    def test_fra_reference_uses_latest_year_up_to_project_start(self):
        country = self.project.country
        start = self.project.start_year_of_activities
        ipcc_models.FRACarbonStock.objects.filter(country=country).delete()
        ipcc_models.FRACarbonStock.objects.create(country=country, year=start - 10, agb=1, bgb=1, litter=1, deadwood=1)
        ipcc_models.FRACarbonStock.objects.create(country=country, year=start - 5, agb=50, bgb=12, litter=None, deadwood=3)
        ipcc_models.FRACarbonStock.objects.create(country=country, year=start + 5, agb=99, bgb=99, litter=99, deadwood=99)

        fra = stock_difference_defaults(self.module)["stock_fra_reference"]
        self.assertEqual(fra["year"], start - 5)
        self.assertEqual(fra["country"], country.name)
        self.assertEqual(fra["data_source"], models.DataSource.objects.get(short_name="FRA").id)
        self.assertEqual((fra["agb"], fra["bgb"], fra["litter"], fra["deadwood"]), (50, 12, 0, 3))

    def test_fra_reference_falls_back_to_nearest_later_year(self):
        country = self.project.country
        start = self.project.start_year_of_activities
        ipcc_models.FRACarbonStock.objects.filter(country=country).delete()
        ipcc_models.FRACarbonStock.objects.create(country=country, year=start + 8, agb=7, bgb=7, litter=7, deadwood=7)
        ipcc_models.FRACarbonStock.objects.create(country=country, year=start + 3, agb=5, bgb=None, litter=5, deadwood=5)

        fra = stock_difference_defaults(self.module)["stock_fra_reference"]
        self.assertEqual(fra["year"], start + 3)
        self.assertEqual(fra["bgb"], 0)

    def test_fra_reference_without_country_data(self):
        ipcc_models.FRACarbonStock.objects.filter(country=self.project.country).delete()
        fra = stock_difference_defaults(self.module)["stock_fra_reference"]
        self.assertIsNone(fra["year"])
        self.assertIsNone(fra["agb"])

    def test_not_ready_module_still_gets_stock_defaults(self):
        self.edit_module(self.module, self.user, {"approach": "stock_difference"})
        self.module.refresh_from_db()
        self.assertFalse(self.module.is_ready())
        self.assertIn("stock_agb_start_default", self.defaults())

    def test_stock_difference_defaults_do_not_need_growth_data(self):
        self.edit_module(self.module, self.user, {"approach": "stock_difference", **stock_fields()})
        self.module.refresh_from_db()
        self.assertTrue(self.module.is_ready())
        ipcc_models.ForestManagementAGBGrowth.objects.all().delete()

        values = self.defaults()
        self.assertAlmostEqual(values["stock_agb_start_default"], (self.agb_ref.agb_min + self.agb_ref.agb_max) / 2 * NON_MANGROVE_FACTOR)

    def test_gain_loss_defaults_keep_their_fields_and_add_stocks(self):
        values = self.defaults()
        self.assertIn("soc_t2_start_default", values)
        self.assertIn("stock_soc_start_default", values)
