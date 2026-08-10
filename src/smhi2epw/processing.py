"""Processing & modeling layer: imputation, conversions and derived physics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import constants as C
from .errors import DataGapError
from .solar import solar_zenith, extraterrestrial_radiation, erbs_decomposition

log = logging.getLogger("smhi2epw")


@dataclass
class ProcessingReport:
    """Diagnostics produced by the processing stage."""

    interpolated_fraction: Dict[str, float] = field(default_factory=dict)
    total_interpolated_fraction: float = 0.0
    clamped_dni_hours: int = 0
    energy_balance_max_residual: float = 0.0
    missing_columns: List[str] = field(default_factory=list)
    cloud_available: bool = False
    solar_source: str = "strang"  # "strang" | "measured+erbs"


# --------------------------------------------------------------------------- #
# Imputation
# --------------------------------------------------------------------------- #
def _max_gap_length(mask: np.ndarray) -> int:
    """Length (in samples) of the longest run of ``True`` values."""
    longest = run = 0
    for flag in mask:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    return longest


def impute(
    frame: pd.DataFrame,
    required: List[str],
    optional: Optional[List[str]] = None,
    max_gap_hours: int = C.MAX_GAP_HOURS,
    report: Optional[ProcessingReport] = None,
) -> ProcessingReport:
    """Interpolate short gaps with a split required/optional policy.

    Required columns abort with :class:`DataGapError` on any gap longer than
    ``max_gap_hours``. Optional columns are interpolated where possible but left
    as NaN across long gaps (they map to EPW "missing" tokens) so they never
    block compilation. Operates in-place and returns a :class:`ProcessingReport`.
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

        if n_missing == 0:
            continue

        longest = _max_gap_length(missing)
        if column in required and longest > max_gap_hours:
            raise DataGapError(
                f"column '{column}' has a {longest}-hour gap exceeding the "
                f"{max_gap_hours}-hour interpolation window; refusing to "
                "generate a corrupted weather file"
            )

        limit = None if column in optional else max_gap_hours
        frame[column] = series.interpolate(
            method="linear", limit=limit, limit_direction="both"
        )

    report.total_interpolated_fraction = (
        total_missing / total_cells if total_cells else 0.0
    )
    return report


