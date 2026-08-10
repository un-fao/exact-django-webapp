"""Tests for the read-only activity_count / module_count serializer fields.

These fields let the frontend decide between the synchronous and asynchronous
report/copy endpoints. module_count must match the copy_async threshold formula
exactly: the number of activity -> module_types join rows across the project's
activities (join rows, not distinct module types).

The value assertions call the serializer getters and the ProjectViewSet batch
helper directly. Those paths only count the activity -> module_types M2M join
rows (Count over the relation) and never dereference ModuleType.class_name, so
the tests can use bare ModuleType rows and need no reference data. Full
ReadProjectSerializer .data is only exercised on module-free projects, because
its get_total_hectares getter walks Activity.modules, which does dereference
class_name.
"""

from django.test import TestCase

from api.models import Country, ModuleType, Project
from api.serializers import ProjectSummarySerializer, ReadProjectSerializer
from api.tests.factories import ActivityFactory, ProjectFactory, UserFactory
from api.views import ProjectViewSet


def make_module_type(name):
    """Create a bare ModuleType for join-row counting.

    ModuleType.name is unique, so every caller passes a distinct name. class_name
    is left null on purpose: these tests only count activity -> module_types join
    rows, which never dereferences class_name.
    """
    return ModuleType.objects.create(name=name)


def copy_formula_module_count(project):
    """Mirror the copy_async endpoint's module_count computation exactly."""
    return sum(a.module_types.count() for a in project.activities.all())


class ProjectCountDetailSerializerTests(TestCase):
    def setUp(self):
        self.country = Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()
        self.user = UserFactory(email="counts-detail@example.com")

    def test_module_count_matches_copy_formula(self):
        project = ProjectFactory(owner=self.user, country=self.country)
        a1 = ActivityFactory(project=project)
        a2 = ActivityFactory(project=project)
        ActivityFactory(project=project)  # a3: zero module types

        a1.module_types.add(make_module_type("counts-detail-a1-x"), make_module_type("counts-detail-a1-y"))
        a2.module_types.add(
            make_module_type("counts-detail-a2-x"),
            make_module_type("counts-detail-a2-y"),
            make_module_type("counts-detail-a2-z"),
        )

        serializer = ReadProjectSerializer(project)
        expected_modules = copy_formula_module_count(project)

        self.assertEqual(expected_modules, 5)
        self.assertEqual(serializer.get_activity_count(project), 3)
        self.assertEqual(serializer.get_module_count(project), expected_modules)

    def test_module_count_counts_join_rows_not_distinct_types(self):
        # A module type shared across activities must be counted once per activity
        # (join-row semantics), matching the copy_async threshold. distinct here
        # would wrongly collapse the shared type to one.
        project = ProjectFactory(owner=self.user, country=self.country)
        shared = make_module_type("counts-detail-shared")
        a1 = ActivityFactory(project=project)
        a2 = ActivityFactory(project=project)

        a1.module_types.add(shared, make_module_type("counts-detail-only-a1"))
        a2.module_types.add(shared)

        serializer = ReadProjectSerializer(project)
        expected_modules = copy_formula_module_count(project)

        self.assertEqual(expected_modules, 3)  # 2 (a1) + 1 (a2); shared counted twice
        self.assertEqual(serializer.get_activity_count(project), 2)
        self.assertEqual(serializer.get_module_count(project), expected_modules)

    def test_data_auto_includes_keys_and_zero_module_edge(self):
        # Meta.fields = "__all__" auto-includes declared SerializerMethodFields
        # (same as the existing role / total_hectares fields). Verify on a
        # module-free project so full .data is safe to compute.
        project = ProjectFactory(owner=self.user, country=self.country)
        ActivityFactory(project=project)  # activity with zero module types
        ActivityFactory(project=project)

        data = ReadProjectSerializer(project).data

        self.assertIn("activity_count", data)
        self.assertIn("module_count", data)
        self.assertEqual(data["activity_count"], 2)
        self.assertEqual(data["module_count"], 0)  # activities with zero module types contribute 0

    def test_empty_project_returns_zero_counts(self):
        project = ProjectFactory(owner=self.user, country=self.country)

        data = ReadProjectSerializer(project).data

        self.assertEqual(data["activity_count"], 0)
        self.assertEqual(data["module_count"], 0)

    def test_fallback_computes_without_attached_attributes(self):
        project = ProjectFactory(owner=self.user, country=self.country)
        a1 = ActivityFactory(project=project)
        a1.module_types.add(make_module_type("counts-fallback-x"), make_module_type("counts-fallback-y"))

        # Re-fetch so no _activity_count / _module_count attributes are attached.
        fresh = Project.objects.get(pk=project.pk)
        self.assertFalse(hasattr(fresh, "_activity_count"))
        self.assertFalse(hasattr(fresh, "_module_count"))

        serializer = ReadProjectSerializer(fresh)
        self.assertEqual(serializer.get_activity_count(fresh), 1)
        self.assertEqual(serializer.get_module_count(fresh), 2)


