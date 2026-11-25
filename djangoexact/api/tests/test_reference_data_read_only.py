"""Reference data is maintained in the Django admin; the API only reads it.

The structural checks walk the routers so that a newly registered reference route
(for example another ``public_generic_viewset(...)``) is covered without editing this file.
"""

from rest_framework import permissions, status
from rest_framework.test import APITestCase

from api.models import Country, CustomUser, InputType
from api.urls import router as api_router
from ipcc.models import GlobalWarmingPotential
from ipcc.urls import router as ipcc_router
from ipcc.utilities import get_url_name

WRITE_ACTIONS = ("create", "update", "partial_update", "destroy")


def write_actions(viewset):
    return [name for name in WRITE_ACTIONS if hasattr(viewset, name)]


class ReferenceViewSetsAreReadOnlyTestCase(APITestCase):
    def test_public_api_viewsets_expose_no_writes(self):
        for prefix, viewset, _ in api_router.registry:
            if permissions.AllowAny not in getattr(viewset, "permission_classes", []):
                continue
            with self.subTest(route=prefix):
                self.assertEqual(write_actions(viewset), [])

    def test_ipcc_viewsets_expose_no_writes(self):
        for prefix, viewset, _ in ipcc_router.registry:
            with self.subTest(route=prefix):
                self.assertEqual(write_actions(viewset), [])


class ReferenceDataWritesTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(name="Read-only test country", iso3="ROT")
        cls.gwp = GlobalWarmingPotential.objects.create(name="Read-only test GWP", co2=1, ch4=28, n2o=265)
        cls.input_type = InputType.objects.create(name="Read-only test input", unit="t N/yr")
        cls.ipcc_gwp_url = f"/api/ipcc/{get_url_name(GlobalWarmingPotential.__name__)}/"

    def attempt_writes(self, list_url, pk, payload):
        detail_url = f"{list_url}{pk}/"
        return [
            self.client.post(list_url, payload).status_code,
            self.client.put(detail_url, payload).status_code,
            self.client.patch(detail_url, payload).status_code,
            self.client.delete(detail_url).status_code,
        ]

    def test_anonymous_writes_to_public_reference_routes_are_rejected(self):
        cases = [
            ("/api/countries/", self.country, {"name": "Renamed"}),
            ("/api/global-warming-potentials/", self.gwp, {"name": "Renamed", "co2": 1, "ch4": 1, "n2o": 1}),
            ("/api/input-types/", self.input_type, {"name": "Renamed", "unit": "t/yr"}),
        ]
        for url, row, payload in cases:
            with self.subTest(route=url):
                self.assertEqual(self.attempt_writes(url, row.pk, payload), [status.HTTP_405_METHOD_NOT_ALLOWED] * 4)

        self.country.refresh_from_db()
        self.gwp.refresh_from_db()
        self.input_type.refresh_from_db()
        self.assertEqual(
            (self.country.name, self.gwp.ch4, self.input_type.unit),
            ("Read-only test country", 28, "t N/yr"),
        )
        self.assertFalse(Country.objects.filter(name="Renamed").exists())

    def test_public_reference_routes_stay_readable_without_login(self):
        for url in ("/api/countries/", f"/api/countries/{self.country.pk}/", "/api/input-types/", f"/api/input-types/{self.input_type.pk}/"):
            with self.subTest(route=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_comment_writes_need_a_login_and_definitions_are_read_only(self):
        anonymous_writes = [
            self.client.post("/api/threads/", {}).status_code,
            self.client.patch("/api/threads/1/", {}).status_code,
            self.client.post("/api/comments/", {}).status_code,
            self.client.delete("/api/comments/1/").status_code,
        ]
        self.assertEqual(anonymous_writes, [status.HTTP_401_UNAUTHORIZED] * 4)
        self.assertEqual(self.client.post("/api/definitions/", {}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_ipcc_routes_stay_readable_and_reject_writes(self):
        # ipcc's AuthenticatedViewSet mixin sits after APIView in the MRO, so these routes have
        # always been public. Reads stay public here because the web client reads them.
        payload = {"name": "Renamed", "co2": 1, "ch4": 1, "n2o": 1}

        self.assertEqual(self.client.get(self.ipcc_gwp_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.attempt_writes(self.ipcc_gwp_url, self.gwp.pk, payload), [status.HTTP_405_METHOD_NOT_ALLOWED] * 4)

        self.client.force_authenticate(CustomUser.objects.create(email="reference-reader@example.com"))
        self.assertEqual(self.attempt_writes(self.ipcc_gwp_url, self.gwp.pk, payload), [status.HTTP_405_METHOD_NOT_ALLOWED] * 4)

        self.gwp.refresh_from_db()
        self.assertEqual(self.gwp.ch4, 28)
