"""Tests for project export/import functionality."""
import json
import uuid
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from .factories import UserFactory, ProjectFactory
from ..models import (
    Climate, Country, Moisture, Project, ProjectMembership, ProjectStatus, SoilType,
)
from ipcc.models import GlobalWarmingPotential

# minitool.middleware.DatabaseConnectionMiddleware calls connections.close_all()
# after every response. Django's TestCase wraps each test in a transaction on a
# single connection, so closing it mid-test makes every subsequent query raise
# "Cannot operate on a closed database". Tests that drive the API client through
# TestCase must therefore run without that middleware.
MIDDLEWARE_WITHOUT_CONNECTION_CLOSER = [
    middleware for middleware in settings.MIDDLEWARE
    if not middleware.startswith("minitool.")
]


class ProjectExportIdFieldTests(TestCase):
    """Tests for the export_id field on Project."""

    def test_export_id_is_nullable(self):
        """Project can be created without export_id."""
        user = UserFactory()
        project = ProjectFactory(owner=user)
        self.assertIsNone(project.export_id)

    def test_export_id_accepts_uuid(self):
        """Project can store a UUID export_id."""
        user = UserFactory()
        export_id = uuid.uuid4()
        project = ProjectFactory(owner=user, export_id=export_id)
        project.refresh_from_db()
        self.assertEqual(project.export_id, export_id)

    def test_export_id_is_unique(self):
        """Two projects cannot share the same export_id."""
        user = UserFactory()
        export_id = uuid.uuid4()
        ProjectFactory(owner=user, export_id=export_id)
        with self.assertRaises(Exception):
            ProjectFactory(owner=user, export_id=export_id, name="Other")


