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

        self.land_use_types = models.LandUseType.objects.all()
