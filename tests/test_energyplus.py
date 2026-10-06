"""Required consumer tests: provider payloads -> installed package -> EnergyPlus.

These deterministic cases validate mechanics and building response. They are
engineering fixtures, not evidence of accuracy against measured weather.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fixtures.provider_replay import compile_weather

from smhi2epw import read_epw

EXAMPLES = Path(
    os.environ.get("SMHI2EPW_EXAMPLES_DIR", Path(__file__).parents[1] / "examples")
)
sys.path.insert(0, str(EXAMPLES / "support"))
from energyplus import run_energyplus  # noqa: E402

pytestmark = pytest.mark.energyplus


@pytest.mark.parametrize(
    "year,scenario,latitude,longitude",
    [
        (2023, "primary", 57.7, 12.0),
        (2024, "primary", 57.7, 12.0),
        (2016, "primary", 57.7, 12.0),
        (2023, "primary", 65.0, 20.0),
        (2023, "reconstructed", 57.7, 12.0),
        (2023, "reanalysis_only", 57.7, 12.0),
    ],
)
def test_compiled_weather_runs_in_energyplus(
    tmp_path, year, scenario, latitude, longitude
):
    result = compile_weather(tmp_path / "weather", year, scenario, latitude, longitude)
    simulation = run_energyplus(result.output_path, tmp_path / "simulation")
    hourly = simulation["hourly"]
    summary = simulation["summary"]
    weather = _read_hourly_weather(result.output_path)
    assert summary["hours"] == result.rows
    assert summary["warning_count"] == 0
    assert all(
        summary[name] > 0 for name in ("heating_kwh", "cooling_kwh", "window_solar_kwh")
    )
    assert (
        19.9 <= hourly.zone_temperature.min() <= hourly.zone_temperature.max() <= 26.1
    )

    # At six timesteps/hour, temperature interpolation weights the current
    # hour 7/12 and previous hour 5/12. Skip hour1, whose starting value comes
    # from hour24 of day1 during initialization, rather than the previous year.
    expected_temperature = (7 * weather.dry_bulb + 5 * weather.dry_bulb.shift()) / 12
    np.testing.assert_allclose(
        hourly.dry_bulb.iloc[1:], expected_temperature.iloc[1:], atol=1e-8
    )
    # Solar interpolation is centred differently; use constant daylight
    # plateaus to verify magnitudes without assuming pointwise EPW equality.
    plateau = (
        weather.dni.eq(400)
        & weather.dni.shift().eq(400)
        & weather.dni.shift(-1).eq(400)
    )
    assert plateau.sum() > 500
    np.testing.assert_allclose(hourly.direct_solar[plateau], 400, atol=1e-8)
    assert hourly.direct_solar.max() <= weather.dni.max() + 1e-8
    assert hourly.diffuse_solar.max() <= weather.dhi.max() + 1e-8
    assert hourly.diffuse_solar.gt(0).sum() > 500
    # Horizon handling can alter transition hours slightly; the annual diffuse
    # input must still reach the engine within1% for these smooth fixtures.
    assert hourly.diffuse_solar.sum() == pytest.approx(weather.dhi.sum(), rel=0.01)

    # Keep one real provider-to-engine EPW and its receipt for notebook CI.
    notebook_path = os.environ.get("SMHI2EPW_NOTEBOOK_EPW_PATH")
    if notebook_path and (year, scenario, latitude) == (2023, "primary", 57.7):
        path = Path(notebook_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result.output_path, path)
        shutil.copyfile(result.output_path + ".json", str(path) + ".json")

    if latitude == 65:
        _check_low_sun_response(tmp_path, result.output_path, simulation)


def _read_hourly_weather(path):
    """Give actual-year EPW rows their local hour-ending timestamps."""
    weather = read_epw(path)
    weather.index = pd.to_datetime(weather[["year", "month", "day"]]) + pd.to_timedelta(
        weather.hour, unit="h"
    )
    return weather


def _check_low_sun_response(tmp_path, epw_path, reference):
    """Check winter DNI and the response to the old five-degree suppression."""
    weather = _read_hourly_weather(epw_path)
    # Fixed independent geometry: Dec1,2023,65N20E has midpoint elevations
    # about3.32 and2.53degrees at11/12UTC (12/13LST). Both have supplied DNI.
    winter = weather.loc[pd.to_datetime(["2023-12-01 12:00", "2023-12-01 13:00"])]
    assert winter.dni.gt(0).all()
    assert reference["hourly"].loc[winter.index, "direct_solar"].gt(0).all()

    # Isolate the former defect with identical weather/model, changing only
    # supplied DNI during north-winter hours below the five-degree threshold.
    # This is a regression experiment, not a confidence interval for recovery.
    from fixtures.provider_replay import _daylight

    midpoint = (weather.index - pd.Timedelta(hours=1, minutes=30)).tz_localize("UTC")
    cosine = _daylight(midpoint, 65, 20)
    suppressed = (cosine > 0) & (cosine < np.sin(np.deg2rad(5))) & weather.dni.gt(0)
    assert suppressed.sum() > 20
    lines = Path(epw_path).read_text().splitlines()
    for position in np.flatnonzero(suppressed):
        fields = lines[position + 8].split(",")
        fields[14] = "0"  # EPW direct-normal radiation only; other inputs fixed.
        lines[position + 8] = ",".join(fields)
    counterfactual = tmp_path / "suppressed_dni.epw"
    counterfactual.write_text("\n".join(lines) + "\n")
    altered = run_energyplus(counterfactual, tmp_path / "suppressed_simulation")
    solar_difference = (
        reference["summary"]["window_solar_kwh"]
        - altered["summary"]["window_solar_kwh"]
    )
    assert solar_difference > 1
    evidence = {
        "purpose": "deterministic regression: effect of removing valid low-sun DNI",
        "engine_version": reference["engine_version"],
        "year": 2023,
        "latitude": 65,
        "longitude": 20,
        "suppressed_hours": int(suppressed.sum()),
        "same_weather_and_building_except_dni": True,
        "reference": reference["summary"],
        "suppressed_dni": altered["summary"],
        "window_solar_difference_kwh": solar_difference,
    }
    destination = Path(os.environ.get("SMHI2EPW_VALIDATION_DIR", tmp_path))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "low_sun_response.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )


def test_required_engine_is_not_silently_skipped(tmp_path, monkeypatch):
    """A missing engine is an integration failure, even with valid weather."""
    monkeypatch.setenv("ENERGYPLUS_EXE", str(tmp_path / "missing-energyplus"))
    with pytest.raises(FileNotFoundError):
        run_energyplus(tmp_path / "unused.epw", tmp_path / "unused-output")
