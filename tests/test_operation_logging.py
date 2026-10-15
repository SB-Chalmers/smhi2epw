# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EPSM Development contributors
# License: See LICENSE at the project root.
"""Public operation logging keeps calculation inputs and host configuration separate."""

import inspect
import logging

from smhi2epw import compile_epw


def test_public_operation_accepts_explicit_context():
    parameter = inspect.signature(compile_epw).parameters["log_context"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None


def test_import_does_not_install_output_handlers():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import smhi2epw; import logging; assert not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger('smhi2epw').handlers)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout and not result.stderr


def test_rejected_operation_keeps_context_and_reports_failure(caplog):
    import pytest

    with caplog.at_level(logging.DEBUG):
        with pytest.raises((ValueError, TypeError, AttributeError)):
            compile_epw(
                None, log_context={"study_id": "logging-test", "operation_id": "parent"}
            )
    records = [record for record in caplog.records if hasattr(record, "epsm_event")]
    assert records[0].epsm_event.endswith(".started")
    assert records[-1].epsm_event.endswith(".failed")
    assert records[0].epsm_context["parent_operation_id"] == "parent"
    assert records[-1].epsm_context["study_id"] == "logging-test"
    assert records[-1].epsm_details["duration_s"] >= 0
    assert not any(record.exc_info for record in records)


def test_weather_worker_events_keep_parent_context(tmp_path, caplog):
    from fixtures.provider_replay import compile_weather

    with caplog.at_level(logging.DEBUG):
        result = compile_weather(tmp_path, log_context={"study_id": "weather-trace"})
    assert result.rows == 8760
    records = [r for r in caplog.records if hasattr(r, "epsm_event")]
    ingest = next(r for r in records if r.epsm_event == "weather.ingest.started")
    fetches = [
        r
        for r in records
        if r.epsm_event
        in (
            "weather.provider.metobs.fetch.started",
            "weather.provider.strang.fetch.started",
        )
    ]
    assert fetches
    assert all(r.epsm_context["study_id"] == "weather-trace" for r in fetches)
    assert all(
        r.epsm_context["parent_operation_id"] == ingest.epsm_context["operation_id"]
        for r in fetches
    )
