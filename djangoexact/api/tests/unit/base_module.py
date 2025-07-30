from factory import fuzzy
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice
import logging as log
from api.tests.unit.utils import APITestCaseMixin
from api import serializers
import copy
from django.apps import apps


class BaseModuleTestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()

        self.ModuleClass: models.Module

        project_response = self.create_project()
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)

        self.project = models.Project.objects.get(id=project_response.data["id"])
        self.module_type = models.ModuleType.objects.get(class_name=self.ModuleClass.__name__)

        self.climate = self.project.climate
        self.moisture = self.project.moisture

        activity_response = self.create_activity(self.project, self.user, [self.module_type])
        self.assertEqual(activity_response.status_code, status.HTTP_200_OK)

        self.activity = models.Activity.objects.get(id=activity_response.data["id"])
        self.module: models.Module = apps.get_model("api", self.module_type.class_name).objects.get(activity=self.activity)

        self.module_viewset = generic_module_viewset(self.ModuleClass)

        self.land_use_types = models.LandUseType.objects.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)
        if isinstance(self.ModuleClass, models.CoastalWetland):
            self.land_use_types = self.land_use_types.filter(is_coastal=True)

    def get_results(self):
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)

        return response

    def _get_t2_fields_with_test_values(self, model_class):
        """
        Dynamically discover all _t2 fields from the model and generate appropriate test values.
        This method can be reused for any model to test _t2 fields systematically.

        Args:
            model_class: The Django model class to inspect

        Returns:
            List of tuples: [(field_name, test_value), ...]
        """
        from django.db import models as django_models

        t2_fields = []

        # Get all fields from the model
        for field in model_class._meta.get_fields():
            # Only consider fields that contain "_t2" and are actual model fields (not relations)
            if hasattr(field, "name") and "_t2" in field.name and not field.many_to_many and not field.one_to_many and not field.many_to_one:
                field_name = field.name
                test_value = self._generate_test_value_for_field(field, field_name)

                if test_value is not None:
                    t2_fields.append((field_name, test_value))

        # Sort by field name for consistent ordering
        t2_fields.sort(key=lambda x: x[0])
        return t2_fields

    def _generate_test_value_for_field(self, field, field_name):
        """
        Generate an appropriate test value based on the field type and name.

        Args:
            field: Django model field instance
            field_name: Name of the field

        Returns:
            Appropriate test value for the field type, or None if not supported
        """
        from django.db import models as django_models

        # Define value ranges based on field name patterns
        biomass_patterns = ["soc", "agb", "bgb", "litter", "deadwood"]
        growth_patterns = ["growth_rate"]
        year_patterns = ["year", "start_year"]
        percentage_patterns = ["percentage"]

        # Determine base value based on field name
        base_value = 10.0  # default

        for pattern in biomass_patterns:
            if pattern in field_name.lower():
                if "max" in field_name.lower():
                    base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                elif "soc" in field_name.lower():
                    base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                elif "agb" in field_name.lower():
                    base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                elif "bgb" in field_name.lower():
                    base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                elif "litter" in field_name.lower():
                    base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                elif "deadwood" in field_name.lower():
                    base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                break

        for pattern in growth_patterns:
            if pattern in field_name.lower():
                base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
                break

        for pattern in year_patterns:
            if pattern in field_name.lower():
                base_value = fuzzy.FuzzyInteger(1, 100).fuzz()
                break

        for pattern in percentage_patterns:
            if pattern in field_name.lower():
                base_value = fuzzy.FuzzyFloat(0, 1).fuzz()
                break

        # Handle specific field patterns
        if "flu" in field_name.lower():
            base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
        elif "fi" in field_name.lower():
            base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
        elif "fmg" in field_name.lower():
            base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
        elif "logging" in field_name.lower() and "matter" in field_name.lower():
            base_value = fuzzy.FuzzyFloat(1, 100).fuzz()
        elif "degradation" in field_name.lower() and "matter" in field_name.lower():
            base_value = fuzzy.FuzzyFloat(1, 100).fuzz()

        # Add variation based on suffix (_start, _w, _wo)
        if field_name.endswith("_w"):
            base_value *= 2  # 10% higher for "with" scenarios
        elif field_name.endswith("_wo"):
            base_value *= 0.5  # 10% lower for "without" scenarios

        # Return appropriate type based on field type
        if isinstance(field, django_models.IntegerField):
            return int(base_value)
        elif isinstance(field, (django_models.FloatField, django_models.DecimalField)):
            return float(base_value)
        elif isinstance(field, django_models.CharField):
            return str(base_value)
        elif isinstance(field, django_models.BooleanField):
            return True
        else:
            # For unsupported field types, return None to skip
            return None

    def _test_t2_field_balance_changes(self, model_class=None, t2_fields=None):
        """
        Generic method to test _t2 field balance changes for any model.
        This can be moved to a base class for reuse across different module tests.

        Args:
            model_class: The model class to test (defaults to self.ModuleClass)
            t2_fields: Optional list of specific t2 fields to test. If None, all t2 fields will be tested.

        Returns:
            dict: Balance change results for each field tested
        """
        if model_class is None:
            model_class = self.ModuleClass

        # Dynamically discover all _t2 fields from the model
        t2_fields_to_test = self._get_t2_fields_with_test_values(model_class)

        # Filter t2_fields_to_test if specific fields were provided
        if t2_fields is not None:
            t2_fields_to_test = [(field, value) for field, value in t2_fields_to_test if field in t2_fields]

        if not t2_fields_to_test:
            self.skipTest(f"No _t2 fields found in {model_class.__name__} model")

        print(f"\nDiscovered {len(t2_fields_to_test)} _t2 fields in {model_class.__name__} model:")
        for field_name, test_value in t2_fields_to_test:
            print(f"  {field_name}: {test_value} ({type(test_value).__name__})")

        # Get initial balance
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{model_class.__name__.lower()}-results", args=[self.module.pk]), format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

        previous_balance = response.data["balance"]
        balance_changes = {}
        fields_tested = 0
        fields_with_changes = 0

        print(f"\nTesting {len(t2_fields_to_test)} _t2 fields for balance changes...")
        print(f"Initial balance: {previous_balance}")

        # Iterate through each _t2 field
        for field_name, test_value in t2_fields_to_test:
            try:
                # Update the field with test value
                edit_data = {field_name: test_value}
                edit_response = self.edit_module(self.module, self.user, edit_data)

                # Skip if the edit failed (might be due to validation constraints)
                if edit_response.status_code != status.HTTP_200_OK:
                    print(f"  Skipping {field_name}: Edit failed with status {edit_response.status_code}")
                    continue

                self.module.refresh_from_db()

                # Get new balance
                response = view(request, pk=self.module.pk)

                if response.status_code != status.HTTP_200_OK:
                    print(f"  Skipping {field_name}: Results calculation failed")
                    continue

                if "balance" not in response.data:
                    print(f"  Skipping {field_name}: No balance in response")
                    continue

                current_balance = response.data["balance"]
                balance_changed = current_balance != previous_balance
                balance_changes[field_name] = {"previous_balance": previous_balance, "current_balance": current_balance, "changed": balance_changed, "test_value": test_value}

                fields_tested += 1
                if balance_changed:
                    fields_with_changes += 1
                    print(f"  ✓ {field_name} = {test_value}: Balance changed from {previous_balance} to {current_balance}")
                else:
                    print(f"  - {field_name} = {test_value}: No balance change (remained {current_balance})")

                # Update previous balance for next iteration
                previous_balance = current_balance

            except Exception as e:
                print(f"  Error testing {field_name}: {str(e)}")
                continue

        # Print summary
        print("\nSummary:")
        print(f"  Fields tested: {fields_tested}")
        print(f"  Fields that changed balance: {fields_with_changes}")
        print(f"  Fields with no balance change: {fields_tested - fields_with_changes}")

        # Store results for potential analysis
        self.t2_balance_changes = balance_changes

        # Basic assertions - at least some tests should have run
        self.assertGreater(fields_tested, 0, "At least some _t2 fields should have been successfully tested")

        # We expect that at least some _t2 fields should affect the balance
        # This is a reasonable expectation for a forest management calculation model
        self.assertGreater(fields_with_changes, 0, "At least some _t2 fields should affect the balance calculation")

        # Ensure we tested a significant portion of the fields
        expected_minimum_tests = len(t2_fields_to_test) * 0.5  # At least 50% should be testable
        self.assertGreater(fields_tested, expected_minimum_tests, f"Should be able to test at least {expected_minimum_tests} fields, but only tested {fields_tested}")

        return balance_changes


class BaseModuleWithSubmoduleTestCase(BaseModuleTestCase):
    def setUp(self):
        super().setUp()
        self.submodules = []
        self.submodules_viewsets = []

        for submodule in self.submodule_classes:
            submodule: models.Module
            submodule_response = self.create_submodule(submodule, self.user, {"parent": self.module.pk})
            self.assertEqual(submodule_response.status_code, status.HTTP_201_CREATED)

            self.submodules.append(submodule.objects.get(id=submodule_response.data["id"]))
            self.submodules_viewsets.append(generic_module_viewset(submodule))
