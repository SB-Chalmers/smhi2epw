"""Select complete same-year weather without concealing reconstruction.

This is a source hierarchy, not a weather generator. Original observations,
limited temporal estimates, assessed donors and ERA5 are kept distinguishable.
Extreme but representable weather is preserved; physically inconsistent solar
and unavailable required data are repaired or reported explicitly.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import constants as C
from . import gap_recovery as G
from . import processing as P
from . import reanalysis
from .errors import DataGapError, IngestionError
from .ingestion import CachedClient, StationMeta
from .solar import interval_solar_geometry

REQUIRED = list(C.METOBS_REQUIRED_PARAMETERS.values())
SOLAR = ["ghi", "dni", "dirh", C.METOBS_RADIATION_COLUMN]
MAX_SOLAR = 2000.0  # Broad hourly plausibility ceiling; not an extreme-weather filter.


def warn(report: P.ProcessingReport, code: str, message: str, **details) -> None:
    """Append a structured, serializable warning to the quality report."""
    report.warnings.append({"code": code, "message": message, "details": details})


def _temporal(series: pd.Series, column: str, report: P.ProcessingReport) -> pd.Series:
    """Fill solar gaps under the temporal ceiling and preserve diagnostics."""
    filled, linear, diurnal, longest = P._fill_scalar_series(
        series,
        required=False,
        solar=True,
        short_gap_hours=C.SHORT_GAP_HOURS,
        max_gap_hours=C.MAX_GAP_HOURS,
    )
    report.interpolated_fraction[column] = float(series.isna().mean())
    report.linear_filled_hours[column] = linear
    report.diurnal_filled_hours[column] = diurnal
    report.max_gap_hours[column] = longest
    return filled


def _dark_hours(index: pd.DatetimeIndex, lat: float, lon: float) -> np.ndarray:
    """Identify preceding intervals entirely below the geometric solar horizon."""
    return interval_solar_geometry(index, lat, lon)[3]


def _solar_inputs(
    frame: pd.DataFrame, report: P.ProcessingReport, lat: float, lon: float
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Clean radiation, fill bounded gaps and prefer measured hourly GHI."""
    dark = _dark_hours(pd.DatetimeIndex(frame.index), lat, lon)
    raw_masks = {}
    for column in (C.METOBS_RADIATION_COLUMN, "ghi"):
        if column in frame:
            raw = frame[column].where(
                np.isfinite(frame[column]) & frame[column].between(0, MAX_SOLAR)
            )
            raw = raw.mask(dark & raw.gt(1.0))
            raw_masks[column] = raw.notna()
        else:
            raw_masks[column] = pd.Series(False, index=frame.index)
    for column in SOLAR:
        if column not in frame:
            frame[column] = np.nan
        series = frame[column]
        if column == C.METOBS_RADIATION_COLUMN and not series.notna().any():
            continue
        invalid = series.notna() & (
            ~np.isfinite(series) | ~series.between(0, MAX_SOLAR)
        )
        if invalid.any():
            warn(
                report,
                "invalid_radiation",
                f"Discarded invalid {column} samples",
                variable=column,
                hours=int(invalid.sum()),
            )
        series = series.where(np.isfinite(series) & series.between(0, MAX_SOLAR))
        positive_dark = dark & series.gt(1.0)
        if positive_dark.any():
            warn(
                report,
                "nighttime_radiation",
                f"Replaced {column} during fully dark intervals with physical zero",
                variable=column,
                hours=int(positive_dark.sum()),
            )
        # Darkness establishes zero without a donor or an API request. The
        # interval check keeps real radiation near sunrise/sunset intact.
        series.loc[dark] = 0.0
        frame[column] = _temporal(series, column, report)
    measured = frame[C.METOBS_RADIATION_COLUMN]
    ghi = measured.combine_first(frame["ghi"])
    chosen_original = (measured.notna() & raw_masks[C.METOBS_RADIATION_COLUMN]) | (
        measured.isna() & raw_masks["ghi"]
    )
    source: pd.Series[Any] = pd.Series(
        np.where(chosen_original, "primary", "missing"), index=frame.index
    )
    source.loc[~chosen_original & ghi.notna()] = "temporal"
    source.loc[dark & ~chosen_original] = "physical"
    return ghi, measured.notna(), pd.Series(dark, index=frame.index), source


