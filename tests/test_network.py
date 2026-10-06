"""Network integration test for smhi2epw.

These tests hit the live SMHI MetObs + STRÅNG endpoints and are skipped by
default. Run them explicitly with ``pytest -m network``.
"""

from __future__ import annotations

import pytest

from smhi2epw.compiler import EPWConfig, compile_epw

# Göteborg A (automatic station) across historical, leap, and recent paths.
STATION_ID = 71420


@pytest.mark.network
@pytest.mark.parametrize(
    "station_id,year,radiation_auto,expected_source,expected_rows",
    [
        (71420, 2016, True, "measured+strang_partition", 8784),
        (72420, 2020, False, "strang", 8784),
        (71420, 2023, True, "measured+strang_partition", 8760),
    ],
)
def test_compile_gothenburg_live(
    tmp_path, station_id, year, radiation_auto, expected_source, expected_rows
):
    out = tmp_path / f"gothenburg_{year}_live.epw"
    config = EPWConfig(
        station_id=station_id,
        year=year,
        output_path=str(out),
        city="Gothenburg",
        latitude=57.7156,
        longitude=11.9924,
        utc_offset=1.0,
        cache_dir=str(tmp_path / "cache"),
        radiation_station_auto=radiation_auto,
    )
    result = compile_epw(config)

    assert result.rows == expected_rows
    assert result.report.solar_source == expected_source
    assert out.exists()

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8 + expected_rows
    # Sentinel cleaning + solar energy balance should be physically consistent.
    assert result.report.energy_balance_max_residual < 1e-6
    assert all(len(line.split(",")) == 35 for line in lines[8:])
    # Extraterrestrial direct-normal is populated (not the 9999 missing token).
    midday = lines[8 + 2900].split(",")
    assert midday[11] != "9999"  # extraterrestrial horizontal
    assert midday[12] != "9999"  # extraterrestrial direct normal


@pytest.mark.network
def test_find_nearest_station_live():
    from smhi2epw.ingestion import CachedClient, find_nearest_station

    client = CachedClient(cache_dir=None)
    meta = find_nearest_station(57.7156, 11.9924, 2023, client)
    assert meta.station_id > 0
    assert meta.distance_km(57.7156, 11.9924) < 50.0


@pytest.mark.network
def test_open_meteo_era5_units_and_interval(tmp_path):
    """Exercise the explicitly selected archive model on a small historical window."""
    import numpy as np
    import pandas as pd

    from smhi2epw import reanalysis
    from smhi2epw.ingestion import CachedClient

    index = pd.date_range("2018-07-20", periods=48, freq="h", tz="UTC")
    client = CachedClient(cache_dir=str(tmp_path / "era5-cache"))
    frame, metadata = reanalysis.fetch(57.7, 12.0, 50.0, index, client)
    assert frame.index.equals(index)
    assert (
        np.isfinite(
            frame[
                [
                    "dry_bulb",
                    "relative_humidity",
                    "reanalysis_surface_pressure",
                    "wind_speed",
                    "wind_direction",
                    "ghi",
                ]
            ]
        )
        .all()
        .all()
    )
    assert metadata["model"] == "ERA5"
    assert metadata["elevation_m"] == 50.0
    assert metadata["radiation_interval"] == "preceding_hour_mean"
    assert frame.reanalysis_surface_pressure.between(31000, 120000).all()
