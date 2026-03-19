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
