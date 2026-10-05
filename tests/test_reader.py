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


@pytest.mark.parametrize("minute", [0, 60])
def test_read_epw_accepts_consistent_hourly_minute_conventions(tmp_path, minute):
    path = _write_valid_epw(tmp_path / "minutes.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    for row in rows[8:]:
        row[4] = str(minute)
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    assert read_epw(path)["minute"].eq(minute).all()


def test_read_epw_accepts_leap_composite_tmy_calendar(tmp_path):
    path = _write_valid_epw(tmp_path / "leap-composite.epw", 2020)
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    for row in rows[8:]:
        month = int(row[1])
        row[0] = str(2004 if month == 2 else 2000 + month)
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    assert len(read_epw(path)) == 8784


@pytest.mark.parametrize(
    "column,value",
    [
        ("year", "2021.5"),
        ("month", "1.5"),
        ("day", "1.5"),
        ("hour", "1.5"),
        ("minute", "0.5"),
        ("year", "inf"),
    ],
)
def test_read_epw_rejects_noninteger_calendar_fields(tmp_path, column, value):
    path = _write_valid_epw(tmp_path / "fractional.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    rows[8][EPW_COLUMNS.index(column)] = value
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match=f"'{column}'.*finite integers"):
        read_epw(path)


@pytest.mark.parametrize("day", [29, 31])
def test_read_epw_rejects_impossible_representative_date(tmp_path, day):
    path = _write_valid_epw(tmp_path / "impossible.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    february = next(row for row in rows[8:] if row[1] == "2")
    february[2] = str(day)
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="impossible calendar date"):
        read_epw(path)


@pytest.mark.parametrize("corruption", ["duplicate", "reordered", "missing"])
def test_read_epw_rejects_incomplete_ordered_calendar(tmp_path, corruption):
    path = _write_valid_epw(tmp_path / "sequence.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    if corruption == "duplicate":
        rows[9] = rows[8].copy()
    elif corruption == "reordered":
        rows[8], rows[9] = rows[9], rows[8]
    else:
        # Keep cardinality valid while skipping one hour and appending a duplicate.
        rows.pop(9)
        rows.append(rows[-1].copy())
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="complete ordered hourly calendar"):
        read_epw(path)


@pytest.mark.parametrize("minute", [30, 60])
def test_read_epw_rejects_intermediate_or_mixed_minutes(tmp_path, minute):
    path = _write_valid_epw(tmp_path / "mixed-minutes.epw")
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    rows[8][4] = "0"
    rows[9][4] = str(minute)
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="consistently be 0 or 60"):
        read_epw(path)


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


@pytest.mark.parametrize(
    "year,flag,count,weekday",
    [
        (2020, "Yes", 8784, "Wednesday"),
        (2021, "No", 8760, "Friday"),
        (2000, "Yes", 8784, "Saturday"),
        (2100, "No", 8760, "Friday"),
    ],
)
def test_actual_year_export_header_and_february_rows(
    tmp_path, year, flag, count, weekday
):
    path = _write_valid_epw(tmp_path / "weather.epw", year)
    lines = path.read_text().splitlines()
    assert lines[4] == f"HOLIDAYS/DAYLIGHT SAVINGS,{flag},0,0,0"
    assert lines[7] == f"DATA PERIODS,1,1,Data,{weekday},1/1,12/31"
    assert len(lines) == 8 + count
    feb29 = [line for line in lines[8:] if line.split(",")[1:3] == ["2", "29"]]
    assert len(feb29) == (24 if flag == "Yes" else 0)


@pytest.mark.parametrize(
    "line_number,value,message",
    [
        (4, "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0", "leap-day header"),
        (7, "DATA PERIODS,1,1,Data,Friday,1/1,12/31", "data-period header"),
    ],
)
def test_export_rejects_inconsistent_actual_year_headers(
    tmp_path, line_number, value, message, monkeypatch
):
    original = build_header

    def inconsistent_header(*args, **kwargs):
        header = original(*args, **kwargs)
        header[line_number] = value
        return header

    monkeypatch.setattr(
        __import__(__name__, fromlist=["build_header"]),
        "build_header",
        inconsistent_header,
    )
    path = tmp_path / "weather.epw"
    path.write_text("preserve existing artifact")
    with pytest.raises(ValidationError, match=message):
        _write_valid_epw(path, 2020)
    assert path.read_text() == "preserve existing artifact"
