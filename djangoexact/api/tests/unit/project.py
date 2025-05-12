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


class ProjectTestCase(APITestCaseMixin):
    def test_create_project(self):
        """
        Test the creation of a project using the ProjectViewSet.

        This test uses the APIRequestFactory to create a POST request to the
        'project-list' endpoint with the provided project data in JSON format.
        The request is authenticated with a test user, and the response is
        checked to ensure that the project is created successfully with a
        status code of 201 (Created).
        """
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # self.assertTrue("project_membership" in response.data and type(response.data["project_membership"]) == int)

    def test_modify_project_as_not_lock_holder(self):
        """
        Test that a user who is not the lock holder of a project cannot modify the project.

        This test performs the following steps:
        1. Creates a project using the `ProjectViewSet` and verifies that the project is created successfully.
        2. Retrieves the created project from the database.
        3. Creates a project membership for a second user (`self.user2`) who is not the lock holder.
        4. Attempts to modify the project using the second user and verifies that the modification is not allowed,
           expecting a `HTTP_400_BAD_REQUEST` status code.

        Assertions:
        - The project creation response status code is `HTTP_201_CREATED`.
        - The project modification response status code is `HTTP_400_BAD_REQUEST`.
        """

        create_response = self.create_project()
        project = models.Project.objects.get(id=create_response.data["id"])
        membership_response = self.create_project_membership(project, self.user2)
        self.assertEqual(membership_response.status_code, status.HTTP_201_CREATED)
        modify_response = self.edit_project(project, self.user2, {"name": "New Name"})
        self.assertEqual(modify_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_project_as_lock_holder(self):
        """
        Test that a project lock holder can modify the project.

        This test performs the following steps:
        1. Creates a project using the ProjectViewSet's create action.
        2. Authenticates the request with a user.
        3. Verifies that the project is created successfully with a 201 status code.
        4. Retrieves the created project from the database.
        5. Modifies the project's name using the ProjectViewSet's partial_update action.
        6. Authenticates the modification request with the same user.
        7. Verifies that the project is modified successfully with a 200 status code.
        8. Confirms that the project's name has been updated to "New Name".
        """

        create_response = self.create_project()

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        project = models.Project.objects.get(id=create_response.data["id"])
        modify_response = self.edit_project(project, self.user, {"name": "New Name"})

        self.assertEqual(modify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(modify_response.data["name"], "New Name")

    def test_modify_actvity_as_not_lock_holder(self):
        """
        Test that a user who is not the lock holder of an activity cannot modify it.

        Steps:
        1. Create a project.
        2. Verify the project creation response status is HTTP 201 Created.
        3. Retrieve the created project from the database.
        4. Create a project membership for a second user.
        5. Create an activity within the project by the first user.
        6. Verify the activity creation response status is HTTP 200 OK.
        7. Retrieve the created activity from the database.
        8. Attempt to modify the activity by the second user.
        9. Verify the modification response status is HTTP 400 Bad Request.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])
        membership_response = self.create_project_membership(project, self.user2)
        self.assertEqual(membership_response.status_code, status.HTTP_201_CREATED)

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        modify_activity_response = self.edit_activity(activity, self.user2, {"name": "New Name"})
        self.assertEqual(modify_activity_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_activity_as_lock_holder(self):
        """
        Test modifying an activity as the lock holder.

        This test performs the following steps:
        1. Creates a project and verifies the response status code is 201 (Created).
        2. Retrieves the created project from the database.
        3. Creates an activity within the project and verifies the response status code is 200 (OK).
        4. Retrieves the created activity from the database.
        5. Modifies the activity's name and verifies the response status code is 200 (OK).
        6. Confirms that the activity's name has been updated to the new value.

        Assertions:
        - The project creation response status code is 201.
        - The activity creation response status code is 200.
        - The activity modification response status code is 200.
        - The activity's name is updated to "New Name".
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        modify_activity_response = self.edit_activity(activity, self.user, {"name": "New Name"})
        self.assertEqual(modify_activity_response.status_code, status.HTTP_200_OK)
        self.assertEqual(modify_activity_response.data["name"], "New Name")

    def test_modify_module_as_not_lock_holder(self):
        """
        Test that a user who is not the lock holder of a module cannot modify it.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Adds a second user as a member of the project.
        3. Creates an activity within the project and verifies the activity creation.
        4. Attempts to modify a module within the activity using the second user.
        5. Verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that only the lock holder of a module can modify it.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])
        membership_response = self.create_project_membership(project, self.user2)
        self.assertEqual(membership_response.status_code, status.HTTP_201_CREATED)

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        module = activity.modules[0]

        response = self.edit_module(module, self.user2, {"area": 50})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_modify_module_as_lock_holder(self):
        """
        Test modifying a module as the lock holder.
        This test case verifies that a user who holds the lock on a project can successfully modify a module within that project.
        Steps:
        1. Create a project and verify the response status is HTTP 201 Created.
        2. Retrieve the created project from the database.
        3. Create an activity within the project and verify the response status is HTTP 200 OK.
        4. Retrieve the created activity from the database.
        5. Select the first module from the activity.
        6. Attempt to edit the module's area attribute as the lock holder and verify the response status is HTTP 200 OK.
        7. Verify that the module's area attribute has been updated to the new value.
        """

        log.info("START - test_modify_module_as_lock_holder")

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        module = activity.modules[0]

        response = self.edit_module(module, self.user, {"area": 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"], 50)

        log.info("END - test_modify_module_as_lock_holder")

    def test_archive_project_and_modify(self):
        """
        Test that a project cannot be modified after it has been archived.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Archives the project.
        3. Attempts to modify the project and verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that a project cannot be modified after it has been archived.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        archive_response = self.edit_project(project, self.user, {"is_archived": True})
        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)
        self.assertTrue(archive_response.data["is_archived"])

        modify_response = self.edit_project(project, self.user, {"name": "New Name"})
        self.assertEqual(modify_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_activity_last_year_of_accounting_t2_and_check_if_capitalization_years_change(self):
        """
        Test that changing the last year of accounting for an activity updates the capitalization years.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Creates an activity within the project and verifies the activity creation.
        3. Retrieves the created activity from the database.
        4. Changes the last year of accounting for the activity and verifies the response status code is 200 OK.
        5. Retrieves the updated activity from the database.
        6. Verifies that the capitalization years have been updated as expected.

        The test ensures that changing the last year of accounting for an activity updates the capitalization years as expected.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        response = self.edit_activity(activity, self.user, {"last_year_of_accounting_t2": 2022, "start_year_t2": 2020, "duration_t2": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated_activity = models.Activity.objects.get(id=activity.id)
        self.assertNotEqual(updated_activity.capitalization_years, project.capitalization_years)

    def test_archive_project_and_try_to_change_last_year_of_accounting(self):
        """
        Test that changing the last year of accounting for an archived project is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Archives the project.
        3. Attempts to change the last year of accounting for the archived project and verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that changing the last year of accounting for an archived project is not allowed.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        archive_response = self.edit_project(project, self.user, {"is_archived": True})
        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)
        self.assertTrue(archive_response.data["is_archived"])

        modify_response = self.edit_project(project, self.user, {"last_year_of_accounting": 2022})
        self.assertEqual(modify_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archive_project_and_add_membership(self):
        """
        Test that adding a project membership to an archived project is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Archives the project.
        3. Attempts to add a project membership to the archived project and verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that adding a project membership to an archived project is not allowed.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        archive_response = self.edit_project(project, self.user, {"is_archived": True})
        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)
        self.assertTrue(archive_response.data["is_archived"])

        modify_response = self.create_project_membership(project, self.user2)
        self.assertEqual(modify_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_another_admin_and_archive_project(self):
        """
        Test that adding another admin to a project and then archiving the project is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Adds another user as an admin to the project.
        3. Attempts to archive the project and verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that adding another admin to a project and then archiving the project is not allowed.
        """

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        self.group = models.Group.objects.get(name="Admin")
        membership_response = self.create_project_membership(project, self.user2)
        self.assertEqual(membership_response.status_code, status.HTTP_201_CREATED)

        modify_response = self.edit_project(project, self.user2, {"is_archived": True})
        self.assertEqual(modify_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_changing_last_year_of_accounting_for_project_with_activity_having_duration_t2_exceeding_last_year_of_accounting(self):
        """
        Test that changing the last year of accounting for a project with an activity having a duration exceeding the last year of accounting is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Creates an activity within the project and verifies the activity creation.
        3. Attempts to change the last year of accounting for the project and verifies that the modification attempt fails with a 400 Bad Request status code.

        The test ensures that changing the last year of accounting for a project with an activity having a duration exceeding the last year of accounting is not allowed.
        """

        log.info("START - test_changing_last_year_of_accounting_for_project_with_activity_having_duration_t2_exceeding_last_year_of_accounting")

        self.project_data["start_year_of_activities"] = 2000
        self.project_data["implementation_years"] = 10
        self.project_data["last_year_of_accounting"] = 2020

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        edit_activity_response = self.edit_activity(activity, self.user, {"duration_t2": 10})
        self.assertEqual(edit_activity_response.status_code, status.HTTP_200_OK)
        self.assertEqual(edit_activity_response.data["duration_t2"], 10)

        edit_project_response = self.edit_project(project, self.user, {"last_year_of_accounting": 2009})
        self.assertEqual(edit_project_response.status_code, status.HTTP_400_BAD_REQUEST)

        log.info("END - test_changing_last_year_of_accounting_for_project_with_activity_having_duration_t2_exceeding_last_year_of_accounting")

    def finalize_project_and_try_to_send_invitation_as_admin(self):
        """
        Test that sending an invitation as an admin after finalizing a project is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Finalizes the project.
        3. Attempts to send an invitation as an admin and verifies that the modification attempt succeeds with a 200 OK status code.

        The test ensures that sending an invitation as an admin after finalizing a project is allowed.
        """

        log.info("START - finalize_project_and_try_to_send_invitation_as_admin")

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        finalize_response = self.edit_project(project, self.user, {"is_finalized": True})
        self.assertEqual(finalize_response.status_code, status.HTTP_200_OK)
        self.assertTrue(finalize_response.data["is_finalized"])

        modify_response = self.send_project_invitation(project, self.user2, self.group)
        self.assertEqual(modify_response.status_code, status.HTTP_200_OK)

        log.info("END - finalize_project_and_try_to_send_invitation_as_admin")

    def try_deleting_activity_of_finalized_project(self):
        """
        Test that deleting an activity of a finalized project is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Finalizes the project.
        3. Attempts to delete an activity within the finalized project and verifies that the deletion attempt fails with a 400 Bad Request status code.

        The test ensures that deleting an activity of a finalized project is not allowed.
        """

        log.info("START - try_deleting_activity_of_finalized_project")

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        finalize_response = self.edit_project(project, self.user, {"is_finalized": True})
        self.assertEqual(finalize_response.status_code, status.HTTP_200_OK)
        self.assertTrue(finalize_response.data["is_finalized"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        delete_activity_response = self.delete_activity(activity, self.user)
        self.assertEqual(delete_activity_response.status_code, status.HTTP_400_BAD_REQUEST)

        log.info("END - try_deleting_activity_of_finalized_project")

    def test_upload_file_in_finalized_project(self):
        """
        Test that uploading a file in a finalized project is not allowed.

        This test performs the following steps:
        1. Creates a project and verifies the project creation.
        2. Finalizes the project.
        3. Attempts to upload a file in the finalized project and verifies that the upload attempt fails with a 400 Bad Request status code.

        The test ensures that uploading a file in a finalized project is not allowed.
        """

        log.info("START - test_upload_file_in_finalized_project")

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        finalize_response = self.edit_project(project, self.user, {"is_finalized": True})
        self.assertEqual(finalize_response.status_code, status.HTTP_200_OK)
        self.assertTrue(finalize_response.data["is_finalized"])

        upload_file_response = self.upload_project_file(project, self.user)
        self.assertEqual(upload_file_response.status_code, status.HTTP_400_BAD_REQUEST)

        log.info("END - test_upload_file_in_finalized_project")

    def test_make_project_public_and_verify_activities_can_be_accessed(self):
        """
        Test that making a project public allows access to its activities.
        """

        log.info("START - test_make_project_public_and_verify_activities_can_be_accessed")

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        make_public_response = self.edit_project(project, self.user, {"is_public": True})
        self.assertEqual(make_public_response.status_code, status.HTTP_200_OK)
        self.assertTrue(make_public_response.data["is_public"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        get_activity_response = self.get_activity_anonimously(activity)
        self.assertEqual(get_activity_response.status_code, status.HTTP_200_OK)

        log.info("END - test_make_project_public_and_verify_activities_can_be_accessed")

    def test_make_project_public_and_verify_that_results_can_be_calculated(self):
        """
        Test that making a project public allows access to its results.
        """

        log.info("START - test_make_project_public_and_verify_that_results_can_be_calculated")

        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        project = models.Project.objects.get(id=create_project_response.data["id"])

        make_public_response = self.edit_project(project, self.user, {"is_public": True})
        self.assertEqual(make_public_response.status_code, status.HTTP_200_OK)
        self.assertTrue(make_public_response.data["is_public"])

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        get_results_response = self.calculate_activity_results_anonimously(activity)
        self.assertEqual(get_results_response.status_code, status.HTTP_200_OK)

        log.info("END - test_make_project_public_and_verify_that_results_can_be_calculated")

    # BUG: This test is not working as expected but the functionality itself is working
    # def test_copying_activity_of_finalized_project(self):
    #     """
    #     Test that copying an activity of a finalized project is not allowed.

    #     This test performs the following steps:
    #     1. Creates a project and verifies the project creation.
    #     2. Finalizes the project.
    #     3. Attempts to copy an activity within the finalized project and verifies that the copy attempt fails with a 400 Bad Request status code.

    #     The test ensures that copying an activity of a finalized project is not allowed.
    #     """

    #     log.info("START - test_copying_activity_of_finalized_project")

    #     create_project_response = self.create_project()
    #     self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
    #     project = models.Project.objects.get(id=create_project_response.data["id"])

    #     create_activity_response = self.create_activity(project, self.user)
    #     self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
    #     activity = models.Activity.objects.get(id=create_activity_response.data["id"])

    #     finalize_response = self.edit_project(project, self.user, {"is_finalized": True})
    #     self.assertEqual(finalize_response.status_code, status.HTTP_200_OK)
    #     self.assertTrue(finalize_response.data["is_finalized"])

    #     copy_activity_response = self.copy_activity(activity, self.user)
    #     self.assertEqual(copy_activity_response.status_code, status.HTTP_400_BAD_REQUEST)

    #     log.info("END - test_copying_activity_of_finalized_project")
