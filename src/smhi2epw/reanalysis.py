"""Fetch explicitly selected ERA5 hourly weather through Open-Meteo.

The public archive service is noncommercial and rate limited. Responses use
UTC instantaneous meteorology and preceding-hour mean solar radiation. This
adapter adds neither a new dependency nor implicit model selection.
"""

from __future__ import annotations

from urllib.parse import urlencode

import numpy as np
import pandas as pd

from .errors import IngestionError
from .ingestion import CachedClient

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = {
    "temperature_2m": ("dry_bulb", "°C"),
    "relative_humidity_2m": ("relative_humidity", "%"),
    "surface_pressure": ("reanalysis_surface_pressure", "hPa"),
    "wind_speed_10m": ("wind_speed", "m/s"),
    "wind_direction_10m": ("wind_direction", "°"),
    "cloud_cover": ("cloud_cover", "%"),
    "shortwave_radiation": ("ghi", "W/m²"),
    "direct_normal_irradiance": ("dni", "W/m²"),
    "direct_radiation": ("dirh", "W/m²"),
}


def fetch(
    latitude: float,
    longitude: float,
    elevation: float | None,
    index: pd.DatetimeIndex,
    client: CachedClient,
) -> tuple[pd.DataFrame, dict]:
    """Return unit-checked ERA5 values aligned to the buffered UTC grid.

    Request dates include both calendar boundaries required by Local Standard
    Time export. Surface pressure is returned in Pa at the provider's resolved
    elevation; cloud percentage is converted to SMHI-compatible octas. Missing
    hourly values remain NaN for final source selection and validation.
    """
    params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": index[0].strftime("%Y-%m-%d"),
        "end_date": index[-1].strftime("%Y-%m-%d"),
        "hourly": ",".join(VARIABLES),
        "models": "era5",
        "timezone": "GMT",
        "temperature_unit": "celsius",
        "wind_speed_unit": "ms",
        "timeformat": "iso8601",
    }
    if elevation is not None:
        params["elevation"] = elevation
    url = ENDPOINT + "?" + urlencode(params)
    payload = client.get_json(url)
    if not isinstance(payload, dict) or payload.get("error"):
        raise IngestionError("Open-Meteo returned an invalid ERA5 response")
    hourly = payload.get("hourly")
    units = payload.get("hourly_units")
    if not isinstance(hourly, dict) or not isinstance(units, dict):
        raise IngestionError("ERA5 response lacks hourly data or units")
    if payload.get("utc_offset_seconds") != 0:
        raise IngestionError("ERA5 response must use UTC")
    try:
        times = pd.DatetimeIndex(
            pd.to_datetime(pd.Series(hourly["time"]), utc=True, errors="raise")
        )
        if len(times) == 0 or not times.is_unique or not times.is_monotonic_increasing:
            raise ValueError("timestamps are empty, duplicated or reordered")
        if not (times.to_series().diff().dropna() == pd.Timedelta(hours=1)).all():
            raise ValueError("timestamps are not continuously hourly")
        if not index.isin(times).all():
            raise ValueError("buffered requested-year timestamps are missing")
        frame = pd.DataFrame(index=times)
        for variable, (column, expected_unit) in VARIABLES.items():
            values = hourly.get(variable)
            if not isinstance(values, list) or len(values) != len(times):
                raise ValueError(f"invalid array length for {variable}")
            if units.get(variable) != expected_unit:
                raise ValueError(
                    f"unexpected unit for {variable}: {units.get(variable)}"
                )
            frame[column] = pd.to_numeric(values, errors="coerce")
        resolved: dict = {
            "provider": "Open-Meteo",
            "model": "ERA5",
            "url": url,
            "latitude": float(payload["latitude"]),
            "longitude": float(payload["longitude"]),
            "elevation_m": float(payload["elevation"]),
            "radiation_interval": "preceding_hour_mean",
            "attribution": "ERA5 / Copernicus Climate Change Service; Open-Meteo (CC BY 4.0)",
        }
        if not all(
            np.isfinite(resolved[key])
            for key in ("latitude", "longitude", "elevation_m")
        ):
            raise ValueError("nonfinite location metadata")
        if (
            not -90 <= resolved["latitude"] <= 90
            or not -180 <= resolved["longitude"] <= 180
        ):
            raise ValueError("invalid grid coordinates")
        if not -1000 <= resolved["elevation_m"] <= 9999:
            raise ValueError("unsupported elevation")
        if elevation is not None and abs(resolved["elevation_m"] - elevation) > 1:
            raise ValueError(
                "resolved elevation differs from requested surface-pressure height"
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise IngestionError(f"Invalid ERA5 hourly response: {exc}") from exc
    frame["reanalysis_surface_pressure"] *= 100.0
    frame["cloud_cover"] *= 8.0 / 100.0
    return frame.reindex(index), resolved
