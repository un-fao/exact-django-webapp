"""Database-free checks for IPCC bounds in module defaults."""

import os
from types import SimpleNamespace
from unittest.mock import patch

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
os.environ.setdefault("DJANGO_DEBUG", "True")
django.setup()

from django.test import SimpleTestCase  # noqa: E402

from api.defaults import BuildingDefaults, CoastalWetlandDefaults, DefaultsFactory, FuelDefaults, _with_ranges  # noqa: E402
from ipcc.models import BuildingEmissionFactor, EnergyDefaultEmissionFactor  # noqa: E402


class DefaultUncertaintyTests(SimpleTestCase):
    def test_building_defaults_include_bounds_from_selected_ipcc_row(self):
        row = BuildingEmissionFactor(value=12, value_min=10, value_max=15)
        calculator = SimpleNamespace(ef=row, get_defaults=lambda calculate=False: None)
        provider = object.__new__(BuildingDefaults)
        provider.input = object()

        with patch("api.defaults.calcs.BuildingCalculator", return_value=calculator):
            values = provider.get_defaults()

        for scenario in ("start", "w", "wo"):
            name = f"ef_t2_{scenario}_default"
            self.assertEqual(getattr(values, name), 12)
            self.assertEqual(getattr(values, f"{name}_min"), 10)
            self.assertEqual(getattr(values, f"{name}_max"), 15)

    def test_replaced_or_unpublished_values_have_no_claimed_range(self):
        row = BuildingEmissionFactor(value=12, value_min=10, value_max=15)
        replaced = _with_ranges(SimpleNamespace(ef_t2_w_default=20), [(('ef_t2_w_default',), row, 'value')])
        self.assertIsNone(replaced.ef_t2_w_default_min)
        self.assertIsNone(replaced.ef_t2_w_default_max)

        row.value_min = row.value_max = None
        unpublished = _with_ranges(SimpleNamespace(ef_t2_w_default=12), [(('ef_t2_w_default',), row, 'value')])
        self.assertIsNone(unpublished.ef_t2_w_default_min)
        self.assertIsNone(unpublished.ef_t2_w_default_max)

    def test_fuel_defaults_use_each_scenarios_selected_row(self):
        rows = [EnergyDefaultEmissionFactor(co2=number, co2_min=number - 1, co2_max=number + 1) for number in (10, 20, 30)]
        calculator = SimpleNamespace(
            energy_ef_default_start=rows[0],
            energy_ef_default_w=rows[1],
            energy_ef_default_wo=rows[2],
            get_defaults=lambda calculate=False: None,
        )
        provider = object.__new__(FuelDefaults)
        provider.input = object()

        with patch("api.defaults.calcs.FuelCalculator", return_value=calculator):
            values = provider.get_defaults()

        for scenario, number in zip(("start", "w", "wo"), (10, 20, 30)):
            name = f"energy_ef_co2_t2_{scenario}_default"
            self.assertEqual(getattr(values, name), number)
            self.assertEqual(getattr(values, f"{name}_min"), number - 1)
            self.assertEqual(getattr(values, f"{name}_max"), number + 1)

    def test_unready_module_has_null_bounds(self):
        class PlaceholderDefaults:
            def __init__(self, input):
                self.values = SimpleNamespace(ef_t2_w_default=0, country_t2_default="Italy")

        with patch("api.defaults._get_defaults_class", return_value=PlaceholderDefaults):
            values = DefaultsFactory.get_defaults(SimpleNamespace(is_ready=lambda: False))

        self.assertIsNone(values.ef_t2_w_default_min)
        self.assertIsNone(values.ef_t2_w_default_max)
        self.assertFalse(hasattr(values, "country_t2_default_min"))

    def test_every_numeric_default_has_bound_keys_for_ready_modules(self):
        for returned in (
            SimpleNamespace(ef_t2_w_default=12, ef_t2_w_default_min=10, ef_t2_w_default_max=15, fui_t2_w_default=3.5, country_t2_default="Italy"),
            {"ef_t2_w_default": 12, "ef_t2_w_default_min": 10, "ef_t2_w_default_max": 15, "fui_t2_w_default": 3.5, "country_t2_default": "Italy"},
        ):
            class ReadyDefaults:
                def __init__(self, input):
                    pass

                def get_defaults(self, calculate=False, returned=returned):
                    return returned

            with patch("api.defaults._get_defaults_class", return_value=ReadyDefaults):
                values = DefaultsFactory.get_defaults(SimpleNamespace(is_ready=lambda: True))

            fields = values if isinstance(values, dict) else vars(values)
            self.assertEqual((fields["ef_t2_w_default_min"], fields["ef_t2_w_default_max"]), (10, 15))
            self.assertIsNone(fields["fui_t2_w_default_min"])
            self.assertIsNone(fields["fui_t2_w_default_max"])
            self.assertNotIn("country_t2_default_min", fields)

    def test_coastal_wetland_litter_and_deadwood_defaults_per_scenario(self):
        row = lambda value: SimpleNamespace(value=value)  # noqa: E731
        calculator = SimpleNamespace(
            agb_default=row(1), bgb_default=row(1), soil_1m=row(1), pc_c_lost_excavation=row(1),
            ef_drainage=row(1), rewetting_c=row(1), rewetting_ch4=row(1), salinity_type=row("<18"),
            soil_type_name="Mineral", litter=row(0.7), dw=row(10.7),
            get_defaults=lambda calculate=False: None,
        )
        provider = object.__new__(CoastalWetlandDefaults)
        provider.input = object()

        with patch("api.defaults.calcs.CoastalWetlandCalculator", return_value=calculator):
            values = provider.get_defaults()

        for scenario in ("start", "w", "wo"):
            self.assertEqual(getattr(values, f"litter_t2_{scenario}_default"), 0.7)
            self.assertEqual(getattr(values, f"deadwood_t2_{scenario}_default"), 10.7)
