"""Calculate solar geometry and split global irradiance into EPW components.

Solar position, extraterrestrial irradiance, and Erbs-Driesse decomposition
use pvlib. Timestamps must be timezone-aware; the compiler integrates geometry
over each preceding hour. Supplied components retain their own interval means.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pvlib import irradiance, solarposition


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
    geometric horizon. pvlib evaluates the NREL SPA with NumPy and estimates
    delta-T for each UTC year and month. We use true geometric zenith, without
    atmospheric refraction, at the default sea-level altitude.

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
    Reda, I., & Andreas, A. (2004). *Solar position algorithm for solar
    radiation applications*. Solar Energy, 76(5), 577--589.
    """
    if index.tz is None:
        raise ValueError("solar_zenith requires a timezone-aware (UTC) index")

    utc = index.tz_convert("UTC")
    position = solarposition.get_solarposition(
        utc, latitude, longitude, method="nrel_numpy", delta_t=None
    )
    # Apparent zenith includes refraction and would change our horizon rule.
    zenith = position["zenith"].to_numpy(dtype=float)
    cos_zenith = np.cos(np.deg2rad(zenith))
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
    correction using pvlib's ASCE method and the existing 1367 W/m² constant;
    horizontal is that projected onto the horizontal plane (>= 0).
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
    # Integer UTC day-of-year preserves the existing daily ASCE correction.
    direct_normal = np.asarray(
        irradiance.get_extra_radiation(
            doy, solar_constant=C.SOLAR_CONSTANT, method="asce"
        ),
        dtype=float,
    )
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
    """Estimate DHI and DNI from hourly GHI using pvlib Erbs-Driesse.

    Parameters
    ----------
    ghi
        Nonnegative global horizontal irradiance in W/m².
    etrh
        Extraterrestrial horizontal irradiance averaged over the same hour.
    cos_zenith
        Mean positive zenith cosine over the hour. Inputs may broadcast.

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
    The effective normal input ``ETRH/cos_zenith`` keeps pvlib's clearness
    index equal to ``GHI/ETRH`` for these interval means. Erbs-Driesse smooths
    the classic Erbs diffuse fraction, changing it by less than 0.0005.
    DNI follows from horizontal closure. At cosine <= 0.087 or nonpositive
    ETRH, DNI is zero and all GHI is diffuse. This inversion guard applies to
    inferred DNI; supplied components are handled separately by processing.
    The existing helper name and ``+erbs`` source labels denote the family.

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
    Driesse, A., Jensen, A., & Perez, R. (2024). *A continuous form of the Perez
    diffuse sky model for forward and reverse transposition*. Solar Energy,
    267, 112093. doi:10.1016/j.solener.2023.112093.
    """
    from . import constants as C

    ghi, etrh, cos_z = np.broadcast_arrays(
        np.asarray(ghi, dtype=float),
        np.asarray(etrh, dtype=float),
        np.asarray(cos_zenith, dtype=float),
    )
    dhi = ghi.copy()
    dni = np.zeros_like(ghi)
    usable = (cos_z > C.COS_ZENITH_FLOOR) & (etrh > 0.0)
    if np.any(usable):
        cosine = cos_z[usable]
        zenith = np.rad2deg(np.arccos(np.clip(cosine, -1.0, 1.0)))
        # ETRH / mean cosine is an effective normal for the clearness index.
        # It is NOT the exported mean ETRN, which is zero during dark samples.
        components = irradiance.erbs_driesse(
            ghi[usable],
            zenith,
            dni_extra=etrh[usable] / cosine,
            min_cos_zenith=C.COS_ZENITH_FLOOR,
            max_zenith=np.rad2deg(np.arccos(C.COS_ZENITH_FLOOR)),
        )
        dhi[usable] = components["dhi"]
        dni[usable] = components["dni"]
    return dhi, dni
