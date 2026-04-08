# TDD RED → GREEN
"""Tests for the FAOSTAT Yield Data Service.

Spec coverage
-------------
Acceptance Criteria : AC-1 through AC-10
Business Rules      : BR-1 through BR-7
Edge Cases          : all eight listed in the spec

The external ``faostat`` library calls are patched with unittest.mock so that
the test suite never makes real network requests.

Run with:
    pytest djangoexact/api/tests/test_faostat_service.py
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the modules under test.
# ---------------------------------------------------------------------------
from api.faostat_exceptions import (  # noqa: E402
    FAOSTATError,
    FAOSTATInvalidInputError,
    FAOSTATNetworkError,
    FAOSTATNoDataError,
)
from api.faostat_service import get_yield  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FAOSTAT_DATA_PATH = "api.faostat_service.faostat"


def _make_row(*, area="Italy", item="Wheat", year=2022, value="3500.0", flag="A", element="Yield", unit="hg/ha"):
    """Return a dict that mirrors a single FAOSTAT API response row."""
    return {
        "Area": area,
        "Item": item,
        "Year": year,
        "Value": value,
        "Flag": flag,
        "Element": element,
        "Unit": unit,
    }


def _mock_faostat_returning(rows: list[dict]):
    """Return a MagicMock for the ``faostat`` module that yields *rows* from get_data_df."""
    import pandas as pd

    mock_faostat = MagicMock()
    if rows:
        mock_faostat.get_data_df.return_value = pd.DataFrame(rows)
    else:
        mock_faostat.get_data_df.return_value = pd.DataFrame()
    return mock_faostat


# ---------------------------------------------------------------------------
# Exception hierarchy — BR-8 / AC-8
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """All domain exceptions are catchable via FAOSTATError (AC-8, BR-8)."""

    def test_faostat_no_data_error_is_subclass_of_faostat_error(self):
        assert issubclass(FAOSTATNoDataError, FAOSTATError)

    def test_faostat_network_error_is_subclass_of_faostat_error(self):
        assert issubclass(FAOSTATNetworkError, FAOSTATError)

    def test_faostat_invalid_input_error_is_subclass_of_faostat_error(self):
        assert issubclass(FAOSTATInvalidInputError, FAOSTATError)

    def test_all_three_are_catchable_via_base_type(self):
        """Raising any domain exception and catching FAOSTATError must succeed."""
        for exc_cls in (FAOSTATNoDataError, FAOSTATNetworkError, FAOSTATInvalidInputError):
            with pytest.raises(FAOSTATError):
                raise exc_cls("test")


# ---------------------------------------------------------------------------
# AC-1  Valid area, valid item, no year → returns latest-year record
# ---------------------------------------------------------------------------


class TestGetYieldNoYearReturnsLatest:
    """AC-1, BR-2: no year → record with highest year in response returned."""

    def test_no_year_returns_record_with_element_yield(self, monkeypatch):
        # HIGH-2: ensure token is present so tests exercise the intended logic.
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2021, value="3200.0"),
            _make_row(year=2022, value="3500.0"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.element == "Yield"

    def test_no_year_returns_record_with_correct_area(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(year=2022, value="3500.0")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.area == "Italy"

    def test_no_year_returns_record_with_correct_item(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(year=2022, value="3500.0")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.item == "Wheat"

    def test_no_year_returns_most_recent_year_from_multi_year_response(self, monkeypatch):
        """BR-2, Edge: Multi-year response → scan all rows, pick highest year."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2019, value="3100.0"),
            _make_row(year=2021, value="3200.0"),
            _make_row(year=2022, value="3500.0"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.year == 2022

    def test_no_year_returns_float_value(self, monkeypatch):
        """AC-9: returned value field is Python float, not string."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(year=2022, value="3500.0")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert isinstance(result.value, float)


# ---------------------------------------------------------------------------
# AC-2  Valid area, valid item, explicit year with data → year matches
# ---------------------------------------------------------------------------


class TestGetYieldExplicitYearFound:
    """AC-2, BR-3: year supplied → exact match returned."""

    def test_explicit_year_returns_matching_year(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2020, value="3100.0"),
            _make_row(year=2021, value="3300.0"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat", year=2021)
        assert result.year == 2021

    def test_explicit_year_returned_value_is_float(self, monkeypatch):
        """AC-9 also applies to the explicit-year path."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(year=2021, value="3300.0")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat", year=2021)
        assert isinstance(result.value, float)
        assert result.value == pytest.approx(3300.0)


