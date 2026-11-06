"""No translated reference name in the committed fixtures has surrounding whitespace.

Run with:
    python manage.py test api.tests.test_reference_name_whitespace
"""
import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase
from modeltranslation.translator import translator
from modeltranslation.utils import get_translation_fields

from api.fixtures_manifest import MANIFEST


class ReferenceNameWhitespaceTestCase(SimpleTestCase):
    def test_translated_fields_in_fixtures_are_stripped(self):
        offenders = []
        for spec in MANIFEST:
            model = apps.get_model(spec.model)
            if model not in translator.get_registered_models():
                continue
            base_fields = translator.get_options_for_model(model).fields
            fields = {*base_fields, *get_translation_fields(*base_fields)}
            path = Path(settings.BASE_DIR) / spec.app / "fixtures" / spec.fixture_file
            for row in json.loads(path.read_text(encoding="utf-8")):
                for field in fields:
                    value = row["fields"].get(field)
                    if isinstance(value, str) and value != value.strip():
                        offenders.append(f"{spec.model} pk={row['pk']} {field}={value!r}")
        self.assertEqual(offenders, [])
