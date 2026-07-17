"""Export layer: UTC->LST shift, EPW row formatting and streaming file writer."""

from __future__ import annotations

import logging
from typing import Iterable, List

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
    naive_utc = frame.tz_localize(None)
    lst = frame.copy()
    lst.index = naive_utc.index + pd.Timedelta(hours=utc_offset)

    n_hours = expected_rows(year)
    grid = pd.date_range(
        start=pd.Timestamp(year, 1, 1, 1, 0, 0), periods=n_hours, freq="h"
    )
    out = lst.reindex(grid)
    # Fill the handful of boundary hours introduced by the constant shift.
    out = out.bfill().ffill()
    return out


# --------------------------------------------------------------------------- #
# Field formatting helpers
# --------------------------------------------------------------------------- #
def _fmt_float(value: float, missing: float, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return f"{missing:.{decimals}f}"
    return f"{float(value):.{decimals}f}"


def _fmt_int(value: float, missing: int) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
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
) -> List[str]:
    """Return the 8 mandatory EPW header lines."""
    return [
        (
            f"LOCATION,{city},{region},{country},SMHI-AMY,{wmo_id},"
            f"{latitude:.4f},{longitude:.4f},{time_zone:.1f},{elevation:.1f}"
        ),
        "DESIGN CONDITIONS,0",
        "TYPICAL/ACTUAL WEATHER PERIODS,1,1,Actual,1/1,12/31",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,Generated via smhi2epw hybrid compiler utility.",
        (
            "COMMENTS 2,Thermodynamics via SMHI MetObs. "
            "Solar Vectors via SMHI STRÅNG Mesoscale Model."
        ),
        "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
    ]


# --------------------------------------------------------------------------- #
# EPW data rows
# --------------------------------------------------------------------------- #
def _row_iter(frame: pd.DataFrame) -> Iterable[str]:
    """Yield formatted EPW data lines from an LST-gridded frame."""
    index = frame.index
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
        sky = _fmt_int(rec.get("sky_cover"), sd["total_sky_cover"])
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
            sky,
            sky,
            tail,
        ]
        yield ",".join(fields)


def write_epw(
    path: str,
    header_lines: List[str],
    frame: pd.DataFrame,
    year: int,
) -> int:
    """Stream the EPW file to ``path`` and return the number of data rows."""
    expected = expected_rows(year)
    if len(frame) != expected:
        raise ValidationError(
            f"row cardinality mismatch: got {len(frame)} rows, "
            f"expected {expected} for year {year}"
        )

    written = 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for line in header_lines:
            fh.write(line + "\n")
        for line in _row_iter(frame):
            fh.write(line + "\n")
            written += 1

    if written != expected:
        raise ValidationError(
            f"wrote {written} rows, expected {expected} for year {year}"
        )
    return written
