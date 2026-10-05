"""Assess nearby same-year observations before reconstructing primary gaps."""

from __future__ import annotations

from typing import Any

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
# Engineering acceptance limits in source units, not accuracy guarantees.
MAX_MAE = {
    "dry_bulb": 3.0,
    "relative_humidity": 15.0,
    "wind_speed": 3.0,
    "wind_direction": 45.0,
    "pressure": 5.0,
}
ASSESSMENT_WINDOW_DAYS = 30
MIN_TRAINING_HOURS = 168
MIN_TRAINING_DATES = 7
MIN_CORRECTION_IMPROVEMENT = 0.10


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
    """Locate missing hours after giving short interpolation first priority.

    Assessed donors precede daily profiles for gaps longer than three hours.
    This preview never modifies the original observations used for assessment.
    Cancelling short wind vectors remain eligible for donor recovery.
    """
    kwargs = dict(
        required=False,
        short_gap_hours=C.SHORT_GAP_HOURS,
        max_gap_hours=C.SHORT_GAP_HOURS,
    )
    if column == "wind_direction":
        filled, *_ = P._fill_wind_direction(series, **kwargs)
    else:
        filled, *_ = P._fill_scalar_series(series, solar=False, **kwargs)
    return filled.isna()


def _differences(predicted, primary, column):
    """Calculate signed scalar differences or shortest angular differences."""
    difference = predicted - primary
    if column == "wind_direction":
        difference = (difference + 180) % 360 - 180
    return difference


def _intervals(mask):
    """Describe contiguous selected hours using inclusive UTC timestamps."""
    return [
        [mask.index[start].isoformat(), mask.index[end - 1].isoformat()]
        for start, end in P._gap_runs(mask.to_numpy())
    ]


