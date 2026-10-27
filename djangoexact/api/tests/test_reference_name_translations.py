"""Migration 0298 fills the report's missing ProjectStatus and ModuleType translations.

Run with:
    python manage.py test api.tests.test_reference_name_translations --keepdb
"""
from __future__ import annotations

from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.utils.translation import override

from api.models import ModuleType, ProjectStatus

migration = import_module("api.migrations.0298_translate_projectstatus_and_moduletype_names")


def _module_type(name_en, **names):
    row, _ = ModuleType.objects.get_or_create(name_en=name_en, defaults={"name": name_en})
    for field in ("name_fr", "name_es", "name_ru"):
        setattr(row, field, names.get(field))
    row.save()
    return row


class ReferenceNameTranslationMigrationTestCase(TestCase):
    def test_project_status_follows_the_active_language(self):
        ProjectStatus.objects.filter(value=3).delete()
        status = ProjectStatus.objects.create(name="Terminal Evaluation", value=3)

        migration.forwards(apps, None)

        status.refresh_from_db()
        with override("fr"):
            self.assertEqual(str(status), "Évaluation finale")
        with override("en"):
            self.assertEqual(str(status), "Terminal Evaluation")

    def test_blank_and_english_copies_are_filled_but_real_translations_are_kept(self):
        grassland = _module_type("Grassland", name_fr="Prairie (saisie manuelle)")
        processing = _module_type("Processing", name_fr="Transformation\n", name_es="Processing")

        migration.forwards(apps, None)

        grassland.refresh_from_db()
        processing.refresh_from_db()
        self.assertEqual(grassland.name_fr, "Prairie (saisie manuelle)")
        self.assertEqual(grassland.name_es, "Pastizales")
        self.assertEqual(processing.name_es, "Procesamiento")
        self.assertEqual(processing.name_fr, "Transformation")
