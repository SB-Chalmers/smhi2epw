"""Export layer: UTC-to-LST shift, EPW formatting, validation, and atomic writes."""

from __future__ import annotations

import calendar
import csv
import io
import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List

import numpy as np
import pandas as pd

from . import constants as C
from .errors import ValidationError

log = logging.getLogger("smhi2epw")


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def expected_rows(year: int) -> int:
    return 8784 if is_leap_year(year) else 8760


# --------------------------------------------------------------------------- #
# UTC -> Local Standard Time shift (DST ignored)
# --------------------------------------------------------------------------- #
def shift_to_lst(frame: pd.DataFrame, year: int, utc_offset: float) -> pd.DataFrame:
    """Relabel a UTC-indexed frame onto the target-year LST hour grid.

    The grid runs from ``year-01-01 01:00`` to ``year+1-01-01 00:00`` so that
    each calendar day is represented by hours 1..24, where hour 24 is midnight
    at the end of the day. DST is intentionally ignored (constant offset).
    """
    frame_index = pd.DatetimeIndex(frame.index)
    if frame_index.tz is None:
        raise ValidationError("UTC source frame must have a timezone-aware index")
    if not float(utc_offset).is_integer():
        raise ValidationError("fractional UTC offsets are not supported")

    n_hours = expected_rows(year)
    grid = pd.date_range(
        start=pd.Timestamp(year, 1, 1, 1, 0, 0), periods=n_hours, freq="h"
    )
    source_index = (grid - pd.Timedelta(hours=utc_offset)).tz_localize("UTC")
    missing = source_index.difference(frame_index)
    if len(missing):
        raise ValidationError(
            f"UTC source frame does not cover {len(missing)} required LST hours"
        )
    out = frame.reindex(source_index).copy()
    out.index = grid
    return out


# --------------------------------------------------------------------------- #
# Field formatting helpers
# --------------------------------------------------------------------------- #
def _fmt_float(value: Any, missing: float, decimals: int = 1) -> str:
    if value is None or bool(pd.isna(value)):
        return f"{missing:.{decimals}f}"
    return f"{float(value):.{decimals}f}"


def _fmt_int(value: Any, missing: float) -> str:
    if value is None or bool(pd.isna(value)):
        return str(int(missing))
    return str(int(round(float(value))))


# --------------------------------------------------------------------------- #
# EPW header
# --------------------------------------------------------------------------- #
def build_header(
    city: str,
    region: str,
    country: str,
    wmo_id: str,
    latitude: float,
    longitude: float,
    time_zone: float,
    elevation: float,
    year: int,
    station_id: int,
) -> List[str]:
    """Return the 8 mandatory EPW header lines."""
    text_fields = (city, region, country, wmo_id)
    if any(
        "," in str(value) or "\n" in str(value) or "\r" in str(value)
        for value in text_fields
    ):
        raise ValidationError(
            "EPW header text fields cannot contain commas or newlines"
        )
    start_weekday = calendar.day_name[date(year, 1, 1).weekday()]
    return [
        (
            f"LOCATION,{city},{region},{country},SMHI-AMY,{wmo_id},"
            f"{latitude:.4f},{longitude:.4f},{time_zone:.1f},{elevation:.1f}"
        ),
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        (
            "COMMENTS 1,Generated via smhi2epw hybrid compiler utility. "
            f"SMHI MetObs station ID {station_id}; actual meteorological year {year}."
        ),
        (
            "COMMENTS 2,Thermodynamics via SMHI MetObs. "
            "Solar via SMHI STRÅNG (strang.smhi.se). "
            "STRÅNG data produced with support from the Swedish Radiation "
            "Protection Authority and the Swedish Environmental Agency."
        ),
        f"DATA PERIODS,1,1,Data,{start_weekday},1/1,12/31",
    ]


