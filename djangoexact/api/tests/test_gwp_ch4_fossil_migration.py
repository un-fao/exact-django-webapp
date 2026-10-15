"""ipcc/0067 sets the fossil CH4 GWPs from the reference sheet and drops stale cached results.

Cached module results do not expire when reference data changes, so the
migration has to null them for open projects on the changed GWP sets, or
reports keep serving numbers computed with the old 0.
"""

from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from api.models import Energy, EnergyEntry, Group, Project
from api.tests.factories import ActivityFactory, ProjectFactory, UserFactory
from ipcc.models import GlobalWarmingPotential

migration = import_module("ipcc.migrations.0067_globalwarmingpotential_ch4_fossil_reference_values")

AR5_WITH = "IPCC Fifth Assessment Report (AR5) with Climate Change Feedback"


class Ch4FossilMigrationTestCase(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name="Admin")
        GlobalWarmingPotential.objects.filter(name__in=migration.CH4_FOSSIL).update(ch4_fossil=0.0)
        self.gwp = GlobalWarmingPotential.objects.get(name=AR5_WITH)
        user = UserFactory(email="gwp-migration@example.com")
        self.open_project = ProjectFactory(owner=user, gw_potential=self.gwp)
        self.finalized_project = ProjectFactory(owner=user, gw_potential=self.gwp)
        self.override_project = ProjectFactory(owner=user, gw_potential=self.gwp, gwp_ch4_fossil_t2=40.0)
        self.energies = {}
        for project in (self.open_project, self.finalized_project, self.override_project):
            energy = Energy.objects.create(activity=ActivityFactory(project=project))
            EnergyEntry.objects.create(parent=energy)
            self.energies[project.pk] = energy.pk
        # update() bypasses save(), which would itself touch the caches and the finalized guard.
        Project.objects.filter(pk=self.finalized_project.pk).update(is_finalized=True)
        now = timezone.now()
        Energy.objects.all().update(last_cached_at=now, cached_results_total={"x": 1})
        EnergyEntry.objects.all().update(last_cached_at=now, cached_results_total={"x": 1})

    def run_migration(self):
        migration.set_ch4_fossil(apps, None)

    def cache_of(self, project):
        energy = Energy.objects.get(pk=self.energies[project.pk])
        entry = EnergyEntry.objects.get(parent=energy)
        return energy.last_cached_at, entry.last_cached_at

    def test_sets_reference_values(self):
        self.run_migration()
        values = dict(GlobalWarmingPotential.objects.filter(name__in=migration.CH4_FOSSIL).values_list("name", "ch4_fossil"))
        self.assertEqual(
            values,
            {
                "IPCC Second Assessment Report (SAR)": 21.0,
                "IPCC Fourth Assessment Report (AR4)": 25.0,
                "IPCC Fifth Assessment Report (AR5) without Climate Change Feedback": 30.0,
                AR5_WITH: 36.0,
            },
        )

    def test_invalidates_module_and_submodule_caches_of_open_projects(self):
        self.run_migration()
        self.assertEqual(self.cache_of(self.open_project), (None, None))

    def test_keeps_caches_of_finalized_and_overridden_projects(self):
        self.run_migration()
        self.assertNotIn(None, self.cache_of(self.finalized_project))
        self.assertNotIn(None, self.cache_of(self.override_project))

    def test_rerun_on_current_values_touches_no_cache(self):
        self.run_migration()
        Energy.objects.all().update(last_cached_at=timezone.now())
        self.run_migration()
        self.assertIsNotNone(Energy.objects.get(pk=self.energies[self.open_project.pk]).last_cached_at)
