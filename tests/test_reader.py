"""Offline tests for the public EPW reader."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smhi2epw import EPW_COLUMNS, read_epw
from smhi2epw.errors import ValidationError
from smhi2epw.export import build_header, expected_rows, write_epw


def _write_valid_epw(path: Path, year: int = 2021) -> Path:
    count = expected_rows(year)
    index = pd.date_range(f"{year}-01-01 01:00", periods=count, freq="h")
    angle = np.arange(count) * 2.0 * np.pi / 24.0
    dry = 10.0 + 5.0 * np.sin(angle)
    frame = pd.DataFrame(
        {
            "dry_bulb": dry,
            "dew_point": dry - 4.0,
            "relative_humidity": 70.0,
            "pressure": 101325.0,
            "etrh": 500.0,
            "etrn": 1367.0,
            "horizontal_ir": 300.0,
            "ghi": np.clip(500.0 * np.sin(angle), 0.0, None),
            "dni": np.clip(600.0 * np.sin(angle), 0.0, None),
            "dhi": np.clip(150.0 * np.sin(angle), 0.0, None),
            "wind_direction": 180.0,
            "wind_speed": 3.0,
            "sky_cover": 5.0,
        },
        index=index,
    )
    header = build_header(
        "Gothenburg", "VG", "SWE", "999999", 57.7156, 11.9924, 1.0, 3.0, year, 71420
    )
    write_epw(str(path), header, frame, year)
    return path


def test_read_epw_round_trip_and_metadata(tmp_path):
    path = _write_valid_epw(tmp_path / "weather.epw")
    weather = read_epw(path)

    assert tuple(weather.columns) == EPW_COLUMNS
    assert len(weather) == 8760
    assert weather.attrs["location"]["city"] == "Gothenburg"
    assert weather.attrs["location"]["latitude"] == pytest.approx(57.7156)
    assert len(weather.attrs["header"]) == 8
    assert weather.attrs["source_path"] == str(path)
    assert weather["opaque_sky_cover"].isna().all()


def test_read_epw_retains_missing_tokens_on_request(tmp_path):
    path = _write_valid_epw(tmp_path / "raw.epw")
    weather = read_epw(path, missing_as_nan=False)
    assert set(weather["opaque_sky_cover"]) == {99}


def test_read_epw_accepts_leap_and_composite_tmy_years(tmp_path):
    leap = read_epw(_write_valid_epw(tmp_path / "leap.epw", 2020))
    assert len(leap) == 8784

    path = _write_valid_epw(tmp_path / "composite.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    representative_years = {month: 2000 + month for month in range(1, 13)}
    for row in rows[8:]:
        row[0] = str(representative_years[int(row[1])])
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    composite = read_epw(path)
    assert composite.groupby("month")["year"].nunique().eq(1).all()
    assert composite["year"].nunique() == 12


def test_read_epw_rejects_wrong_field_count(tmp_path):
    path = _write_valid_epw(tmp_path / "malformed.epw")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[8] = ",".join(lines[8].split(",")[:-1])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="34 fields"):
        read_epw(path)


def test_read_epw_rejects_partial_file(tmp_path):
    path = _write_valid_epw(tmp_path / "partial.epw")
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="8759 rows"):
        read_epw(path)


def test_read_epw_validation_can_be_disabled(tmp_path):
    path = _write_valid_epw(tmp_path / "range.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    rows[8][6] = "85.0"
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="dry_bulb"):
        read_epw(path)
    assert read_epw(path, validate=False).iloc[0]["dry_bulb"] == 85.0


def test_read_epw_reports_invalid_location_header(tmp_path):
    path = _write_valid_epw(tmp_path / "location.epw")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,too,few,fields"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="LOCATION"):
        read_epw(path)


def test_read_epw_rejects_nonnumeric_weather_value(tmp_path):
    path = _write_valid_epw(tmp_path / "nonnumeric.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    rows[8][6] = "not-a-temperature"
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="nonnumeric"):
        read_epw(path)