# --------------------------------------------------------------------------- #
# EPW data rows
# --------------------------------------------------------------------------- #
def _row_iter(frame: pd.DataFrame) -> Iterable[str]:
    """Yield formatted EPW data lines from an LST-gridded frame."""
    index = pd.DatetimeIndex(frame.index)
    is_midnight = index.hour == 0
    label = index.where(~is_midnight, index - pd.Timedelta(hours=1))
    hours = np.where(is_midnight, 24, index.hour)

    years = label.year.to_numpy()
    months = label.month.to_numpy()
    days = label.day.to_numpy()

    sd = C.EPW_SECONDARY_DEFAULTS
    secondary = (
        f"{sd['global_horizontal_illuminance']},"
        f"{sd['direct_normal_illuminance']},"
        f"{sd['diffuse_horizontal_illuminance']},"
        f"{sd['zenith_luminance']},"
    )
    # Fields 25..35 (everything after the two sky-cover columns).
    tail = (
        f"{sd['visibility']},{sd['ceiling_height']},"
        f"{sd['present_weather_observation']},{sd['present_weather_codes']},"
        f"{sd['precipitable_water']},{sd['aerosol_optical_depth']},"
        f"{sd['snow_depth']},{sd['days_since_last_snowfall']},"
        f"{sd['albedo']},{sd['liquid_precip_depth']},"
        f"{sd['liquid_precip_quantity']}"
    )

    cols = frame.to_dict("records")
    m = C.EPW_MISSING
    for i, rec in enumerate(cols):
        total_sky = _fmt_int(rec.get("sky_cover"), sd["total_sky_cover"])
        opaque_sky = _fmt_int(rec.get("opaque_sky_cover"), sd["opaque_sky_cover"])
        fields = [
            str(int(years[i])),
            str(int(months[i])),
            str(int(days[i])),
            str(int(hours[i])),
            "60",
            C.EPW_DATA_FLAGS,
            _fmt_float(rec.get("dry_bulb"), m["dry_bulb"]),
            _fmt_float(rec.get("dew_point"), m["dew_point"]),
            _fmt_int(rec.get("relative_humidity"), m["relative_humidity"]),
            _fmt_int(rec.get("pressure"), m["pressure"]),
            _fmt_int(rec.get("etrh"), sd["extraterrestrial_horizontal"]),
            _fmt_int(rec.get("etrn"), sd["extraterrestrial_direct_normal"]),
            _fmt_int(rec.get("horizontal_ir"), m["horizontal_ir"]),
            _fmt_int(rec.get("ghi"), m["ghi"]),
            _fmt_int(rec.get("dni"), m["dni"]),
            _fmt_int(rec.get("dhi"), m["dhi"]),
            secondary.rstrip(","),
            _fmt_int(rec.get("wind_direction"), m["wind_direction"]),
            _fmt_float(rec.get("wind_speed"), m["wind_speed"]),
            total_sky,
            opaque_sky,
            tail,
        ]
        yield ",".join(fields)


def write_epw(
    path: str,
    header_lines: List[str],
    frame: pd.DataFrame,
    year: int,
) -> int:
    """Validate and atomically write an EPW file."""
    _validate_header(header_lines)
    _validate_frame(frame, year)
    expected = expected_rows(year)
    rows = list(_row_iter(frame))
    if len(rows) != expected:
        raise ValidationError(
            f"formatted {len(rows)} rows, expected {expected} for year {year}"
        )
    for number, row in enumerate(rows, start=1):
        fields = next(csv.reader(io.StringIO(row)))
        if len(fields) != 35:
            raise ValidationError(
                f"EPW row {number} has {len(fields)} fields instead of 35"
            )

    output = Path(path)
    if not output.parent.exists():
        raise ValidationError(f"output directory does not exist: {output.parent}")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            delete=False,
        ) as fh:
            tmp_path = fh.name
            for line in header_lines:
                fh.write(line + "\n")
            for row in rows:
                fh.write(row + "\n")
        os.replace(tmp_path, output)
    except OSError as exc:
        raise ValidationError(f"could not write EPW file '{path}': {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return len(rows)


def _validate_header(header_lines: List[str]) -> None:
    expected_keywords = [
        "LOCATION,",
        "DESIGN CONDITIONS,",
        "TYPICAL/EXTREME PERIODS,",
        "GROUND TEMPERATURES,",
        "HOLIDAYS/DAYLIGHT SAVINGS,",
        "COMMENTS 1,",
        "COMMENTS 2,",
        "DATA PERIODS,",
    ]
    if len(header_lines) != 8:
        raise ValidationError(f"EPW header has {len(header_lines)} lines instead of 8")
    for number, (line, keyword) in enumerate(
        zip(header_lines, expected_keywords), start=1
    ):
        if not line.startswith(keyword):
            raise ValidationError(
                f"EPW header line {number} must start with '{keyword}'"
            )
        if "\n" in line or "\r" in line:
            raise ValidationError(f"EPW header line {number} contains a newline")


def _validate_frame(frame: pd.DataFrame, year: int) -> None:
    expected = expected_rows(year)
    if len(frame) != expected:
        raise ValidationError(
            f"row cardinality mismatch: got {len(frame)} rows, expected {expected} for year {year}"
        )
    expected_index = pd.date_range(
        start=pd.Timestamp(year, 1, 1, 1), periods=expected, freq="h"
    )
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValidationError("EPW frame index must be unique and increasing")
    if not frame.index.equals(expected_index):
        raise ValidationError("EPW frame does not cover the exact target-year LST grid")

    ranges = {
        "dry_bulb": (-70.0, 70.0),
        "dew_point": (-70.0, 70.0),
        "relative_humidity": (0.0, 100.0),
        "pressure": (31000.0, 120000.0),
        "horizontal_ir": (0.0, np.inf),
        "ghi": (0.0, np.inf),
        "dni": (0.0, np.inf),
        "dhi": (0.0, np.inf),
        "wind_direction": (0.0, 360.0),
        "wind_speed": (0.0, 40.0),
    }
    for column, (minimum, maximum) in ranges.items():
        if column not in frame:
            raise ValidationError(f"required EPW column '{column}' is missing")
        values = frame[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValidationError(
                f"required EPW column '{column}' contains missing/nonfinite data"
            )
        if np.any(values < minimum) or np.any(values > maximum):
            raise ValidationError(
                f"required EPW column '{column}' contains values outside [{minimum}, {maximum}]"
            )
    if np.any(frame["dew_point"].to_numpy() > frame["dry_bulb"].to_numpy() + 0.2):
        raise ValidationError("dew point exceeds dry-bulb temperature")
