"""Excel Results rows for OrganicSoil: the activity total carries the organic soil balance.

OrganicSoil is its own module on the activity (the land calculators skip mineral SOC/SOM when it is
present and never read its fluxes), so its drainage, rewetting, soil fire and peat extraction lines
reach the Results sheet only through its own report.

Run with:
    python manage.py test api.tests.reports.test_organic_soil_report_rows --keepdb
"""

from rest_framework import status

import api.models as models
import ipcc.models as ipcc_models
from api.reports import compute_project_result
from api.reports.modules import OrganicSoilReport
from api.tests.unit.utils import APITestCaseMixin


class OrganicSoilReportRowsTestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        self.project_data.update(
            climate=models.Climate.objects.get(name_en="Cool Temperate").id,
            moisture=models.Moisture.objects.get(name_en="Moist").id,
            gw_potential=ipcc_models.GlobalWarmingPotential.objects.order_by("pk").first().id,
        )
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=response.data["id"])

        module_types = [models.ModuleType.objects.get(class_name=name) for name in ("Grassland", "OrganicSoil")]
        response = self.create_activity(self.project, self.user, module_types)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        grassland = models.Grassland.objects.get(activity_id=response.data["id"])
        management_type = models.GrasslandManagementType.objects.order_by("pk").first()
        for scenario in ("start", "w", "wo"):
            setattr(grassland, f"grassland_management_type_{scenario}", management_type)
            setattr(grassland, f"is_fire_used_{scenario}", False)
        grassland.save()

        organic_soil = models.OrganicSoil.objects.get(activity_id=response.data["id"])
        organic_soil.peat_type = models.PeatType.objects.get(name_en="Nutrient Rich")
        for scenario, peat_area in (("start", 100.0), ("w", 40.0), ("wo", 100.0)):
            setattr(organic_soil, f"peat_area_{scenario}", peat_area)
            setattr(organic_soil, f"peat_ditches_area_{scenario}", 0.1)
            setattr(organic_soil, f"peat_extraction_height_{scenario}", 2.0)
        organic_soil.save()

        self.result = compute_project_result(self.project)
        self.activity = self.result.activity_results[0]
        self.organic_soil_index = next(
            i for i, report in enumerate(self.activity._module_reports) if isinstance(report, OrganicSoilReport)
        )

    def assertSeriesEqual(self, got, want):
        self.assertEqual(len(got), len(want), msg=f"{got} != {want}")
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w, places=6, msg=f"{got} != {want}")

    def test_organic_soil_balance_is_not_empty(self):
        organic_soil_report = self.activity._module_reports[self.organic_soil_index]
        self.assertTrue(any(abs(v) > 1e-6 for v in organic_soil_report._balance_total()))

    def test_activity_total_equals_project_yearly_balance(self):
        for suffix in ("", "_w", "_wo"):
            with self.subTest(scenario=suffix or "balance"):
                self.assertSeriesEqual(
                    getattr(self.activity, "total_emissions" + suffix),
                    getattr(self.result.aggregated, "yearly_balance" + suffix),
                )

    def test_peat_extraction_lands_in_named_rows(self):
        rows = {row.label: row.yearly_values for row in self.activity.module_results[self.organic_soil_index].result_rows}
        self.assertTrue(any(abs(v) > 1e-6 for v in rows["CO2 from extracted peat (off-site)"]))
        self.assertNotIn("Other emissions (CO2-eq)", rows)

    def test_organic_soil_rows_add_up_to_its_total(self):
        module_result = self.activity.module_results[self.organic_soil_index]
        for suffix in ("", "_w", "_wo"):
            with self.subTest(scenario=suffix or "balance"):
                rows = getattr(module_result, "result_rows" + suffix)
                row_sum = [sum(year) for year in zip(*(row.yearly_values for row in rows))]
                self.assertSeriesEqual(row_sum, getattr(module_result, "total_emissions" + suffix))
