"""Network integration test for smhi2epw.

These tests hit the live SMHI MetObs + STRÅNG endpoints and are skipped by
default. Run them explicitly with ``pytest -m network``.
"""

from __future__ import annotations

import pytest

from smhi2epw.compiler import EPWConfig, compile_epw

# Göteborg A (automatic station) for a recent, fully-corrected year.
STATION_ID = 71420
YEAR = 2023


@pytest.mark.network
def test_compile_gothenburg_live(tmp_path):
    out = tmp_path / "gothenburg_live.epw"
    config = EPWConfig(
        station_id=STATION_ID,
        year=YEAR,
        output_path=str(out),
        city="Gothenburg",
        latitude=57.7156,
        longitude=11.9924,
        utc_offset=1.0,
        cache_dir=str(tmp_path / "cache"),
    )
    result = compile_epw(config)

    assert result.rows == 8760
    assert out.exists()

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8 + 8760
    # Sentinel cleaning + solar energy balance should be physically consistent.
    assert result.report.energy_balance_max_residual < 200.0
    # Extraterrestrial direct-normal is populated (not the 9999 missing token).
    midday = lines[8 + 2900].split(",")
    assert midday[11] != "9999"  # extraterrestrial horizontal
    assert midday[12] != "9999"  # extraterrestrial direct normal


@pytest.mark.network
def test_find_nearest_station_live():
    from smhi2epw.ingestion import CachedClient, find_nearest_station

    client = CachedClient(cache_dir=None)
    meta = find_nearest_station(57.7156, 11.9924, YEAR, client)
    assert meta.station_id > 0
    assert meta.distance_km(57.7156, 11.9924) < 50.0
