"""DB-free regression tests for the recap email window, advance rule and admin gate.

Follows the fake-object idiom established in test_finalized_member_management.py.
`api/tests/factories.py` executes reference-data queries at import time, so it
(and anything that pulls it in) must not be imported here.
"""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

import api.security as security
from api.utilities import ChangeLog, Change, ChangeReasons, send_changes_email
from api.views import ProjectNotificationPreferenceViewSet


class _FakeHistoryManager:
    """Stands in for `project.history`, recording the kwargs `.filter()` was handed."""

    def __init__(self):
        self.filter_kwargs = None

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return []


class _FakeActivities:
    """Stands in for `project.activities`; always empty so no `a.history` is touched."""

    def all(self):
        return []


class _FakeProject:
    """Stands in for `Project` so `send_changes_email` needs no database."""

    def __init__(self, last_recap_sent_at=None):
        self.id = 1
        self.name = "Test Project"
        self.last_recap_sent_at = last_recap_sent_at
        self.locked_at = None
        self.locked_by = None
        self.activities = _FakeActivities()
        self.history = _FakeHistoryManager()
        self.save_calls = []

    def save(self, update_fields=None):
        self.save_calls.append(update_fields)


def _recipient(email="admin@example.com"):
    return SimpleNamespace(user=SimpleNamespace(email=email))


def _non_empty_changelog():
    return [ChangeLog(datetime(2026, 1, 1, tzinfo=dt_timezone.utc), "someone@example.com", ChangeReasons.UPDATE.value, [Change("name", "old", "new")])]


