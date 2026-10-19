"""NDC framing (ported from NEXT): project analysis purpose / phase, activity conditionality,
and the project balance split by conditionality.

Run with:
    python manage.py test api.tests.test_ndc_framing --keepdb
"""

import json
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import resolve
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from api.models import Activity, AnalysisPurpose, Climate, Country, Group, Moisture, Project, ProjectMembership, ProjectPhase, SoilType
from api.reports.data_types import ActivityResult
from api.reports.renderer import ExcelRenderer
from api.serializers import ActivityResultSerializer, ActivitySummarySerializer, ProjectExportSerializer, ReadProjectSerializer, WriteActivitySerializer
from api.services.conditionality_results import aggregate_by_conditionality
from api.tests.factories import ActivityFactory, ProjectFactory, UserFactory


def call(user, method, path, data=None):
    """Dispatch straight to the view.

    The test client would run minitool's DatabaseConnectionMiddleware, which closes
    every connection after each response and breaks the next query in a TestCase.
    """
    request = getattr(APIRequestFactory(), method)(path, data, format="json")
    force_authenticate(request, user=user)
    match = resolve(path.split("?")[0])
    return match.func(request, *match.args, **match.kwargs)


def gas_rows(*per_gas_yearly):
    return [{"gas_type": {"name": gas}, "emissions": [{"value": v} for v in values]} for gas, values in zip(("CO2", "CH4", "N2O"), per_gas_yearly)]


def activity_payload(conditionality, balance, w=None, wo=None):
    """One activity with one module; ``balance`` etc. are lists of per-gas yearly lists."""
    return {
        "conditionality": conditionality,
        "modules": [{"results": {"balance": gas_rows(*balance), "total_w": gas_rows(*(w or balance)), "total_wo": gas_rows(*(wo or [[0.0]]))}}],
    }


class AggregateByConditionalityTests(SimpleTestCase):
    def test_mixed_project(self):
        activities = [
            activity_payload("unconditional", [[1.0, 2.0], [0.5, 0.5]], w=[[3.0, 3.0]], wo=[[1.0, 1.0]]),
            activity_payload("conditional", [[-10.0, -10.0, -10.0]]),
            activity_payload(None, [[4.0]]),
            activity_payload("unconditional", [[1.0]]),
        ]

        out = aggregate_by_conditionality(activities, start_year=2024)

        self.assertEqual(out["unconditional"]["cumulative"], {"balance": 5.0, "total_w": 7.0, "total_wo": 2.0})
        self.assertEqual(out["conditional"]["cumulative"]["balance"], -30.0)
        self.assertEqual(out["unspecified"]["cumulative"]["balance"], 4.0)
        self.assertEqual([y["balance"] for y in out["unconditional"]["annual"]], [2.5, 2.5, 0.0])
        self.assertEqual([y["year"] for y in out["conditional"]["annual"]], [2024, 2025, 2026])
        for group in out.values():
            self.assertEqual(len(group["annual"]), 3)

    def test_groups_reconcile_with_project_total(self):
        activities = [activity_payload("conditional", [[2.0, 3.0], [1.0, 1.0]]), activity_payload(None, [[5.0]])]
        out = aggregate_by_conditionality(activities, start_year=2024)
        self.assertEqual(sum(g["cumulative"]["balance"] for g in out.values()), 12.0)

    def test_all_null_lands_in_unspecified(self):
        out = aggregate_by_conditionality([activity_payload(None, [[1.0, 1.0]])], start_year=2024)
        self.assertEqual(out["unspecified"]["cumulative"]["balance"], 2.0)
        self.assertEqual(out["unconditional"]["cumulative"]["balance"], 0.0)
        self.assertEqual(out["conditional"]["cumulative"]["balance"], 0.0)

    def test_failed_modules_contribute_nothing(self):
        activities = [{"conditionality": "conditional", "modules": [{"results": {"balance": "Module is not ready"}}, {"results": "error"}]}]
        out = aggregate_by_conditionality(activities, start_year=2024)
        self.assertEqual(out["conditional"], {"cumulative": {"total_w": 0, "total_wo": 0, "balance": 0}, "annual": []})


class FieldRoundTripTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.user = UserFactory(email="ndc-framing@example.com", is_superuser=True, is_staff=True)
        self.project = ProjectFactory(owner=self.user, country=Country.objects.first())
        self.purpose = AnalysisPurpose.objects.get(name_en="Nationally Determined Contribution")
        self.phase = ProjectPhase.objects.get(name_en="Design")

    def patch_project(self, payload):
        with mock.patch("api.views.security.check_permission", return_value=None), \
             mock.patch("api.views.ProjectViewSet.get_object", return_value=self.project), \
             mock.patch("api.models.Project._check_lock_expiration"):
            return call(self.user, "patch", f"/api/projects/{self.project.pk}/", payload)

    def test_lookup_endpoints_list_the_next_options(self):
        purposes = call(self.user, "get", "/api/analysis-purposes/")
        phases = call(self.user, "get", "/api/project-phases/")
        self.assertEqual(purposes.status_code, 200)
        self.assertEqual(len(purposes.data), 6)
        self.assertEqual(len(phases.data), 5)

    def test_project_defaults_to_null(self):
        data = ReadProjectSerializer(self.project, context={"request": mock.Mock(user=self.user)}).data
        self.assertIsNone(data["analysis_purpose"])
        self.assertIsNone(data["project_phase"])

    def test_patch_and_read_back(self):
        resp = self.patch_project({"analysis_purpose": self.purpose.pk, "project_phase": self.phase.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.project.refresh_from_db()
        self.assertEqual(self.project.analysis_purpose, self.purpose)
        self.assertEqual(self.project.project_phase, self.phase)

        resp = self.patch_project({"analysis_purpose": None})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.analysis_purpose)

    def test_framing_change_keeps_module_caches(self):
        with mock.patch("api.models.invalidate_module_caches") as invalidate:
            resp = self.patch_project({"project_phase": self.phase.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        invalidate.assert_not_called()

    def test_activity_conditionality(self):
        activity = ActivityFactory(project=self.project, owner=self.user)
        self.assertIsNone(activity.conditionality)
        request = mock.Mock(user=self.user)

        serializer = WriteActivitySerializer(activity, data={"conditionality": "conditional"}, partial=True, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with mock.patch("api.models.invalidate_module_caches") as invalidate:
            serializer.save()
        invalidate.assert_not_called()
        activity.refresh_from_db()
        self.assertEqual(activity.conditionality, Activity.Conditionality.CONDITIONAL)
        self.assertEqual(ActivityResultSerializer(activity).data["conditionality"], "conditional")
        self.assertEqual(ActivitySummarySerializer(activity).data["conditionality"], "conditional")

        bad = WriteActivitySerializer(activity, data={"conditionality": "maybe"}, partial=True, context={"request": request})
        self.assertFalse(bad.is_valid())
        self.assertIn("conditionality", bad.errors)


class ProjectResultsByConditionalityTests(TestCase):
    """View wiring; the arithmetic is pinned by AggregateByConditionalityTests."""

    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        self.user = UserFactory(email="ndc-results@example.com", is_superuser=True, is_staff=True)
        self.project = ProjectFactory(owner=self.user, country=Country.objects.first(), start_year_of_activities=2024)
        self.unconditional = ActivityFactory(project=self.project, owner=self.user, conditionality="unconditional")
        self.conditional = ActivityFactory(project=self.project, owner=self.user, conditionality="conditional")
        self.unspecified = ActivityFactory(project=self.project, owner=self.user)
        # Captured here because the fake below runs on worker threads, which cannot see this test's transaction.
        self.conditionality_by_pk = {a.pk: a.conditionality for a in (self.unconditional, self.conditional, self.unspecified)}
        self.calls = []

    def fake_activity_results(self, _viewset, _request, pk=None, aggregate=None):
        self.calls.append(aggregate)
        balance = {self.unconditional.pk: 10.0, self.conditional.pk: -4.0, self.unspecified.pk: 1.0}[pk]
        if aggregate == "gas":
            results = {"balance": gas_rows([balance, balance]), "total_w": gas_rows([balance]), "total_wo": gas_rows([0.0])}
        else:
            results = {"balance": 2 * balance, "total_w": balance, "total_wo": 0.0}
        return Response({"id": pk, "conditionality": self.conditionality_by_pk[pk], "modules": [{"results": results}]})

    def get_results(self, query=""):
        with mock.patch("api.views.ActivityViewSet.results", new=self.fake_activity_results):
            return call(self.user, "get", f"/api/projects/{self.project.pk}/results/{query}")

    def test_aggregate_conditionality(self):
        resp = self.get_results("?aggregate=conditionality")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(self.calls), {"gas"})
        split = resp.data["conditionality"]
        self.assertEqual(split["unconditional"]["cumulative"]["balance"], 20.0)
        self.assertEqual(split["conditional"]["cumulative"]["balance"], -8.0)
        self.assertEqual(split["unspecified"]["cumulative"]["balance"], 2.0)
        self.assertEqual([y["year"] for y in split["conditional"]["annual"]], [2024, 2025])
        self.assertEqual(len(resp.data["activities"]), 3)

    def test_default_results_are_unchanged(self):
        resp = self.get_results()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(self.calls), {None})
        self.assertNotIn("conditionality", resp.data)


class ExportImportTests(TestCase):
    def setUp(self):
        self.user = UserFactory(is_superuser=True, is_staff=True)
        self.project = ProjectFactory(
            owner=self.user,
            name="NDC Round Trip",
            climate=Climate.objects.first(),
            moisture=Moisture.objects.first(),
            soil_type=SoilType.objects.first(),
            country=Country.objects.first(),
            analysis_purpose=AnalysisPurpose.objects.get(value=5),
            project_phase=ProjectPhase.objects.get(value=3),
        )
        ProjectMembership.objects.create(project=self.project, user=self.user, group=Group.objects.get_or_create(name="Admin")[0])
        ActivityFactory(project=self.project, owner=self.user, name="U", conditionality="unconditional")
        ActivityFactory(project=self.project, owner=self.user, name="N")

    def test_round_trip_keeps_the_fields(self):
        exported = call(self.user, "get", f"/api/projects/{self.project.id}/export/")
        self.assertEqual(exported.status_code, http_status.HTTP_200_OK)
        payload = json.loads(exported.content)

        resp = call(self.user, "post", "/api/projects/import_project/?forceCopy=true", payload)
        self.assertEqual(resp.status_code, http_status.HTTP_201_CREATED, getattr(resp, "data", None))

        imported = Project.objects.get(id=resp.data["projectId"])
        self.assertEqual(imported.analysis_purpose.value, 5)
        self.assertEqual(imported.project_phase.value, 3)
        self.assertEqual(dict(imported.activities.values_list("name", "conditionality")), {"U": "unconditional", "N": None})

    def test_export_of_unset_fields_is_null(self):
        project = ProjectFactory(owner=self.user, country=Country.objects.first())
        data = ProjectExportSerializer(project).data
        self.assertIsNone(data["analysis_purpose"])
        self.assertIsNone(data["project_phase"])


class ExcelReportTests(SimpleTestCase):
    DURATION = 3

    def render(self, conditionalities, purpose=None):
        project = mock.Mock(status=None, project_phase=None, analysis_purpose=mock.Mock() if purpose else None, implementation_years=2, capitalization_years=1)
        project.configure_mock(**{
            "name": "P", "country.name": "Kenya", "climate.name": "Tropical", "moisture.name": "Wet", "soil_type.name": "HAC",
            "gwp.name": "AR5", "gwp.co2": 1, "gwp.ch4": 28, "gwp.n2o": 265, "gwp.ch4_fossil": 30,
        })
        if purpose:
            project.analysis_purpose.name = purpose
        result = mock.Mock(project=project, start_year=2024, last_year=2024 + self.DURATION, duration=self.DURATION)
        result.activity_results = [
            ActivityResult(title=f"A{i}", module_results=[], total_emissions=[1.0, 2.0, 3.0], total_hectares_yearly=[], conditionality=c)
            for i, c in enumerate(conditionalities)
        ]
        renderer = ExcelRenderer(result)
        wb = renderer._manager.get_workbook()
        renderer._write_skeleton(wb)
        renderer._write_conditionality_summary(wb)
        for ar in result.activity_results:
            renderer._write_activity(wb, ar)
        return wb

    def test_metadata_rows(self):
        meta = self.render([None], purpose="Nationally Determined Contribution")["Metadata"]
        self.assertEqual((meta.cell(16, 1).value, meta.cell(16, 2).value), ("Analysis purpose", "Nationally Determined Contribution"))
        self.assertEqual((meta.cell(17, 1).value, meta.cell(17, 2).value), ("Project phase", "N/A"))

    def test_results_layout_unchanged_without_conditionality(self):
        wb = self.render([None, None])
        self.assertEqual(wb["Results"].cell(15, 1).value, "A0")
        labels = [c.value for c in wb["Metadata"]["A"]]
        self.assertNotIn("NDC conditionality", labels)

    def test_results_split_by_conditionality(self):
        wb = self.render(["unconditional", "conditional", None, "unconditional"])
        res = wb["Results"]
        rows = {res.cell(r, 1).value: [res.cell(r, c).value for c in range(2, 2 + self.DURATION)] for r in range(15, 21)}
        self.assertEqual(rows["Unconditional - cumulative balance in Tco2-eq"], [2.0, 6.0, 12.0])
        self.assertEqual(rows["Conditional - yearly balance in Tco2-eq"], [1.0, 2.0, 3.0])
        self.assertEqual(rows["Not specified - cumulative balance in Tco2-eq"], [1.0, 3.0, 6.0])
        self.assertEqual(res.cell(21, 1).value, "A0")
        self.assertIn("NDC conditionality", [c.value for c in wb["Metadata"]["A"]])