def _model_overlap(
    originals: dict,
    model: pd.DataFrame,
    lat: float,
    elevation: float,
    report: P.ProcessingReport,
) -> None:
    """Report ERA5 disagreement against original observations without rejecting extremes."""
    comparisons = {}
    for column in REQUIRED:
        primary = originals[column].copy()
        prediction = model[
            "reanalysis_surface_pressure" if column == "pressure" else column
        ]
        limit = G.MAX_MAE[column]
        if column == "pressure":
            valid = primary.notna() & originals["dry_bulb"].notna()
            primary.loc[~valid] = np.nan
            primary.loc[valid] = P.pressure_at_elevation(
                primary[valid] * 100, originals["dry_bulb"][valid], lat, elevation
            )
            prediction = prediction.where(prediction.between(31000, 120000))
            limit *= 100
        else:
            prediction = G.valid_observations(prediction, column)
        overlap = primary.notna() & prediction.notna()
        difference = prediction[overlap] - primary[overlap]
        if column == "wind_direction":
            difference = (difference + 180) % 360 - 180
        comparisons[column] = {
            "hours": int(overlap.sum()),
            "mean_absolute_difference": float(difference.abs().mean())
            if overlap.any()
            else None,
            "mean_difference": float(difference.mean()) if overlap.any() else None,
            "units": "Pa" if column == "pressure" else "source_units",
        }
        if overlap.any() and difference.abs().mean() > limit:
            warn(
                report,
                "reanalysis_disagreement",
                f"ERA5 differs substantially from available original {column}; fallback remains modelled and uncertain",
                variable=column,
                **comparisons[column],
            )
    report.reanalysis_metadata["overlap"] = comparisons


