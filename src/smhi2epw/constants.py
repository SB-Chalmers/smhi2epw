"""Project-wide constants: API endpoints, parameter codes and EPW tokens."""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# SMHI Meteorological Observations (metobs) API
# --------------------------------------------------------------------------- #
METOBS_BASE = "https://opendata-download-metobs.smhi.se/api/version/1.0"
METOBS_PERIOD = "corrected-archive"

# metobs parameter codes -> internal canonical column names.
#
# Required parameters are subject to the hard gap-abort policy; optional ones
# are filled when present but never block compilation if missing.
METOBS_REQUIRED_PARAMETERS = {
    1: "dry_bulb",           # Air temperature, instantaneous (degC)
    6: "relative_humidity",  # Relative humidity (%)
    9: "pressure",           # Air pressure at station level (hPa)
    4: "wind_speed",         # Wind speed (m/s)
    3: "wind_direction",     # Wind direction (degrees)
}
METOBS_OPTIONAL_PARAMETERS = {
    16: "cloud_cover",       # Total cloud cover (octas 0-8)
}
METOBS_PARAMETERS = {**METOBS_REQUIRED_PARAMETERS, **METOBS_OPTIONAL_PARAMETERS}

# Radiation (pyranometer) parameter — fetched from a separate "Sol" station when
# available; dramatically improves GHI accuracy and enables Erbs DNI decomposition.
METOBS_RADIATION_PARAMETER = 11   # Global Irradiance (W/m², hourly mean)
METOBS_RADIATION_COLUMN   = "ghi_measured"

# metobs quality codes that are accepted as usable observations. Anything else
# is treated as missing (and therefore eligible for interpolation).
METOBS_ACCEPTED_QUALITY = {"G", "Y"}

# --------------------------------------------------------------------------- #
# SMHI STRÅNG mesoscale solar model API
# --------------------------------------------------------------------------- #
STRANG_BASE = (
    "https://opendata-download-metanalys.smhi.se/api/category/strang1g/version/1"
)

# STRÅNG parameter codes -> internal canonical column names.
#
# NOTE: the live STRÅNG (strang1g v1) API semantics differ from the original
# spec's assumptions. Verified empirically (param 118 * cos(zenith) == param
# 121 at every hour):
#   117 = Global Horizontal Irradiance (W/m^2)
#   118 = Direct *Normal* Irradiance   (W/m^2)  -- already normal, no projection
#   121 = Direct beam on the horizontal plane (W/m^2)  -- used to close diffuse
# Diffuse Horizontal is therefore derived as GHI - beam_horizontal (117 - 121).
#
# Params 118 and 121 are only available from April 18, 2017 onwards.
# For earlier years only param 117 (GHI) is fetched; DHI/DNI are estimated
# via Erbs decomposition.
STRANG_PARAMETERS = {
    117: "ghi",   # Global Horizontal Irradiance (W/m^2)
    118: "dni",   # Direct Normal Irradiance (W/m^2)
    121: "dirh",  # Direct beam on horizontal plane (W/m^2)
}
STRANG_GHI_ONLY_PARAMETERS = {117: "ghi"}   # params available before Apr 2017
STRANG_DIRECT_AVAILABLE_YEAR = 2017          # conservative cutoff (full years)

# --------------------------------------------------------------------------- #
# Physical constants
# --------------------------------------------------------------------------- #
STEFAN_BOLTZMANN = 5.670374419e-8  # W/(m^2 K^4)
KELVIN = 273.15
SOLAR_CONSTANT = 1367.0  # W/m^2 (mean extraterrestrial irradiance)

# Solar-elevation floor for the DHI -> DNI projection.
# cos(zenith) <= 0.087 corresponds to a solar elevation below ~5 degrees.
COS_ZENITH_FLOOR = 0.087

# Imputation policy: maximum contiguous gap (hours) resolved by interpolation.
MAX_GAP_HOURS = 3

# --------------------------------------------------------------------------- #
# EPW missing-value / default tokens (per EnergyPlus Auxiliary Programs spec)
# --------------------------------------------------------------------------- #
EPW_MISSING = {
    "dry_bulb": 99.9,
    "dew_point": 99.9,
    "relative_humidity": 999,
    "pressure": 999999,
    "horizontal_ir": 9999,
    "ghi": 9999,
    "dni": 9999,
    "dhi": 9999,
    "wind_direction": 999,
    "wind_speed": 99.9,
}

# Uncertainty/observation data-flags field (col 6): 47 nines.
EPW_DATA_FLAGS = "9" * 47

# Default tokens for the secondary fields (cols 23..35) that core EnergyPlus
# thermal simulation does not consume.
EPW_SECONDARY_DEFAULTS = {
    "extraterrestrial_horizontal": 9999,
    "extraterrestrial_direct_normal": 9999,
    "global_horizontal_illuminance": 999999,
    "direct_normal_illuminance": 999999,
    "diffuse_horizontal_illuminance": 999999,
    "zenith_luminance": 9999,
    "total_sky_cover": 99,
    "opaque_sky_cover": 99,
    "visibility": 9999,
    "ceiling_height": 99999,
    "present_weather_observation": 9,
    "present_weather_codes": 999999999,
    "precipitable_water": 999,
    "aerosol_optical_depth": 0.999,
    "snow_depth": 999,
    "days_since_last_snowfall": 99,
    "albedo": 999,
    "liquid_precip_depth": 999,
    "liquid_precip_quantity": 99,
}
