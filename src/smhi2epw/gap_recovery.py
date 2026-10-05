"""Bounded recovery from quality-filtered, same-hour nearby observations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import constants as C
from . import ingestion as I
from . import processing as P
from .errors import IngestionError

LIMITS = {
    "dry_bulb": (-70, 70),
    "relative_humidity": (0, 100),
    "wind_speed": (0, 40),
    "wind_direction": (0, 360),
    "pressure": (310, 1200),
}


def valid_observations(series, column):
    """Retain finite source observations within representable physical bounds."""
    low, high = LIMITS[column]
    return series.where(np.isfinite(series) & series.between(low, high))


def hourly_observations(series, column):
    """Aggregate valid observations hourly, preserving angular wind continuity."""
    series = valid_observations(series, column)
    if column == "wind_direction":
        angles = np.deg2rad(series)
        sine = np.sin(angles).resample("h").mean()
        cosine = np.cos(angles).resample("h").mean()
        result = np.rad2deg(np.arctan2(sine, cosine)) % 360
        return result.where(np.hypot(sine, cosine) > 1e-8)
    return series.resample("h").mean()


def unresolved(series, column):
    """Locate missing hours the bounded temporal policy cannot reconstruct."""
    kwargs = dict(
        required=False, short_gap_hours=C.SHORT_GAP_HOURS, max_gap_hours=C.MAX_GAP_HOURS
    )
    if column == "wind_direction":
        filled, *_ = P._fill_wind_direction(series, **kwargs)
    else:
        filled, *_ = P._fill_scalar_series(series, solar=False, **kwargs)
    return filled.isna()


def recover(
    frame,
    station,
    year,
    latitude,
    longitude,
    client,
    *,
    max_distance_km=75.0,
    max_stations=3,
):
    """Modify only invalid/missing primary cells; leave temporal filling to process.

    No solar data is borrowed. Pressure observations remain sea-level QFF and
    are converted to target-site pressure by the existing processing pipeline.
    Whole missing variables are allowed only when actual donor observations
    cover them; the temporal 48-hour ceiling remains in force.
    """
    report = P.ProcessingReport()
    columns = list(C.METOBS_REQUIRED_PARAMETERS.values())
    originals = {}
    masks = {}
    for column in columns:
        series = (
            frame[column] if column in frame else pd.Series(np.nan, index=frame.index)
        )
        cleaned = valid_observations(series, column)
        report.invalid_observation_hours[column] = int(
            (series.notna() & cleaned.isna()).sum()
        )
        report.primary_missing_hours[column] = int(cleaned.isna().sum())
        originals[column] = cleaned.copy()
        frame[column] = cleaned
        masks[column] = unresolved(cleaned, column)
    report.required_reconstructed_fraction = sum(
        report.primary_missing_hours.values()
    ) / (len(frame) * len(columns))
    if not any(mask.any() for mask in masks.values()):
        return report
    # Each variable may use a different station. Require metadata coverage for
    # that variable, rather than unnecessarily requiring all five at each donor.
    candidates = {}
    for parameter, column in C.METOBS_REQUIRED_PARAMETERS.items():
        if not masks[column].any():
            continue
        for sid, record in I._stations_for_parameter(parameter, client).items():
            distance = I._haversine_km(latitude, longitude, record[0], record[1])
            if (
                sid != station.station_id
                and distance <= max_distance_km
                and I._covers_year(record, year)
            ):
                candidate = candidates.setdefault(
                    sid, {"distance": distance, "parameters": {}}
                )
                candidate["parameters"][parameter] = column
    window = (frame.index[0], frame.index[-1])
    for sid, candidate in sorted(
        candidates.items(), key=lambda item: (item[1]["distance"], item[0])
    )[:max_stations]:
        attempt = {"station_id": sid, "errors": {}}
        report.gap_fallback_attempts.append(attempt)
        try:
            meta = I.get_station_metadata(sid, client, year=year)
        except IngestionError as exc:
            attempt["errors"]["metadata"] = str(exc)
            continue
        distance = meta.distance_km(latitude, longitude)
        if distance > max_distance_km:
            attempt["errors"]["metadata"] = (
                "Year-specific position exceeds fallback radius"
            )
            continue
        source = {
            "station_id": sid,
            "latitude": meta.latitude,
            "longitude": meta.longitude,
            "distance_km": distance,
            "method": "same_hour_observation",
            "filled_hours": {},
            "intervals_utc": {},
            "overlap": {},
        }
        for parameter, column in candidate["parameters"].items():
            if not masks[column].any():
                continue
            try:
                observations = I.fetch_metobs_parameter(
                    sid,
                    parameter,
                    column,
                    window,
                    client,
                    accepted_quality=C.METOBS_ACCEPTED_QUALITY,
                )
            except IngestionError as exc:
                attempt["errors"][column] = str(exc)
                continue
            donor = hourly_observations(observations, column).reindex(frame.index)
            replace = masks[column] & donor.notna() & frame[column].isna()
            count = int(replace.sum())
            if not count:
                continue
            overlap = originals[column].notna() & donor.notna()
            difference = donor[overlap] - originals[column][overlap]
            if column == "wind_direction":
                difference = (difference + 180) % 360 - 180
            source["overlap"][column] = {
                "hours": int(overlap.sum()),
                "mean_absolute_difference": float(difference.abs().mean())
                if overlap.any()
                else None,
                "mean_difference": float(difference.mean()) if overlap.any() else None,
            }
            frame.loc[replace, column] = donor[replace]
            source["filled_hours"][column] = count
            source["intervals_utc"][column] = [
                [frame.index[start].isoformat(), frame.index[end - 1].isoformat()]
                for start, end in P._gap_runs(replace.to_numpy())
            ]
            report.cross_station_filled_hours[column] = (
                report.cross_station_filled_hours.get(column, 0) + count
            )
            masks[column] = unresolved(frame[column], column)
        if source["filled_hours"]:
            report.gap_fallback_sources.append(source)
        if not any(mask.any() for mask in masks.values()):
            break
    return report
