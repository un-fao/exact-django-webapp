from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework import status
from django.urls import reverse
from api.views import generic_module_viewset
import api.models as models
import ipcc.models as ipcc_models
import api.tests.factories as factories
from rest_framework.test import force_authenticate
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyChoice, FuzzyFloat
import logging as log
from api.tests.unit.utils import APITestCaseMixin
from api import serializers
import copy
from . import base_module


class WaterbodyTestCase(base_module.BaseModuleTestCase):
    def create_project(self):
        # Tier 1 CH4 factors exist for only some climate/moisture pairs; a random pair without one
        # made results and defaults fail at random.
        ef = ipcc_models.OtherConstructedWaterbodiesEmissionFactor.objects.order_by("pk").first()
        self.project_data.update(climate=ef.climate_id, moisture=ef.moisture_id)
        return super().create_project()

    def setUp(self):
        self.ModuleClass = models.Waterbody
        super().setUp()

        self.land_use_types = self.land_use_types.filter(module_types__class_name=self.ModuleClass.__name__, climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        self.validated_data = {
            "waterbody_type": models.WaterbodyType.objects.filter(is_reservoir=False).order_by("?").first().id,
            "area": FuzzyInteger(1, 100).fuzz(),
            "trophic_type_start": models.TrophicType.objects.order_by("?").first().id,
            "trophic_type_w": models.TrophicType.objects.order_by("?").first().id,
            "trophic_type_wo": models.TrophicType.objects.order_by("?").first().id,
        }

        self.edit_module(self.module, self.user, self.validated_data)
        self.module.refresh_from_db()

    def test_modify(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["waterbody_type"] = models.WaterbodyType.objects.filter(is_reservoir=False).order_by("?").first().id
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "READY")

    def test_patch_to_not_ready(self):

        validated_data = copy.deepcopy(self.validated_data)
        validated_data["waterbody_type"] = None
        response = self.edit_module(self.module, self.user, validated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"]["name"], "EMPTY")

    def test_calculate_results(self):

        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-results", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("balance" in response.data)

    def test_get_defaults(self):

        view = self.module_viewset.as_view({"get": "defaults"})
        request = self.request_factory.get(reverse(f"{self.ModuleClass.__name__.lower()}-defaults", args=[self.module.pk]), format="json")

        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(type(response.data) == dict)

    def test_bom_waterbody_type_merge_keeps_modules(self):
        from importlib import import_module

        from django.apps import apps as django_apps

        clean = models.WaterbodyType.objects.get(name="Freshwater Pond")
        dup = models.WaterbodyType.objects.create(name="\ufeffFreshwater Pond", name_en="\ufeffFreshwater Pond")
        ef = ipcc_models.OtherConstructedWaterbodiesEmissionFactor.objects.filter(waterbody_type=clean).first()
        ipcc_models.OtherConstructedWaterbodiesEmissionFactor.objects.create(waterbody_type=dup, climate=ef.climate, moisture=ef.moisture, value=1)
        models.Waterbody.objects.filter(pk=self.module.pk).update(waterbody_type=dup)

        import_module("api.migrations.0299_merge_bom_waterbody_type").merge_bom_waterbody_types(django_apps, None)

        self.module.refresh_from_db()
        self.assertEqual(self.module.waterbody_type_id, clean.pk)
        self.assertFalse(models.WaterbodyType.objects.filter(name__startswith="\ufeff").exists())
        self.assertEqual(ipcc_models.OtherConstructedWaterbodiesEmissionFactor.objects.filter(waterbody_type=clean, climate=ef.climate, moisture=ef.moisture).count(), 1)
