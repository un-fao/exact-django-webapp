"""Tests for the reference-data natural-key registry and its duplicate detector.

Django `TestCase`, not pytest: this project has no pytest-django, so anything
touching the ORM must subclass Django's test classes.

These run against a database that may already hold the committed reference
fixtures (`manage.py test --keepdb` on a seeded database), so every row the
tests need is created with `get_or_create` on a distinctive name rather than
assumed absent or assumed present.
"""

import io
import json

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase
from django.utils.translation import override

from api import models
from ipcc.models import GlobalWarmingPotential
from api.natural_keys import (
    COUNTRY_NAME_ALIASES,
    NATURAL_KEY_SPECS,
    LegacyReferenceIdError,
    ReferenceResolutionError,
    UnresolvableNaturalKeyError,
    natural_key_for,
    natural_key_for_pk,
    resolve_natural_key,
    spec_for,
    verify_legacy_reference_pk,
)


class NaturalKeyRegistryIntegrityTests(TestCase):
    """A typo in the registry must fail here, not in production at import time."""

    def test_every_entry_names_a_resolvable_model(self):
        for label in NATURAL_KEY_SPECS:
            with self.subTest(label=label):
                model = apps.get_model(label)
                self.assertEqual(model._meta.label, label)

    def test_every_field_path_resolves_against_its_model(self):
        for label, spec in NATURAL_KEY_SPECS.items():
            model = apps.get_model(label)
            for path in spec.fields:
                with self.subTest(label=label, path=path):
                    current = model
                    for part in path.split("__"):
                        field = current._meta.get_field(part)
                        if field.is_relation:
                            current = field.related_model
                    self.assertIsNotNone(field)

    def test_label_matches_the_registry_key(self):
        for label, spec in NATURAL_KEY_SPECS.items():
            with self.subTest(label=label):
                self.assertEqual(spec.label, label)

    def test_global_warming_potential_is_registered(self):
        # Highest priority entry: disjoint pk ranges plus a NOT NULL FK on
        # Project is what makes every online-to-offline import fail at row one.
        self.assertIn("ipcc.GlobalWarmingPotential", NATURAL_KEY_SPECS)
        self.assertEqual(NATURAL_KEY_SPECS["ipcc.GlobalWarmingPotential"].fields, ("name_en",))

    def test_fuel_type_key_is_composite(self):
        self.assertEqual(
            NATURAL_KEY_SPECS["api.FuelType"].fields,
            ("name_en", "fuel_use_type__name_en", "macro_fuel_type__name_en"),
        )


class NaturalKeyEncodeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.climate, _ = models.Climate.objects.get_or_create(
            name_en="Tropical", defaults={"name": "Tropical"}
        )

    def test_natural_key_for_returns_the_english_name(self):
        self.assertEqual(natural_key_for(self.climate), ("Tropical",))

    def test_natural_key_is_language_independent(self):
        # An export produced under ?lang=fr must not emit French keys.
        self.climate.name_fr = "Tropical (fr)"
        self.climate.save(update_fields=["name_fr"])

        with override("fr"):
            self.assertEqual(natural_key_for(self.climate), ("Tropical",))
            self.assertEqual(
                natural_key_for_pk(models.Climate, self.climate.pk), ("Tropical",)
            )

    def test_unregistered_model_returns_none(self):
        region, _ = models.Region.objects.get_or_create(name="NK Test Region")

        self.assertIsNone(spec_for(models.Region))
        self.assertIsNone(natural_key_for(region))
        self.assertIsNone(natural_key_for_pk(models.Region, region.pk))

    def test_null_pk_returns_none(self):
        self.assertIsNone(natural_key_for_pk(models.Climate, None))

    def test_missing_row_returns_none(self):
        missing_pk = models.Climate.objects.order_by("-pk").first().pk + 1000

        self.assertIsNone(natural_key_for_pk(models.Climate, missing_pk))

    def test_cache_is_populated_and_reused(self):
        cache = {}

        first = natural_key_for_pk(models.Climate, self.climate.pk, cache=cache)
        with self.assertNumQueries(0):
            second = natural_key_for_pk(models.Climate, self.climate.pk, cache=cache)

        self.assertEqual(first, ("Tropical",))
        self.assertEqual(second, ("Tropical",))


class NaturalKeyResolveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.climate, _ = models.Climate.objects.get_or_create(
            name_en="Tropical", defaults={"name": "Tropical"}
        )
        cls.turkiye, _ = models.Country.objects.get_or_create(name="Türkiye")

        cls.use_type, _ = models.FuelUseType.objects.get_or_create(
            name_en="NK Stationary", defaults={"name": "NK Stationary"}
        )
        cls.macro_type, _ = models.MacroFuelType.objects.get_or_create(
            name_en="NK Fossil", defaults={"name": "NK Fossil"}
        )
        cls.fuel_type, _ = models.FuelType.objects.get_or_create(
            name_en="NK Diesel",
            fuel_use_type=cls.use_type,
            macro_fuel_type=cls.macro_type,
            defaults={"name": "NK Diesel"},
        )
        cls.macroless_fuel_type, _ = models.FuelType.objects.get_or_create(
            name_en="NK Macroless",
            fuel_use_type=cls.use_type,
            macro_fuel_type=None,
            defaults={"name": "NK Macroless"},
        )

    def test_resolves_to_the_local_pk(self):
        self.assertEqual(
            resolve_natural_key(models.Climate, ("Tropical",)), self.climate.pk
        )

    def test_unknown_key_raises(self):
        with self.assertRaises(UnresolvableNaturalKeyError) as ctx:
            resolve_natural_key(models.Climate, ("Nonexistent",))

        message = str(ctx.exception)
        self.assertIn("api.Climate", message)
        self.assertIn("Nonexistent", message)
        self.assertIn("does not exist in this installation", message)

    def test_country_rename_resolves_through_the_alias_table(self):
        self.assertIn("Turkey", COUNTRY_NAME_ALIASES)

        self.assertEqual(
            resolve_natural_key(models.Country, ("Turkey",)), self.turkiye.pk
        )

    def test_country_literal_name_wins_over_the_alias(self):
        literal, _ = models.Country.objects.get_or_create(name="Turkey")

        self.assertEqual(
            resolve_natural_key(models.Country, ("Turkey",)), literal.pk
        )

    def test_unaliased_country_rename_raises_rather_than_guessing(self):
        with self.assertRaises(UnresolvableNaturalKeyError):
            resolve_natural_key(models.Country, ("Definitely Not A Country",))

    def test_composite_key_resolves(self):
        key = ("NK Diesel", "NK Stationary", "NK Fossil")

        self.assertEqual(
            resolve_natural_key(models.FuelType, key), self.fuel_type.pk
        )

    def test_composite_key_with_a_null_member_resolves(self):
        # macro_fuel_type is nullable, so None is part of the identity and must
        # become an isnull lookup rather than an equality test against NULL.
        key = ("NK Macroless", "NK Stationary", None)

        self.assertEqual(
            resolve_natural_key(models.FuelType, key), self.macroless_fuel_type.pk
        )

    def test_composite_encode_and_decode_round_trip(self):
        key = natural_key_for(self.fuel_type)

        self.assertEqual(key, ("NK Diesel", "NK Stationary", "NK Fossil"))
        self.assertEqual(resolve_natural_key(models.FuelType, key), self.fuel_type.pk)

    def test_wrong_key_arity_raises(self):
        with self.assertRaises(UnresolvableNaturalKeyError) as ctx:
            resolve_natural_key(models.FuelType, ("NK Diesel",))

        self.assertIn("Expected 3 key component(s)", str(ctx.exception))

    def test_unregistered_model_raises_rather_than_returning_none(self):
        with self.assertRaises(UnresolvableNaturalKeyError) as ctx:
            resolve_natural_key(models.Region, ("NK Test Region",))

        self.assertIn("no declared natural key", str(ctx.exception))

    def test_empty_key_raises(self):
        with self.assertRaises(UnresolvableNaturalKeyError):
            resolve_natural_key(models.Climate, ("",))

    def test_resolution_is_language_independent(self):
        self.climate.name_fr = "Tropical (fr)"
        self.climate.save(update_fields=["name_fr"])

        with override("fr"):
            self.assertEqual(
                resolve_natural_key(models.Climate, ("Tropical",)), self.climate.pk
            )

    def test_cache_is_populated_and_reused(self):
        cache = {}

        resolve_natural_key(models.Climate, ("Tropical",), cache=cache)
        with self.assertNumQueries(0):
            again = resolve_natural_key(models.Climate, ("Tropical",), cache=cache)

        self.assertEqual(again, self.climate.pk)


