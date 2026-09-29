"""Guards for the analyst narrative request boundary.

Milestone 3 is the first time user-supplied prose reaches the PDF engine, which
is version-pinned under a CVE exemption. Escaping happens in the template; what
happens here is everything that must fail *loudly* rather than quietly:

  - an over-cap value is a 400, never a truncation;
  - a misspelled field name is a 400, because DRF would otherwise drop it and
    the analyst would receive an un-editable PDF missing a passage they wrote,
    with nothing to notice;
  - narrative keyed to an activity the report does not contain is a 400, for
    the same reason;
  - a report whose template does not read narrative refuses it outright.

Run with:
    python manage.py test api.tests.reports.test_narrative
"""
from __future__ import annotations

import datetime
from unittest.mock import Mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from api.reports.narrative import clean_narrative, narrative_from_request


def _activities(*pks):
    return [Mock(pk=pk) for pk in pks]


def _request(body):
    return Mock(data=body)


class CleanNarrativeTestCase(SimpleTestCase):
    def test_full_payload_validates(self):
        narrative = clean_narrative(
            {
                "tier2_specification": "Dairy cattle productivity.",
                "data_limitations": "Tier 1 defaults for soil carbon.",
                "assumption_set_date": "2026-03-14",
                "top_activity_driver": "Avoided deforestation.",
                "additional_sources": ["Mwangi et al. (2021)."],
                "activities": {"41": {"wop": "Maize.", "wp": "Agroforestry.", "data_source": "PDR p. 37"}},
            },
            _activities(41, 42),
        )
        self.assertEqual(narrative["assumption_set_date"], datetime.date(2026, 3, 14))
        self.assertEqual(narrative["activities"]["41"]["data_source"], "PDR p. 37")

    def test_date_is_parsed_not_carried_as_text(self):
        """A real date cannot carry a payload, which takes one field off the boundary."""
        narrative = clean_narrative({"assumption_set_date": "2026-03-14"}, [])
        self.assertIsInstance(narrative["assumption_set_date"], datetime.date)

        with self.assertRaises(ValidationError):
            clean_narrative({"assumption_set_date": "<script>"}, [])

    def test_unknown_field_is_rejected_rather_than_dropped(self):
        with self.assertRaises(ValidationError) as caught:
            clean_narrative({"tier_2_specification": "typo"}, [])
        self.assertIn("tier_2_specification", str(caught.exception))

    def test_over_cap_values_are_rejected_not_truncated(self):
        for field, cap in (
            ("tier2_specification", 2000),
            ("data_limitations", 4000),
            ("top_activity_driver", 2000),
        ):
            with self.subTest(field=field):
                clean_narrative({field: "x" * cap}, [])
                with self.assertRaises(ValidationError):
                    clean_narrative({field: "x" * (cap + 1)}, [])

    def test_activity_field_caps(self):
        clean_narrative({"activities": {"41": {"wop": "x" * 4000}}}, _activities(41))
        with self.assertRaises(ValidationError):
            clean_narrative({"activities": {"41": {"wop": "x" * 4001}}}, _activities(41))
        with self.assertRaises(ValidationError):
            clean_narrative({"activities": {"41": {"data_source": "x" * 501}}}, _activities(41))

    def test_additional_sources_are_capped_in_count_and_length(self):
        clean_narrative({"additional_sources": ["s"] * 20}, [])
        with self.assertRaises(ValidationError):
            clean_narrative({"additional_sources": ["s"] * 21}, [])
        with self.assertRaises(ValidationError):
            clean_narrative({"additional_sources": ["x" * 501]}, [])

    def test_narrative_for_an_activity_not_in_the_report_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            clean_narrative({"activities": {"99": {"wop": "Lost prose."}}}, _activities(41, 42))
        self.assertIn("99", str(caught.exception))

    def test_non_numeric_activity_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            clean_narrative({"activities": {"all": {"wop": "x"}}}, _activities(41))


class NarrativeFromRequestTestCase(SimpleTestCase):
    def test_no_body_means_no_narrative(self):
        self.assertEqual(narrative_from_request(_request({}), "ifad", []), (None, None))

    def test_get_request_without_data_is_tolerated(self):
        self.assertEqual(narrative_from_request(Mock(spec=[]), "ifad", []), (None, None))

    def test_raw_and_cleaned_differ_in_the_way_the_paths_need(self):
        raw, cleaned = narrative_from_request(
            _request({"narrative": {"assumption_set_date": "2026-03-14"}}), "ifad", [],
        )
        self.assertEqual(raw, {"assumption_set_date": "2026-03-14"})
        self.assertEqual(cleaned["assumption_set_date"], datetime.date(2026, 3, 14))

    def test_a_report_that_does_not_read_narrative_refuses_it(self):
        for template_name in ("fao", None):
            with self.subTest(template=template_name):
                with self.assertRaises(ValidationError):
                    narrative_from_request(
                        _request({"narrative": {"data_limitations": "x"}}), template_name, [],
                    )
