from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import ProjectViewSet, ActivityViewSet, generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice
import logging as log
from api.tests.unit.utils import APITestCaseMixin
import api.calculators as calculators
from api import serializers


class ValueChainTestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()

    def create_value_chain(self):
        """
        Create a value chain using the ValueChainViewSet.

        This method creates a project and an activity with a ValueChain module
        type. It then creates a ValueChain instance associated with the
        activity and returns the response.

        Returns:
            Response: The response from the ValueChainViewSet.
        """

        project_response = self.create_project()
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)

        project = models.Project.objects.get(id=project_response.data["id"])

        activity = self.create_activity(project, self.user, module_types=[models.ModuleType.objects.get(class_name="ValueChain").pk])
        self.assertEqual(activity.status_code, status.HTTP_200_OK)

        value_chain = models.ValueChain.objects.get(activity=activity.data["id"])
        return value_chain

    def test_create_value_chain(self):
        """
        Test the creation of a value chain using the ValueChainViewSet.

        This test uses the APIRequestFactory to create a POST request to the
        'valuechain-list' endpoint with the provided value chain data in JSON format.
        The request is authenticated with a test user, and the response is
        checked to ensure that the value chain is created successfully with a
        status code of 201 (Created).
        """

        value_chain = self.create_value_chain()
        assert value_chain.id is not None

    def test_create_value_chain_with_processing(self):

        parent = self.create_value_chain()
        data = {
            "name": "Processing",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Processing, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_value_chain_with_storage(self):

        parent = self.create_value_chain()
        data = {
            "name": "Storage",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Storage, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_value_chain_with_transport(self):

        parent = self.create_value_chain()
        data = {
            "name": "Transport",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Transport, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_value_chain_with_packaging(self):

        parent = self.create_value_chain()
        data = {
            "name": "Packaging",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Packaging, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_value_chain_with_processing_and_calculate_results(self):

        parent = self.create_value_chain()
        data = {
            "name": "Processing",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Processing, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        processing = models.Processing.objects.get(id=response.data["id"])

        fuel_types = models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").all()

        processing_data = {
            "fuel_type_start": FuzzyChoice(fuel_types).fuzz().id,
            "fuel_type_w": FuzzyChoice(fuel_types).fuzz().id,
            "fuel_type_wo": FuzzyChoice(fuel_types).fuzz().id,
            "kwh_energy_per_year_start": FuzzyInteger(1, 100).fuzz(),
            "kwh_energy_per_year_w": FuzzyInteger(1, 100).fuzz(),
            "kwh_energy_per_year_wo": FuzzyInteger(1, 100).fuzz(),
        }

        response = self.edit_module(processing, self.user, processing_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results_view = generic_module_viewset(models.ValueChain).as_view({"get": "results"})

        results_request = self.request_factory.get(
            reverse("valuechain-detail", args=[parent.pk]),
            format="json",
        )

        force_authenticate(results_request, user=self.user)

        results_response = results_view(results_request, pk=parent.pk)
        print(results_response.data)
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)

    def test_create_value_chains_with_storage_and_calculate_results(self):

        parent = self.create_value_chain()
        data = {
            "name": "Storage",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Storage, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        storage = models.Storage.objects.get(id=response.data["id"])

        refrigerant_types = models.RefrigerantType.objects.all()

        storage_data = {
            "kwh_energy_per_year_start": FuzzyInteger(1, 100).fuzz(),
            "kwh_energy_per_year_w": FuzzyInteger(1, 100).fuzz(),
            "kwh_energy_per_year_wo": FuzzyInteger(1, 100).fuzz(),
            "is_refrigerant_used": FuzzyChoice([False, False]).fuzz(),
            "refrigerant_type_start": FuzzyChoice(refrigerant_types).fuzz().id,
            "refrigerant_type_w": FuzzyChoice(refrigerant_types).fuzz().id,
            "refrigerant_type_wo": FuzzyChoice(refrigerant_types).fuzz().id,
        }

        response = self.edit_module(storage, self.user, storage_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results_view = generic_module_viewset(models.ValueChain).as_view({"get": "results"})

        results_request = self.request_factory.get(
            reverse("valuechain-detail", args=[parent.pk]),
            format="json",
        )

        force_authenticate(results_request, user=self.user)

        results_response = results_view(results_request, pk=parent.pk)
        print(results_response.data)
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)

    def test_create_value_chains_with_transport_and_calculate_results(self):

        parent = self.create_value_chain()
        data = {
            "name": "Transport",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Transport, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        transport = models.Transport.objects.get(id=response.data["id"])

        fuel_types = models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").all()

        transport_data = {
            "fuel_type_start": FuzzyChoice(fuel_types).fuzz().id,
            "fuel_type_w": FuzzyChoice(fuel_types).fuzz().id,
            "fuel_type_wo": FuzzyChoice(fuel_types).fuzz().id,
            "fuel_used_per_year_start": FuzzyInteger(1, 100).fuzz(),
            "fuel_used_per_year_w": FuzzyInteger(1, 100).fuzz(),
            "fuel_used_per_year_wo": FuzzyInteger(1, 100).fuzz(),
        }

        response = self.edit_module(transport, self.user, transport_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results_view = generic_module_viewset(models.ValueChain).as_view({"get": "results"})

        results_request = self.request_factory.get(
            reverse("valuechain-detail", args=[parent.pk]),
            format="json",
        )

        force_authenticate(results_request, user=self.user)

        results_response = results_view(results_request, pk=parent.pk)
        print(results_response.data)
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)

    def test_create_value_chains_with_packaging_and_calculate_results(self):

        parent = self.create_value_chain()
        data = {
            "name": "Packaging",
            "parent": parent.id,
        }

        response = self.create_submodule(models.Packaging, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        packaging = models.Packaging.objects.get(id=response.data["id"])

        packaging_material_types = models.PackagingMaterialType.objects.all()

        packaging_data = {
            "packaging_material_type_start": FuzzyChoice(packaging_material_types).fuzz().id,
            "packaging_material_type_w": FuzzyChoice(packaging_material_types).fuzz().id,
            "packaging_material_type_wo": FuzzyChoice(packaging_material_types).fuzz().id,
            "kg_of_packaging_material_start": FuzzyInteger(1, 100).fuzz(),
            "kg_of_packaging_material_w": FuzzyInteger(1, 100).fuzz(),
            "kg_of_packaging_material_wo": FuzzyInteger(1, 100).fuzz(),
        }

        response = self.edit_module(packaging, self.user, packaging_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results_view = generic_module_viewset(models.ValueChain).as_view({"get": "results"})

        results_request = self.request_factory.get(
            reverse("valuechain-detail", args=[parent.pk]),
            format="json",
        )

        force_authenticate(results_request, user=self.user)

        results_response = results_view(results_request, pk=parent.pk)
        print(results_response.data)
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
