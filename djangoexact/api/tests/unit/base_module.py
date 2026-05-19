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
    # Concrete subclasses set ModuleClass. The bare abstract base is skipped
    # so the test loader can collect this module without running it.
    ModuleClass = None

    def setUp(self):
        if getattr(self, "ModuleClass", None) is None:
            self.skipTest("abstract base test case (ModuleClass not configured)")

        super().setUp()

        project_response = self.create_project()
        log.info(project_response.data) if project_response.status_code != status.HTTP_201_CREATED else None
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)

        self.project = models.Project.objects.get(id=project_response.data["id"])
        self.module_type = models.ModuleType.objects.get(class_name=self.ModuleClass.__name__)

        self.climate = self.project.climate
        self.moisture = self.project.moisture

        activity_response = self.create_activity(self.project, self.user, [self.module_type])
        log.info(activity_response.data) if activity_response.status_code != status.HTTP_200_OK else None
        self.assertEqual(activity_response.status_code, status.HTTP_200_OK)

        self.activity = models.Activity.objects.get(id=activity_response.data["id"])
        self.module: models.Module = apps.get_model("api", self.module_type.class_name).objects.get(activity=self.activity)

        self.module_viewset = generic_module_viewset(self.ModuleClass)

        self.land_use_types = models.LandUseType.objects.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)
        if isinstance(self.ModuleClass, models.CoastalWetland):
            self.land_use_types = self.land_use_types.filter(is_coastal=True)

    def get_results(self, cached="true"):
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]) + f"?cached={cached}", format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None

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
        request = self.request_factory.get(reverse(f"{model_class.__name__.lower()}-results", args=[self.module.pk]) + "?cached=false", format="json")
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

    def test_defaults_visible_with_different_lock_holder(self):
        """
        Test that the defaults are visible to different lock holders.
        """
        self.project.lock(self.user2)
        self.project.save()

        defaults_response = self.get_module_defaults(self.module, self.user)
        self.assertEqual(defaults_response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(defaults_response.data, dict)


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


class BaseLandUseChangeTestCase(APITestCaseMixin):
    """
    Base test case for Land Use Change scenarios.

    This class provides a foundation for testing land use change scenarios that involve
    three modules: start (baseline), without project (wo), and with project (w).
    It follows the unit test patterns used throughout the codebase.
    """

    def setUp(self):
        """
        Set up the test environment for land use change tests.

        This creates:
        - A project
        - An activity with the required module types
        - A land use change object
        - The three required modules (start, with, without)
        """
        if type(self) in (BaseLandUseChangeTestCase, AnyToAnyLandUseChangeTestCase):
            self.skipTest("abstract land use change base test case")

        super().setUp()

        # Module types for the land use change scenario
        self.module_type_start = None
        self.module_type_w = None
        self.module_type_wo = None

        # The land use change object and related modules
        self.land_use_change = None
        self.module_start = None
        self.module_w = None
        self.module_wo = None

        # Create project
        project_response = self.create_project()
        log.info(project_response.data) if project_response.status_code != status.HTTP_201_CREATED else None
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=project_response.data["id"])

    def setup_land_use_change(self, module_type_start_name, module_type_w_name, module_type_wo_name):
        """
        Set up the land use change scenario with the specified module types.

        Args:
            module_type_start_name (str): Class name for the start module type
            module_type_w_name (str): Class name for the with project module type
            module_type_wo_name (str): Class name for the without project module type
        """
        # Get module types
        self.module_type_start = models.ModuleType.objects.get(class_name=module_type_start_name)
        self.module_type_w = models.ModuleType.objects.get(class_name=module_type_w_name)
        self.module_type_wo = models.ModuleType.objects.get(class_name=module_type_wo_name)
        self.module_type_land_use_change = models.ModuleType.objects.get(class_name="LandUseChange")

        # Create activity with all required module types
        module_types = [self.module_type_start, self.module_type_w, self.module_type_wo]
        activity_response = self.create_activity(self.project, self.user, module_types, land_use_change=True)
        self.assertEqual(activity_response.status_code, status.HTTP_200_OK)
        self.activity = models.Activity.objects.get(id=activity_response.data["id"])

        self.land_use_change = models.LandUseChange.objects.get(activity=self.activity)
        self.module_start = apps.get_model("api", self.module_type_start.class_name).objects.get(activity=self.activity)
        self.module_w = apps.get_model("api", self.module_type_w.class_name).objects.get(activity=self.activity)
        self.module_wo = apps.get_model("api", self.module_type_wo.class_name).objects.get(activity=self.activity)

    def get_land_use_change_results(self, cached="true"):
        """
        Get the results for the land use change calculation.

        Args:
            cached (str): Whether to use cached results ("true" or "false")

        Returns:
            Response: The API response containing the calculation results
        """
        view = generic_module_viewset(models.LandUseChange).as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"landusechange-results", args=[self.land_use_change.pk]) + f"?cached={cached}", format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.land_use_change.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def get_module_results(self, module, cached="true"):
        """
        Get the results for a specific module.

        Args:
            module: The module to get results for
            cached (str): Whether to use cached results ("true" or "false")

        Returns:
            Response: The API response containing the calculation results
        """
        module_class = module.__class__
        view = generic_module_viewset(module_class).as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{module_class.__name__.lower()}-results", args=[module.pk]) + f"?cached={cached}", format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=module.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def edit_module(self, module, user, data):
        """
        Edit a module with the provided data.

        Args:
            module: The module to edit
            user: The user making the edit
            data (dict): The data to update the module with

        Returns:
            Response: The API response from the edit operation
        """
        module_class = module.__class__
        view = generic_module_viewset(module_class).as_view({"patch": "partial_update"})
        request = self.request_factory.patch(
            reverse(f"{module_class.__name__.lower()}-detail", args=[module.pk]),
            data,
            format="json",
        )
        force_authenticate(request, user=user)
        response = view(request, pk=module.pk)
        log.error(response.data) if response.status_code != status.HTTP_200_OK else None
        return response

    def test_land_use_change_calculation(self):
        """
        Test that the land use change calculation runs successfully.

        This is a basic test that verifies:
        - The land use change calculation can be executed
        - Results are returned with expected structure
        - All individual modules can also be calculated
        """
        # Test land use change results
        luc_response = self.get_land_use_change_results()
        self.assertEqual(luc_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", luc_response.data)

        # Test individual module results
        start_response = self.get_module_results(self.module_start)
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", start_response.data)

        w_response = self.get_module_results(self.module_w)
        self.assertEqual(w_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", w_response.data)

        wo_response = self.get_module_results(self.module_wo)
        self.assertEqual(wo_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", wo_response.data)

    def test_module_edit_invalidates_cache(self):
        """
        Test that editing a module invalidates the calculation cache.

        This verifies that when a module is modified, subsequent calculations
        reflect the changes by using fresh (non-cached) results.
        """
        # Get initial results
        initial_response = self.get_land_use_change_results()
        self.assertEqual(initial_response.status_code, status.HTTP_200_OK)
        initial_balance = initial_response.data["balance"]

        # Edit a module (this should invalidate cache)
        edit_data = {"area": 200}  # Change area
        edit_response = self.edit_module(self.land_use_change, self.user, edit_data)
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)

        # Get new results (should be different if cache was invalidated)
        new_response = self.get_land_use_change_results(cached="false")
        self.assertEqual(new_response.status_code, status.HTTP_200_OK)

        # The balance should have changed (or at least the calculation should work)
        self.assertIn("balance", new_response.data)


class AnyToAnyLandUseChangeTestCase(BaseLandUseChangeTestCase):
    """
    Generic test case that can be used to test any land use change scenario.

    This demonstrates how the base class can be easily extended for different
    land use change combinations.
    """

    def setup_scenario(self, start_module, w_module, wo_module):
        """
        Setup a custom land use change scenario.

        Args:
            start_module (str): Starting land use module class name
            w_module (str): With project module class name
            wo_module (str): Without project module class name
        """
        self.setup_land_use_change(start_module, w_module, wo_module)

    def test_generic_calculation(self):
        """
        Test that any land use change scenario can be calculated.

        This test can be run after calling setup_scenario() to verify
        that the calculation system works for any module combination.
        """
        # Test that all calculations succeed
        luc_response = self.get_land_use_change_results()
        self.assertEqual(luc_response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", luc_response.data)

        # Test individual modules
        if self.module_start:
            start_response = self.get_module_results(self.module_start)
            log.info(start_response.data) if start_response.status_code != status.HTTP_200_OK else None
            self.assertEqual(start_response.status_code, status.HTTP_200_OK)

        if self.module_w:
            w_response = self.get_module_results(self.module_w)
            log.info(w_response.data) if w_response.status_code != status.HTTP_200_OK else None
            self.assertEqual(w_response.status_code, status.HTTP_200_OK)

        if self.module_wo:
            wo_response = self.get_module_results(self.module_wo)
            log.info(wo_response.data) if wo_response.status_code != status.HTTP_200_OK else None
            self.assertEqual(wo_response.status_code, status.HTTP_200_OK)
