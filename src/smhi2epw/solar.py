"""Solar geometry helpers (NOAA solar-position algorithm).

Implemented with numpy only so the package keeps zero heavy dependencies.
All inputs are UTC; outputs are returned for each timestamp in the index.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def solar_zenith(index: pd.DatetimeIndex, latitude: float, longitude: float):
    """Return ``(zenith_degrees, cos_zenith)`` for a UTC ``DatetimeIndex``.

    Uses the NOAA general solar-position equations. ``longitude`` is east
    positive, ``latitude`` is north positive. Because timestamps are UTC the
    timezone correction term is zero.
    """
    if index.tz is None:
        raise ValueError("solar_zenith requires a timezone-aware (UTC) index")

    utc = index.tz_convert("UTC")
    doy = utc.dayofyear.to_numpy(dtype=float)
    hour = (
        utc.hour.to_numpy(dtype=float)
        + utc.minute.to_numpy(dtype=float) / 60.0
        + utc.second.to_numpy(dtype=float) / 3600.0
    )

    # Fractional year (radians).
    gamma = 2.0 * np.pi / 365.0 * (doy - 1.0 + (hour - 12.0) / 24.0)

    # Equation of time (minutes).
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )

    # Solar declination (radians).
    decl = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )

    # True solar time (minutes). timezone term omitted because input is UTC.
    time_offset = eqtime + 4.0 * longitude
    tst = hour * 60.0 + time_offset
    hour_angle = np.radians(tst / 4.0 - 180.0)

    lat_rad = np.radians(latitude)
    cos_zenith = np.sin(lat_rad) * np.sin(decl) + np.cos(lat_rad) * np.cos(decl) * np.cos(
        hour_angle
    )
    cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
    zenith = np.degrees(np.arccos(cos_zenith))
    return zenith, cos_zenith


def extraterrestrial_radiation(index: pd.DatetimeIndex, cos_zenith):
    """Return ``(horizontal, direct_normal)`` extraterrestrial irradiance (W/m^2).

    Direct-normal is the solar constant scaled by the Earth-Sun distance
    correction; horizontal is that projected onto the horizontal plane (>= 0).
    """
    from . import constants as C

    doy = index.tz_convert("UTC").dayofyear.to_numpy(dtype=float)
    eccentricity = 1.0 + 0.033 * np.cos(2.0 * np.pi * doy / 365.0)
    direct_normal = C.SOLAR_CONSTANT * eccentricity
    cos_z = np.asarray(cos_zenith)
    horizontal = np.where(cos_z > 0.0, direct_normal * cos_z, 0.0)
    # Convention (matches EnergyPlus TMY): etrn is 0 when sun is below horizon.
    direct_normal = np.where(cos_z > 0.0, direct_normal, 0.0)
    return horizontal, direct_normal


def erbs_decomposition(ghi, etrh, cos_zenith):
    """Erbs (1982) GHI → DHI + DNI decomposition.

    Given measured global horizontal irradiance ``ghi`` (W/m²), the
    extraterrestrial horizontal ``etrh`` (W/m²) and the cosine of the solar
    zenith angle, estimate the diffuse-horizontal (DHI) and direct-normal
    (DNI) components.

    Reference: Erbs, Klein & Duffie (1982), *Estimation of the diffuse radiation
    fraction for hourly, daily and monthly-average global radiation*, Solar Energy
    29(4), 369-378.
    """
    from . import constants as C

    ghi = np.asarray(ghi, dtype=float)
    etrh = np.asarray(etrh, dtype=float)
    cos_z = np.asarray(cos_zenith, dtype=float)

    # Clearness index kt (0 = overcast, 1 = clear); set 0 when sun below horizon.
    etrh_safe = np.where(etrh > 0.0, etrh, 1.0)
    kt = np.clip(ghi / etrh_safe, 0.0, 1.0)
    kt = np.where(etrh > 0.0, kt, 0.0)

    # Diffuse fraction (Erbs piecewise polynomial).
    fd = np.where(
        kt <= 0.22,
        1.0 - 0.09 * kt,
        np.where(
            kt <= 0.80,
            0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4,
            0.165,
        ),
    )
    dhi = np.clip(fd * ghi, 0.0, ghi)

    # DNI from energy balance: GHI = DHI + DNI * cos(zenith).
    cos_z_safe = np.where(cos_z > C.COS_ZENITH_FLOOR, cos_z, 1.0)
    dni = np.where(cos_z > C.COS_ZENITH_FLOOR, (ghi - dhi) / cos_z_safe, 0.0)
    dni = np.clip(dni, 0.0, None)
    return dhi, dni