# ---------------------------------------------------------------------------
# AC-3  Explicit year with NO data → FAOSTATNoDataError
# ---------------------------------------------------------------------------


class TestGetYieldExplicitYearNotFound:
    """AC-3, BR-3, Edge: future year → FAOSTAT returns no rows → FAOSTATNoDataError."""

    def test_explicit_year_not_in_response_raises_no_data_error(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(year=2020, value="3100.0")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            with pytest.raises(FAOSTATNoDataError):
                get_yield(area="Italy", item="Wheat", year=2025)

    def test_future_year_raises_no_data_error(self, monkeypatch):
        """Edge: future year → FAOSTAT returns empty → FAOSTATNoDataError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning([])):
            with pytest.raises(FAOSTATNoDataError):
                get_yield(area="Italy", item="Wheat", year=2099)


# ---------------------------------------------------------------------------
# AC-4 & AC-5  Unrecognised area or item → FAOSTATInvalidInputError
# ---------------------------------------------------------------------------


class TestGetYieldUnrecognisedInputs:
    """AC-4, AC-5, BR-7: area or item not recognised by FAOSTAT → FAOSTATInvalidInputError.

    FAOSTAT signals an invalid area/item by returning an empty result set.
    """

    def test_unrecognised_area_raises_invalid_input_error(self, monkeypatch):
        """AC-4: area string not found in FAOSTAT → FAOSTATInvalidInputError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning([])):
            with pytest.raises(FAOSTATInvalidInputError):
                get_yield(area="NotARealCountry", item="Wheat")

    def test_unrecognised_item_raises_invalid_input_error(self, monkeypatch):
        """AC-5: item string not found in FAOSTAT → FAOSTATInvalidInputError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning([])):
            with pytest.raises(FAOSTATInvalidInputError):
                get_yield(area="Italy", item="NotARealCrop")


# ---------------------------------------------------------------------------
# AC-6  Endpoint unreachable → FAOSTATNetworkError with __cause__
# ---------------------------------------------------------------------------


class TestGetYieldNetworkError:
    """AC-6: network/API unreachable → FAOSTATNetworkError; original error is __cause__."""

    def test_network_exception_raises_faostat_network_error(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        mock_faostat = MagicMock()
        mock_faostat.get_data_df.side_effect = ConnectionError("timeout")
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATNetworkError):
                get_yield(area="Italy", item="Wheat")

    def test_network_error_wraps_original_exception_as_cause(self, monkeypatch):
        """AC-6: original exception is chained via __cause__."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        original = ConnectionError("timeout")
        mock_faostat = MagicMock()
        mock_faostat.get_data_df.side_effect = original
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATNetworkError) as exc_info:
                get_yield(area="Italy", item="Wheat")
        assert exc_info.value.__cause__ is original

    def test_invalid_token_raises_faostat_network_error(self, monkeypatch):
        """Edge: token present but invalid/expired → FAOSTATNetworkError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        mock_faostat = MagicMock()
        mock_faostat.get_data_df.side_effect = PermissionError("401 Unauthorized")
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATNetworkError):
                get_yield(area="Italy", item="Wheat")


# ---------------------------------------------------------------------------
# AC-7  FAOSTAT_TOKEN missing/empty → FAOSTATNetworkError before any request
# ---------------------------------------------------------------------------


class TestGetYieldMissingToken:
    """AC-7, BR-5: FAOSTAT_TOKEN absent or empty → FAOSTATNetworkError, no network call."""

    def test_missing_token_env_var_raises_network_error(self, monkeypatch):
        """BR-5: absent token → FAOSTATNetworkError before any network call."""
        monkeypatch.delenv("FAOSTAT_TOKEN", raising=False)
        mock_faostat = MagicMock()
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATNetworkError):
                get_yield(area="Italy", item="Wheat")
        mock_faostat.get_data_df.assert_not_called()

    def test_empty_token_env_var_raises_network_error(self, monkeypatch):
        """BR-5: empty string token treated same as absent token."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "")
        mock_faostat = MagicMock()
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATNetworkError):
                get_yield(area="Italy", item="Wheat")
        mock_faostat.get_data_df.assert_not_called()


