from rest_framework import status
from rest_framework.test import APITestCase

from api.models import CustomUser, InputType


class InputTypeAccessTestCase(APITestCase):
    """Public Inputs pages read input types without a login; changing them still needs one."""

    @classmethod
    def setUpTestData(cls):
        cls.input_type = InputType.objects.create(name="Access test input", unit="t N/yr")
        cls.detail_url = f"/api/input-types/{cls.input_type.pk}/"

    def test_anonymous_can_list_input_types_with_units(self):
        response = self.client.get("/api/input-types/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("t N/yr", [row["unit"] for row in response.data])

    def test_anonymous_can_retrieve_an_input_type(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unit"], "t N/yr")

    def test_anonymous_cannot_write(self):
        payload = {"name": "Anonymous write", "unit": "t/yr"}
        attempts = [
            self.client.post("/api/input-types/", payload),
            self.client.put(self.detail_url, payload),
            self.client.patch(self.detail_url, payload),
            self.client.delete(self.detail_url),
        ]

        self.assertEqual([r.status_code for r in attempts], [status.HTTP_403_FORBIDDEN] * 4)
        self.input_type.refresh_from_db()
        self.assertEqual(self.input_type.name, "Access test input")
        self.assertFalse(InputType.objects.filter(name="Anonymous write").exists())

    def test_logged_in_user_can_still_write(self):
        self.client.force_authenticate(CustomUser.objects.create(email="input-type-editor@example.com"))

        response = self.client.patch(self.detail_url, {"unit": "t/yr"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.input_type.refresh_from_db()
        self.assertEqual(self.input_type.unit, "t/yr")
