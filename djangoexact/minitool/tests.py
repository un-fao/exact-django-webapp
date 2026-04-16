from django.db import router
from django.test import SimpleTestCase, TestCase

from minitool.models import (
    ChangeAggregate,
    ChangeRecord,
    EmissionScenario,
    EmissionScenarioCategory,
    EmissionStatisticsByModule,
    Entry,
    StatisticsModuleTotal,
)

# Create your tests here.


class RoutingRegressionTest(SimpleTestCase):
    """
    Guardrail for the minitool SQLite → Postgres migration (PR 1).
    After this PR lands, every minitool model must route to the default DB.
    """

    databases = {"default"}

    def test_all_minitool_models_route_to_default(self):
        models = [
            Entry,
            StatisticsModuleTotal,
            EmissionStatisticsByModule,
            ChangeRecord,
            ChangeAggregate,
            EmissionScenarioCategory,
            EmissionScenario,
        ]
        for model in models:
            with self.subTest(model=model.__name__):
                self.assertEqual(
                    router.db_for_write(model),
                    "default",
                    f"{model.__name__} must route to default DB after migration",
                )