# ---------------------------------------------------------------------------
# AC-10  Empty string inputs → FAOSTATInvalidInputError, no network call
# ---------------------------------------------------------------------------


class TestGetYieldEmptyStringInputs:
    """AC-10, Edge: area="" or item="" → FAOSTATInvalidInputError, no network request."""

    def test_empty_area_raises_invalid_input_error(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        mock_faostat = MagicMock()
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATInvalidInputError):
                get_yield(area="", item="Wheat")
        mock_faostat.get_data_df.assert_not_called()

    def test_empty_item_raises_invalid_input_error(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        mock_faostat = MagicMock()
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATInvalidInputError):
                get_yield(area="Italy", item="")
        mock_faostat.get_data_df.assert_not_called()

    def test_both_empty_raises_invalid_input_error(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        mock_faostat = MagicMock()
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATInvalidInputError):
                get_yield(area="", item="")
        mock_faostat.get_data_df.assert_not_called()


# ---------------------------------------------------------------------------
# BR-1  Fixed params: Domain=QCL, Element=Yield
# (Group=Production is implicit: domain QCL sits under Production in
#  FAOSTAT's hierarchy; the library has no separate group parameter.)
# ---------------------------------------------------------------------------


class TestGetYieldFixedFaostatParams:
    """BR-1: service must always call faostat with domain=QCL and element filter Yield."""

    def test_get_data_df_called_with_domain_qcl(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row()]
        mock_faostat = _mock_faostat_returning(rows)
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            get_yield(area="Italy", item="Wheat")
        call_kwargs = mock_faostat.get_data_df.call_args
        # Domain QCL must appear in the call (as a positional or keyword arg)
        all_args = str(call_kwargs)
        assert "QCL" in all_args

    def test_returned_record_element_is_always_yield(self, monkeypatch):
        """BR-1: element field in the returned record is always 'Yield'."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(element="Yield")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.element == "Yield"


# ---------------------------------------------------------------------------
# BR-4  Tie-breaking: multiple rows same year → prefer flag "A"
# ---------------------------------------------------------------------------


class TestGetYieldTieBreaking:
    """BR-4, Edge: multiple rows same year → prefer flag "A"; if none → FAOSTATNoDataError."""

    def test_multiple_rows_same_year_prefers_flag_a_row(self, monkeypatch):
        """BR-4: when two rows share the year, the one with Flag='A' is returned."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2022, value="3500.0", flag="A"),
            _make_row(year=2022, value="9999.0", flag="E"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat", year=2022)
        assert result.value == pytest.approx(3500.0)

    def test_multiple_rows_same_year_no_flag_a_raises_no_data_error(self, monkeypatch):
        """BR-4: tie with no flag 'A' row → FAOSTATNoDataError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2022, value="3500.0", flag="E"),
            _make_row(year=2022, value="3400.0", flag="F"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            with pytest.raises(FAOSTATNoDataError):
                get_yield(area="Italy", item="Wheat", year=2022)

    def test_no_year_multiple_rows_highest_year_flag_a_selected(self, monkeypatch):
        """BR-2 + BR-4: no year → highest year chosen; if tie, flag A wins."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2022, value="3500.0", flag="A"),
            _make_row(year=2022, value="9999.0", flag="E"),
            _make_row(year=2021, value="3200.0", flag="A"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.year == 2022
        assert result.value == pytest.approx(3500.0)

    def test_no_year_highest_year_multiple_rows_no_flag_a_raises_no_data_error(self, monkeypatch):
        """HIGH-4: no year, highest year has multiple rows, none with flag 'A' → FAOSTATNoDataError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [
            _make_row(year=2022, value="3500.0", flag="E"),
            _make_row(year=2022, value="3400.0", flag="F"),
            _make_row(year=2021, value="3200.0", flag="A"),
        ]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            with pytest.raises(FAOSTATNoDataError):
                get_yield(area="Italy", item="Wheat")


# ---------------------------------------------------------------------------
# BR-6  No internal caching — two calls issue two FAOSTAT requests
# ---------------------------------------------------------------------------


class TestGetYieldNoCaching:
    """BR-6: no internal caching — repeated calls always hit faostat."""

    def test_two_identical_calls_issue_two_faostat_requests(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row()]
        mock_faostat = _mock_faostat_returning(rows)
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            get_yield(area="Italy", item="Wheat")
            get_yield(area="Italy", item="Wheat")
        assert mock_faostat.get_data_df.call_count == 2


# ---------------------------------------------------------------------------
# Return record shape — all fields present and correctly typed
# ---------------------------------------------------------------------------


class TestGetYieldReturnShape:
    """Verify the returned record carries all required fields with correct types."""

    def test_returned_record_has_value_field_as_float(self, monkeypatch):
        """AC-9."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(value="3500.5")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert isinstance(result.value, float)

    def test_returned_record_has_unit_field_as_str(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(unit="hg/ha")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert isinstance(result.unit, str)
        assert result.unit == "hg/ha"

    def test_returned_record_has_year_field_as_int(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(year=2022)]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert isinstance(result.year, int)

    def test_returned_record_has_item_field(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(item="Wheat")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.item == "Wheat"

    def test_returned_record_has_area_field(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(area="Italy")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.area == "Italy"

    def test_returned_record_has_element_field_equal_to_yield(self, monkeypatch):
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(element="Yield")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.element == "Yield"

    def test_string_value_from_faostat_is_cast_to_float(self, monkeypatch):
        """AC-9: FAOSTAT returns values as strings; service must coerce to float."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(value="1234.56")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            result = get_yield(area="Italy", item="Wheat")
        assert result.value == pytest.approx(1234.56)
        assert type(result.value) is float


# ---------------------------------------------------------------------------
# Edge: empty result set → FAOSTATInvalidInputError (no year path)
# ---------------------------------------------------------------------------


class TestGetYieldEmptyResultSet:
    """Edge: empty result set from a plausible but unknown area/item combo."""

    def test_empty_dataframe_for_valid_looking_inputs_raises_invalid_input_error(self, monkeypatch):
        """MEDIUM-4: empty response with no year → FAOSTATInvalidInputError.

        When FAOSTAT returns nothing and no year was requested, the service
        cannot distinguish between an unknown area/item and one with no data;
        the spec resolves this by raising FAOSTATInvalidInputError (AC-4/AC-5).
        """
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning([])):
            with pytest.raises(FAOSTATInvalidInputError):
                get_yield(area="Italy", item="Wheat")


# ---------------------------------------------------------------------------
# MEDIUM-2 — _row_to_record schema guard
# ---------------------------------------------------------------------------


class TestRowToRecordSchemaGuard:
    """MEDIUM-2: malformed FAOSTAT rows raise FAOSTATNetworkError."""

    def test_non_numeric_value_raises_network_error(self, monkeypatch):
        """MEDIUM-2: non-numeric Value field → FAOSTATNetworkError."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        rows = [_make_row(value="N/A")]
        with patch(_FAOSTAT_DATA_PATH, _mock_faostat_returning(rows)):
            with pytest.raises(FAOSTATNetworkError):
                get_yield(area="Italy", item="Wheat")

    def test_missing_value_column_raises_network_error(self, monkeypatch):
        """MEDIUM-2: missing Value column → FAOSTATNetworkError."""
        import pandas as pd

        monkeypatch.setenv("FAOSTAT_TOKEN", "dummy-token")
        row = {"Area": "Italy", "Item": "Wheat", "Year": 2022, "Flag": "A", "Element": "Yield", "Unit": "hg/ha"}
        mock_faostat = MagicMock()
        mock_faostat.get_data_df.return_value = pd.DataFrame([row])
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            with pytest.raises(FAOSTATNetworkError):
                get_yield(area="Italy", item="Wheat")


# ---------------------------------------------------------------------------
# MEDIUM-3 — Token is passed to the faostat library
# ---------------------------------------------------------------------------


class TestTokenPassedToFaostatLibrary:
    """MEDIUM-3: verify the token is forwarded to faostat.set_requests_args."""

    def test_set_requests_args_called_with_correct_token(self, monkeypatch):
        """MEDIUM-3: get_yield must call faostat.set_requests_args(token=<value>)."""
        monkeypatch.setenv("FAOSTAT_TOKEN", "my-secret-token")
        rows = [_make_row()]
        mock_faostat = _mock_faostat_returning(rows)
        with patch(_FAOSTAT_DATA_PATH, mock_faostat):
            get_yield(area="Italy", item="Wheat")
        mock_faostat.set_requests_args.assert_called_once_with(token="my-secret-token")
