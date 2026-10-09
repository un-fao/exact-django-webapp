"""DB-free regression tests: state that must not follow a project into its copy.

Project.export_id is unique and set by the export endpoint on first download.
create_project_shell used to deep-copy it onto the new row, so the insert
violated api_project_export_id_key and every copy of an exported project
returned 500 (production, 2026-10-07).

Run with:
    python manage.py test api.tests.test_copy_exported_project
"""
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.utils import timezone

from api import utilities
from api.models import Project


class CopyExportedProjectTestCase(SimpleTestCase):
    def test_copy_does_not_reuse_the_source_export_id(self):
        source_export_id = uuid.uuid4()
        source = Project(pk=1, name="Exported", export_id=source_export_id)
        saved = {}

        def record_insert(self, *args, **kwargs):
            saved["export_id"] = self.export_id

        # __wrapped__ skips transaction.atomic, which would open a DB connection.
        with mock.patch.object(Project, "save", record_insert), \
                mock.patch.object(utilities, "get_unique_name", return_value="Exported (1)"), \
                mock.patch.object(utilities, "_ensure_admin_membership"):
            shell = utilities.create_project_shell.__wrapped__(source, get_user_model()(pk=7))

        self.assertIsNone(saved["export_id"])
        self.assertIsNone(shell.pk)
        self.assertEqual(source.export_id, source_export_id)

    def test_copy_starts_unlocked_active_and_without_recap_history(self):
        """The copier only needs view access, so the source may be locked by someone else."""
        now = timezone.now()
        locker = get_user_model()(pk=3)
        source = Project(
            pk=1, name="Busy", is_locked=True, locked_at=now, lock_updated_at=now, locked_by=locker,
            is_archived=True, archived_at=now, last_recap_sent_at=now,
        )
        reset_fields = ["is_locked", "locked_at", "lock_updated_at", "locked_by_id", "is_archived", "archived_at", "last_recap_sent_at"]
        saved = {}

        def record_insert(self, *args, **kwargs):
            saved.update({field: getattr(self, field) for field in reset_fields})

        with mock.patch.object(Project, "save", record_insert), \
                mock.patch.object(utilities, "get_unique_name", return_value="Busy (1)"), \
                mock.patch.object(utilities, "_ensure_admin_membership"):
            utilities.create_project_shell.__wrapped__(source, get_user_model()(pk=7))

        self.assertEqual(saved, {
            "is_locked": False, "locked_at": None, "lock_updated_at": None, "locked_by_id": None,
            "is_archived": False, "archived_at": None, "last_recap_sent_at": None,
        })
        self.assertTrue(source.is_locked)
        self.assertEqual(source.locked_by_id, locker.pk)
        self.assertTrue(source.is_archived)
        self.assertEqual(source.last_recap_sent_at, now)