def _assessment(primary, donor, column, start, end):
    """Validate raw transfer and scalar offsets against original observations.

    Each gap uses paired observations within thirty days of its boundaries.
    Three complete UTC validation days represent early, middle, and late
    overlap. Their adjacent days are excluded from each training fold to
    avoid fitting on observations immediately neighbouring the held-out day.
    Only scalar median offsets that improve held-out MAE by at least ten
    percent are eligible; angular wind direction always uses raw transfer.
    """
    near = (primary.index >= start - pd.Timedelta(days=ASSESSMENT_WINDOW_DAYS)) & (
        primary.index <= end + pd.Timedelta(days=ASSESSMENT_WINDOW_DAYS)
    )
    overlap = near & primary.notna() & donor.notna()
    paired_primary = primary[overlap]
    paired_donor = donor[overlap]
    assessment = {
        "gap_utc": [start.isoformat(), end.isoformat()],
        "status": "rejected",
        "reason": "insufficient_overlap",
        "overlap_hours": int(overlap.sum()),
        "overlap_period_utc": [
            paired_primary.index[0].isoformat(),
            paired_primary.index[-1].isoformat(),
        ]
        if overlap.any()
        else None,
        "validation_limit_mae": MAX_MAE[column],
        "folds": [],
        "method": None,
        "offset": None,
        "raw_mae": None,
        "corrected_mae": None,
        "selected_mae": None,
        "filled_hours": 0,
        "intervals_utc": [],
    }
    if not overlap.any():
        return assessment
    days = paired_primary.index.tz_convert("UTC").normalize()
    complete_days = pd.Series(1, index=days).groupby(level=0).sum()
    complete_days = complete_days[complete_days == 24].index
    if len(complete_days) < 3:
        return assessment
    selected_days = complete_days[[0, len(complete_days) // 2, -1]]
    raw_errors = []
    corrected_errors = []
    correction_valid = column != "wind_direction"
    for day in selected_days:
        validation = days == day
        training = (days < day - pd.Timedelta(days=1)) | (
            days > day + pd.Timedelta(days=1)
        )
        train_primary = paired_primary[training]
        train_donor = paired_donor[training]
        fold = {
            "validation_day_utc": day.isoformat(),
            "training_hours": int(training.sum()),
            "training_dates": int(days[training].nunique()),
            "training_intervals_utc": _intervals(
                pd.Series(overlap, index=primary.index)
                & ~primary.index.tz_convert("UTC")
                .normalize()
                .isin(pd.date_range(day - pd.Timedelta(days=1), periods=3, freq="D"))
            ),
        }
        assessment["folds"].append(fold)
        if (
            training.sum() < MIN_TRAINING_HOURS
            or days[training].nunique() < MIN_TRAINING_DATES
        ):
            return assessment
        raw_difference = _differences(
            paired_donor[validation], paired_primary[validation], column
        )
        raw_errors.extend(raw_difference.abs().tolist())
        fold["raw_mae"] = float(raw_difference.abs().mean())
        if column != "wind_direction":
            offset = float((train_primary - train_donor).median())
            corrected = paired_donor[validation] + offset
            fold["offset"] = offset
            if valid_observations(corrected, column).isna().any():
                correction_valid = False
            corrected_difference = corrected - paired_primary[validation]
            corrected_errors.extend(corrected_difference.abs().tolist())
            fold["corrected_mae"] = float(corrected_difference.abs().mean())
    raw_mae = float(np.mean(raw_errors))
    corrected_mae = float(np.mean(corrected_errors)) if corrected_errors else None
    use_correction = (
        correction_valid
        and corrected_mae is not None
        and raw_mae > 0
        and corrected_mae <= raw_mae * (1 - MIN_CORRECTION_IMPROVEMENT)
    )
    selected_mae = corrected_mae if use_correction else raw_mae
    assessment.update(
        raw_mae=raw_mae,
        corrected_mae=corrected_mae,
        selected_mae=selected_mae,
        method="median_offset" if use_correction else "same_hour_observation",
        offset=float((paired_primary - paired_donor).median())
        if use_correction
        else 0.0,
    )
    if selected_mae > MAX_MAE[column]:
        assessment["reason"] = "excessive_validation_error"
    else:
        assessment.update(status="accepted", reason=None)
    return assessment


def _warn(report, code, message, column, **details):
    """Append a structured warning describing donor recovery decisions."""
    report.warnings.append(
        {"code": code, "message": message, "variable": column, "details": details}
    )


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
    report: P.ProcessingReport | None = None,
):
    """Fill unresolved primary gaps only with assessed nearby observations.

    Valid original primary observations remain untouched and provide all
    training and validation data. Each parameter resolves its own donor
    metadata, permitting partial stations without temperature observations.
    Pressure stays in sea-level QFF hPa for subsequent target-site conversion.
    Short interpolation retains first priority. Insufficient overlap and
    unsuitable transfers leave gaps for bounded daily profiles and, in
    automatic mode, reanalysis. The caller applies bounded temporal filling.
    """
    report = report if report is not None else P.ProcessingReport()
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
    candidates: dict[int, dict] = {}
    for parameter, column in C.METOBS_REQUIRED_PARAMETERS.items():
        if not masks[column].any():
            continue
        try:
            catalog = I._stations_for_parameter(parameter, client)
        except IngestionError as exc:
            report.gap_fallback_attempts.append(
                {"station_id": None, "errors": {column: str(exc)}}
            )
            _warn(
                report,
                "donor_catalog_failed",
                "Nearby donor discovery failed for a missing variable.",
                column,
                error=str(exc),
            )
            continue
        for sid, record in catalog.items():
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
        attempt: dict[str, Any] = {"station_id": sid, "errors": {}, "assessments": {}}
        report.gap_fallback_attempts.append(attempt)
        source: dict[str, Any] = {
            "station_id": sid,
            "method": "assessed_same_hour_observation",
            "filled_hours": {},
            "intervals_utc": {},
            "overlap": {},
            "assessments": {},
            "parameter_metadata": {},
        }
        for parameter, column in candidate["parameters"].items():
            if not masks[column].any():
                continue
            try:
                meta = I.get_station_metadata(
                    sid, client, year=year, parameter=parameter
                )
                distance = meta.distance_km(latitude, longitude)
                if distance > max_distance_km:
                    raise IngestionError(
                        "Year-specific position exceeds fallback radius"
                    )
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
                _warn(
                    report,
                    "donor_request_failed",
                    "A nearby donor could not provide usable observations.",
                    column,
                    station_id=sid,
                    error=str(exc),
                )
                continue
            metadata = {
                "latitude": meta.latitude,
                "longitude": meta.longitude,
                "distance_km": distance,
            }
            source["parameter_metadata"][column] = metadata
            if "latitude" not in source:
                source.update(metadata)
            donor = hourly_observations(observations, column).reindex(frame.index)
            overlap = originals[column].notna() & donor.notna()
            difference = _differences(
                donor[overlap], originals[column][overlap], column
            )
            source["overlap"][column] = {
                "hours": int(overlap.sum()),
                "mean_absolute_difference": float(difference.abs().mean())
                if overlap.any()
                else None,
                "mean_difference": float(difference.mean()) if overlap.any() else None,
            }
            assessments = []
            total_replace = pd.Series(False, index=frame.index)
            for start, end in P._gap_runs(masks[column].to_numpy()):
                assessment = _assessment(
                    originals[column],
                    donor,
                    column,
                    frame.index[start],
                    frame.index[end - 1],
                )
                assessments.append(assessment)
                if assessment["status"] != "accepted":
                    _warn(
                        report,
                        "donor_rejected",
                        "A nearby donor failed the gap-specific assessment.",
                        column,
                        station_id=sid,
                        reason=assessment["reason"],
                        gap_utc=assessment["gap_utc"],
                    )
                    continue
                corrected = donor + assessment["offset"]
                usable = valid_observations(corrected, column)
                gap = pd.Series(False, index=frame.index)
                gap.iloc[start:end] = True
                invalid_correction = gap & corrected.notna() & usable.isna()
                if invalid_correction.any():
                    _warn(
                        report,
                        "donor_correction_out_of_bounds",
                        "Corrected donor values outside physical bounds were skipped.",
                        column,
                        station_id=sid,
                        hours=int(invalid_correction.sum()),
                    )
                replace = gap & usable.notna() & frame[column].isna()
                frame.loc[replace, column] = usable[replace]
                total_replace |= replace
                assessment["filled_hours"] = int(replace.sum())
                assessment["intervals_utc"] = _intervals(replace)
                if replace.any():
                    _warn(
                        report,
                        "donor_gap_filled",
                        "Missing primary hours were reconstructed from an assessed donor.",
                        column,
                        station_id=sid,
                        method=assessment["method"],
                        offset=assessment["offset"],
                        validation_mae=assessment["selected_mae"],
                        hours=int(replace.sum()),
                    )
            attempt["assessments"][column] = assessments
            source["assessments"][column] = assessments
            count = int(total_replace.sum())
            if count:
                source["filled_hours"][column] = count
                source["intervals_utc"][column] = _intervals(total_replace)
                report.cross_station_filled_hours[column] = (
                    report.cross_station_filled_hours.get(column, 0) + count
                )
                # Eligibility is fixed by the original gap. Small holes left
                # by one donor still get a chance to use the next donor before
                # the caller falls back to interpolation or daily profiles.
                masks[column] &= frame[column].isna()
        if source["filled_hours"]:
            report.gap_fallback_sources.append(source)
        if not any(mask.any() for mask in masks.values()):
            break
    return report
