"""Regression tests for cumulative land-area aggregation.

These exercise the pure aggregation helper (no Django ORM, no DB), covering the
land-use-change double-count fix: the Excel "Cumulative Hectares Impacted" row
must count each activity's physical hectares once, matching the app's
``total_hectares`` (Activity.get_land_modules_area / commit 6d37c194f).
"""

import unittest

from api.reports.aggregation import (
    HectaresContribution,
    cumulative_activity_hectares,
)


def _standalone(units_w, units_wo=None, is_with=True, is_without=True):
    return HectaresContribution(
        luc_group=None,
        is_with=is_with,
        is_without=is_without,
        units_breakdown_w=units_w,
        units_breakdown_wo=units_wo or [],
    )


def _luc(group, units_w=None, units_wo=None, is_with=False, is_without=False):
    return HectaresContribution(
        luc_group=group,
        is_with=is_with,
        is_without=is_without,
        units_breakdown_w=units_w or [],
        units_breakdown_wo=units_wo or [],
    )


class CumulativeActivityHectaresTest(unittest.TestCase):
    def test_empty_returns_zeros(self):
        self.assertEqual(cumulative_activity_hectares(3, []), [0.0, 0.0, 0.0])

    def test_single_standalone_land_module_counted_once(self):
        contribs = [_standalone([100.0, 100.0, 100.0])]
        self.assertEqual(
            cumulative_activity_hectares(3, contribs), [100.0, 100.0, 100.0]
        )

    def test_non_land_contribution_is_skipped(self):
        # Livestock / energy modules carry empty breakdowns -> contribute nothing.
        contribs = [_standalone([], [], is_with=True, is_without=True)]
        self.assertEqual(cumulative_activity_hectares(3, contribs), [0.0, 0.0, 0.0])

    def test_two_distinct_standalone_modules_are_summed(self):
        # Genuinely different parcels (no shared LUC) add up.
        contribs = [
            _standalone([50.0, 50.0]),
            _standalone([30.0, 30.0]),
        ]
        self.assertEqual(cumulative_activity_hectares(2, contribs), [80.0, 80.0])

    def test_luc_group_counted_once_not_summed(self):
        # A land-use-change activity: with-module + without-module + LandUseChange
        # module all describe the SAME 100 ha and share one LUC group.
        # Before the fix this summed to ~300; it must be 100.
        group = 42
        contribs = [
            _luc(group, units_wo=[100.0, 100.0], is_without=True),   # forest (without)
            _luc(group, units_w=[100.0, 100.0], is_with=True),       # annual (with)
            _luc(group, units_w=[100.0, 100.0], is_with=True),       # LandUseChange
        ]
        self.assertEqual(cumulative_activity_hectares(2, contribs), [100.0, 100.0])

    def test_luc_group_uses_later_member_when_first_has_no_units(self):
        # First member of the group yields no usable breakdown; the group must
        # still be counted once via a later member.
        group = 7
        contribs = [
            _luc(group, is_with=True, units_w=[]),                    # unusable
            _luc(group, units_w=[80.0, 80.0], is_with=True),         # supplies area
            _luc(group, units_w=[80.0, 80.0], is_with=True),         # deduped
        ]
        self.assertEqual(cumulative_activity_hectares(2, contribs), [80.0, 80.0])

    def test_two_distinct_luc_groups_are_summed(self):
        # Two separate transitions in one activity -> two distinct areas.
        contribs = [
            _luc(1, units_w=[10.0, 10.0], is_with=True),
            _luc(1, units_wo=[10.0, 10.0], is_without=True),  # deduped into group 1
            _luc(2, units_w=[25.0, 25.0], is_with=True),
        ]
        self.assertEqual(cumulative_activity_hectares(2, contribs), [35.0, 35.0])

    def test_prefers_with_over_without_breakdown(self):
        # When a module is part of both scenarios, the with breakdown wins
        # (unchanged selection behaviour).
        contribs = [
            HectaresContribution(
                luc_group=None,
                is_with=True,
                is_without=True,
                units_breakdown_w=[5.0, 5.0],
                units_breakdown_wo=[9.0, 9.0],
            )
        ]
        self.assertEqual(cumulative_activity_hectares(2, contribs), [5.0, 5.0])

    def test_ragged_breakdown_padded_to_duration(self):
        # Shorter breakdowns are zero-filled to the project duration.
        contribs = [_standalone([100.0])]
        self.assertEqual(cumulative_activity_hectares(3, contribs), [100.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
