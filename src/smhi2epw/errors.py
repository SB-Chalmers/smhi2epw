"""Exception hierarchy for smhi2epw."""

from __future__ import annotations


class Smhi2EpwError(Exception):
    """Base class for all errors raised by smhi2epw."""


class IngestionError(Smhi2EpwError):
    """Raised when an API request or payload parsing fails."""


class DataGapError(Smhi2EpwError):
    """Raised when an observation gap exceeds the interpolation window.

    Generating an EPW from data with large gaps would produce a corrupted
    weather file, so the pipeline aborts instead.
    """


class ValidationError(Smhi2EpwError):
    """Raised when the compiled dataset fails a structural validation check."""
