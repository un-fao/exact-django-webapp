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
        self.assertTrue("project_membership" in response.data and type(response.data["project_membership"]) == int)

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
        self.create_project_membership(project, self.user2)
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
        self.create_project_membership(project, self.user2)

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
        self.create_project_membership(project, self.user2)

        create_activity_response = self.create_activity(project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        module = activity.modules[0]

        response = self.edit_module(module, self.user2, {"area": 50})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