class ProjectCountBatchAndListTests(TestCase):
    def setUp(self):
        self.country = Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()
        self.user = UserFactory(email="counts-list@example.com")

    def _build_project(self, tag, module_counts_per_activity):
        project = ProjectFactory(owner=self.user, country=self.country)
        for activity_index, module_count in enumerate(module_counts_per_activity):
            activity = ActivityFactory(project=project)
            for module_index in range(module_count):
                activity.module_types.add(make_module_type(f"counts-list-{tag}-{activity_index}-{module_index}"))
        return project

    def test_batch_helper_attaches_correct_values_across_projects(self):
        p1 = self._build_project("p1", [2, 3])  # 2 activities, 5 join rows
        p2 = self._build_project("p2", [1])     # 1 activity, 1 join row
        p3 = self._build_project("p3", [])      # 0 activities, 0 join rows

        ProjectViewSet()._attach_project_counts([p1, p2, p3])

        self.assertEqual((p1._activity_count, p1._module_count), (2, 5))
        self.assertEqual((p2._activity_count, p2._module_count), (1, 1))
        self.assertEqual((p3._activity_count, p3._module_count), (0, 0))

    def test_batch_helper_shared_module_type_not_deduped(self):
        # activity_count must stay correct (distinct) while module_count counts
        # join rows (non-distinct), even when the module_types join inflates rows.
        project = ProjectFactory(owner=self.user, country=self.country)
        shared = make_module_type("counts-list-shared")
        a1 = ActivityFactory(project=project)
        a2 = ActivityFactory(project=project)
        a1.module_types.add(shared, make_module_type("counts-list-a1-extra"))
        a2.module_types.add(shared)

        ProjectViewSet()._attach_project_counts([project])

        self.assertEqual(project._activity_count, 2)
        self.assertEqual(project._module_count, 3)
        self.assertEqual(project._module_count, copy_formula_module_count(project))

    def test_summary_serializer_reads_attached_counts(self):
        project = self._build_project("summary", [2, 1])  # activity_count=2, module_count=3
        ProjectViewSet()._attach_project_counts([project])

        data = ProjectSummarySerializer(project).data

        self.assertEqual(data["activity_count"], 2)
        self.assertEqual(data["module_count"], 3)

    def test_summary_serializer_fallback_without_attached_counts(self):
        project = self._build_project("summary-fallback", [1, 1])

        # Re-fetch so the serializer getters take the fallback (compute) path.
        fresh = Project.objects.get(pk=project.pk)
        data = ProjectSummarySerializer(fresh).data

        self.assertEqual(data["activity_count"], 2)
        self.assertEqual(data["module_count"], 2)

    def test_attach_no_projects_is_noop(self):
        # Empty input must not raise (and issues no query).
        ProjectViewSet()._attach_project_counts([])
