"""FAOSTAT Yield Data Service.

Callable contract
-----------------
get_yield(area, item, year=None) -> YieldRecord

Business rules implemented
--------------------------
BR-1  Fixed params: domain=QCL, element=Yield.
BR-2  No year supplied → record with highest year in response.
BR-3  Year supplied → exact match or FAOSTATNoDataError.
BR-4  Multiple rows same year → prefer Flag="A"; if none → FAOSTATNoDataError.
BR-5  FAOSTAT_TOKEN absent/empty → FAOSTATNetworkError before any network call.
BR-6  No internal caching.
BR-7  area/item are case-sensitive; no fuzzy matching.

AC-9  Returned value is Python float.
AC-10 area="" or item="" → FAOSTATInvalidInputError, no network call.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Final, NamedTuple

import faostat  # patched in tests via: patch("api.faostat_service.faostat", ...)

from api.faostat_exceptions import (
    FAOSTATInvalidInputError,
    FAOSTATNetworkError,
    FAOSTATNoDataError,
)

logger = logging.getLogger(__name__)

_DOMAIN: Final[str] = "QCL"
_ELEMENT: Final[str] = "Yield"
_FLAG_OFFICIAL: Final[str] = "A"

_TOKEN_ENV_VAR: Final[str] = "FAOSTAT_TOKEN"

# HIGH-1: faostat.set_requests_args mutates global state on the faostat module.
# The library does not support per-call token passing; every call to
# set_requests_args overwrites the shared Authorization header.  We guard
# the set_requests_args + get_data_df block with a module-level lock so that
# concurrent threads cannot interleave token writes and network calls.
_faostat_lock: threading.Lock = threading.Lock()


class YieldRecord(NamedTuple):
    """Structured result returned by get_yield."""

    value: float
    unit: str
    year: int
    item: str
    area: str
    element: str


def _get_token() -> str:
    """Read FAOSTAT_TOKEN from the environment (BR-5).

    Raises FAOSTATNetworkError if the token is absent or empty.
    """
    token: str = os.environ.get(_TOKEN_ENV_VAR, "")

    if not token:
        raise FAOSTATNetworkError(
            f"{_TOKEN_ENV_VAR} is not set or is empty. "
            "Set the environment variable before calling get_yield()."
        )

    return token


def _row_to_record(row: dict) -> YieldRecord:
    """Convert a single response row dict to a YieldRecord.

    Raises FAOSTATNetworkError if the row is missing expected columns or
    the Value field cannot be coerced to float (MEDIUM-2).
    """
    try:
        value = float(row["Value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FAOSTATNetworkError(
            "Unexpected FAOSTAT response schema: "
            f"could not parse Value field — {exc}"
        ) from exc

    try:
        return YieldRecord(
            value=value,
            unit=str(row["Unit"]),
            year=int(row["Year"]),
            item=str(row["Item"]),
            area=str(row["Area"]),
            element=str(row["Element"]),
        )
    except KeyError as exc:
        raise FAOSTATNetworkError(
            f"Unexpected FAOSTAT response schema: missing column {exc}"
        ) from exc


def get_yield(area: str, item: str, year: int | None = None) -> YieldRecord:
    """Fetch yield data from FAOSTAT for the given area and item.

    Parameters
    ----------
    area:
        FAOSTAT area label (case-sensitive), e.g. "Italy".
    item:
        FAOSTAT item label for domain QCL (case-sensitive), e.g. "Wheat".
    year:
        Optional four-digit calendar year.  When omitted the record with
        the highest year in the FAOSTAT response is returned (BR-2).

    Returns
    -------
    YieldRecord
        Named tuple with fields: value, unit, year, item, area, element.

    Raises
    ------
    FAOSTATInvalidInputError
        If area or item is an empty string (AC-10), or if the FAOSTAT API
        returns an empty result set (meaning the area/item is unrecognised).
    FAOSTATNoDataError
        If a specific year is requested but no matching row is found (BR-3),
        or if the best year has multiple rows and none carries flag "A" (BR-4).
    FAOSTATNetworkError
        If FAOSTAT_TOKEN is absent/empty (BR-5) or if the FAOSTAT endpoint
        raises any network/auth exception (AC-6).
    """
    # AC-10: validate inputs before touching the network.
    if not area or not item:
        raise FAOSTATInvalidInputError(
            "area and item must be non-empty strings."
        )

    # BR-5: verify token before any network call.
    token: str = _get_token()

    # HIGH-1: serialise token write + network call to avoid races between
    # concurrent threads overwriting the shared faostat global auth header.
    #
    # HIGH-3: The spec mandates Group=Production, Domain=QCL, Element=Yield.
    # The faostat library does not expose a dedicated "group" parameter —
    # domain code QCL (Crops and Livestock Products) implicitly sits under
    # the Production group in FAOSTAT's classification hierarchy.  Filtering
    # by domain=QCL already restricts results to the Production group; no
    # separate group filter is needed or supported by the library.
    with _faostat_lock:
        faostat.set_requests_args(token=token)

        # BR-1, BR-6: fetch from FAOSTAT (no caching).
        try:
            df = faostat.get_data_df(
                _DOMAIN,
                pars={
                    "area": area,
                    "item": item,
                    "element": _ELEMENT,
                },
                show_flags=True,
                strval=True,
            )
        except Exception as exc:
            raise FAOSTATNetworkError(
                f"FAOSTAT request failed: {exc}"
            ) from exc

    # Empty DataFrame handling differs by whether a year was requested.
    if df is None or df.empty:
        if year is not None:
            # A year was explicitly requested but no rows came back — the
            # area/item might be valid but there is simply no data for that
            # year (e.g. a future year).  Raise NoDataError (BR-3).
            raise FAOSTATNoDataError(
                f"No FAOSTAT data found for area={area!r}, item={item!r}, "
                f"year={year}."
            )
        # No year requested and the response is empty → the area or item is
        # not recognised by FAOSTAT (AC-4, AC-5).
        raise FAOSTATInvalidInputError(
            f"No FAOSTAT data found for area={area!r}, item={item!r}. "
            "The area or item label may be unrecognised."
        )

    # Normalise to list of row dicts for simpler processing.
    rows: list[dict] = df.to_dict(orient="records")

    # Determine the target year.
    if year is not None:
        # BR-3: exact year match required.
        year_rows = [r for r in rows if int(r["Year"]) == year]
        if not year_rows:
            raise FAOSTATNoDataError(
                f"No FAOSTAT data found for area={area!r}, item={item!r}, "
                f"year={year}."
            )
        target_rows = year_rows
    else:
        # BR-2: pick the highest year present.
        max_year: int = max(int(r["Year"]) for r in rows)
        target_rows = [r for r in rows if int(r["Year"]) == max_year]

    # BR-4: if there are multiple rows for the target year, prefer Flag="A".
    if len(target_rows) == 1:
        return _row_to_record(target_rows[0])

    official_rows = [r for r in target_rows if str(r.get("Flag", "")) == _FLAG_OFFICIAL]
    if not official_rows:
        raise FAOSTATNoDataError(
            f"Multiple rows found for area={area!r}, item={item!r} in the "
            f"target year but none carries Flag={_FLAG_OFFICIAL!r}."
        )

    # Take the first (and typically only) official row.
    return _row_to_record(official_rows[0])