class LegacyReferenceIdVerifyTests(TestCase):
    """`verify_legacy_reference_pk`: the formatVersion 1 path.

    A v1 payload carries no natural key, so its integers are the exporting
    installation's private identifiers. Before this existed they were written
    straight into the FK column and the database rejected them several frames
    later as a bare "FOREIGN KEY constraint failed" naming neither table nor
    column. The verifier's whole job is to turn that into a named refusal at the
    point the bad value is read.
    """

    @classmethod
    def setUpTestData(cls):
        # co2/ch4/n2o are all non-null FloatFields with no default.
        cls.gwp, _ = GlobalWarmingPotential.objects.get_or_create(
            name_en="Legacy Verify AR6",
            defaults={
                "name": "Legacy Verify AR6",
                "co2": 1.0,
                "ch4": 27.2,
                "n2o": 273.0,
            },
        )

    def _absent_pk(self):
        """A pk one past the highest that exists, so it cannot collide."""
        return (
            GlobalWarmingPotential.objects.order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        ) + 1

    def test_existing_pk_passes_through_unchanged(self):
        self.assertEqual(
            verify_legacy_reference_pk(
                GlobalWarmingPotential, "gw_potential", self.gwp.pk
            ),
            self.gwp.pk,
        )

    def test_absent_pk_raises_naming_model_field_and_id(self):
        absent = self._absent_pk()

        with self.assertRaises(LegacyReferenceIdError) as ctx:
            verify_legacy_reference_pk(
                GlobalWarmingPotential, "gw_potential", absent
            )

        message = str(ctx.exception)
        self.assertIn("ipcc.GlobalWarmingPotential", message)
        self.assertIn("gw_potential", message)
        self.assertIn(str(absent), message)

    def test_message_tells_the_user_what_to_do(self):
        with self.assertRaises(LegacyReferenceIdError) as ctx:
            verify_legacy_reference_pk(
                GlobalWarmingPotential, "gw_potential", self._absent_pk()
            )

        message = str(ctx.exception)
        # The remedy is the only part of this the user can act on, and it is the
        # reason the error exists at all rather than a bare integrity error.
        self.assertIn("file format 1", message)
        self.assertIn("Export the project again", message)

    def test_error_is_a_reference_resolution_error(self):
        """import_project catches the base, so both encodings must share it."""
        self.assertTrue(
            issubclass(LegacyReferenceIdError, ReferenceResolutionError)
        )
        self.assertTrue(
            issubclass(UnresolvableNaturalKeyError, ReferenceResolutionError)
        )

    def test_boundary_pks_are_rejected_not_treated_as_absent_sentinels(self):
        # 0 and negatives are not "no value": they are ids that do not exist.
        # A guard keyed on truthiness would let 0 through to the database.
        for pk in (0, -1):
            with self.subTest(pk=pk):
                with self.assertRaises(LegacyReferenceIdError):
                    verify_legacy_reference_pk(
                        GlobalWarmingPotential, "gw_potential", pk
                    )

    def test_hit_is_cached_and_not_requeried(self):
        cache = {}

        verify_legacy_reference_pk(
            GlobalWarmingPotential, "gw_potential", self.gwp.pk, cache=cache
        )
        with self.assertNumQueries(0):
            again = verify_legacy_reference_pk(
                GlobalWarmingPotential, "gw_potential", self.gwp.pk, cache=cache
            )

        self.assertEqual(again, self.gwp.pk)

    def test_miss_is_cached_and_still_raises(self):
        """A payload naming the same bad id on 400 modules costs one query."""
        cache = {}
        absent = self._absent_pk()

        with self.assertRaises(LegacyReferenceIdError):
            verify_legacy_reference_pk(
                GlobalWarmingPotential, "gw_potential", absent, cache=cache
            )
        with self.assertNumQueries(0):
            with self.assertRaises(LegacyReferenceIdError):
                verify_legacy_reference_pk(
                    GlobalWarmingPotential, "gw_potential", absent, cache=cache
                )

    def test_verify_cache_does_not_collide_with_the_resolve_cache(self):
        """Both share one dict per import request, under separate namespaces."""
        cache = {}

        verify_legacy_reference_pk(
            GlobalWarmingPotential, "gw_potential", self.gwp.pk, cache=cache
        )
        resolved = resolve_natural_key(
            GlobalWarmingPotential, ("Legacy Verify AR6",), cache=cache
        )

        self.assertEqual(resolved, self.gwp.pk)


