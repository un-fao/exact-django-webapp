"""Database-free unit tests for api.results_cache.

All tests here are django.test.SimpleTestCase (or plain assertions inside one), so the
module runs locally with `manage.py test api.tests.test_results_cache` even though this
sandbox has no Postgres. Anything that needs a database (the read/write/clear_for_projects
functions, which touch ProjectResultCache) belongs in
api/tests/test_project_results_cache_api.py instead, not here.
"""

import string
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from api import results_cache
from api.services import results_jobs


class BuildCacheKeyTests(SimpleTestCase):
    def test_order_does_not_create_a_second_entry(self):
        self.assertEqual(results_cache.build_cache_key([2, 1]), results_cache.build_cache_key([1, 2]))

    def test_duplicates_collapse(self):
        self.assertEqual(results_cache.build_cache_key([1, 1, 2]), results_cache.build_cache_key([1, 2]))

    def test_empty_list_is_stable_and_distinct(self):
        empty_key = results_cache.build_cache_key([])
        self.assertEqual(empty_key, results_cache.build_cache_key([]))
        self.assertNotEqual(empty_key, results_cache.build_cache_key([1]))

    def test_string_and_int_pks_collapse(self):
        self.assertEqual(results_cache.build_cache_key(["1", 2]), results_cache.build_cache_key([1, 2]))

    def test_key_is_64_lowercase_hex_characters(self):
        key = results_cache.build_cache_key([1, 2, 3])
        self.assertEqual(len(key), 64)
        self.assertTrue(set(key).issubset(set(string.hexdigits.lower())))
        self.assertEqual(key, key.lower())

    def test_schema_version_change_changes_the_key(self):
        activity_pks = [1, 2]
        original_key = results_cache.build_cache_key(activity_pks)
        with mock.patch.object(results_cache, "RESULTS_SCHEMA_VERSION", results_cache.RESULTS_SCHEMA_VERSION + 1):
            bumped_key = results_cache.build_cache_key(activity_pks)
        self.assertNotEqual(original_key, bumped_key)


class NormalizePayloadTests(SimpleTestCase):
    def test_round_trips_decimal_and_datetime_to_plain_json_types(self):
        now = timezone.now()
        payload = {"amount": Decimal("12.50"), "computed_at": now, "nested": {"count": 3}}

        normalized = results_cache.normalize_payload(payload)

        self.assertIsInstance(normalized["amount"], (float, str))
        self.assertIsInstance(normalized["computed_at"], str)
        self.assertEqual(normalized["nested"], {"count": 3})

    def test_normalize_payload_is_idempotent(self):
        now = timezone.now()
        payload = {"amount": Decimal("12.50"), "computed_at": now}

        once = results_cache.normalize_payload(payload)
        twice = results_cache.normalize_payload(once)

        self.assertEqual(once, twice)


class IsSupersededTests(SimpleTestCase):
    def test_none_job_stamp_is_never_superseded(self):
        self.assertFalse(results_jobs.is_superseded(None, 5))

    def test_equal_stamps_are_not_superseded(self):
        self.assertFalse(results_jobs.is_superseded(5, 5))

    def test_lower_job_stamp_is_superseded(self):
        self.assertTrue(results_jobs.is_superseded(3, 5))
