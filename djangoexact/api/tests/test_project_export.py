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
