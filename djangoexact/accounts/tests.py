from django.test import TestCase
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserSummarySerializer

User = get_user_model()


class RegisterSerializerTestCase(TestCase):
    def test_register_serializer_includes_is_opted_out_of_emails(self):
        """Verify RegisterSerializer includes is_opted_out_of_emails in fields."""
        serializer = RegisterSerializer()
        self.assertIn("is_opted_out_of_emails", serializer.fields.keys())

    def test_register_serializer_create_with_is_opted_out_of_emails(self):
        """Verify RegisterSerializer.create handles is_opted_out_of_emails."""
        data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "is_opted_out_of_emails": True,
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertTrue(user.is_opted_out_of_emails)

    def test_register_serializer_create_default_is_opted_out_of_emails(self):
        """Verify RegisterSerializer.create defaults is_opted_out_of_emails to False."""
        data = {
            "email": "test2@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertFalse(user.is_opted_out_of_emails)


class UserSummarySerializerTestCase(TestCase):
    def test_user_summary_serializer_includes_is_opted_out_of_emails(self):
        """Verify UserSummarySerializer includes is_opted_out_of_emails in fields."""
        serializer = UserSummarySerializer()
        self.assertIn("is_opted_out_of_emails", serializer.fields.keys())