class SendChangesEmailWindowTestCase(SimpleTestCase):
    """D-02 / D-04: the history filter kwargs prove which window was queried."""

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_first_send_has_no_lower_date_bound(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = _non_empty_changelog()
        mock_render.return_value = "<html></html>"

        project = _FakeProject(last_recap_sent_at=None)
        send_changes_email(project, recipients=[_recipient()])

        self.assertEqual(project.history.filter_kwargs, {})

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_subsequent_send_bounds_on_last_recap_timestamp(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = _non_empty_changelog()
        mock_render.return_value = "<html></html>"

        last_recap = datetime(2026, 6, 1, tzinfo=dt_timezone.utc)
        project = _FakeProject(last_recap_sent_at=last_recap)
        send_changes_email(project, recipients=[_recipient()])

        self.assertEqual(project.history.filter_kwargs, {"history_date__gte": last_recap})


class SendChangesEmailAdvanceRuleTestCase(SimpleTestCase):
    """D-05: the stored timestamp only moves after at least one successful send."""

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_successful_send_returns_count_and_advances_timestamp(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = _non_empty_changelog()
        mock_render.return_value = "<html></html>"
        mock_send_mail.return_value = None

        previous = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
        project = _FakeProject(last_recap_sent_at=previous)

        result = send_changes_email(project, recipients=[_recipient()])

        self.assertEqual(result, 1)
        self.assertEqual(project.save_calls, [["last_recap_sent_at"]])
        self.assertGreater(project.last_recap_sent_at, previous)

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_empty_diff_sends_nothing_and_leaves_timestamp_untouched(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = []

        previous = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
        project = _FakeProject(last_recap_sent_at=previous)

        result = send_changes_email(project, recipients=[_recipient()])

        self.assertEqual(result, 0)
        mock_send_mail.assert_not_called()
        self.assertEqual(project.save_calls, [])
        self.assertEqual(project.last_recap_sent_at, previous)

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_failed_send_returns_zero_and_leaves_timestamp_untouched(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = _non_empty_changelog()
        mock_render.return_value = "<html></html>"
        mock_send_mail.side_effect = Exception("SMTP is down")

        previous = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
        project = _FakeProject(last_recap_sent_at=previous)

        result = send_changes_email(project, recipients=[_recipient()])

        self.assertEqual(result, 0)
        self.assertEqual(project.save_calls, [])
        self.assertEqual(project.last_recap_sent_at, previous)


class _FakeMembers:
    """Stands in for `project.members` so `check_project_admin` needs no database."""

    def __init__(self, admins):
        self.admins = list(admins)

    def filter(self, user=None, group__name=None):
        matched = group__name == "Admin" and any(admin is user for admin in self.admins)
        return SimpleNamespace(exists=lambda: matched)


def _user(is_superuser=False):
    return SimpleNamespace(is_superuser=is_superuser)


def _project_for_permission_check(admins=()):
    return SimpleNamespace(members=_FakeMembers(admins))


class CheckProjectAdminTestCase(SimpleTestCase):
    """D-06: admin members and superusers pass; everyone else gets 403."""

    def test_admin_group_member_is_allowed(self):
        admin = _user()
        result = security.check_project_admin(admin, _project_for_permission_check(admins=[admin]))
        self.assertIsNone(result)

    def test_superuser_is_allowed(self):
        result = security.check_project_admin(_user(is_superuser=True), _project_for_permission_check())
        self.assertIsNone(result)

    def test_non_admin_member_is_rejected(self):
        result = security.check_project_admin(_user(), _project_for_permission_check())
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 403)


class _FakeProjectMembersRecorder:
    """Stands in for `project.members` inside send_changes_email; records the exact
    kwargs `.filter()` was called with. Distinct from `_FakeMembers` above, which
    backs the `check_project_admin` tests and has a different, narrower signature."""

    def __init__(self):
        self.filter_calls = []

    def filter(self, **kwargs):
        self.filter_calls.append(kwargs)
        return []


class SendChangesEmailRecipientDerivationTestCase(SimpleTestCase):
    """D-01: recipient derivation is one queryset covering cases (a) no row, (b)
    subscribed, (c) subscribed but globally opted out — all three regress together
    if any condition is dropped from the single filter() call."""

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_recipient_queryset_shape(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = _non_empty_changelog()
        mock_render.return_value = "<html></html>"

        project = _FakeProject()
        project.members = _FakeProjectMembersRecorder()

        send_changes_email(project)

        self.assertEqual(
            project.members.filter_calls,
            [
                {
                    "group__name": "Admin",
                    "user__is_opted_out_of_emails": False,
                    "user__project_notification_preferences__project": project,
                    "user__project_notification_preferences__is_subscribed": True,
                }
            ],
        )

    @patch("api.utilities.send_mail")
    @patch("api.utilities.render_to_string")
    @patch("api.utilities.get_changes")
    def test_explicit_recipients_bypasses_derivation(self, mock_get_changes, mock_render, mock_send_mail):
        mock_get_changes.return_value = _non_empty_changelog()
        mock_render.return_value = "<html></html>"

        project = _FakeProject()
        project.members = _FakeProjectMembersRecorder()

        send_changes_email(project, recipients=[_recipient()])

        self.assertEqual(project.members.filter_calls, [])


class _RecordingPreferenceManager:
    """Stands in for `ProjectNotificationPreference.objects` inside
    `ProjectNotificationPreferenceViewSet.create`; records `get_or_create` kwargs."""

    def __init__(self, return_value):
        self.get_or_create_calls = []
        self._return_value = return_value

    def get_or_create(self, **kwargs):
        self.get_or_create_calls.append(kwargs)
        return self._return_value


def _fake_write_serializer(project, is_subscribed=True):
    return SimpleNamespace(is_valid=lambda: True, validated_data={"project": project, "is_subscribed": is_subscribed})


class ProjectNotificationPreferenceCreateGateTestCase(SimpleTestCase):
    """D-02: create() gates on project admin before any write (case d), and an admin
    reaches get_or_create with the renamed field (pins the Task 1 rename)."""

    @patch("api.views.ProjectNotificationPreferenceReadSerializer")
    @patch("api.views.ProjectNotificationPreference")
    @patch("api.views.ProjectNotificationPreferenceWriteSerializer")
    def test_non_admin_create_is_rejected_and_writes_nothing(self, mock_write_serializer_class, mock_model, mock_read_serializer_class):
        user = _user()
        project = _project_for_permission_check(admins=[])  # empty admin list -> non-admin
        mock_write_serializer_class.return_value = _fake_write_serializer(project)
        mock_model.objects = _RecordingPreferenceManager(return_value=(SimpleNamespace(), True))

        request = SimpleNamespace(user=user, data={"project": 1, "is_subscribed": True})
        response = ProjectNotificationPreferenceViewSet().create(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(mock_model.objects.get_or_create_calls, [])

    @patch("api.views.ProjectNotificationPreferenceReadSerializer")
    @patch("api.views.ProjectNotificationPreference")
    @patch("api.views.ProjectNotificationPreferenceWriteSerializer")
    def test_admin_create_reaches_get_or_create_with_new_field_name(self, mock_write_serializer_class, mock_model, mock_read_serializer_class):
        user = _user()
        project = _project_for_permission_check(admins=[user])
        mock_write_serializer_class.return_value = _fake_write_serializer(project, is_subscribed=True)
        mock_model.objects = _RecordingPreferenceManager(return_value=(SimpleNamespace(is_subscribed=True), True))

        request = SimpleNamespace(user=user, data={"project": 1, "is_subscribed": True})
        response = ProjectNotificationPreferenceViewSet().create(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mock_model.objects.get_or_create_calls), 1)
        call_kwargs = mock_model.objects.get_or_create_calls[0]
        self.assertEqual(call_kwargs["defaults"], {"is_subscribed": True})
