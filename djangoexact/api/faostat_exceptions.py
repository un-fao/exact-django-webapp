"""Domain exceptions for the FAOSTAT Yield Data Service.

All three concrete exceptions are subclasses of FAOSTATError so callers
can catch the base type when they do not need to distinguish causes (AC-8).
"""
from __future__ import annotations


class FAOSTATError(Exception):
    """Base exception for all FAOSTAT service errors."""


class FAOSTATNoDataError(FAOSTATError):
    """Raised when the FAOSTAT API returns no data matching the request."""


class FAOSTATNetworkError(FAOSTATError):
    """Raised when the FAOSTAT API is unreachable or authentication fails."""


class FAOSTATInvalidInputError(FAOSTATError):
    """Raised when area or item inputs are empty or unrecognised by FAOSTAT."""
