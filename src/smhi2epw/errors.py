"""Define the expected-error boundary for ingestion, processing, and export.

Applications can catch :class:`Smhi2EpwError` once while contributors and
advanced users retain specific failure types for recovery and diagnostics.
"""

from __future__ import annotations


class Smhi2EpwError(Exception):
    """Base class for expected, user-facing package failures.

    Catch this exception when an application wants one boundary for ingestion,
    gap, and output-validation failures while allowing programming errors to
    propagate normally.
    """


class IngestionError(Smhi2EpwError):
    """Report invalid configuration, unavailable data, or malformed API input.

    This exception covers failures that occur before scientific processing,
    including HTTP errors, corrupt cached payloads, station-coverage failures,
    unsupported years, and invalid coordinates or UTC offsets.
    """


class DataGapError(Smhi2EpwError):
    """Raised when an observation gap exceeds the interpolation window.

    Required fields are never synthesized across gaps longer than 48 hours or
    when no valid daily reference profile exists. Aborting is safer than
    producing a weather file whose apparent precision hides missing evidence.
    """


class ValidationError(Smhi2EpwError):
    """Report a structural, range, or filesystem EPW validation failure.

    Examples include an incorrect header order, a row with other than 35
    fields, a partial year, physically invalid required values, or failure to
    atomically replace the destination file.
    """
