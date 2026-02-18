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