def impute_solar(
    frame: pd.DataFrame,
    columns: List[str],
    report: Optional[ProcessingReport] = None,
) -> ProcessingReport:
    """Fill solar gaps using diurnal-aware (same-hour, day-to-day) interpolation.

    STRÅNG occasionally drops whole days of irradiance. Linear interpolation
    across such a gap would smear daytime values into the night, so instead each
    hour-of-day series is interpolated independently across adjacent days. Any
    residual NaN (e.g. a leading/trailing gap) is back/forward filled, and
    negatives are clipped to zero.
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
        if n_missing == 0:
            continue
        hour = series.index.hour
        filled = series.groupby(hour).transform(
            lambda g: g.interpolate(method="linear", limit_direction="both")
        )
        filled = filled.bfill().ffill().clip(lower=0.0)
        frame[column] = filled
    return report


# --------------------------------------------------------------------------- #
# Unit conversions
# --------------------------------------------------------------------------- #
def convert_units(frame: pd.DataFrame) -> None:
    """Apply EPW-facing unit conversions in-place (hPa -> Pa)."""
    if "pressure" in frame.columns:
        frame["pressure"] = frame["pressure"] * 100.0  # hPa -> Pa


# --------------------------------------------------------------------------- #
# Dew point (Magnus formula)
# --------------------------------------------------------------------------- #
def dew_point(dry_bulb: pd.Series, relative_humidity: pd.Series) -> pd.Series:
    """Dew-point temperature (degC) from dry-bulb (degC) and RH (%)."""
    b, c = 17.625, 243.04
    rh = relative_humidity.clip(lower=1.0, upper=100.0) / 100.0
    alpha = np.log(rh) + (b * dry_bulb) / (c + dry_bulb)
    return (c * alpha) / (b - alpha)


# --------------------------------------------------------------------------- #
# Horizontal infrared radiation (Berdahl & Martin, with cloud correction)
# --------------------------------------------------------------------------- #
def horizontal_ir(
    dry_bulb_c: pd.Series,
    dew_point_c: pd.Series,
    opaque_fraction: Optional[pd.Series] = None,
) -> pd.Series:
    """Down-welling longwave sky radiation (W/m^2).

    Clear-sky emissivity follows Berdahl & Martin; when an opaque cloud
    fraction ``N`` in [0, 1] is supplied, the standard cubic cloud-amplification
    factor ``1 + 0.0224 N - 0.0035 N^2 + 0.00028 N^3`` raises emissivity toward
    unity under overcast skies.
    """
    eps_sky = 0.741 + 0.0062 * dew_point_c
    if opaque_fraction is not None:
        n = opaque_fraction.clip(lower=0.0, upper=1.0)
        eps_sky = eps_sky * (1.0 + 0.0224 * n - 0.0035 * n**2 + 0.00028 * n**3)
        eps_sky = eps_sky.clip(upper=1.0)
    t_dry_k = dry_bulb_c + C.KELVIN
    return eps_sky * C.STEFAN_BOLTZMANN * t_dry_k**4


# --------------------------------------------------------------------------- #
# Sky cover (octas -> EPW tenths)
# --------------------------------------------------------------------------- #
def sky_cover_tenths(cloud_octas: pd.Series) -> pd.Series:
    """Convert SMHI total cloud cover (octas 0-8) to EPW tenths (0-10).

    Values are rounded to the nearest tenth and clamped to [0, 10]. NaNs are
    preserved so the exporter can emit the EPW missing token.
    """
    tenths = (cloud_octas / 8.0 * 10.0).round()
    return tenths.clip(lower=0.0, upper=10.0)


# --------------------------------------------------------------------------- #
# Solar transformation: finalize EPW solar fields
# --------------------------------------------------------------------------- #
def apply_solar(
    frame: pd.DataFrame, lat: float, lon: float, report: Optional[ProcessingReport] = None
) -> None:
    """Finalize DNI, DHI and extraterrestrial EPW fields in-place.

    **Solar path selection (in priority order):**

    1. **Measured GHI + STRÅNG beam** — pyranometer GHI with STRÅNG direct-beam
       (params 118/121); DHI closed as ``max(GHI_measured - beam_horizontal, 0)``.
    2. **Measured GHI + Erbs** — pyranometer GHI with Erbs decomposition (pre-2017
       when direct-beam params are unavailable).
    3. **STRÅNG all-params** — GHI/DNI/dirh directly from STRÅNG (post-2017).
    4. **STRÅNG GHI + Erbs** — only param 117 available (pre-2017, no Sol station).
    """
    zenith, cos_z = solar_zenith(frame.index, lat, lon)
    etrh, etrn = extraterrestrial_radiation(frame.index, cos_z)
    frame["etrh"] = etrh
    frame["etrn"] = etrn

    use_measured = (
        C.METOBS_RADIATION_COLUMN in frame.columns
        and not frame[C.METOBS_RADIATION_COLUMN].isna().all()
    )
    has_strang_direct = (
        "dirh" in frame.columns and not frame["dirh"].isna().all()
        and "dni" in frame.columns and not frame["dni"].isna().all()
    )

    below = cos_z <= C.COS_ZENITH_FLOOR

    if use_measured and has_strang_direct:
        ghi_m = np.clip(frame[C.METOBS_RADIATION_COLUMN].to_numpy(dtype=float), 0.0, None)
        # Retain STRÅNG beam decomposition; only the total GHI comes from the sensor.
        dirh = np.clip(frame["dirh"].to_numpy(dtype=float), 0.0, ghi_m)
        frame["ghi"] = ghi_m
        frame["dhi"] = np.clip(ghi_m - dirh, 0.0, None)
        # DNI from STRÅNG param 118 (direct normal), floored below horizon.
        dni = np.clip(frame["dni"].to_numpy(dtype=float), 0.0, None)
        frame["dni"] = np.where(below, 0.0, dni)
        if report is not None:
            report.solar_source = "measured+strang_beam"
        # kt proxy for IR cloud correction.
        etrh_safe = np.where(etrh > 0.0, etrh, 1.0)
        kt = np.clip(np.where(etrh > 0.0, ghi_m / etrh_safe, 0.0), 0.0, 1.0)
        frame["_kt"] = kt

    elif use_measured:
        # Pre-2017: decompose measured GHI via Erbs (no STRÅNG direct beam).
        ghi_m = np.clip(frame[C.METOBS_RADIATION_COLUMN].to_numpy(dtype=float), 0.0, None)
        dhi, dni_erbs = erbs_decomposition(ghi_m, etrh, cos_z)
        frame["ghi"] = ghi_m
        frame["dhi"] = np.clip(dhi, 0.0, None)
        frame["dni"] = np.where(below, 0.0, np.clip(dni_erbs, 0.0, None))
        if "dirh" not in frame.columns:
            frame["dirh"] = np.where(below, 0.0,
                                     np.clip(frame["dni"].to_numpy() * np.clip(cos_z, 0.0, None),
                                             0.0, None))
        if report is not None:
            report.solar_source = "measured+erbs"
        etrh_safe = np.where(etrh > 0.0, etrh, 1.0)
        kt = np.clip(np.where(etrh > 0.0, ghi_m / etrh_safe, 0.0), 0.0, 1.0)
        frame["_kt"] = kt

    elif has_strang_direct:
        # Post-2017 STRÅNG-only path.
        dni = np.clip(frame["dni"].to_numpy(dtype=float), 0.0, None)
        frame["dni"] = np.where(below, 0.0, dni)
        frame["dhi"] = (frame["ghi"] - frame["dirh"]).clip(lower=0.0)
        if report is not None:
            report.solar_source = "strang"

    else:
        # Pre-2017 STRÅNG GHI-only: decompose via Erbs.
        ghi = frame["ghi"].to_numpy(dtype=float)
        dhi, dni_erbs = erbs_decomposition(ghi, etrh, cos_z)
        frame["dhi"] = np.clip(dhi, 0.0, None)
        frame["dni"] = np.where(below, 0.0, np.clip(dni_erbs, 0.0, None))
        frame["dirh"] = np.where(below, 0.0,
                                  np.clip(frame["dni"].to_numpy() * np.clip(cos_z, 0.0, None),
                                          0.0, None))
        if report is not None:
            report.solar_source = "strang_ghi+erbs"

    if report is not None:
        report.clamped_dni_hours = int(
            np.count_nonzero(frame["dni"].to_numpy(dtype=float) == 0.0)
        )
        beam_h = frame["dni"].to_numpy(dtype=float) * np.clip(cos_z, 0.0, None)
        residual = np.abs(
            frame["ghi"].to_numpy(dtype=float)
            - (frame["dhi"].to_numpy(dtype=float) + beam_h)
        )
        report.energy_balance_max_residual = float(np.nanmax(residual)) if len(residual) else 0.0


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def process(frame: pd.DataFrame, lat: float, lon: float) -> ProcessingReport:
    """Run the full processing pipeline in-place and return diagnostics.

    Adds ``dew_point``, ``horizontal_ir``, ``dni``, ``dhi``, ``etrh``/``etrn``
    and (when cloud data is present) ``sky_cover`` columns, and converts units.
    The input ``frame`` must be indexed by a continuous hourly UTC grid.
    """
    required = list(C.METOBS_REQUIRED_PARAMETERS.values())
    optional = list(C.METOBS_OPTIONAL_PARAMETERS.values())
    solar_columns = list(C.STRANG_PARAMETERS.values())

    report = impute(frame, required, optional)
    impute_solar(frame, solar_columns, report)
    convert_units(frame)

    frame["dew_point"] = dew_point(frame["dry_bulb"], frame["relative_humidity"])

    # --- Cloud opacity for the longwave IR model ---
    # Priority: (1) param 16 octas, (2) kt-based proxy from measured GHI (after
    # apply_solar stores _kt), (3) clear-sky only (no correction).
    opaque_fraction = None
    if "cloud_cover" in frame.columns and not frame["cloud_cover"].isna().all():
        report.cloud_available = True
        opaque_fraction = (frame["cloud_cover"] / 8.0).clip(lower=0.0, upper=1.0)
        frame["sky_cover"] = sky_cover_tenths(frame["cloud_cover"])

    # apply_solar runs first so _kt is available as kt proxy.
    apply_solar(frame, lat, lon, report)

    if opaque_fraction is None and "_kt" in frame.columns:
        # kt close to 1 → clear sky (low clouds); kt close to 0 → overcast.
        # Linear mapping: opaque ≈ 1 − kt (only during daytime hours).
        kt = frame["_kt"]
        daytime = kt > 0.0
        proxy = (1.0 - kt).clip(lower=0.0, upper=1.0)
        proxy[~daytime] = np.nan  # no meaningful kt at night → IR unchanged
        if proxy.notna().any():
            opaque_fraction = proxy
            report.cloud_available = True   # proxy counts as cloud info
            frame["sky_cover"] = sky_cover_tenths(
                (proxy * 8.0).clip(lower=0.0, upper=8.0)
            )
        del frame["_kt"]

    frame["horizontal_ir"] = horizontal_ir(
        frame["dry_bulb"], frame["dew_point"], opaque_fraction
    )
    return report
