"""
Unit tests for the sync_firebase_emails management command.

Tests:
1. Command execution with mismatched emails
2. Email sending functionality
3. Email content formatting
4. Verification link generation and validation
"""

from django.test import TestCase
from django.core.management import call_command
from unittest.mock import patch, Mock
from io import StringIO

from api.models import CustomUser


class SyncFirebaseEmailsTestCase(TestCase):
    def setUp(self):
        self.user1 = CustomUser.objects.create_user(email="test1@example.com", password="testpass123", first_name="Test", last_name="User1", firebase_uid="firebase_uid_1")
        self.user2 = CustomUser.objects.create_user(email="test2@example.com", password="testpass123", first_name="John", last_name="Doe", firebase_uid="firebase_uid_2")
        self.user3 = CustomUser.objects.create_user(email="test3@example.com", password="testpass123", firebase_uid="firebase_uid_3")
        self.user_no_firebase = CustomUser.objects.create_user(email="nofirebase@example.com", password="testpass123")

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_sync_firebase_emails_updates_mismatched_emails(self, mock_send_mail, mock_firebase_utils, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        mock_firebase_user1 = Mock()
        mock_firebase_user1.email = "different1@example.com"
        mock_firebase_user1.uid = "firebase_uid_1"

        mock_firebase_user2 = Mock()
        mock_firebase_user2.email = "test2@example.com"
        mock_firebase_user2.uid = "firebase_uid_2"

        mock_firebase_user3 = Mock()
        mock_firebase_user3.email = "test3@example.com"
        mock_firebase_user3.uid = "firebase_uid_3"

        def get_user_side_effect(uid):
            uid_map = {
                "firebase_uid_1": mock_firebase_user1,
                "firebase_uid_2": mock_firebase_user2,
                "firebase_uid_3": mock_firebase_user3,
            }
            if uid in uid_map:
                return uid_map[uid]
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect

        mock_firebase_utils.generate_email_verification_link.return_value = "https://example.com/verify?token=abc123"

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        output = out.getvalue()
        self.assertIn("Updated user", output)
        self.assertIn("test1@example.com", output)

        calls_for_test1 = [call for call in mock_firebase_cmd.update_user.call_args_list if len(call[0]) > 0 and call[0][0] == "firebase_uid_1"]
        self.assertEqual(len(calls_for_test1), 1)
        self.assertEqual(calls_for_test1[0][0][0], "firebase_uid_1")
        self.assertEqual(calls_for_test1[0][1]["email"], "test1@example.com")
        self.assertFalse(calls_for_test1[0][1]["email_verified"])

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_sync_firebase_emails_sends_email(self, mock_send_mail, mock_firebase_utils, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect
        mock_firebase_utils.generate_email_verification_link.return_value = "https://example.com/verify?token=abc123"

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[0][0], "Verify your email address")
        self.assertEqual(call_args[0][3], ["test1@example.com"])

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_email_content_format(self, mock_send_mail, mock_firebase_utils, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect
        mock_firebase_utils.generate_email_verification_link.return_value = "https://example.com/verify?token=abc123"

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        email_calls = [call for call in mock_send_mail.call_args_list if call[0][3] == ["test1@example.com"]]
        self.assertTrue(len(email_calls) > 0)
        email_call = email_calls[0]
        email_message = email_call[0][1]
        email_subject = email_call[0][0]

        self.assertEqual(email_subject, "Verify your email address")
        self.assertIn("Hi Test User1,", email_message)
        self.assertIn("We have recently updated your email address", email_message)
        self.assertIn("apologize for any inconvenience", email_message.lower())
        self.assertIn("login issues", email_message.lower())
        self.assertIn("https://example.com/verify?token=abc123", email_message)
        self.assertIn("The EX-ACT Team", email_message)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_email_content_without_name(self, mock_send_mail, mock_firebase_utils, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_3":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_3"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect
        mock_firebase_utils.generate_email_verification_link.return_value = "https://example.com/verify?token=xyz789"

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        email_calls = [call for call in mock_send_mail.call_args_list if call[0][3] == ["test3@example.com"]]
        self.assertTrue(len(email_calls) > 0)
        email_message = email_calls[0][0][1]
        self.assertIn("Hi test3@example.com,", email_message)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    def test_verification_link_generation(self, mock_firebase_utils, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect
        expected_link = "https://example.com/verify?token=test_token_123"
        mock_firebase_utils.generate_email_verification_link.return_value = expected_link

        with patch("accounts.utils.send_mail") as mock_send_mail:
            out = StringIO()
            call_command("sync_firebase_emails", stdout=out)

            email_calls = [call for call in mock_send_mail.call_args_list if call[0][3] == ["test1@example.com"]]
            self.assertTrue(len(email_calls) > 0)
            email_call = email_calls[0]
            email_message = email_call[0][1]
            self.assertIn(expected_link, email_message)
            self.assertTrue(expected_link.startswith("http"))
            self.assertIn("test1@example.com", [call[0][0] for call in mock_firebase_utils.generate_email_verification_link.call_args_list])

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    def test_skips_users_with_matching_emails(self, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_2":
                mock_user = Mock()
                mock_user.email = "test2@example.com"
                mock_user.uid = "firebase_uid_2"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out, dry_run=True)

        calls_for_test2 = [call for call in mock_firebase_cmd.update_user.call_args_list if len(call[0]) > 0 and call[0][0] == "firebase_uid_2"]
        self.assertEqual(len(calls_for_test2), 0)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    def test_skips_users_without_firebase_uid(self, mock_firebase_cmd):
        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        output = out.getvalue()
        user_count = CustomUser.objects.filter(firebase_uid__isnull=False).exclude(firebase_uid="").count()
        self.assertIn(f"Processing {user_count} users", output)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_skip_email_flag(self, mock_send_mail, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect

        out = StringIO()
        call_command("sync_firebase_emails", "--skip-email", stdout=out)

        email_calls_for_test1 = [call for call in mock_send_mail.call_args_list if len(call[0]) > 3 and call[0][3] == ["test1@example.com"]]
        self.assertEqual(len(email_calls_for_test1), 0)
        calls_for_test1 = [call for call in mock_firebase_cmd.update_user.call_args_list if len(call[0]) > 0 and call[0][0] == "firebase_uid_1"]
        self.assertEqual(len(calls_for_test1), 1)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    def test_dry_run_mode(self, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect

        out = StringIO()
        call_command("sync_firebase_emails", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("[DRY RUN]", output)
        self.assertIn("Would update user", output)
        calls_for_test1 = [call for call in mock_firebase_cmd.update_user.call_args_list if len(call[0]) > 0 and call[0][0] == "firebase_uid_1"]
        self.assertEqual(len(calls_for_test1), 0)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    def test_handles_firebase_user_not_found(self, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                raise NotFoundError("User not found")
            raise Exception(f"Unexpected UID: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        output = out.getvalue()
        self.assertIn("Firebase user not found", output)
        calls_for_test1 = [call for call in mock_firebase_cmd.update_user.call_args_list if len(call[0]) > 0 and call[0][0] == "firebase_uid_1"]
        self.assertEqual(len(calls_for_test1), 0)

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_verification_link_in_email_content(self, mock_send_mail, mock_firebase_utils, mock_firebase_cmd):
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect
        test_link = "https://auth.firebaseapp.com/verify?token=test_token_456&email=test1%40example.com"
        mock_firebase_utils.generate_email_verification_link.return_value = test_link

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        email_calls = [call for call in mock_send_mail.call_args_list if call[0][3] == ["test1@example.com"]]
        self.assertTrue(len(email_calls) > 0)
        email_message = email_calls[0][0][1]
        self.assertIn(test_link, email_message)
        self.assertIn("verify your email address by clicking on the link below", email_message.lower())

    @patch("api.management.commands.sync_firebase_emails.firebase_admin_auth")
    @patch("accounts.utils.firebase_admin_auth")
    @patch("accounts.utils.send_mail")
    def test_verification_link_is_valid_url(self, mock_send_mail, mock_firebase_utils, mock_firebase_cmd):
        from urllib.parse import urlparse
        from firebase_admin.exceptions import NotFoundError

        def get_user_side_effect(uid):
            if uid == "firebase_uid_1":
                mock_user = Mock()
                mock_user.email = "different@example.com"
                mock_user.uid = "firebase_uid_1"
                return mock_user
            raise NotFoundError(f"User not found: {uid}")

        mock_firebase_cmd.get_user.side_effect = get_user_side_effect
        test_link = "https://example.com/verify?token=test_token&email=test1%40example.com"
        mock_firebase_utils.generate_email_verification_link.return_value = test_link

        out = StringIO()
        call_command("sync_firebase_emails", stdout=out)

        email_calls = [call for call in mock_send_mail.call_args_list if call[0][3] == ["test1@example.com"]]
        self.assertTrue(len(email_calls) > 0)
        email_message = email_calls[0][0][1]
        self.assertIn(test_link, email_message)

        parsed_url = urlparse(test_link)
        self.assertTrue(parsed_url.scheme in ["http", "https"])
        self.assertTrue(parsed_url.netloc)
        self.assertTrue("token" in parsed_url.query or "email" in parsed_url.query)
