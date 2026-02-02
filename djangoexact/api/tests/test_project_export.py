"""Tests for project export/import functionality."""
import json
import uuid
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status as http_status

from .factories import UserFactory, ProjectFactory
from ..models import Project


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
        # First export
        response1 = self.client.get(f'/api/projects/{self.project.id}/export/')
        data1 = json.loads(response1.content)

        # Second export
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