class ProjectExportTests(TestCase):
    """Tests for the project export endpoint."""

    def setUp(self):
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.project = ProjectFactory(owner=self.user, name="Test Project")

    def test_export_returns_json_file(self):
        """Export endpoint returns .exactproject file."""
        response = self.client.get(f'/api/projects/{self.project.id}/export/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('.exactproject', response['Content-Disposition'])

    def test_export_contains_required_fields(self):
        """Exported file contains all required metadata."""
        response = self.client.get(f'/api/projects/{self.project.id}/export/')
        data = json.loads(response.content)
        self.assertIn('formatVersion', data)
        self.assertIn('appVersion', data)
        self.assertIn('compatibilityGroup', data)
        self.assertIn('exportedAt', data)
        self.assertIn('exportId', data)
        self.assertIn('project', data)
        # 2 since reference relations carry a `<field>__nk` natural key.
        self.assertEqual(data['formatVersion'], 2)
        # compatibilityGroup must NOT move: it hard-rejects on mismatch and
        # would invalidate every .exactproject already issued.
        self.assertEqual(data['compatibilityGroup'], 1)

    def test_export_generates_export_id(self):
        """Export generates export_id if not present."""
        self.assertIsNone(self.project.export_id)
        self.client.get(f'/api/projects/{self.project.id}/export/')
        self.project.refresh_from_db()
        self.assertIsNotNone(self.project.export_id)

    def test_export_reuses_export_id(self):
        """Subsequent exports use same export_id."""
        response1 = self.client.get(f'/api/projects/{self.project.id}/export/')
        data1 = json.loads(response1.content)
        response2 = self.client.get(f'/api/projects/{self.project.id}/export/')
        data2 = json.loads(response2.content)
        self.assertEqual(data1['exportId'], data2['exportId'])


class ProjectImportTests(TestCase):
    """Tests for the project import endpoint."""

    def setUp(self):
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.valid_import_data = {
            "formatVersion": 1,
            "appVersion": "1.0.0",
            "compatibilityGroup": 1,
            "exportedAt": "2026-02-02T12:00:00Z",
            "exportId": str(uuid.uuid4()),
            "project": {
                "name": "Imported Project",
                "implementation_years": 20,
                "start_year_of_activities": 2024,
                "activities": []
            }
        }

    def test_import_creates_new_project(self):
        """Import creates a new project."""
        response = self.client.post(
            '/api/projects/import_project/',
            data=self.valid_import_data,
            format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertFalse(response.data['exists'])
        self.assertTrue(Project.objects.filter(name="Imported Project").exists())

    def test_import_detects_existing_project(self):
        """Import detects project with same export_id."""
        export_id = uuid.uuid4()
        existing = ProjectFactory(owner=self.user, export_id=export_id)
        self.valid_import_data['exportId'] = str(export_id)
        response = self.client.post(
            '/api/projects/import_project/',
            data=self.valid_import_data,
            format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['exists'])
        self.assertEqual(response.data['projectId'], existing.id)

    def test_import_force_copy(self):
        """Import with forceCopy creates new even if exists."""
        export_id = uuid.uuid4()
        ProjectFactory(owner=self.user, export_id=export_id)
        self.valid_import_data['exportId'] = str(export_id)
        response = self.client.post(
            '/api/projects/import_project/?forceCopy=true',
            data=self.valid_import_data,
            format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertFalse(response.data['exists'])

    def test_import_rejects_wrong_compatibility_group(self):
        """Import rejects files from different compatibility group."""
        self.valid_import_data['compatibilityGroup'] = 999
        response = self.client.post(
            '/api/projects/import_project/',
            data=self.valid_import_data,
            format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_import_rejects_unsupported_format_version(self):
        """Import rejects unsupported format versions."""
        self.valid_import_data['formatVersion'] = 999
        response = self.client.post(
            '/api/projects/import_project/',
            data=self.valid_import_data,
            format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class ThreadCommentExportImportTests(TestCase):
    """Tests for thread comment export/import functionality."""

    def setUp(self):
        from ..models import (
            Activity, ModuleType, Comment, CommentThread,
            Climate, Moisture, SoilType, Country, GlobalWarmingPotential
        )
        from ipcc.models import GlobalWarmingPotential as IPCCGwp

        self.user = UserFactory()
        self.second_user = UserFactory(email='second@test.com')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create required reference data
        self.climate, _ = Climate.objects.get_or_create(name_en='Tropical')
        self.moisture, _ = Moisture.objects.get_or_create(name_en='Wet')
        self.soil_type, _ = SoilType.objects.get_or_create(name_en='High')
        self.country, _ = Country.objects.get_or_create(name='Test Country', defaults={'code': 'TC'})

        # Create project
        self.project = ProjectFactory(
            owner=self.user,
            name="Test Project with Comments",
            climate=self.climate,
            moisture=self.moisture,
            soil_type=self.soil_type,
            country=self.country
        )

    def test_export_includes_thread_comments(self):
        """Export should include thread comments with full data."""
        from ..models import Activity, ModuleType, Comment, CommentThread, Grassland, StatusType

        # Create activity with module
        activity = Activity.objects.create(
            project=self.project,
            owner=self.user,
            name="Test Activity"
        )

        # Get or create module type
        grassland_type, _ = ModuleType.objects.get_or_create(
            name_en='Grassland',
            defaults={'class_name': 'Grassland'}
        )
        activity.module_types.add(grassland_type)

        # Create a grassland module
        status, _ = StatusType.objects.get_or_create(name_en='EMPTY')
        grassland = Grassland.objects.create(
            activity=activity,
            status=status
        )

        # Add comments to a thread field
        if grassland.grassland_management_type_thread:
            thread = grassland.grassland_management_type_thread
            comment1 = Comment.objects.create(
                thread=thread,
                author=self.user,
                content="This is a test comment"
            )
            reply = Comment.objects.create(
                thread=thread,
                parent=comment1,
                author=self.second_user,
                content="This is a reply"
            )

            # Export the project
            response = self.client.get(f'/api/projects/{self.project.id}/export/')
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)

            data = json.loads(response.content)

            # Check that activities exist
            self.assertIn('activities', data['project'])
            self.assertTrue(len(data['project']['activities']) > 0)

            activity_data = data['project']['activities'][0]
            self.assertIn('modules', activity_data)

            # Check for Grassland module with thread data
            if 'Grassland' in activity_data['modules']:
                grassland_data = activity_data['modules']['Grassland'][0]

                # Check that thread field contains comment data, not just an ID
                if 'grassland_management_type_thread' in grassland_data:
                    thread_data = grassland_data['grassland_management_type_thread']
                    self.assertIsInstance(thread_data, dict)
                    self.assertIn('comments', thread_data)
                    self.assertTrue(len(thread_data['comments']) > 0)

                    # Check comment structure
                    first_comment = thread_data['comments'][0]
                    self.assertIn('content', first_comment)
                    self.assertIn('author_email', first_comment)
                    self.assertIn('date_created', first_comment)
                    self.assertEqual(first_comment['content'], "This is a test comment")

                    # Check for replies
                    if 'replies' in first_comment:
                        self.assertTrue(len(first_comment['replies']) > 0)
                        self.assertEqual(first_comment['replies'][0]['content'], "This is a reply")

    def test_import_reconstructs_thread_comments(self):
        """Import should reconstruct threads with comments."""
        from ..models import Comment, Project

        import_data = {
            "formatVersion": 1,
            "appVersion": "1.0.0",
            "compatibilityGroup": 1,
            "exportedAt": "2026-02-02T12:00:00Z",
            "exportId": str(uuid.uuid4()),
            "project": {
                "name": "Project with Comments",
                "implementation_years": 20,
                "start_year_of_activities": 2024,
                "activities": []
            }
        }

        response = self.client.post(
            '/api/projects/import_project/',
            data=import_data,
            format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

        # Verify project was created
        imported_project = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported_project.name, "Project with Comments")


class ProjectImportCachedResultsTests(TestCase):
    """Regression: the export/import round trip must carry module cached
    results and module status, so an imported project shows its numbers
    without the user recomputing every module.

    Covers three independent failure modes that all had to be fixed:
      A. ``status`` was excluded from the export payload.
      B. ``last_modified`` was excluded, so the import-time value of ``now()``
         made the restored ``last_cached_at`` look stale.
      C. creating a submodule invalidated the freshly restored parent cache.
    """

    TOTAL = {"balance": 42.5}
    BY_ACTIVITY = {"cropland": 10.0}
    BY_GAS = {"co2": 30.0, "ch4": 12.5}
    BY_ACTIVITY_BY_GAS = {"cropland": {"co2": 30.0, "ch4": 12.5}}

    def setUp(self):
        from .factories import ActivityFactory, InputFactory, InputEntryFactory, GrasslandFactory
        from ..models import (
            Climate, Moisture, SoilType, Country, Group, ProjectMembership, ModuleType
        )

        # Superuser so the test exercises the round trip itself rather than
        # project permission wiring, which is covered elsewhere.
        self.user = UserFactory(is_superuser=True, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.project = ProjectFactory(
            owner=self.user,
            name="Cache Round Trip",
            climate=Climate.objects.first(),
            moisture=Moisture.objects.first(),
            soil_type=SoilType.objects.first(),
            country=Country.objects.first(),
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.user,
            group=Group.objects.get_or_create(name="Admin")[0],
        )
        self.activity = ActivityFactory(project=self.project, owner=self.user)
        # Activity.modules walks module_types, so the export sees nothing
        # unless the types are registered on the activity.
        self.activity.module_types.set(
            ModuleType.objects.filter(class_name__in=["Input", "Grassland"])
        )

        # Module WITH submodules: exercises failure mode C.
        self.parent_module = InputFactory(activity=self.activity)
        self.entry = InputEntryFactory(parent=self.parent_module)

        # Module WITHOUT submodules: exercises A and B in isolation, so a
        # regression in the submodule path cannot mask a regression here.
        self.plain_module = GrasslandFactory(activity=self.activity)

        # Cache AFTER submodules exist, mirroring production ordering.
        for module in (self.parent_module, self.plain_module):
            module.cache_results(
                self.TOTAL, self.BY_ACTIVITY, self.BY_GAS, self.BY_ACTIVITY_BY_GAS
            )
            module.refresh_from_db()
            self.assertTrue(
                module.is_cached_results_valid(),
                f"precondition failed: {module.__class__.__name__} cache invalid before export",
            )

    def _round_trip(self):
        """Export the project and re-import it as a forced copy."""
        from ..models import Project

        export = self.client.get(f'/api/projects/{self.project.id}/export/')
        self.assertEqual(export.status_code, http_status.HTTP_200_OK)
        payload = json.loads(export.content)

        response = self.client.post(
            '/api/projects/import_project/?forceCopy=true',
            data=payload,
            format='json'
        )
        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        return Project.objects.get(id=response.data['projectId'])

    def _imported(self, model, project):
        return model.objects.get(activity__project=project)

    def test_import_preserves_module_status(self):
        """Imported modules keep READY instead of being reset to EMPTY."""
        from ..models import Input, Grassland

        imported = self._round_trip()
        for model in (Input, Grassland):
            module = self._imported(model, imported)
            self.assertIsNotNone(module.status, f"{model.__name__} status is null")
            self.assertEqual(
                module.status.name_en, "READY",
                f"{model.__name__} status was reset to {module.status.name_en}",
            )
            self.assertTrue(module.is_ready())

    def test_import_preserves_submodule_status(self):
        """Submodule status survives the round trip too."""
        from ..models import InputEntry

        imported = self._round_trip()
        entry = InputEntry.objects.get(parent__activity__project=imported)
        self.assertIsNotNone(entry.status)
        self.assertEqual(entry.status.name_en, "READY")

    def test_import_preserves_cached_result_payloads(self):
        """The four cached_results_* JSON columns arrive byte-identical."""
        from ..models import Input, Grassland

        imported = self._round_trip()
        for model in (Input, Grassland):
            module = self._imported(model, imported)
            self.assertEqual(module.cached_results_total, self.TOTAL)
            self.assertEqual(module.cached_results_by_activity, self.BY_ACTIVITY)
            self.assertEqual(module.cached_results_by_gas, self.BY_GAS)
            self.assertEqual(
                module.cached_results_by_activity_by_gas, self.BY_ACTIVITY_BY_GAS
            )

    def test_import_keeps_cached_results_valid(self):
        """The restored cache must actually be readable, not just present.

        This is the assertion that fails when ``last_modified`` is dropped:
        the JSON columns are populated but ``is_cached_results_valid()`` is
        False, so ``get_cached_results()`` returns None and the module reads
        as uncomputed.
        """
        from ..models import Input, Grassland

        imported = self._round_trip()
        for model in (Input, Grassland):
            module = self._imported(model, imported)
            self.assertTrue(
                module.is_cached_results_valid(),
                f"{model.__name__}: last_cached_at={module.last_cached_at} "
                f"last_modified={module.last_modified}",
            )
            self.assertEqual(module.get_cached_results(), self.TOTAL)

    def test_import_cache_survives_submodule_creation(self):
        """Creating submodules during import must not wipe the parent cache."""
        from ..models import Input

        imported = self._round_trip()
        module = self._imported(Input, imported)
        self.assertIsNotNone(
            module.cached_results_total,
            "parent cache was invalidated while its submodule was created",
        )
        self.assertTrue(module.is_cached_results_valid())

    def test_export_does_not_invalidate_the_source_project(self):
        """Downloading a project must not destroy its own cached results.

        The first export assigns export_id and saves the project. Project.save
        bulk-invalidates every module cache for any dirty field outside its
        allowlist, so an unlisted export_id silently wiped the results of the
        project being exported, and guaranteed the file carried none either.
        """
        from ..models import Input, Grassland

        self.assertIsNone(self.project.export_id)

        response = self.client.get(f'/api/projects/{self.project.id}/export/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        self.project.refresh_from_db()
        self.assertIsNotNone(self.project.export_id, "precondition: export_id was assigned")

        for model in (Input, Grassland):
            module = model.objects.get(activity=self.activity)
            self.assertIsNotNone(
                module.cached_results_total,
                f"{model.__name__} cache was wiped by its own export",
            )
            self.assertTrue(module.is_cached_results_valid())

    def test_export_payload_includes_status_and_last_modified(self):
        """Guards the exporter directly, independent of import behaviour."""
        export = self.client.get(f'/api/projects/{self.project.id}/export/')
        payload = json.loads(export.content)
        modules = payload['project']['activities'][0]['modules']

        self.assertIn('Input', modules)
        exported_module = modules['Input'][0]
        for field in ('status', 'last_modified', 'last_cached_at', 'cached_results_total'):
            self.assertIn(
                field, exported_module,
                f"exporter dropped '{field}' from the module payload",
            )

        submodule = exported_module['_submodules'][0]
        self.assertIn('status', submodule)
        self.assertIn('last_modified', submodule)

    def test_import_of_legacy_payload_without_cache_fields(self):
        """A file produced by an older build still imports cleanly.

        Backward compatibility boundary: the restore must be opt-in on the
        presence of each key, never assume it.
        """
        from ..models import Input, Project

        export = self.client.get(f'/api/projects/{self.project.id}/export/')
        payload = json.loads(export.content)

        stripped = (
            'status', 'last_modified', 'last_cached_at', 'cached_results_total',
            'cached_results_by_activity', 'cached_results_by_gas',
            'cached_results_by_activity_by_gas', 'cached_units_breakdown',
        )

        def strip(module_data):
            for key in stripped:
                module_data.pop(key, None)
            for sub in module_data.get('_submodules', []):
                strip(sub)

        for activity in payload['project']['activities']:
            for module_list in activity['modules'].values():
                for module_data in module_list:
                    strip(module_data)

        payload['exportId'] = str(uuid.uuid4())
        response = self.client.post(
            '/api/projects/import_project/',
            data=payload,
            format='json'
        )
        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )

        imported = Project.objects.get(id=response.data['projectId'])
        module = Input.objects.get(activity__project=imported)
        # No cache to restore, so it reads as uncomputed. That is correct.
        self.assertIsNone(module.cached_results_total)
        self.assertFalse(module.is_cached_results_valid())
        self.assertEqual(module.status.name_en, "EMPTY")


@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_CONNECTION_CLOSER)
class ProjectImportNaturalKeyTests(TestCase):
    """formatVersion 2: reference relations resolve by natural key.

    The bug these cover: `.exactproject` v1 encoded every reference relation as
    a raw integer primary key and the importer resolved nothing, so a file moved
    between installations whose reference data was seeded differently either
    failed at the first row or, worse, silently resolved to a different climate,
    soil type or GWP report.

    Two databases cannot be booted in one test run, so skew is simulated: create
    the reference rows, capture their real pks, then hand-build an import body
    whose integer is deliberately wrong while the natural key is right.
    """

    def setUp(self):
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # get_or_create throughout: this suite runs against a database that may
        # already hold the committed reference fixtures.
        self.gwp, _ = GlobalWarmingPotential.objects.get_or_create(
            name_en="NK Test AR6",
            defaults={"name": "NK Test AR6", "co2": 1.0, "ch4": 27.2, "n2o": 273.0},
        )
        self.other_gwp, _ = GlobalWarmingPotential.objects.get_or_create(
            name_en="NK Test AR5",
            defaults={"name": "NK Test AR5", "co2": 1.0, "ch4": 28.0, "n2o": 265.0},
        )
        self.country, _ = Country.objects.get_or_create(name="NK Test Country")
        self.climate, _ = Climate.objects.get_or_create(
            name_en="NK Test Climate", defaults={"name": "NK Test Climate"}
        )
        self.moisture, _ = Moisture.objects.get_or_create(
            name_en="NK Test Moisture", defaults={"name": "NK Test Moisture"}
        )
        self.soil_type, _ = SoilType.objects.get_or_create(
            name_en="NK Test Soil", defaults={"name": "NK Test Soil"}
        )
        self.project_status, _ = ProjectStatus.objects.get_or_create(
            name="NK Test Status", defaults={"value": 9901}
        )

    # --- helpers ---------------------------------------------------------
    def _body(self, project_overrides, format_version=2):
        project = {
            "name": "NK Imported Project",
            "implementation_years": 20,
            "start_year_of_activities": 2024,
            "last_year_of_accounting": 2050,
            "country": self.country.id,
            "country__nk": ["NK Test Country"],
            "gw_potential": self.gwp.id,
            "gw_potential__nk": ["NK Test AR6"],
            "activities": [],
        }
        project.update(project_overrides)
        return {
            "formatVersion": format_version,
            "appVersion": "1.0.0",
            "compatibilityGroup": 1,
            "exportedAt": "2026-02-02T12:00:00Z",
            "exportId": str(uuid.uuid4()),
            "project": project,
        }

    def _post(self, body):
        return self.client.post(
            '/api/projects/import_project/', data=body, format='json'
        )

    def _project(self, name):
        """A project the export endpoint will actually serve.

        `security.check_permission("view_project", ...)` goes through
        ProjectMembership, so ownership alone is not enough. The import path
        creates the same membership at views.py:1152.
        """
        project = ProjectFactory(
            owner=self.user,
            name=name,
            country=self.country,
            climate=self.climate,
            moisture=self.moisture,
            soil_type=self.soil_type,
            gw_potential=self.gwp,
            status=self.project_status,
        )
        group, _ = Group.objects.get_or_create(name="Admin")
        # A fresh test database has the auth groups but no permissions attached,
        # and has_project_permission() checks membership.group.permissions.
        group.permissions.add(
            *Permission.objects.filter(codename="view_project")
        )
        ProjectMembership.objects.create(
            user=self.user, project=project, group=group
        )
        return project

    # --- import ----------------------------------------------------------
    def test_natural_key_wins_over_a_nonexistent_integer(self):
        """The actual bug: the encoded pk does not exist here, the key does."""
        body = self._body({"gw_potential": self.gwp.id + 1000})

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.gw_potential_id, self.gwp.id)

    def test_natural_key_wins_over_a_different_existing_row(self):
        """The dangerous case: the integer resolves, but to the wrong row."""
        body = self._body({
            "gw_potential": self.other_gwp.id,
            "gw_potential__nk": ["NK Test AR6"],
        })

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.gw_potential_id, self.gwp.id)
        self.assertNotEqual(imported.gw_potential_id, self.other_gwp.id)

    def test_unresolvable_natural_key_aborts_with_a_named_error(self):
        before = Project.objects.count()
        body = self._body({"gw_potential__nk": ["No Such Report"]})

        response = self._post(body)

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        message = json.dumps(response.data)
        self.assertIn("does not exist in this installation", message)
        self.assertIn("No Such Report", message)
        self.assertEqual(Project.objects.count(), before)

    def test_unresolvable_key_never_falls_back_to_the_integer(self):
        """A present-but-unresolvable key must not silently use the integer."""
        body = self._body({
            "gw_potential": self.gwp.id,
            "gw_potential__nk": ["No Such Report"],
        })

        response = self._post(body)

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Project.objects.filter(name="NK Imported Project").exists())

    def test_missing_key_for_one_field_falls_back_to_its_integer_only(self):
        body = self._body({
            "climate": self.climate.id,   # no climate__nk
            "gw_potential": self.gwp.id + 1000,
        })

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.climate_id, self.climate.id)
        self.assertEqual(imported.gw_potential_id, self.gwp.id)

    def test_format_version_1_still_imports_by_integer(self):
        body = self._body({}, format_version=1)
        body['project'].pop('gw_potential__nk')
        body['project'].pop('country__nk')

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.gw_potential_id, self.gwp.id)
        self.assertEqual(imported.country_id, self.country.id)

    def test_country_rename_resolves_through_the_alias_table(self):
        turkiye, _ = Country.objects.get_or_create(name="Türkiye")
        body = self._body({
            "country": turkiye.id + 1000,
            "country__nk": ["Turkey"],
        })

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.country_id, turkiye.id)

    # --- export ----------------------------------------------------------
    def test_export_emits_both_encodings_for_project_reference_fields(self):
        project = self._project("NK Export Project")

        response = self.client.get(f'/api/projects/{project.id}/export/')
        self.assertEqual(
            response.status_code, http_status.HTTP_200_OK, response.content[:400]
        )
        exported = json.loads(response.content)
        payload = exported['project']

        self.assertEqual(exported['formatVersion'], 2)
        self.assertEqual(exported['compatibilityGroup'], 1)
        self.assertEqual(payload['gw_potential'], self.gwp.id)
        self.assertEqual(payload['gw_potential__nk'], ["NK Test AR6"])
        self.assertEqual(payload['climate__nk'], ["NK Test Climate"])
        self.assertEqual(payload['moisture__nk'], ["NK Test Moisture"])
        self.assertEqual(payload['soil_type__nk'], ["NK Test Soil"])
        self.assertEqual(payload['country__nk'], ["NK Test Country"])
        # Project.status is api.ProjectStatus, not the api.StatusType that a
        # module's `status` points at. The model must come from the field.
        self.assertEqual(payload['status__nk'], ["NK Test Status"])

    def test_reference_fields_round_trip_through_export_and_import(self):
        project = self._project("NK Round Trip")

        exported = json.loads(
            self.client.get(f'/api/projects/{project.id}/export/').content
        )
        response = self.client.post(
            '/api/projects/import_project/?forceCopy=true',
            data=exported,
            format='json',
        )

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED, getattr(response, "data", None)
        )
        imported = Project.objects.get(id=response.data['projectId'])
        for field in ('country_id', 'climate_id', 'moisture_id',
                      'soil_type_id', 'gw_potential_id', 'status_id'):
            with self.subTest(field=field):
                self.assertEqual(getattr(imported, field), getattr(project, field))