def prepare(
    frame: pd.DataFrame,
    station: StationMeta | None,
    year: int,
    lat: float,
    lon: float,
    elevation: float | None,
    client: CachedClient,
    report: P.ProcessingReport,
    *,
    max_distance_km: float,
    max_stations: int,
) -> tuple[float, pd.DataFrame]:
    """Fill unresolved inputs and return resolved elevation and source tags.

    Pressure remains QFF until processing; reanalysis surface pressure travels
    in its own Pa column. Solar replacement uses one coherent component group.
    Per-hour source tags are internal and reduced over the exported LST grid.
    """
    tags = pd.DataFrame(index=frame.index)
    originals = {}
    for column in REQUIRED:
        if column not in frame:
            frame[column] = np.nan
        raw = frame[column]
        originals[column] = G.valid_observations(raw, column)
        tags[column] = np.where(originals[column].notna(), "primary", "missing")
    if station is not None:
        try:
            G.recover(
                frame,
                station,
                year,
                lat,
                lon,
                client,
                max_distance_km=max_distance_km,
                max_stations=max_stations,
                report=report,
            )
        except IngestionError as exc:
            warn(
                report,
                "donor_discovery_failed",
                f"Donor discovery failed; remaining gaps will use ERA5: {exc}",
            )
    for column in REQUIRED:
        # Also clean when station metadata was unavailable or discovery failed.
        invalid = (
            frame[column].notna() & G.valid_observations(frame[column], column).isna()
        )
        report.invalid_observation_hours.setdefault(column, int(invalid.sum()))
        report.primary_missing_hours.setdefault(
            column, int(originals[column].isna().sum())
        )
        frame[column] = G.valid_observations(frame[column], column)
        tags.loc[originals[column].isna() & frame[column].notna(), column] = "donor"
    report.required_reconstructed_fraction = sum(
        report.primary_missing_hours.values()
    ) / (len(frame) * len(REQUIRED))
    before_temporal = frame[REQUIRED].isna()
    P.impute(
        frame, [], REQUIRED + list(C.METOBS_OPTIONAL_PARAMETERS.values()), report=report
    )
    for column in REQUIRED:
        tags.loc[before_temporal[column] & frame[column].notna(), column] = "temporal"
        frame[column] = G.valid_observations(frame[column], column)
        tags.loc[frame[column].isna(), column] = "missing"
    if "cloud_cover" in frame:
        frame["cloud_cover"] = frame["cloud_cover"].where(
            np.isfinite(frame["cloud_cover"]) & frame["cloud_cover"].between(0, 8)
        )
    if elevation is not None:
        valid = frame["pressure"].notna() & frame["dry_bulb"].notna()
        surface = P.pressure_at_elevation(
            frame.loc[valid, "pressure"] * 100,
            frame.loc[valid, "dry_bulb"],
            lat,
            elevation,
        )
        bad = valid.copy()
        bad.loc[valid] = (surface < 31000) | (surface > 120000)
        if bad.any():
            frame.loc[bad, "pressure"] = np.nan
            tags.loc[bad, "pressure"] = "missing"
            warn(
                report,
                "invalid_surface_pressure",
                "Discarded QFF samples producing unrepresentable surface pressure",
                hours=int(bad.sum()),
            )
    ghi, measured_mask, dark, solar_tags = _solar_inputs(frame, report, lat, lon)
    tags["ghi"] = solar_tags
    missing = {column: frame[column].isna() for column in REQUIRED}
    need_era5 = (
        any(mask.any() for mask in missing.values())
        or ghi.isna().any()
        or elevation is None
    )
    if need_era5:
        try:
            model, metadata = reanalysis.fetch(
                lat, lon, elevation, pd.DatetimeIndex(frame.index), client
            )
        except IngestionError as exc:
            raise DataGapError(
                f"Same-year sources cannot complete the requested weather: {exc}"
            ) from exc
        report.reanalysis_metadata = metadata
        if elevation is None:
            elevation = metadata["elevation_m"]
        _model_overlap(originals, model, lat, elevation, report)
        for column in REQUIRED:
            model_column = (
                "reanalysis_surface_pressure" if column == "pressure" else column
            )
            model_values = model[model_column]
            if column == "pressure":
                model_values = model_values.where(
                    np.isfinite(model_values) & model_values.between(31000, 120000)
                )
                frame[model_column] = model_values.where(missing[column])
            else:
                model_values = G.valid_observations(model_values, column)
                frame.loc[missing[column], column] = model_values[missing[column]]
            used = missing[column] & model_values.notna()
            tags.loc[used, column] = "reanalysis"
            report.reanalysis_filled_hours[column] = int(used.sum())
        # Temperature or elevation may only now be available. Recheck QFF
        # conversion and recover values outside the surface-pressure domain.
        valid_qff = frame["pressure"].notna() & frame["dry_bulb"].notna()
        surface = P.pressure_at_elevation(
            frame.loc[valid_qff, "pressure"] * 100,
            frame.loc[valid_qff, "dry_bulb"],
            lat,
            elevation,
        )
        bad_qff = valid_qff.copy()
        bad_qff.loc[valid_qff] = (surface < 31000) | (surface > 120000)
        if bad_qff.any():
            fallback = model["reanalysis_surface_pressure"].where(
                model["reanalysis_surface_pressure"].between(31000, 120000)
            )
            frame.loc[bad_qff, "pressure"] = np.nan
            frame.loc[bad_qff, "reanalysis_surface_pressure"] = fallback[bad_qff]
            tags.loc[bad_qff, "pressure"] = np.where(
                fallback[bad_qff].notna(), "reanalysis", "missing"
            )
            report.reanalysis_filled_hours["pressure"] += int(
                (bad_qff & fallback.notna()).sum()
            )
            warn(
                report,
                "invalid_surface_pressure",
                "Reanalysis replaced pressure inconsistent with resolved temperature/elevation",
                hours=int(bad_qff.sum()),
            )
        solar_missing = ghi.isna()
        model_ghi = model["ghi"].where(
            np.isfinite(model["ghi"]) & model["ghi"].between(0, MAX_SOLAR)
        )
        ghi.loc[solar_missing] = model_ghi[solar_missing]
        solar_used = solar_missing & model_ghi.notna()
        tags.loc[solar_used, "ghi"] = "reanalysis"
        report.reanalysis_filled_hours["ghi"] = int(solar_used.sum())
        # Optional cloud augmentation follows actual ERA5 weather replacement.
        # Fetching an archive for one gap must not change longwave radiation
        # throughout otherwise usable primary weather, or on metadata-only calls.
        if "cloud_cover" not in frame:
            frame["cloud_cover"] = np.nan
        clouds = model["cloud_cover"].where(
            np.isfinite(model["cloud_cover"]) & model["cloud_cover"].between(0, 8)
        )
        era5_hours = tags[REQUIRED].isin(["reanalysis"]).any(axis=1) | solar_used
        cloud_used = era5_hours & frame["cloud_cover"].isna() & clouds.notna()
        frame.loc[cloud_used, "cloud_cover"] = clouds[cloud_used]
        report.reanalysis_filled_hours["cloud_cover"] = int(cloud_used.sum())
        # Copy the ERA5 solar group only where its GHI is selected. All other
        # hours retain STRÅNG partitioning or use GHI-driven Erbs below.
        for column in ("dni", "dirh"):
            model_values = model[column].where(
                np.isfinite(model[column]) & model[column].between(0, MAX_SOLAR)
            )
            frame.loc[solar_used, column] = model_values[solar_used]
        total = sum(report.reanalysis_filled_hours.values())
        warn(
            report,
            "reanalysis_used",
            f"ERA5 supplied {total} weather samples; local extremes remain uncertain",
            filled_hours=dict(report.reanalysis_filled_hours),
        )
    unresolved = [column for column in REQUIRED if (tags[column] == "missing").any()]
    if unresolved or ghi.isna().any():
        raise DataGapError(
            f"No physically valid complete same-year source for {', '.join(unresolved + (['ghi'] if ghi.isna().any() else []))}"
        )
    assert elevation is not None
    _finish_solar(frame, ghi, measured_mask, tags, lat, lon, report)
    frame.attrs["automatic_prepared"] = True
    temporal_hours = int(tags.isin(["temporal"]).sum().sum())
    if temporal_hours:
        warn(
            report,
            "temporal_reconstruction",
            f"Bounded temporal reconstruction supplied {temporal_hours} weather samples",
            hours=temporal_hours,
        )
    return elevation, tags


