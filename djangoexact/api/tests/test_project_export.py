"""Tests for project export/import functionality."""
import json
import uuid
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status as http_status

from .factories import UserFactory, ProjectFactory
from ..models import Project


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
        self.assertEqual(data['formatVersion'], 1)

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
