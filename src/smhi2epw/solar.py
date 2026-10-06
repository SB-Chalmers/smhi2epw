"""Calculate solar geometry and split global irradiance into EPW components.

The vectorized helpers use the NOAA fractional-year approximation and the Erbs
hourly diffuse-fraction correlation. They depend only on NumPy and pandas,
keeping the core package lightweight. Timestamps must be timezone-aware; the
compiler integrates them over the preceding-hour radiation interval.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def solar_zenith(index: pd.DatetimeIndex, latitude: float, longitude: float):
    """Calculate solar zenith angle for timezone-aware timestamps.

    Parameters
    ----------
    index
        Timezone-aware timestamps. They are converted to UTC internally.
    latitude, longitude
        Observer coordinates in decimal degrees; north and east are positive.

    Returns
    -------
    tuple of numpy.ndarray
        Zenith angle in degrees and its cosine, one value per timestamp.

    Raises
    ------
    ValueError
        If ``index`` is timezone-naive.

    Notes
    -----
    Zenith is 0° when the sun is directly overhead and exceeds 90° below the
    geometric horizon. The NOAA general solar-position approximation computes
    fractional year, equation of time, declination, and hour angle. Because the
    timestamps are converted to UTC, the timezone term is zero.

    Examples
    --------
    >>> index = pd.DatetimeIndex(["2023-06-21 12:00"], tz="UTC")
    >>> zenith, cosine = solar_zenith(index, 57.7156, 11.9924)
    >>> bool(30 < zenith[0] < 40)
    True
    >>> bool(cosine[0] > 0)
    True

    References
    ----------
    NOAA Global Monitoring Laboratory, *Solar Calculation Details*.
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
    year_days = np.where(utc.is_leap_year, 366.0, 365.0)
    gamma = 2.0 * np.pi / year_days * (doy - 1.0 + (hour - 12.0) / 24.0)

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
    cos_zenith = np.sin(lat_rad) * np.sin(decl) + np.cos(lat_rad) * np.cos(
        decl
    ) * np.cos(hour_angle)
    cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
    zenith = np.degrees(np.arccos(cos_zenith))
    return zenith, cos_zenith


def extraterrestrial_radiation(index: pd.DatetimeIndex, cos_zenith):
    """Calculate extraterrestrial horizontal and direct-normal irradiance.

    Parameters
    ----------
    index
        Timezone-aware timestamps used for Earth--Sun distance correction.
    cos_zenith
        Cosine of solar zenith for each timestamp.

    Returns
    -------
    tuple of numpy.ndarray
        Extraterrestrial horizontal and direct-normal irradiance in W/m².

    Direct-normal is the solar constant scaled by the Earth-Sun distance
    correction; horizontal is that projected onto the horizontal plane (>= 0).
    Both quantities are zero when the sun is below the horizon, matching EPW
    convention.

    Examples
    --------
    >>> index = pd.DatetimeIndex(["2023-06-21 12:00"], tz="UTC")
    >>> horizontal, normal = extraterrestrial_radiation(index, [0.8])
    >>> round(float(horizontal[0] / normal[0]), 1)
    0.8
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


def interval_solar_geometry(index: pd.DatetimeIndex, latitude: float, longitude: float):
    """Estimate geometry and extraterrestrial means over each preceding hour.

    Five-minute trapezoidal integration includes partially sunlit intervals.
    The mean positive cosine is useful when only horizontal radiation is known;
    supplied hourly DNI and beam-horizontal radiation retain their own means.

    Parameters
    ----------
    index
        Timezone-aware timestamps labelling the end of each interval.
    latitude, longitude
        Observer coordinates in decimal degrees.

    Returns
    -------
    tuple of numpy.ndarray
        Mean positive zenith cosine, mean extraterrestrial horizontal and
        normal irradiance (W/m²), and a mask of wholly dark intervals.
    """
    cosine_mean = np.zeros(len(index), dtype=float)
    horizontal_mean = np.zeros(len(index), dtype=float)
    normal_mean = np.zeros(len(index), dtype=float)
    dark = np.ones(len(index), dtype=bool)
    for minutes in range(0, 61, 5):
        sample = index - pd.Timedelta(minutes=minutes)
        _, cosine = solar_zenith(sample, latitude, longitude)
        horizontal, normal = extraterrestrial_radiation(sample, cosine)
        weight = 0.5 if minutes in (0, 60) else 1.0
        cosine_mean += weight * np.maximum(cosine, 0.0) / 12.0
        horizontal_mean += weight * horizontal / 12.0
        normal_mean += weight * normal / 12.0
        dark &= cosine <= 0.0
    return cosine_mean, horizontal_mean, normal_mean, dark


def erbs_decomposition(ghi, etrh, cos_zenith):
    """Estimate diffuse-horizontal and direct-normal irradiance from GHI.

    Parameters
    ----------
    ghi
        Global horizontal irradiance in W/m².
    etrh
        Extraterrestrial horizontal irradiance in W/m².
    cos_zenith
        Cosine of solar zenith.

    Returns
    -------
    tuple of numpy.ndarray
        Diffuse horizontal irradiance (DHI) and direct normal irradiance (DNI)
        in W/m².

    Given measured global horizontal irradiance ``ghi`` (W/m²), the
    extraterrestrial horizontal ``etrh`` (W/m²) and the cosine of the solar
    zenith angle, estimate the diffuse-horizontal (DHI) and direct-normal
    (DNI) components.

    Notes
    -----
    The clearness index ``kt = GHI/ETRH`` selects one of three empirical diffuse
    fractions. DNI follows from ``GHI = DHI + DNI*cos(zenith)``. Near or below
    the horizon, DNI is set to zero and all GHI is assigned to DHI so closure is
    retained.

    Examples
    --------
    >>> dhi, dni = erbs_decomposition([500.0], [800.0], [0.7])
    >>> round(float(dhi[0] + dni[0] * 0.7), 6)
    500.0

    References
    ----------
    Erbs, D. G., Klein, S. A., & Duffie, J. A. (1982). *Estimation of
    the diffuse radiation fraction for hourly, daily and monthly-average
    global radiation*. Solar Energy, 28(4), 293--302.
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
    # Once direct normal is suppressed near/below the horizon, assign the full
    # global horizontal value to diffuse so the energy balance still closes.
    dhi = np.where(cos_z > C.COS_ZENITH_FLOOR, dhi, ghi)
    return dhi, dni
