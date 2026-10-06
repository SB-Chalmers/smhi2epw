"""Fill source gaps and derive the physical quantities required by EPW.

Ingestion intentionally preserves missing observations. This module decides
which gaps can be reconstructed transparently, converts source units, derives
dew point and longwave radiation, and reconciles four possible solar-data
paths. All transformations operate on a continuous hourly UTC frame; Local
Standard Time conversion belongs to :mod:`smhi2epw.export`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import constants as C
from .errors import DataGapError
from .solar import erbs_decomposition, interval_solar_geometry

log = logging.getLogger("smhi2epw")


@dataclass
class ProcessingReport:
    """Record data filling and solar-quality diagnostics.

    Attributes
    ----------
    interpolated_fraction
        Original missing fraction for each processed source column.
    total_interpolated_fraction
        Mean of the per-column missing fractions.
    clamped_dni_hours
        Hours whose positive DNI was reduced by horizon or extraterrestrial
        limits. Routine nighttime zeros are not counted.
    energy_balance_max_residual
        Maximum absolute interval residual of ``GHI - (DHI + dirh)`` in W/m².
        Mean DNI times a midpoint cosine need not equal mean horizontal beam.
    missing_columns
        Optional source columns that were absent or entirely missing.
    cloud_available
        Whether usable observed or reconstructed total cloud cover was available.
    solar_source
        One of ``"strang"``, ``"measured+strang_partition"``,
        ``"strang_ghi+erbs"``, ``"measured+erbs"``, ``"era5"``, or
        ``"mixed"`` for solar assembled from different hourly sources.
    linear_filled_hours, diurnal_filled_hours
        Filled-hour counts by column and method.
    max_gap_hours
        Longest gap before temporal filling, after any donor recovery.
    bounded_filled_hours
        Reconstructed hours clipped to each variable's representable range.
    primary_missing_hours, invalid_observation_hours
        Required-variable missing and invalid counts before source recovery.
    cross_station_filled_hours
        Required-variable counts filled from same-hour donor observations.
    gap_fallback_sources, gap_fallback_attempts
        Donor receipts and attempted requests, including parameter errors.
    required_reconstructed_fraction
        Pre-recovery missing/invalid fraction across required ingestion cells.
        Populated by automatic or strict donor recovery.
    warnings
        Structured records containing ``code``, ``message`` and optional
        ``variable``/``details``; plausibility warnings retain valid extremes.
    reanalysis_filled_hours
        Weather-variable sample counts supplied by ERA5 on the buffered grid,
        including optional cloud cover during actual weather replacement hours.
    reanalysis_metadata
        Provider, model, grid/elevation, attribution and original overlap
        comparisons; pressure differences are expressed in Pa.
    source_fractions
        Source proportions by variable over exported LST hours.
    weather_classification
        ``"observation_based"``, ``"mixed_reconstructed"`` or
        ``"reanalysis_only"``. Includes reconstructed GHI; routine physical
        nighttime zeros do not downgrade otherwise observation-based inputs.
    """

    interpolated_fraction: Dict[str, float] = field(default_factory=dict)
    total_interpolated_fraction: float = 0.0
    clamped_dni_hours: int = 0
    energy_balance_max_residual: float = 0.0
    missing_columns: List[str] = field(default_factory=list)
    cloud_available: bool = False
    solar_source: str = "strang"
    linear_filled_hours: Dict[str, int] = field(default_factory=dict)
    diurnal_filled_hours: Dict[str, int] = field(default_factory=dict)
    max_gap_hours: Dict[str, int] = field(default_factory=dict)
    bounded_filled_hours: Dict[str, int] = field(default_factory=dict)
    invalid_observation_hours: Dict[str, int] = field(default_factory=dict)
    primary_missing_hours: Dict[str, int] = field(default_factory=dict)
    cross_station_filled_hours: Dict[str, int] = field(default_factory=dict)
    gap_fallback_sources: List[dict] = field(default_factory=list)
    gap_fallback_attempts: List[dict] = field(default_factory=list)
    required_reconstructed_fraction: float = 0.0
    warnings: List[dict] = field(default_factory=list)
    reanalysis_filled_hours: Dict[str, int] = field(default_factory=dict)
    reanalysis_metadata: dict = field(default_factory=dict)
    source_fractions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    weather_classification: str = "observation_based"


# --------------------------------------------------------------------------- #
# Imputation
# --------------------------------------------------------------------------- #
def _max_gap_length(mask: np.ndarray) -> int:
    """Return the longest contiguous run of true values.

    Examples
    --------
    >>> _max_gap_length(np.array([False, True, True, False, True]))
    2
    """
    if not mask.any():
        return 0
    padded = np.concatenate(([False], mask, [False]))
    edges = np.diff(padded.view(np.int8))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    return int((ends - starts).max())


def _gap_runs(mask: np.ndarray) -> List[tuple[int, int]]:
    """Return half-open index pairs for all contiguous true runs.

    Examples
    --------
    >>> _gap_runs(np.array([True, True, False, True]))
    [(0, 2), (3, 4)]
    """
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False]))
    edges = np.diff(padded.view(np.int8))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def _linear_estimate(values: np.ndarray, start: int, end: int) -> Optional[np.ndarray]:
    """Estimate a half-open gap from its immediate endpoint observations.

    Two endpoints produce a linear bridge; a single boundary endpoint produces
    a constant one-sided estimate. ``None`` is returned when neither endpoint
    exists, allowing the caller to raise or leave an optional gap missing.

    Examples
    --------
    >>> values = np.array([0.0, np.nan, np.nan, 3.0])
    >>> _linear_estimate(values, 1, 3)
    array([1., 2.])
    """
    left = values[start - 1] if start > 0 else np.nan
    right = values[end] if end < len(values) else np.nan
    size = end - start
    if np.isfinite(left) and np.isfinite(right):
        return np.linspace(left, right, size + 2, dtype=float)[1:-1]
    if np.isfinite(left):
        return np.full(size, left, dtype=float)
    if np.isfinite(right):
        return np.full(size, right, dtype=float)
    return None


def _profile_estimate(
    values: np.ndarray, start: int, end: int, direction: int
) -> Optional[np.ndarray]:
    """Estimate a gap from the preceding or following valid 24-hour profile.

    Parameters
    ----------
    values
        Numeric hourly values containing the gap.
    start, end
        Half-open gap bounds.
    direction
        ``-1`` selects the preceding valid day; ``+1`` selects the following
        valid day.

    Returns
    -------
    numpy.ndarray or None
        Endpoint-adjusted repeated profile, or ``None`` when a complete
        reference day or gap endpoint is unavailable.

    Notes
    -----
    The daily profile is repeated through the gap and offset linearly so it
    meets the observations surrounding the gap, following Lundström (2012)
    section 4.2.2. ``direction`` is -1 for the preceding profile and +1 for
    the following profile.
    """
    size = end - start
    # Find the nearest complete same-hour reference within one week. Repeated
    # short outages can invalidate both immediately adjacent daily profiles.
    template = None
    for day in range(1, 8):
        template_start = start - 24 * day if direction < 0 else end + 24 * (day - 1)
        template_end = template_start + 24
        if template_start < 0 or template_end > len(values):
            continue
        candidate = values[template_start:template_end]
        if len(candidate) == 24 and np.isfinite(candidate).all():
            template = candidate
            break
    if template is None:
        return None
    if direction < 0:
        base = np.resize(template, size)
        left_base = template[-1]
        right_base = template[size % 24]
    else:
        indices = (np.arange(start, end) - end) % 24
        base = template[indices]
        left_base = template[(start - 1 - end) % 24]
        right_base = template[0]

    left = values[start - 1] if start > 0 else np.nan
    right = values[end] if end < len(values) else np.nan
    if not np.isfinite(left) and not np.isfinite(right):
        return None

    left_delta = left - left_base if np.isfinite(left) else np.nan
    right_delta = right - right_base if np.isfinite(right) else np.nan
    if not np.isfinite(left_delta):
        left_delta = right_delta
    if not np.isfinite(right_delta):
        right_delta = left_delta
    offsets = np.linspace(left_delta, right_delta, size + 2, dtype=float)[1:-1]
    return base + offsets


def _fill_scalar_series(
    series: pd.Series,
    *,
    required: bool,
    solar: bool,
    short_gap_hours: int,
    max_gap_hours: int,
) -> tuple[pd.Series, int, int, int]:
    """Fill one scalar series and calculate method-specific diagnostics.

    Parameters
    ----------
    series
        Hourly scalar values.
    required
        Raise when a gap cannot be reconstructed; otherwise retain ``NaN``.
    solar
        Use daily profiles for every gap and clamp results nonnegative.
    short_gap_hours
        Maximum size assigned to linear interpolation for non-solar data.
    max_gap_hours
        Absolute fill ceiling.

    Returns
    -------
    tuple
        Filled series, linearly filled hours, diurnally filled hours, and
        longest original gap.

    Raises
    ------
    DataGapError
        If a required gap exceeds the ceiling or lacks a valid estimate.

    Notes
    -----
    For longer gaps, valid previous and next profiles are blended 50/50. A
    single valid side is accepted, which is important near year boundaries.
    """
    values = series.to_numpy(dtype=float, copy=True)
    runs = _gap_runs(np.isnan(values))
    longest = max((end - start for start, end in runs), default=0)
    linear_hours = 0
    diurnal_hours = 0

    for start, end in runs:
        size = end - start
        if size > max_gap_hours:
            if required:
                raise DataGapError(
                    f"column '{series.name}' has a {size}-hour gap exceeding the "
                    f"{max_gap_hours}-hour fill limit"
                )
            continue

        estimate: Optional[np.ndarray] = None
        method = "linear"
        if solar or size > short_gap_hours:
            backward = _profile_estimate(values, start, end, -1)
            forward = _profile_estimate(values, start, end, 1)
            if backward is not None and forward is not None:
                estimate = (backward + forward) / 2.0
            else:
                estimate = backward if backward is not None else forward
            method = "diurnal"

        if estimate is None and size <= short_gap_hours:
            estimate = _linear_estimate(values, start, end)
            method = "linear"
        if estimate is None:
            if required:
                raise DataGapError(
                    f"column '{series.name}' has a {size}-hour gap without a valid "
                    "previous or next daily reference profile"
                )
            continue

        values[start:end] = estimate
        if method == "diurnal":
            diurnal_hours += size
        else:
            linear_hours += size

    if solar:
        values = np.clip(values, 0.0, None)
    return (
        pd.Series(values, index=series.index, name=series.name),
        linear_hours,
        diurnal_hours,
        longest,
    )


def _fill_wind_direction(
    series: pd.Series, *, required: bool, short_gap_hours: int, max_gap_hours: int
) -> tuple[pd.Series, int, int, int]:
    """Fill angular wind direction through unit-vector components.

    Direct interpolation would treat 359° and 1° as roughly 180°. Converting
    directions to sine/cosine components preserves circular continuity; the
    filled vector is converted back to degrees in ``[0, 360)``.

    Returns
    -------
    tuple
        Filled direction and the same diagnostics as
        :func:`_fill_scalar_series`.

    Examples
    --------
    >>> index = pd.date_range("2023-01-01", periods=3, freq="h")
    >>> values = pd.Series([359.0, np.nan, 1.0], index=index)
    >>> filled, *_ = _fill_wind_direction(
    ...     values, required=True, short_gap_hours=3, max_gap_hours=48
    ... )
    >>> round(float(filled.iloc[1])) in {0, 360}
    True
    """
    radians = np.radians(series.to_numpy(dtype=float))
    missing = series.isna().to_numpy()
    name = str(series.name) if series.name is not None else "wind_direction"
    sin_series = pd.Series(
        np.where(missing, np.nan, np.sin(radians)), index=series.index
    )
    cos_series = pd.Series(
        np.where(missing, np.nan, np.cos(radians)), index=series.index
    )
    sin_filled, linear, diurnal, longest = _fill_scalar_series(
        sin_series.rename(name),
        required=required,
        solar=False,
        short_gap_hours=short_gap_hours,
        max_gap_hours=max_gap_hours,
    )
    cos_filled, _, _, _ = _fill_scalar_series(
        cos_series.rename(name),
        required=required,
        solar=False,
        short_gap_hours=short_gap_hours,
        max_gap_hours=max_gap_hours,
    )
    direction = np.degrees(np.arctan2(sin_filled, cos_filled)) % 360.0
    invalid = (
        sin_filled.isna()
        | cos_filled.isna()
        | (np.hypot(sin_filled, cos_filled) <= 1e-8)
    )
    direction[invalid] = np.nan
    if required and invalid.any():
        raise DataGapError(
            "Wind direction cannot be reconstructed from cancelling vectors"
        )
    return (
        pd.Series(direction, index=series.index, name=series.name),
        linear,
        diurnal,
        longest,
    )


def impute(
    frame: pd.DataFrame,
    required: List[str],
    optional: Optional[List[str]] = None,
    short_gap_hours: int = C.SHORT_GAP_HOURS,
    max_gap_hours: int = C.MAX_GAP_HOURS,
    report: Optional[ProcessingReport] = None,
) -> ProcessingReport:
    """Fill meteorological gaps and update diagnostics in-place.

    Parameters
    ----------
    frame
        Continuous hourly data frame modified in-place.
    required
        Columns whose unfillable gaps abort processing.
    optional
        Columns that may remain partially or entirely missing.
    short_gap_hours
        Linear interpolation ceiling, three hours by default.
    max_gap_hours
        Daily-profile fill ceiling, 48 hours by default.
    report
        Existing report to extend, or ``None`` to create one.

    Returns
    -------
    ProcessingReport
        Per-column missing fractions, methods, and maximum gaps.

    Raises
    ------
    DataGapError
        If a required column is absent or a required gap is unfillable.

    Notes
    -----
    Required 1--3 hour gaps are linear. Required 4--48 hour gaps use the
    endpoint-adjusted daily-profile method. Optional gaps beyond the same
    ceiling remain missing for honest EPW sentinel output.
    """
    optional = optional or []
    report = report or ProcessingReport()
    total_missing = 0
    total_cells = 0

    for column in required + optional:
        if column not in frame.columns or frame[column].isna().all():
            if column in optional:
                if column not in report.missing_columns:
                    report.missing_columns.append(column)
                continue
            raise DataGapError(
                f"required column '{column}' is entirely missing; cannot "
                "generate a weather file"
            )
        series = frame[column]
        missing = series.isna().to_numpy()
        n_missing = int(missing.sum())
        n = len(series)
        total_missing += n_missing
        total_cells += n
        report.interpolated_fraction[column] = (n_missing / n) if n else 0.0

        if column == "wind_direction":
            filled, linear, diurnal, longest = _fill_wind_direction(
                series,
                required=column in required,
                short_gap_hours=short_gap_hours,
                max_gap_hours=max_gap_hours,
            )
        else:
            filled, linear, diurnal, longest = _fill_scalar_series(
                series,
                required=column in required,
                solar=False,
                short_gap_hours=short_gap_hours,
                max_gap_hours=max_gap_hours,
            )
        # Bound only reconstructed values. Do not silently clip observations.
        limits = {
            "relative_humidity": (0.0, 100.0),
            "wind_speed": (0.0, 40.0),
            "cloud_cover": (0.0, 8.0),
        }
        if column in limits:
            lo, hi = limits[column]
            out_of_bounds = missing & ((filled < lo) | (filled > hi))
            report.bounded_filled_hours[column] = int(out_of_bounds.sum())
            filled.loc[missing] = filled.loc[missing].clip(lo, hi)
        frame[column] = filled
        report.linear_filled_hours[column] = linear
        report.diurnal_filled_hours[column] = diurnal
        report.max_gap_hours[column] = longest

    report.total_interpolated_fraction = (
        total_missing / total_cells if total_cells else 0.0
    )
    return report


def impute_solar(
    frame: pd.DataFrame,
    columns: List[str],
    report: Optional[ProcessingReport] = None,
) -> ProcessingReport:
    """Fill solar gaps without bridging night and day linearly.

    Solar gaps up to 48 hours always use same-hour daily profiles, even when
    only one hour long. Values are clipped nonnegative after filling. Entirely
    missing required solar columns raise :class:`DataGapError`.
    """
    report = report or ProcessingReport()
    for column in columns:
        if column not in frame.columns:
            continue
        series = frame[column]
        n_missing = int(series.isna().sum())
        n = len(series)
        report.interpolated_fraction[column] = (n_missing / n) if n else 0.0
        if n_missing == n:
            raise DataGapError(
                f"solar column '{column}' is entirely missing; cannot model"
            )
        filled, linear, diurnal, longest = _fill_scalar_series(
            series,
            required=True,
            solar=True,
            short_gap_hours=C.SHORT_GAP_HOURS,
            max_gap_hours=C.MAX_GAP_HOURS,
        )
        frame[column] = filled
        report.linear_filled_hours[column] = linear
        report.diurnal_filled_hours[column] = diurnal
        report.max_gap_hours[column] = longest
    return report


# --------------------------------------------------------------------------- #
# Unit conversions
# --------------------------------------------------------------------------- #
def convert_units(frame: pd.DataFrame) -> None:
    """Convert source units to EPW units in-place.

    MetObs sea-level pressure is converted from hPa to Pa here. The full
    pipeline subsequently derives pressure at the target elevation. Missing
    columns are ignored so the helper remains safe for focused examples.

    Examples
    --------
    >>> frame = pd.DataFrame({"pressure": [1013.25]})
    >>> convert_units(frame)
    >>> float(frame.loc[0, "pressure"])
    101325.0
    """
    if "pressure" in frame.columns:
        frame["pressure"] = frame["pressure"] * 100.0  # hPa -> Pa


# --------------------------------------------------------------------------- #
# Dew point (Magnus formula)
# --------------------------------------------------------------------------- #
def pressure_at_elevation(sea_level_pa, dry_bulb_c, latitude_deg, elevation_m):
    """Estimate target surface pressure from SMHI parameter 9 (sea-level QFF).

    Invert SMHI's published reduction: QFF = P * exp(H * B / T1).
    https://www.smhi.se/kunskapsbanken/meteorologi/lufttryck/hur-mats-lufttryck
    T1 is SMHI's piecewise effective layer temperature, not virtual temperature.
    The target height approximates barometer height; station-observed temperature
    represents the target. This is a derived estimate, not a pressure observation.
    Inputs have already passed filling and unit conversion. No clipping is used.
    """
    temperature = np.asarray(dry_bulb_c, dtype=float)
    pressure = np.asarray(sea_level_pa, dtype=float)
    if not (
        np.isfinite(temperature).all()
        and np.isfinite(pressure).all()
        and np.isfinite(latitude_deg)
        and np.isfinite(elevation_m)
    ):
        raise ValueError("Pressure conversion requires finite inputs")
    if not -90 <= latitude_deg <= 90 or not -1000 <= elevation_m <= 9999:
        raise ValueError(
            "Pressure conversion latitude/elevation is outside the supported domain"
        )
    if np.any(temperature <= -273.15):
        raise ValueError("Pressure conversion requires temperature above absolute zero")
    effective = np.where(
        temperature < -7,
        0.500 * temperature + 275.0,
        np.where(
            temperature < 2, 0.535 * temperature + 275.6, 1.07 * temperature + 274.5
        ),
    )
    if np.any(effective <= 0) or np.any(pressure <= 0):
        raise ValueError(
            "Pressure conversion requires positive pressure and layer temperature"
        )
    coefficient = 0.034163 * (1 - 0.0026373 * np.cos(np.deg2rad(2 * latitude_deg)))
    return pressure * np.exp(-elevation_m * coefficient / effective)


def dew_point(dry_bulb: pd.Series, relative_humidity: pd.Series) -> pd.Series:
    """Calculate dew-point temperature with the Magnus approximation.

    Parameters
    ----------
    dry_bulb
        Air temperature in degrees Celsius.
    relative_humidity
        Relative humidity in percent. Values are clipped to 1--100% to avoid
        logarithm singularities and supersaturated output.

    Returns
    -------
    pandas.Series
        Dew-point temperature in degrees Celsius, aligned to the inputs.

    Notes
    -----
    The coefficients ``b=17.625`` and ``c=243.04 °C`` provide a common Magnus
    approximation over normal near-surface weather conditions.

    Examples
    --------
    >>> round(float(dew_point(pd.Series([20.0]), pd.Series([50.0])).iloc[0]), 1)
    9.3
    """
    b, c = 17.625, 243.04
    rh = relative_humidity.clip(lower=1.0, upper=100.0) / 100.0
    alpha = np.log(rh) + (b * dry_bulb) / (c + dry_bulb)
    return (c * alpha) / (b - alpha)


# --------------------------------------------------------------------------- #
# EnergyPlus horizontal infrared radiation with cloud correction
# --------------------------------------------------------------------------- #
def horizontal_ir(
    dry_bulb_c: pd.Series,
    dew_point_c: pd.Series,
    cloud_cover_tenths: Optional[pd.Series] = None,
) -> pd.Series:
    """EnergyPlus-compatible down-welling longwave sky radiation (W/m²).

    Parameters
    ----------
    dry_bulb_c, dew_point_c
        Dry-bulb and dew-point temperature in degrees Celsius.
    cloud_cover_tenths
        Optional total sky cover on the EPW 0--10 scale.

    Returns
    -------
    pandas.Series
        Horizontal infrared radiation intensity in W/m².

    Notes
    -----
    EnergyPlus estimates clear-sky emissivity as
    ``0.787 + 0.764*ln(Tdew/273)`` and applies a cubic cloud multiplier. SMHI
    parameter 16 is total rather than opaque cloud cover. When supplied,
    it is used only as an explicit proxy in the cloud-amplification term; the
    EPW opaque-cover field remains missing.

    Examples
    --------
    >>> value = horizontal_ir(pd.Series([20.0]), pd.Series([10.0])).iloc[0]
    >>> round(float(value), 1)
    341.2
    """
    dew_k = (dew_point_c + C.KELVIN).clip(lower=1.0)
    eps_sky = 0.787 + 0.764 * np.log(dew_k / 273.0)
    if cloud_cover_tenths is not None:
        n = cloud_cover_tenths.clip(lower=0.0, upper=10.0)
        cloud_factor = 1.0 + 0.0224 * n - 0.0035 * n**2 + 0.00028 * n**3
        eps_sky = eps_sky * cloud_factor.fillna(1.0)
    eps_sky = eps_sky.clip(lower=0.0, upper=1.0)
    t_dry_k = dry_bulb_c + C.KELVIN
    return eps_sky * C.STEFAN_BOLTZMANN * t_dry_k**4


# --------------------------------------------------------------------------- #
# Sky cover (octas -> EPW tenths)
# --------------------------------------------------------------------------- #
def sky_cover_tenths(cloud_octas: pd.Series) -> pd.Series:
    """Convert SMHI total cloud cover (octas 0-8) to EPW tenths (0-10).

    Values are rounded to the nearest tenth and clamped to [0, 10]. NaNs are
    preserved so the exporter can emit the EPW missing token.

    Examples
    --------
    >>> sky_cover_tenths(pd.Series([0.0, 4.0, 8.0])).tolist()
    [0.0, 5.0, 10.0]
    """
    tenths = (cloud_octas / 8.0 * 10.0).round()
    return tenths.clip(lower=0.0, upper=10.0)


# --------------------------------------------------------------------------- #
# Solar transformation: finalize EPW solar fields
# --------------------------------------------------------------------------- #
def _finalize_solar(
    frame: pd.DataFrame,
    ghi: pd.Series,
    measured: pd.Series,
    lat: float,
    lon: float,
) -> tuple[np.ndarray, int]:
    """Finalize one solar group without replacing valid interval means.

    Supplied DNI and beam-horizontal are separate hourly averages: their
    product identity applies instantaneously, not at one hourly midpoint.
    Only inferred DNI uses the low-angle inversion guard. Missing horizontal
    beam with supplied DNI uses mean positive interval geometry as an estimate.
    """
    cosine, etrh, etrn, dark = interval_solar_geometry(
        pd.DatetimeIndex(frame.index), lat, lon
    )
    selected = np.maximum(ghi.to_numpy(dtype=float), 0.0)
    model_ghi = frame["ghi"].to_numpy(dtype=float)
    provided_dni = frame.get("dni", pd.Series(np.nan, index=frame.index)).to_numpy(
        dtype=float
    )
    provided_beam = frame.get("dirh", pd.Series(np.nan, index=frame.index)).to_numpy(
        dtype=float
    )
    direct = np.isfinite(provided_dni) & (provided_dni >= 0.0)
    known_beam = np.isfinite(provided_beam) & (provided_beam >= 0.0)
    beam = np.where(known_beam, provided_beam, provided_dni * cosine)
    beam = np.where(provided_dni > 0.0, beam, 0.0)

    # Transfer model components to measured GHI without a small-angle division.
    partition = measured.to_numpy(dtype=bool) & direct & (model_ghi > 0.0)
    scale = np.divide(selected, model_ghi, out=np.ones(len(frame)), where=partition)
    supplied_dni = provided_dni * scale
    supplied_beam = beam * scale
    _, estimated_dni = erbs_decomposition(selected, etrh, cosine)
    dni = np.where(direct, supplied_dni, estimated_dni)
    beam = np.where(direct, supplied_beam, estimated_dni * cosine)
    original_dni = dni.copy()

    # A physical cap changes both members of the supplied component pair.
    capped_dni = np.minimum(np.maximum(dni, 0.0), etrn)
    beam *= np.divide(capped_dni, dni, out=np.zeros(len(frame)), where=dni > 0.0)
    capped_beam = np.minimum(np.maximum(beam, 0.0), selected)
    dni = capped_dni * np.divide(
        capped_beam, beam, out=np.ones(len(frame)), where=beam > 0.0
    )
    dni = np.where(dark, 0.0, dni)
    beam = np.where(dark, 0.0, capped_beam)
    selected = np.where(dark, 0.0, selected)
    frame["ghi"] = selected
    frame["dni"] = dni
    frame["dirh"] = beam
    frame["dhi"] = np.maximum(selected - beam, 0.0)
    frame["etrh"] = etrh
    frame["etrn"] = etrn
    clamped = int(np.count_nonzero(dni < original_dni - 1e-9))
    return direct | dark, clamped


def apply_solar(
    frame: pd.DataFrame,
    lat: float,
    lon: float,
    report: Optional[ProcessingReport] = None,
) -> None:
    """Finalize solar components using their preceding-hour interval semantics.

    Supplied DNI is retained at low solar elevation. Supplied horizontal beam
    closes GHI with DHI; measured GHI scales the model component group. Erbs
    decomposition and a five-degree inversion guard apply only without usable
    supplied DNI. Extraterrestrial caps and wholly dark intervals remain
    physical constraints. Automatic recovery already uses this same finalizer.

    Parameters
    ----------
    frame
        Hourly UTC frame modified in place. It must contain GHI and may contain
        measured GHI, supplied DNI, and direct-horizontal irradiance.
    lat, lon
        Requested solar coordinates in decimal degrees.
    report
        Optional diagnostics object updated with source, clamping, and closure.

    Notes
    -----
    DHI closes against the supplied or estimated horizontal beam interval mean.
    Mean DNI times a midpoint cosine need not equal mean horizontal beam when
    DNI or solar geometry changes within the hour. Measured GHI transfers the
    model partition by scaling both DNI and horizontal beam by the GHI ratio.

    Raises
    ------
    KeyError
        If no GHI column exists; callers normally prevent this through
        :func:`impute_solar`.
    """
    if not frame.attrs.get("automatic_prepared"):
        measured_values = frame.get(
            C.METOBS_RADIATION_COLUMN, pd.Series(np.nan, index=frame.index)
        )
        measured = measured_values.notna()
        ghi = measured_values.combine_first(frame["ghi"])
        direct, clamped = _finalize_solar(frame, ghi, measured, lat, lon)
        if report is not None:
            report.clamped_dni_hours = clamped
            if measured.any():
                report.solar_source = (
                    "measured+strang_partition" if direct.all() else "measured+erbs"
                )
            else:
                report.solar_source = "strang" if direct.all() else "strang_ghi+erbs"
    if report is not None:
        residual = np.abs(frame["ghi"] - (frame["dhi"] + frame["dirh"]))
        report.energy_balance_max_residual = (
            float(residual.max()) if len(frame) else 0.0
        )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def process(
    frame: pd.DataFrame,
    lat: float,
    lon: float,
    *,
    measured_required: bool = False,
    target_elevation_m: float = 0.0,
    report: Optional[ProcessingReport] = None,
) -> ProcessingReport:
    """Run the full processing pipeline in-place and return diagnostics.

    Parameters
    ----------
    frame
        Continuous hourly UTC ingestion frame, modified in-place.
    lat, lon
        Requested solar point in decimal degrees.
    target_elevation_m
        Height used to estimate surface pressure from sea-level QFF. Low-level
        callers default to sea level; compile_epw always supplies the site height.
    measured_required
        If ``True``, unfillable measured GHI raises instead of falling back to
        STRÅNG.
    report
        Optional diagnostics from nearby-observation recovery, updated in place.

    Returns
    -------
    ProcessingReport
        Complete gap, cloud, source, clamp, and closure diagnostics.

    Raises
    ------
    DataGapError
        If required meteorological/solar data cannot satisfy the fill policy.

    Notes
    -----
    Adds ``dew_point``, ``horizontal_ir``, ``dni``, ``dhi``, ``etrh``/``etrn``
    and (when cloud data is present) ``sky_cover`` columns, and converts units.
    The input ``frame`` must be indexed by a continuous hourly UTC grid.

    Measured GHI from an automatically selected station is opportunistic: an
    unfillable series is discarded with a warning and STRÅNG remains usable.
    Explicit measured GHI is a user requirement and therefore fails clearly.
    """
    required = list(C.METOBS_REQUIRED_PARAMETERS.values())
    optional = list(C.METOBS_OPTIONAL_PARAMETERS.values())
    solar_columns = list(C.STRANG_PARAMETERS.values())

    has_surface_fallback = "reanalysis_surface_pressure" in frame
    if has_surface_fallback:
        required.remove("pressure")
        optional.append("pressure")
    if frame.attrs.get("automatic_prepared"):
        report = report or ProcessingReport()
    else:
        report = impute(frame, required, optional, report=report)
        impute_solar(frame, solar_columns, report)

    measured_column = C.METOBS_RADIATION_COLUMN
    if measured_column in frame.columns and not frame[measured_column].isna().all():
        measured = frame[measured_column]
        report.interpolated_fraction[measured_column] = float(measured.isna().mean())
        try:
            filled, linear, diurnal, longest = _fill_scalar_series(
                measured,
                required=True,
                solar=True,
                short_gap_hours=C.SHORT_GAP_HOURS,
                max_gap_hours=C.MAX_GAP_HOURS,
            )
        except DataGapError:
            if measured_required:
                raise
            log.warning(
                "auto-selected measured GHI has an unfillable gap; falling back to STRÅNG"
            )
            frame[measured_column] = np.nan
        else:
            frame[measured_column] = filled
            report.linear_filled_hours[measured_column] = linear
            report.diurnal_filled_hours[measured_column] = diurnal
            report.max_gap_hours[measured_column] = longest
    elif measured_required:
        raise DataGapError(
            "configured radiation station has no measured GHI for the year"
        )

    convert_units(frame)
    if has_surface_fallback:
        valid_pressure = (
            frame["pressure"].notna() & frame["reanalysis_surface_pressure"].isna()
        )
        frame.loc[~valid_pressure, "pressure"] = np.nan
        frame.loc[valid_pressure, "pressure"] = pressure_at_elevation(
            frame.loc[valid_pressure, "pressure"],
            frame.loc[valid_pressure, "dry_bulb"],
            lat,
            target_elevation_m,
        )
        frame["pressure"] = frame["pressure"].combine_first(
            frame["reanalysis_surface_pressure"]
        )
        if not np.isfinite(frame["pressure"]).all():
            raise DataGapError("No complete surface-pressure source is available")
    else:
        frame["pressure"] = pressure_at_elevation(
            frame["pressure"], frame["dry_bulb"], lat, target_elevation_m
        )

    frame["dew_point"] = dew_point(frame["dry_bulb"], frame["relative_humidity"])

    # --- Cloud opacity for the longwave IR model ---
    # Parameter 16 is total cover. It is used as an explicit IR-only proxy;
    # opaque cover remains missing in the exported EPW.
    cloud_tenths = None
    if "cloud_cover" in frame.columns and not frame["cloud_cover"].isna().all():
        report.cloud_available = True
        frame["sky_cover"] = sky_cover_tenths(frame["cloud_cover"])
        cloud_tenths = frame["sky_cover"]

    apply_solar(frame, lat, lon, report)

    frame["horizontal_ir"] = horizontal_ir(
        frame["dry_bulb"], frame["dew_point"], cloud_tenths
    )
    if report.interpolated_fraction:
        report.total_interpolated_fraction = float(
            np.mean(list(report.interpolated_fraction.values()))
        )
    return report