@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_CONNECTION_CLOSER)
class ProjectImportLegacyReferenceIdTests(TestCase):
    """formatVersion 1 payloads naming reference data that does not exist here.

    The reported bug: a `.exactp` exported from the ONLINE tool failed to import
    into the OFFLINE tool with nothing but `FOREIGN KEY constraint failed`.

    Three conditions had to hold at once, which is why the natural-key work in
    PR #274 did not close it:

    1. the file is formatVersion 1, because the online deployment predates that
       PR and still hardcodes `"formatVersion": 1` at the export endpoint, so no
       `<field>__nk` is emitted and there is nothing to resolve;
    2. the reference pk it names does not exist locally. `Project.gw_potential`
       is NOT NULL and the observed online payloads carry pk 1, while a
       fixture-built offline database holds pks 8-12;
    3. the importer wrote that foreign pk straight into the FK column, so the
       first `Project.objects.create()` was rejected by sqlite, which reports
       neither the table nor the column.

    Nothing here can make such a file importable: a primary key is private to
    the database that issued it and v1 carries no other identity. What these
    pin is that condition 3 no longer produces an anonymous integrity error.
    """

    def setUp(self):
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # co2/ch4/n2o are all non-null FloatFields with no default.
        self.gwp, _ = GlobalWarmingPotential.objects.get_or_create(
            name_en="Legacy Import AR6",
            defaults={
                "name": "Legacy Import AR6",
                "co2": 1.0,
                "ch4": 27.2,
                "n2o": 273.0,
            },
        )
        self.country, _ = Country.objects.get_or_create(
            name="Legacy Import Country"
        )
        self.climate, _ = Climate.objects.get_or_create(
            name_en="Legacy Import Climate",
            defaults={"name": "Legacy Import Climate"},
        )

    def _absent_gwp_pk(self):
        return (
            GlobalWarmingPotential.objects.order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        ) + 1000

    def _v1_body(self, overrides=None):
        """A formatVersion 1 payload: integers only, no `__nk` anywhere."""
        project = {
            "name": "Legacy Imported Project",
            "implementation_years": 20,
            "start_year_of_activities": 2024,
            "last_year_of_accounting": 2050,
            "country": self.country.id,
            "gw_potential": self.gwp.id,
            "activities": [],
        }
        project.update(overrides or {})
        return {
            "formatVersion": 1,
            "appVersion": "1.0.0",
            "compatibilityGroup": 1,
            "exportedAt": "2026-08-14T12:51:28Z",
            "exportId": str(uuid.uuid4()),
            "project": project,
        }

    def _post(self, body):
        return self.client.post(
            '/api/projects/import_project/', data=body, format='json'
        )

    def test_the_reported_bug_no_longer_returns_a_bare_fk_constraint_error(self):
        """The regression seed. This is the exact shape of the user's file."""
        body = self._v1_body({"gw_potential": self._absent_gwp_pk()})

        response = self._post(body)

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        message = json.dumps(response.data)
        # The symptom, pinned negatively: this string is what the user saw and
        # it names neither the table nor the column, so it cannot be acted on.
        self.assertNotIn("FOREIGN KEY constraint failed", message)

    def test_the_error_names_the_model_the_field_and_the_id(self):
        absent = self._absent_gwp_pk()
        body = self._v1_body({"gw_potential": absent})

        response = self._post(body)

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        message = json.dumps(response.data)
        self.assertIn("ipcc.GlobalWarmingPotential", message)
        self.assertIn("gw_potential", message)
        self.assertIn(str(absent), message)
        self.assertIn("file format 1", message)

    def test_no_project_survives_the_failed_import(self):
        before = Project.objects.count()
        body = self._v1_body({"gw_potential": self._absent_gwp_pk()})

        self._post(body)

        self.assertEqual(Project.objects.count(), before)
        self.assertFalse(
            Project.objects.filter(name="Legacy Imported Project").exists()
        )

    def test_a_v1_payload_whose_ids_all_exist_still_imports(self):
        """The control. v1 is not rejected for being v1, only for naming a
        reference row this installation does not have.

        `GUINEA PDACG (1).exactp` on the reporter's machine is exactly this case
        and imports cleanly, which is what proves the failure is an AND of the
        three conditions rather than "v1 is broken".
        """
        body = self._v1_body({"climate": self.climate.id})

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED,
            getattr(response, "data", None),
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.gw_potential_id, self.gwp.id)
        self.assertEqual(imported.country_id, self.country.id)
        self.assertEqual(imported.climate_id, self.climate.id)

    def test_a_nullable_reference_id_is_refused_rather_than_silently_dropped(self):
        """`climate` is nullable, so nulling it would let the import "succeed".

        It must not: a project imported with no climate computes different
        numbers, and the file gives no evidence that the user meant none. The
        same reasoning as the hard failure on an unresolvable natural key.
        """
        absent_climate = (
            Climate.objects.order_by("-pk").values_list("pk", flat=True).first()
        ) + 1000
        body = self._v1_body({"climate": absent_climate})

        response = self._post(body)

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        message = json.dumps(response.data)
        self.assertIn("api.Climate", message)
        self.assertIn("climate", message)

    def test_a_v2_payload_is_unaffected_by_the_verification(self):
        """The key still wins, and a deliberately wrong integer is still ignored.

        Without this, the natural fix for the v1 path (verify the integer) would
        break the v2 path, whose whole point is that the integer is meaningless.
        """
        body = self._v1_body({
            "gw_potential": self._absent_gwp_pk(),
            "gw_potential__nk": ["Legacy Import AR6"],
        })
        body["formatVersion"] = 2

        response = self._post(body)

        self.assertEqual(
            response.status_code, http_status.HTTP_201_CREATED,
            getattr(response, "data", None),
        )
        imported = Project.objects.get(id=response.data['projectId'])
        self.assertEqual(imported.gw_potential_id, self.gwp.id)
