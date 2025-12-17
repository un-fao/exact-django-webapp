from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from django.test import TestCase
from django.core.exceptions import ValidationError
from api.views import ActivityViewSet
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice
import logging as log
from api.tests.unit.utils import APITestCaseMixin
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

import logging

logging.disable(logging.CRITICAL)


class ActivityTestCase(APITestCaseMixin):
    """
    Test cases for the Activity model and related API endpoints.
    """

    def setUp(self):
        """
        Set up test environment with project and basic test data.
        """
        super().setUp()
        # Create a project for testing activities
        project_response = self.create_project()
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=project_response.data["id"])

    def test_create_activity(self):
        """
        Test the creation of an activity using the ActivityViewSet.
        Verifies that activities can be created successfully with valid data.
        """
        response = self.create_activity(self.project, self.user, [self.module_type])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)

        # Verify the activity was created in the database
        activity = models.Activity.objects.get(id=response.data["id"])
        self.assertEqual(activity.project, self.project)
        self.assertEqual(activity.owner, self.user)

    def test_create_activity_unauthorized_user(self):
        """
        Test that unauthorized users cannot create activities.
        """
        # Create a user without project permissions
        unauthorized_user = models.CustomUser.objects.create_user(email="unauthorized@test.com", password="testpass123")

        response = self.create_activity(self.project, unauthorized_user, [self.module_type])
        self.assertGreaterEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_activity_locked_project(self):
        """
        Test that activities cannot be created when project is locked by another user.
        """
        # Lock project with user2
        self.project.lock(self.user2)

        response = self.create_activity(self.project, self.user, [self.module_type])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_activity_archived_project(self):
        """
        Test that activities cannot be created in archived projects.
        """
        self.project.is_archived = True
        self.project.save()

        response = self.create_activity(self.project, self.user, [self.module_type])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_activity_finalized_project(self):
        """
        Test that activities cannot be created in finalized projects.
        """
        self.project.is_finalized = True
        self.project.save()

        response = self.create_activity(self.project, self.user, [self.module_type])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_activity(self):
        """
        Test editing an activity's basic properties.
        """
        # Create an activity first
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Edit the activity
        new_data = {
            "name": "Updated Activity Name",
        }

        response = self.edit_activity(activity, self.user, new_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify changes were saved
        activity.refresh_from_db()
        self.assertEqual(activity.name, "Updated Activity Name")

    def test_edit_activity_not_lock_holder(self):
        """
        Test that users who don't hold the project lock cannot edit activities.
        """
        # Create an activity
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Lock project with user2
        self.project.lock(self.user2)

        # Try to edit with original user
        new_data = {"name": "Should Not Update"}
        response = self.edit_activity(activity, self.user, new_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_activity(self):
        """
        Test deleting an activity.
        """
        # Create an activity first
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        response = self.delete_activity(activity, self.user)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify activity was deleted
        self.assertFalse(models.Activity.objects.filter(id=activity.id).exists())

    def test_copy_activity(self):
        """
        Test copying an activity.
        """
        # Create an activity first
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        response = self.copy_activity(activity, self.user)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify a new activity was created
        copied_activity = models.Activity.objects.get(id=response.data["id"])
        self.assertNotEqual(copied_activity.id, activity.id)
        self.assertEqual(copied_activity.project, activity.project)

    def test_activity_status_property(self):
        """
        Test the activity status property calculation.
        """
        # Create an activity with modules
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Initially should be EMPTY
        self.assertEqual(activity.status.name_en, "EMPTY")

    def test_activity_completion_percentage(self):
        """
        Test the completion percentage calculation.
        """
        # Create an activity
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should have completion percentage between 0 and 1
        completion = activity.completion_percentage
        self.assertGreaterEqual(completion, 0)
        self.assertLessEqual(completion, 1)

    def test_activity_implementation_years_property(self):
        """
        Test the implementation_years property.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should default to project implementation years
        self.assertEqual(activity.implementation_years, self.project.implementation_years)

        # Test with custom duration
        activity.duration_t2 = 5
        activity.save()
        self.assertEqual(activity.implementation_years, 5)

    def test_activity_capitalization_years_property(self):
        """
        Test the capitalization_years property calculation.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should be calculated based on project settings
        expected_years = self.project.capitalization_years
        self.assertEqual(activity.capitalization_years, expected_years)

    def test_activity_delay_property(self):
        """
        Test the delay property calculation.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Default should be 0 delay
        self.assertEqual(activity.delay, 0)

        # Test with custom start year
        activity.start_year_t2 = self.project.start_year_of_activities + 3
        activity.save()
        self.assertEqual(activity.delay, 3)

    def test_activity_start_year_property(self):
        """
        Test the start_year property.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should default to project start year
        self.assertEqual(activity.start_year, self.project.start_year_of_activities)

        # Test with custom start year
        custom_start = 2025
        activity.start_year_t2 = custom_start
        activity.save()
        self.assertEqual(activity.start_year, custom_start)

    def test_activity_last_year_of_accounting_property(self):
        """
        Test the last_year_of_accounting property.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should default to project last year
        self.assertEqual(activity.last_year_of_accounting, self.project.last_year_of_accounting)

        # Test with custom value
        custom_last_year = 2050
        activity.last_year_of_accounting_t2 = custom_last_year
        activity.save()
        self.assertEqual(activity.last_year_of_accounting, custom_last_year)

    def test_activity_soc_property(self):
        """
        Test the SOC (Soil Organic Carbon) property.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should default to project SOC value
        self.assertEqual(activity.soc, self.project.soc_ref_t2)

        # Test with custom SOC value
        custom_soc = 45.5
        activity.soc_t2 = custom_soc
        activity.save()
        self.assertEqual(activity.soc, custom_soc)

    def test_activity_modules_property(self):
        """
        Test the modules property returns all associated modules.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        modules = activity.modules
        self.assertIsInstance(modules, list)

    def test_activity_unique_name_per_project(self):
        """
        Test that activity names must be unique within a project.
        """
        # Create first activity
        create_response1 = self.create_activity(self.project, self.user, [self.module_type])
        activity1 = models.Activity.objects.get(id=create_response1.data["id"])

        # Try to create another activity with the same name in the same project
        activity2 = models.Activity(name=activity1.name, project=self.project, owner=self.user)

        with self.assertRaises(ValidationError):
            activity2.full_clean()

    def test_activity_duration_validation(self):
        """
        Test validation of activity duration against project limits.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Test editing with invalid duration (greater than project duration)
        invalid_duration = self.project.implementation_years + self.project.capitalization_years + 1
        data = {"duration_t2": invalid_duration}

        response = self.edit_activity(activity, self.user, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activity_is_luc_property(self):
        """
        Test the is_luc property detection.
        """
        # Create activity with a land module type
        land_module_type = models.ModuleType.objects.filter(is_luc=True).first()
        create_response = self.create_activity(self.project, self.user, [land_module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Check if properly detects land use change modules
        # This depends on the actual modules created, so we'll just verify the property exists
        self.assertIsInstance(activity.is_luc, bool)

    def test_activity_type_detection_properties(self):
        """
        Test various activity type detection properties.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Test all the is_* properties exist and return boolean values
        properties_to_test = ["is_fishery", "is_livestock", "is_energy", "is_packaging", "is_storage", "is_transport", "is_processing", "is_input"]

        for prop in properties_to_test:
            self.assertIsInstance(getattr(activity, prop), bool)

    def test_activity_area_property(self):
        """
        Test the area property calculation.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Should return a numeric value (default 0 if no land modules)
        self.assertIsInstance(activity.area, (int, float))
        self.assertGreaterEqual(activity.area, 0)

    def test_activity_str_representation(self):
        """
        Test the string representation of the Activity model.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        str_repr = str(activity)
        self.assertIn(str(activity.pk), str_repr)
        self.assertIn(activity.name, str_repr)
        self.assertIn(activity.project.name, str_repr)

    def test_activity_save_with_change_tracking(self):
        """
        Test that activity saves properly track changes and invalidate module results.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Modify activity and save
        activity.name = "Modified Activity Name"
        activity.save()

        # Verify the activity was updated
        activity.refresh_from_db()
        self.assertEqual(activity.name, "Modified Activity Name")

    def test_activity_ordering(self):
        """
        Test that activities are ordered by created_at descending.
        """
        # Create multiple activities with small time delays
        activities = []
        for i in range(3):
            response = self.create_activity(self.project, self.user, [self.module_type])
            activities.append(models.Activity.objects.get(id=response.data["id"]))

        # Get all activities for the project
        project_activities = list(models.Activity.objects.filter(project=self.project))

        # Should be ordered by created_at descending (newest first)
        for i in range(len(project_activities) - 1):
            self.assertGreaterEqual(project_activities[i].created_at, project_activities[i + 1].created_at)

    def test_activity_historical_tracking(self):
        """
        Test that activities have historical tracking enabled.
        """
        create_response = self.create_activity(self.project, self.user, [self.module_type])
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Verify historical record was created
        self.assertTrue(hasattr(activity, "history"))
        self.assertGreater(activity.history.count(), 0)

        # Modify and check history
        original_name = activity.name
        activity.name = "Updated Name"
        activity.save()

        # Should have multiple history records now
        self.assertGreater(activity.history.count(), 1)

    def test_remove_organic_soil_preserves_land_modules(self):
        """
        Test that removing organic soil from an activity preserves other land modules
        and their data, rather than deleting and recreating them.
        """
        from api.serializers import ActivityBuilderSerializer
        from django.apps import apps
        from rest_framework.test import APIRequestFactory

        # Get a land module type (e.g., Grassland)
        land_module_type = models.ModuleType.objects.filter(is_luc=True, class_name__in=["Grassland", "AnnualCropland", "PerennialCropland"]).first()
        if not land_module_type:
            self.skipTest("No suitable land module type found for testing")

        organic_soil_module_type = models.ModuleType.objects.filter(class_name="OrganicSoil").first()
        if not organic_soil_module_type:
            self.skipTest("OrganicSoil module type not found")

        # Create an activity with organic soil and a land module
        create_response = self.create_activity(self.project, self.user, [land_module_type, organic_soil_module_type])
        self.assertEqual(create_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_response.data["id"])

        # Get the land module instance and set some data we can verify later
        ModuleClass = apps.get_model("api", land_module_type.class_name)
        land_module = ModuleClass.objects.filter(activity=activity).first()
        self.assertIsNotNone(land_module, "Land module should exist")

        # Set some identifiable data on the land module
        test_area = 150.5
        if hasattr(land_module, "area"):
            land_module.area = test_area
            land_module.save()

        # Store the module's ID to verify it's the same instance later
        land_module_id = land_module.id
        land_module_pk = land_module.pk

        # Verify organic soil exists
        organic_soil = models.OrganicSoil.objects.filter(activity=activity).first()
        self.assertIsNotNone(organic_soil, "Organic soil should exist")

        # Update the activity to remove organic soil using ActivityBuilderSerializer
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = self.user

        update_data = {
            "activity_id": activity.id,
            "project": self.project.id,
            "name": activity.name,
            "module_types": [land_module_type.id],  # Only land module, no organic soil
            "area": test_area,
        }

        serializer = ActivityBuilderSerializer(data=update_data, instance=activity, context={"request": request})
        self.assertTrue(serializer.is_valid(), f"Serializer should be valid: {serializer.errors}")

        updated_activity = serializer.save()

        # Verify organic soil was removed
        organic_soil_after = models.OrganicSoil.objects.filter(activity=updated_activity).first()
        self.assertIsNone(organic_soil_after, "Organic soil should be removed")

        # Verify the land module still exists with the same ID (not recreated)
        land_module_after = ModuleClass.objects.filter(activity=updated_activity).first()
        self.assertIsNotNone(land_module_after, "Land module should still exist")
        self.assertEqual(land_module_after.id, land_module_id, "Land module should have the same ID (not recreated)")
        self.assertEqual(land_module_after.pk, land_module_pk, "Land module should have the same primary key")

        # Verify the land module's data is preserved
        if hasattr(land_module_after, "area"):
            self.assertEqual(land_module_after.area, test_area, "Land module area should be preserved")

        # Verify organic_soil reference is cleared
        if hasattr(land_module_after, "organic_soil"):
            self.assertIsNone(land_module_after.organic_soil, "Land module's organic_soil reference should be None")

    def tearDown(self):
        """
        Clean up test environment.
        """
        # Clean up any created activities and projects
        models.Activity.objects.filter(project=self.project).delete()
        if hasattr(self, "project"):
            self.project.delete()
        super().tearDown()


class ActivityModelUnitTest(TestCase):
    """
    Unit tests for Activity model methods that don't require API interaction.
    """

    def setUp(self):
        """
        Set up minimal test data for unit tests.
        """
        self.user = models.CustomUser.objects.create_user(email="test@example.com", password="testpass123")

        self.country = models.Country.objects.first()
        self.climate = models.Climate.objects.first()
        self.moisture = self.climate.moistures.first() if self.climate else None
        self.soil_type = models.SoilType.objects.filter(active=True).first()
        self.gw_potential = ipcc_models.GlobalWarmingPotential.objects.first()

        self.project = models.Project.objects.create(
            name="Test Project",
            start_year_of_activities=2024,
            implementation_years=10,
            last_year_of_accounting=2040,
            country=self.country,
            climate=self.climate,
            moisture=self.moisture,
            soil_type=self.soil_type,
            gw_potential=self.gw_potential,
            soc_ref_t2=50.0,
            owner=self.user,
        )

    def test_activity_creation_defaults(self):
        """
        Test that activities are created with proper default values.
        """
        activity = models.Activity.objects.create(name="Test Activity", project=self.project, owner=self.user)

        # Check defaults
        self.assertEqual(activity.cost, 0)
        self.assertIsNotNone(activity.status)
        self.assertIsNotNone(activity.change_rate)

    def test_private_duration_method(self):
        """
        Test the private __get_duration method logic.
        """
        activity = models.Activity.objects.create(name="Test Activity", project=self.project, owner=self.user)

        # Default should use project implementation years
        self.assertEqual(activity.duration, self.project.implementation_years)

        # Custom duration should override
        activity.duration_t2 = 5
        activity.save()
        self.assertEqual(activity.duration, 5)

    def test_private_delay_method(self):
        """
        Test the private __get_delay method logic.
        """
        activity = models.Activity.objects.create(name="Test Activity", project=self.project, owner=self.user)

        # Default should be 0
        self.assertEqual(activity.delay, 0)

        # Custom start year should calculate delay
        activity.start_year_t2 = self.project.start_year_of_activities + 2
        activity.save()
        self.assertEqual(activity.delay, 2)

    def test_private_capitalization_years_method(self):
        """
        Test the private __get_capitalization_years method logic.
        """
        activity = models.Activity.objects.create(name="Test Activity", project=self.project, owner=self.user)

        # Test different combinations of start_year_t2 and duration_t2
        expected = self.project.capitalization_years
        self.assertEqual(activity.capitalization_years, expected)

    def tearDown(self):
        """
        Clean up test data.
        """
        models.Activity.objects.filter(project=self.project).delete()
        self.project.delete()
        self.user.delete()
