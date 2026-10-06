"""Run the tutorial's small building and validate its EnergyPlus outputs.

EnergyPlus is optional for weather compilation. This helper is shared by the
simulation notebook and the required release tests, so both inspect the same
model, diagnostics, calendar, and sensible-energy totals.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE_VERSION = "24.2.0-94a887817b"
# Explicit names keep the SQL checks readable and prevent silently selecting a
# different zone, reporting interval, or similarly named output variable.
VARIABLES = {
    "dry_bulb": "Site Outdoor Air Drybulb Temperature",
    "direct_solar": "Site Direct Solar Radiation Rate per Area",
    "diffuse_solar": "Site Diffuse Solar Radiation Rate per Area",
    "zone_temperature": "Zone Mean Air Temperature",
    "heating_kwh": "Zone Ideal Loads Supply Air Sensible Heating Energy",
    "cooling_kwh": "Zone Ideal Loads Supply Air Sensible Cooling Energy",
    "window_solar_kwh": "Surface Window Transmitted Solar Radiation Energy",
}
ENERGY_COLUMNS = ("heating_kwh", "cooling_kwh", "window_solar_kwh")


def find_energyplus(executable: str | Path | None = None) -> Path:
    """Find the pinned engine from an argument, ENERGYPLUS_EXE, or PATH.

    A missing or different build raises an error. Integration tests must never
    pass by skipping the consumer they are intended to validate.
    """
    candidate = (
        executable or os.environ.get("ENERGYPLUS_EXE") or shutil.which("energyplus")
    )
    if candidate is None:
        raise FileNotFoundError(
            "Set ENERGYPLUS_EXE or put EnergyPlus on PATH; see examples/README.md"
        )
    path = Path(candidate).expanduser().resolve()
    version = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, check=True
    )
    if ENGINE_VERSION not in version.stdout:
        raise ValueError(
            f"Expected EnergyPlus {ENGINE_VERSION}, received {version.stdout.strip()}"
        )
    return path


def _read_results(database: Path, year: int) -> tuple[pd.DataFrame, dict]:
    """Read actual-weather hourly results and reconcile annual energy totals."""
    with sqlite3.connect(database) as connection:
        records = pd.read_sql_query(
            """SELECT t.TimeIndex, t.Year, t.Month, t.Day, t.Hour, t.Dst,
                      d.Name, d.ReportingFrequency, r.Value
               FROM ReportData r
               JOIN ReportDataDictionary d USING (ReportDataDictionaryIndex)
               JOIN Time t USING (TimeIndex)
               JOIN EnvironmentPeriods e USING (EnvironmentPeriodIndex)
               WHERE e.EnvironmentType = 3 AND COALESCE(t.WarmupFlag, 0) = 0
               ORDER BY t.TimeIndex""",
            connection,
        )
    hourly_records = records[records.ReportingFrequency == "Hourly"]
    time = hourly_records.drop_duplicates("TimeIndex").set_index("TimeIndex")
    if not time.Dst.eq(0).all():
        raise ValueError("The tutorial requires Local Standard Time without DST")
    # EnergyPlus uses hours 1..24; hour 24 is midnight after the listed date.
    stamps = pd.to_datetime(time[["Year", "Month", "Day"]].rename(columns=str.lower))
    stamps += pd.to_timedelta(time.Hour, unit="h")
    expected = pd.date_range(f"{year}-01-01 01:00", f"{year + 1}-01-01 00:00", freq="h")
    if not pd.DatetimeIndex(stamps).equals(expected):
        raise ValueError(
            "EnergyPlus did not consume the complete actual-year hourly calendar"
        )
    hourly = pd.DataFrame(index=expected)
    annual = records[records.ReportingFrequency == "Run Period"]
    for short_name, variable in VARIABLES.items():
        values = (
            hourly_records[hourly_records.Name == variable].set_index("TimeIndex").Value
        )
        if not values.index.is_unique or not values.index.equals(time.index):
            raise ValueError(f"Missing or duplicate hourly results for {variable}")
        hourly[short_name] = values.to_numpy(dtype=float)
        if short_name in ENERGY_COLUMNS:
            totals = annual[annual.Name == variable].Value.to_numpy(dtype=float)
            if len(totals) != 1 or not np.isfinite(totals).all():
                raise ValueError(f"Expected one finite annual energy for {variable}")
            if not np.isclose(hourly[short_name].sum(), totals[0], rtol=1e-8, atol=0.1):
                raise ValueError(
                    f"Hourly energy does not reconcile with the annual {variable}"
                )
            hourly[short_name] /= 3_600_000  # EnergyPlus reports joules; present kWh.
    if not np.isfinite(hourly.to_numpy()).all():
        raise ValueError("EnergyPlus returned nonfinite weather or building outputs")
    if (hourly[["direct_solar", "diffuse_solar", *ENERGY_COLUMNS]] < -1e-8).any().any():
        raise ValueError("EnergyPlus returned negative solar radiation or energy")
    summary = {
        "hours": len(hourly),
        **{name: float(hourly[name].sum()) for name in ENERGY_COLUMNS},
    }
    return hourly, summary


def run_energyplus(
    epw_path: str | Path,
    output_dir: str | Path,
    executable: str | Path | None = None,
) -> dict:
    """Simulate the versioned one-zone model and return hourly and annual results.

    Output directories must be new so that old SQL or completion files cannot
    masquerade as results from a failed run. All engine warnings fail this
    small fixture; severe and fatal errors are never accepted. Reported loads
    are delivered sensible energy, not HVAC electricity or fuel consumption.
    """
    engine = find_energyplus(executable)
    weather = Path(epw_path).resolve()
    # Fail on mixed-year input before creating output. The package reader also
    # checks the 35-field EPW records and complete hour-ending calendar.
    from smhi2epw import read_epw

    frame = read_epw(weather)
    with weather.open(encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        for _ in range(8):
            next(rows)
        year = int(next(rows)[0])
    if len(frame) != (8784 if pd.Timestamp(year, 12, 31).is_leap_year else 8760):
        raise ValueError("Expected a complete EPW calendar year")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    template = Path(__file__).with_name("single_zone.idf").read_text(encoding="utf-8")
    model = output / "single_zone.idf"
    model.write_text(template.replace("@YEAR@", str(year)), encoding="utf-8")
    process = subprocess.run(
        [
            str(engine),
            "--weather",
            str(weather),
            "--output-directory",
            str(output),
            str(model),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,  # Inspect completion and diagnostics together below.
    )
    (output / "engine.log").write_text(
        process.stdout + process.stderr, encoding="utf-8"
    )
    diagnostics = (output / "eplusout.err").read_text(encoding="utf-8")
    completion = (output / "eplusout.end").read_text(encoding="utf-8")
    if process.returncode or "EnergyPlus Completed Successfully" not in completion:
        raise RuntimeError(
            f"EnergyPlus failed; inspect {output / 'eplusout.err'}\n{diagnostics}"
        )
    if re.search(
        r"\*\*\s*(Warning|Severe|Fatal)\s*\*\*", diagnostics, flags=re.IGNORECASE
    ):
        raise RuntimeError(f"EnergyPlus diagnostics require review:\n{diagnostics}")
    # Check summary counts too, including warnings summarized by the engine.
    if not re.search(r"\b0 Warning;\s*0 Severe Errors", completion):
        raise RuntimeError(
            f"EnergyPlus did not finish with clean diagnostics: {completion}"
        )
    hourly, summary = _read_results(output / "eplusout.sql", year)
    summary["warning_count"] = 0
    return {
        "hourly": hourly,
        "summary": summary,
        "engine_version": ENGINE_VERSION,
        "output_dir": output,
    }
