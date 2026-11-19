"""Creating a module or submodule checks add_modules on the target project before validating.

Serializer validation writes (it takes the project lock, and a land module saves its Land Use Change), so a
caller who is refused must be refused before it runs, or anyone signed in could lock (and keep locked) a
project they are not a member of.
"""

from rest_framework.test import APITestCase

from api.models import Activity, Grassland, Group, Input, ModuleType, Project, ProjectMembership
from api.tests.factories import ActivityFactory, GrasslandFactory, InputFactory, LandUseChangeFactory, UserFactory
from api.tests.test_finalized_results_frozen import calculable_project

MODULES_URL = "/api/inputs/"
SUBMODULES_URL = "/api/input-entries/"
LAND_MODULES_URL = "/api/grasslands/"


def unused_activity_pk() -> int:
    return (Activity.objects.order_by("-pk").values_list("pk", flat=True).first() or 0) + 1000


class ModuleCreatePermissionTestCase(APITestCase):
    def setUp(self):
        self.owner = UserFactory(email="module-create-owner@example.com")
        self.outsider = UserFactory(email="module-create-outsider@example.com")
        self.project = calculable_project(self.owner)
        ProjectMembership.objects.create(user=self.owner, project=self.project, group=Group.objects.get(name="Admin"))
        self.activity = ActivityFactory(project=self.project, name="Module create permission activity")
        self.activity.module_types.add(ModuleType.objects.get(class_name="Input"))

    def assertProjectUnlocked(self, project=None):
        project = Project.objects.get(pk=(project or self.project).pk)
        lock_state = (project.is_locked, project.locked_by, project.locked_at, project.lock_updated_at)
        self.assertEqual(lock_state, (False, None, None, None))

    def post_as(self, user, url, data):
        self.client.force_authenticate(user)
        return self.client.post(url, data, format="json")

    def read_only_member(self):
        reviewer = UserFactory(email="module-create-reviewer@example.com")
        read_only_group = Group.objects.get(name="Second Reviewer")
        ProjectMembership.objects.create(user=reviewer, project=self.project, group=read_only_group)
        return reviewer

    def test_outsider_creating_a_module_is_refused_without_locking_the_project(self):
        resp = self.post_as(self.outsider, MODULES_URL, {"activity": self.activity.pk})

        self.assertEqual(resp.status_code, 403)
        self.assertProjectUnlocked()
        self.assertFalse(Input.objects.filter(activity=self.activity).exists())

    def test_outsider_creating_a_submodule_is_refused_without_locking_the_project(self):
        parent = InputFactory(activity=self.activity)

        resp = self.post_as(self.outsider, SUBMODULES_URL, {"parent": parent.pk})

        self.assertEqual(resp.status_code, 403)
        self.assertProjectUnlocked()
        self.assertFalse(parent.input_entries.exists())

    def test_outsider_creating_a_module_list_is_refused_without_locking_the_project(self):
        resp = self.post_as(self.outsider, MODULES_URL, [{"activity": self.activity.pk}])

        self.assertEqual(resp.status_code, 403)
        self.assertProjectUnlocked()

    def test_member_without_add_modules_is_refused_without_locking_the_project(self):
        resp = self.post_as(self.read_only_member(), MODULES_URL, {"activity": self.activity.pk})

        self.assertEqual(resp.status_code, 403)
        self.assertProjectUnlocked()

    def test_member_without_add_modules_creating_a_submodule_is_refused_without_locking_the_project(self):
        parent = InputFactory(activity=self.activity)

        resp = self.post_as(self.read_only_member(), SUBMODULES_URL, {"parent": parent.pk})

        self.assertEqual(resp.status_code, 403)
        self.assertProjectUnlocked()
        self.assertFalse(parent.input_entries.exists())

    def test_list_reaching_into_a_foreign_project_is_refused_without_locking_either_project(self):
        foreign_project = calculable_project(UserFactory(email="module-create-foreign-owner@example.com"))
        foreign_activity = ActivityFactory(project=foreign_project, name="Foreign activity")
        foreign_activity.module_types.add(ModuleType.objects.get(class_name="Input"))

        payload = [{"activity": self.activity.pk}, {"activity": foreign_activity.pk}]

        resp = self.post_as(self.owner, MODULES_URL, payload)

        self.assertEqual(resp.status_code, 403)
        self.assertProjectUnlocked()
        self.assertProjectUnlocked(foreign_project)

    def test_outsider_creating_a_land_module_does_not_save_the_land_use_change(self):
        grassland = ModuleType.objects.get(class_name="Grassland")
        self.activity.module_types.add(grassland)
        # Saving a Land Use Change reads its start, with and without modules, so the activity needs one.
        GrasslandFactory(activity=self.activity)
        land_use_change = LandUseChangeFactory(
            activity=self.activity,
            module_type_start=grassland,
            module_type_w=grassland,
            module_type_wo=grassland,
        )
        history_rows_before = land_use_change.history.count()

        resp = self.post_as(self.outsider, LAND_MODULES_URL, {"activity": self.activity.pk})

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(land_use_change.history.count(), history_rows_before)
        self.assertEqual(Grassland.objects.filter(activity=self.activity).count(), 1)
        self.assertProjectUnlocked()

    def test_anonymous_caller_is_asked_to_authenticate_whatever_the_payload(self):
        for payload in ({}, [], {"activity": "not-an-id"}, {"activity": self.activity.pk}):
            with self.subTest(payload=payload):
                resp = self.client.post(MODULES_URL, payload, format="json")

                self.assertEqual(resp.status_code, 401)
        self.assertProjectUnlocked()

    def test_nonexistent_target_is_refused_like_a_foreign_one(self):
        missing_activity_pk = unused_activity_pk()

        resp = self.post_as(self.outsider, MODULES_URL, {"activity": missing_activity_pk})

        self.assertEqual(resp.status_code, 403)

    def test_superuser_with_nonexistent_target_gets_the_validation_error(self):
        superuser = UserFactory(email="module-create-superuser@example.com", is_superuser=True)
        missing_activity_pk = unused_activity_pk()

        resp = self.post_as(superuser, MODULES_URL, {"activity": missing_activity_pk})

        self.assertEqual(resp.status_code, 400)
        self.assertIn("activity", resp.data)

    def test_malformed_target_id_gets_the_validation_error(self):
        resp = self.post_as(self.outsider, MODULES_URL, {"activity": "not-an-id"})

        self.assertEqual(resp.status_code, 400)
        self.assertIn("activity", resp.data)

    def test_member_with_add_modules_creates_the_module_and_holds_the_lock(self):
        resp = self.post_as(self.owner, MODULES_URL, {"activity": self.activity.pk})

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Input.objects.filter(activity=self.activity).exists())
        project = Project.objects.get(pk=self.project.pk)
        self.assertEqual((project.is_locked, project.locked_by), (True, self.owner))