class CheckReferenceNaturalKeysCommandTests(TestCase):
    """The duplicate detector, exercised through `api.Unit`.

    Unit is the one registered model with no uniqueness constraint (the shipped
    offline database holds 66 duplicate and 100 blank-named rows, so the
    constraint was withheld rather than deduping reference data). That makes it
    the only model where duplicates can be created to test the detector.
    """

    def _run(self, **kwargs):
        out = io.StringIO()
        try:
            call_command("check_reference_natural_keys", stdout=out, **kwargs)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_clean_database_exits_zero(self):
        output, code = self._run(models="api.Climate")

        self.assertEqual(code, 0)
        self.assertIn("No duplicate or empty natural keys", output)

    def test_duplicates_are_reported_with_model_key_and_pks(self):
        first = models.Unit.objects.create(name="NK Duplicated Unit")
        second = models.Unit.objects.create(name="NK Duplicated Unit")

        output, code = self._run(models="api.Unit")

        self.assertEqual(code, 1)
        self.assertIn("DUPLICATE", output)
        self.assertIn("api.Unit", output)
        self.assertIn("NK Duplicated Unit", output)
        self.assertIn(str(first.pk), output)
        self.assertIn(str(second.pk), output)

    def test_blank_key_component_is_reported(self):
        blank = models.Unit.objects.create(name="")

        output, code = self._run(models="api.Unit")

        self.assertEqual(code, 1)
        self.assertIn("EMPTY KEY", output)
        self.assertIn(str(blank.pk), output)

    def test_json_output_is_machine_readable(self):
        models.Unit.objects.create(name="NK Json Unit")
        models.Unit.objects.create(name="NK Json Unit")

        output, code = self._run(models="api.Unit", as_json=True)

        self.assertEqual(code, 1)
        payload = json.loads(output[output.index("{"):])
        duplicates = [f for f in payload["findings"] if f["kind"] == "duplicate"]
        self.assertTrue(any(f["key"] == ["NK Json Unit"] for f in duplicates))
        self.assertTrue(all(f["model"] == "api.Unit" for f in payload["findings"]))


class NaturalKeyUniquenessConstraintTests(TestCase):
    """The constraints that make the keys trustworthy actually exist."""

    def test_constrained_models_declare_their_constraint(self):
        expected = {
            models.Climate: "uniq_climate_name_en",
            models.Moisture: "uniq_moisture_name_en",
            models.SoilType: "uniq_soil_type_name_en",
            models.ForestType: "uniq_forest_type_name_en",
            models.LandUseType: "uniq_land_use_type_name_en",
            models.SettlementType: "uniq_settlement_type_name_en",
            models.FireType: "uniq_fire_type_name_en",
            models.TrophicType: "uniq_trophic_type_name_en",
            models.ProjectStatus: "uniq_project_status_name",
            models.FuelType: "uniq_fuel_type_name_en_use_macro",
        }
        for model, name in expected.items():
            with self.subTest(model=model.__name__):
                names = {c.name for c in model._meta.constraints}
                self.assertIn(name, names)

    def test_global_warming_potential_is_constrained(self):
        gwp = apps.get_model("ipcc.GlobalWarmingPotential")

        self.assertIn("uniq_gwp_name_en", {c.name for c in gwp._meta.constraints})

    def test_translated_name_is_never_marked_unique_directly(self):
        # unique=True on a translated field propagates to every language column.
        for label in NATURAL_KEY_SPECS:
            model = apps.get_model(label)
            if not hasattr(model, "name_en"):
                continue
            with self.subTest(label=label):
                self.assertFalse(
                    model._meta.get_field("name_en").unique
                    and not model._meta.get_field("name").unique,
                    f"{label}.name_en is uniquely constrained without name being unique",
                )

    def test_unit_has_no_uniqueness_constraint_by_decision(self):
        # Withheld on purpose: the shipped offline database holds duplicate and
        # blank-named Unit rows, and deduping reference data to force the
        # constraint through was refused. See 260813-fvj-DUPLICATES.md.
        self.assertEqual(models.Unit._meta.constraints, [])
