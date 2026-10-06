"""Exercise the complete public compiler with deterministic HTTP payloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from fixtures.provider_replay import ReplaySession, compile_weather

from smhi2epw import read_epw


@pytest.mark.parametrize("year, rows", [(2016, 8784), (2023, 8760), (2024, 8784)])
def test_primary_replay_parses_provider_payloads_and_annual_calendar(
    tmp_path, year, rows
):
    result = compile_weather(tmp_path, year=year)
    weather = read_epw(result.output_path)
    receipt = json.loads(Path(result.output_path + ".json").read_text())
    assert result.rows == len(weather) == rows
    assert result.report.weather_classification == "observation_based"
    assert result.report.required_reconstructed_fraction == 0
    assert result.report.cloud_available
    assert weather.dry_bulb.max() - weather.dry_bulb.min() > 20
    assert weather.ghi.max() > 300
    assert weather.ghi.eq(0).sum() > rows / 3
    assert (
        np.isfinite(weather[["dry_bulb", "dew_point", "pressure", "ghi", "dni", "dhi"]])
        .all()
        .all()
    )
    assert receipt["raw_response_receipts_complete"] is True
    assert (
        receipt["epw_sha256"]
        == hashlib.sha256(Path(result.output_path).read_bytes()).hexdigest()
    )
    urls = [r["url"] for r in receipt["raw_responses"]]
    assert any(
        "/parameter/1/90001" in u or "/parameter/1/station/90001" in u for u in urls
    )
    assert any("/parameter/117/" in u for u in urls)
    assert not any("open-meteo.com" in u for u in urls)
    if year < 2018:
        assert result.report.solar_source == "strang"
        assert any("/parameter/118/" in u for u in urls)
        assert not any("/parameter/121/" in u for u in urls)


def test_reconstructed_replay_uses_temporal_assessed_donor_and_era5(tmp_path):
    primary = compile_weather(tmp_path / "primary")
    result = compile_weather(tmp_path / "reconstructed", scenario="reconstructed")
    assert result.report.weather_classification == "mixed_reconstructed"
    assert result.report.cross_station_filled_hours["dry_bulb"] == 72
    assert result.report.linear_filled_hours["relative_humidity"] == 2
    assert result.report.reanalysis_filled_hours["pressure"] == 96
    assert result.report.source_fractions["dry_bulb"]["donor"] == pytest.approx(
        72 / 8760
    )
    assert result.report.source_fractions["pressure"]["reanalysis"] == pytest.approx(
        96 / 8760
    )
    assert (
        result.report.gap_fallback_sources[0]["method"]
        == "assessed_same_hour_observation"
    )
    before = read_epw(primary.output_path)
    after = read_epw(result.output_path)
    # Scalar correction reproduces the synthetic source; valid original
    # temperature hours and its requested-year seasonal pattern are preserved.
    assert before.dry_bulb.equals(after.dry_bulb)
    receipt = json.loads(Path(result.output_path + ".json").read_text())
    assert receipt["raw_response_receipts_complete"] is True
    assert any("open-meteo.com" in r["url"] for r in receipt["raw_responses"])


def test_reanalysis_only_replay_exposes_same_year_provider_identity(tmp_path):
    result = compile_weather(tmp_path, scenario="reanalysis_only")
    assert result.station is None
    assert result.report.weather_classification == "reanalysis_only"
    assert result.pressure_method == "era5_surface_pressure"
    assert result.report.source_fractions["dry_bulb"] == {"reanalysis": 1.0}
    assert result.report.reanalysis_metadata["model"] == "ERA5"
    assert result.report.required_reconstructed_fraction == 1.0
    weather = read_epw(result.output_path)
    assert weather.ghi.max() > 300
    assert len(weather) == 8760
    assert "ERA5-AMY" in Path(result.output_path).read_text().splitlines()[0]
    assert (
        json.loads(Path(result.output_path + ".json").read_text())[
            "raw_response_receipts_complete"
        ]
        is True
    )


def test_replay_rejects_unknown_url_instead_of_using_live_transport():
    session = ReplaySession()
    with pytest.raises(AssertionError, match="Unexpected URL"):
        session.get("https://example.invalid/unrecognised", timeout=1)
    assert session.unknown_urls == ["https://example.invalid/unrecognised"]
