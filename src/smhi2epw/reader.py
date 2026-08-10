"""Read EnergyPlus Weather files into analysis-ready pandas data frames.

The compiler writes EPW files, but many teaching and quality-control workflows
start by reading an existing AMY or TMY.  This module provides a deliberately
small reader that preserves the EPW calendar fields, names all 35 columns, and
understands the field-specific missing-value sentinels defined by EnergyPlus.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from .errors import ValidationError
from .export import _validate_header

EPW_COLUMNS: Final[tuple[str, ...]] = (
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "data_source_and_uncertainty_flags",
    "dry_bulb",
    "dew_point",
    "relative_humidity",
    "pressure",
    "extraterrestrial_horizontal",
    "extraterrestrial_direct_normal",
    "horizontal_ir",
    "ghi",
    "dni",
    "dhi",
    "global_horizontal_illuminance",
    "direct_normal_illuminance",
    "diffuse_horizontal_illuminance",
    "zenith_luminance",
    "wind_direction",
    "wind_speed",
    "total_sky_cover",
    "opaque_sky_cover",
    "visibility",
    "ceiling_height",
    "present_weather_observation",
    "present_weather_codes",
    "precipitable_water",
    "aerosol_optical_depth",
    "snow_depth",
    "days_since_last_snowfall",
    "albedo",
    "liquid_precipitation_depth",
    "liquid_precipitation_quantity",
)
"""Canonical names of the 35 EPW data fields, in file order."""

_TEXT_COLUMNS = {
    "data_source_and_uncertainty_flags",
    "present_weather_codes",
}
_TEXT_MISSING_TOKENS = {"present_weather_codes": "999999999"}

_MISSING_TOKENS = {
    "dry_bulb": 99.9,
    "dew_point": 99.9,
    "relative_humidity": 999,
    "pressure": 999999,
    "extraterrestrial_horizontal": 9999,
    "extraterrestrial_direct_normal": 9999,
    "horizontal_ir": 9999,
    "ghi": 9999,
    "dni": 9999,
    "dhi": 9999,
    "global_horizontal_illuminance": 999999,
    "direct_normal_illuminance": 999999,
    "diffuse_horizontal_illuminance": 999999,
    "zenith_luminance": 9999,
    "wind_direction": 999,
    "wind_speed": 99.9,
    "total_sky_cover": 99,
    "opaque_sky_cover": 99,
    "visibility": 9999,
    "ceiling_height": 99999,
    "present_weather_observation": 9,
    "precipitable_water": 999,
    "aerosol_optical_depth": 0.999,
    "snow_depth": 999,
    "days_since_last_snowfall": 99,
    "albedo": 999,
    "liquid_precipitation_depth": 999,
    "liquid_precipitation_quantity": 99,
}


def _parse_location(line: str) -> dict[str, object]:
    """Parse the first EPW header line into friendly location metadata.

    Parameters
    ----------
    line
        Comma-separated ``LOCATION`` record.

    Returns
    -------
    dict
        Text identifiers plus numeric latitude, longitude, UTC offset, and
        elevation.

    Raises
    ------
    ValidationError
        If field count, keyword, or numeric conversion is invalid.
    """
    fields = next(csv.reader([line]))
    if len(fields) != 10 or fields[0] != "LOCATION":
        raise ValidationError("EPW LOCATION header must contain exactly 10 fields")
    try:
        return {
            "city": fields[1],
            "region": fields[2],
            "country": fields[3],
            "source": fields[4],
            "wmo_id": fields[5],
            "latitude": float(fields[6]),
            "longitude": float(fields[7]),
            "time_zone": float(fields[8]),
            "elevation": float(fields[9]),
        }
    except ValueError as exc:
        raise ValidationError(
            "EPW LOCATION header has invalid numeric metadata"
        ) from exc


def _validate_read_frame(frame: pd.DataFrame) -> None:
    """Validate EPW row cardinality, calendar fields, and physical ranges.

    Missing sentinels must already be represented by ``NaN``. Missing optional
    fields are accepted, but every finite value must fall within its EPW range.
    Both 8760-row common years and 8784-row leap years are supported, including
    TMY files whose calendar-year column changes between representative months.
    """
    if len(frame) not in {8760, 8784}:
        raise ValidationError(f"EPW data has {len(frame)} rows; expected 8760 or 8784")

    ranges = {
        "month": (1.0, 12.0),
        "day": (1.0, 31.0),
        "hour": (1.0, 24.0),
        "minute": (0.0, 60.0),
        "dry_bulb": (-70.0, 70.0),
        "dew_point": (-70.0, 70.0),
        "relative_humidity": (0.0, 110.0),
        "pressure": (31000.0, 120000.0),
        "horizontal_ir": (0.0, np.inf),
        "ghi": (0.0, np.inf),
        "dni": (0.0, np.inf),
        "dhi": (0.0, np.inf),
        "wind_direction": (0.0, 360.0),
        "wind_speed": (0.0, 40.0),
        "total_sky_cover": (0.0, 10.0),
        "opaque_sky_cover": (0.0, 10.0),
    }
    for column, (minimum, maximum) in ranges.items():
        values = frame[column].dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValidationError(f"EPW column '{column}' contains nonfinite data")
        if np.any(values < minimum) or np.any(values > maximum):
            raise ValidationError(
                f"EPW column '{column}' contains values outside [{minimum}, {maximum}]"
            )

    paired = frame[["dry_bulb", "dew_point"]].dropna()
    if np.any(paired["dew_point"].to_numpy() > paired["dry_bulb"].to_numpy() + 0.2):
        raise ValidationError("EPW dew point exceeds dry-bulb temperature")


def read_epw(
    path: str | os.PathLike[str],
    *,
    validate: bool = True,
    missing_as_nan: bool = True,
) -> pd.DataFrame:
    """Read an AMY or TMY EPW file into a labelled data frame.

    Parameters
    ----------
    path
        Path to an EnergyPlus Weather file.
    validate
        If ``True``, require eight standard headers, 35 fields per row,
        8760 or 8784 data rows, and valid calendar and physical ranges.
    missing_as_nan
        If ``True``, replace each field's EnergyPlus missing sentinel with
        ``numpy.nan``.  Set this to ``False`` when inspecting the raw encoding.

    Returns
    -------
    pandas.DataFrame
        The 35 EPW fields under :data:`EPW_COLUMNS`.  EPW calendar columns are
        preserved rather than converted to an index because TMY files may use
        different representative years for different months.  The original
        headers, parsed location metadata, and source path are available as
        ``frame.attrs['header']``, ``frame.attrs['location']``, and
        ``frame.attrs['source_path']``.

    Raises
    ------
    ValidationError
        If the file cannot be decoded as a structurally valid EPW file.

    Notes
    -----
    EPW hours are numbered 1 through 24 and describe the interval ending at
    that hour.  Thus hour 1 represents 00:00--01:00 and hour 24 represents
    23:00--24:00 in local standard time.

    Examples
    --------
    >>> from smhi2epw import read_epw
    >>> weather = read_epw("gothenburg_2023.epw")  # doctest: +SKIP
    >>> weather[["dry_bulb", "ghi"]].describe()  # doctest: +SKIP
    >>> weather.attrs["location"]["city"]  # doctest: +SKIP
    'Gothenburg'
    """
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValidationError(f"could not read EPW file '{source}': {exc}") from exc

    if len(rows) < 8:
        raise ValidationError("EPW file contains fewer than eight header lines")
    header = [",".join(row) for row in rows[:8]]
    if validate:
        _validate_header(header)
    location = _parse_location(header[0])

    data_rows = rows[8:]
    for number, row in enumerate(data_rows, start=9):
        if len(row) != len(EPW_COLUMNS):
            raise ValidationError(
                f"EPW line {number} has {len(row)} fields instead of 35"
            )

    frame = pd.DataFrame(data_rows, columns=EPW_COLUMNS)
    for column in EPW_COLUMNS:
        if column in _TEXT_COLUMNS:
            frame[column] = frame[column].astype("string")
        else:
            raw = frame[column]
            converted = pd.to_numeric(raw, errors="coerce")
            if validate and converted.isna().any():
                bad_rows = (converted.isna()).to_numpy().nonzero()[0]
                raise ValidationError(
                    f"EPW column '{column}' contains a nonnumeric value on "
                    f"data row {int(bad_rows[0]) + 1}"
                )
            frame[column] = converted
    validation_frame = frame
    if missing_as_nan:
        for column, token in _MISSING_TOKENS.items():
            frame[column] = frame[column].mask(frame[column] == token)
        for column, text_token in _TEXT_MISSING_TOKENS.items():
            frame[column] = frame[column].mask(frame[column] == text_token)
    elif validate:
        validation_frame = frame.copy()
        for column, token in _MISSING_TOKENS.items():
            validation_frame[column] = validation_frame[column].mask(
                validation_frame[column] == token
            )

    if validate:
        _validate_read_frame(validation_frame)

    frame.attrs["header"] = tuple(header)
    frame.attrs["location"] = location
    frame.attrs["source_path"] = str(source)
    return frame