def _finish_solar(
    frame: pd.DataFrame,
    ghi: pd.Series,
    measured: pd.Series,
    tags: pd.DataFrame,
    lat: float,
    lon: float,
    report: P.ProcessingReport,
) -> None:
    """Close radiation per hour using provided direct values or Erbs estimates."""
    direct, clamped = P._finalize_solar(frame, ghi, measured, lat, lon)
    frame.attrs["automatic_clamped_dni_hours"] = clamped
    frame.drop(columns=[C.METOBS_RADIATION_COLUMN], inplace=True)
    reanalysis_hours = int((tags["ghi"] == "reanalysis").sum())
    if reanalysis_hours:
        solar_source = (
            "era5"
            if reanalysis_hours + int((tags["ghi"] == "physical").sum()) == len(frame)
            else "mixed"
        )
    elif measured.all():
        solar_source = "measured+strang_partition" if direct.all() else "measured+erbs"
    elif measured.any() and not measured[tags["ghi"] != "physical"].all():
        solar_source = "mixed"
    else:
        solar_source = "strang" if direct.all() else "strang_ghi+erbs"
    frame.attrs["automatic_solar_source"] = solar_source
    if not direct.all():
        warn(
            report,
            "solar_decomposition",
            "Missing direct solar components were estimated from GHI using Erbs",
            hours=int((~direct).sum()),
        )


def summarize(
    tags: pd.DataFrame, frame: pd.DataFrame, report: P.ProcessingReport
) -> None:
    """Reduce exported-hour source tags and warn about abrupt source changes."""
    for column in tags:
        counts = tags[column].value_counts()
        report.source_fractions[str(column)] = {
            str(source): int(count) / len(tags) for source, count in counts.items()
        }
    if (
        all((tags[column] == "reanalysis").all() for column in REQUIRED)
        and tags["ghi"].isin(["reanalysis", "physical"]).all()
    ):
        report.weather_classification = "reanalysis_only"
    elif (
        any((tags[column] != "primary").any() for column in REQUIRED)
        or tags["ghi"].isin(["temporal", "reanalysis"]).any()
    ):
        report.weather_classification = "mixed_reconstructed"
    limits = {
        "dry_bulb": 10.0,
        "relative_humidity": 40.0,
        "wind_speed": 15.0,
        "pressure": 1000.0,
    }
    for column, limit in limits.items():
        changed_source = tags[column].ne(tags[column].shift())
        jumps = frame[column].diff().abs()
        flagged = changed_source & (jumps > limit)
        if flagged.any():
            warn(
                report,
                "source_boundary_jump",
                f"Large {column} changes at weather-source boundaries; values retained",
                variable=column,
                hours=int(flagged.sum()),
                max_change=float(jumps[flagged].max()),
            )
