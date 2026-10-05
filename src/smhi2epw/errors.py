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
    """Report required weather that remains missing after permitted recovery.

    Temporal reconstruction remains limited to 48 hours. Automatic weather
    policy can fill longer gaps with assessed observations or same-year
    reanalysis; strict policy retains errors when its permitted sources cannot
    supply the required hours. Neither policy fabricates a successful file
    when every available source is incomplete.
    """


class ValidationError(Smhi2EpwError):
    """Report a structural, range, or filesystem EPW validation failure.

    Examples include an incorrect header order, a row with other than 35
    fields, a partial year, physically invalid required values, or failure to
    atomically replace the destination file.
    """
