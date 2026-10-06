"""Centralize API semantics, physical constants, and EPW sentinel values.

Keeping these values in one dependency-free module makes the assumptions used
by ingestion, processing, and export easy to audit. Parameter mappings translate
SMHI numeric IDs to canonical internal column names. Missing-value dictionaries
are field-specific because EPW does not use one universal missing token.

STRÅNG GHI and direct-normal radiation are available from 1999. The separately
published direct-horizontal field begins on 18 April 2017; earlier hours derive
it from instantaneous DNI and solar geometry before interval averaging.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# SMHI Meteorological Observations (metobs) API
# --------------------------------------------------------------------------- #
METOBS_BASE = "https://opendata-download-metobs.smhi.se/api/version/1.0"
METOBS_PERIOD = "corrected-archive"
PRESSURE_METHOD = "smhi_qff_inverse_v1"

# metobs parameter codes -> internal canonical column names.
#
# Required parameters are subject to the hard gap-abort policy; optional ones
# are filled when present but never block compilation if missing.
METOBS_REQUIRED_PARAMETERS = {
    1: "dry_bulb",  # Air temperature, instantaneous (degC)
    6: "relative_humidity",  # Relative humidity (%)
    9: "pressure",  # Sea-level-reduced air pressure, QFF (hPa)
    4: "wind_speed",  # Wind speed (m/s)
    3: "wind_direction",  # Wind direction (degrees)
}
METOBS_OPTIONAL_PARAMETERS = {
    # Internal octas 0–8; normalize SMHI declared percent 0–100 at ingestion.
    16: "cloud_cover",
}
METOBS_PARAMETERS = {**METOBS_REQUIRED_PARAMETERS, **METOBS_OPTIONAL_PARAMETERS}

# Radiation (pyranometer) parameter — fetched from a separate "Sol" station when
# available and partitioned with STRÅNG direct components throughout history.
METOBS_RADIATION_PARAMETER = 11  # Global Irradiance (W/m², hourly mean)
METOBS_RADIATION_COLUMN = "ghi_measured"

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
# Parameter meanings follow SMHI's STRÅNG extraction documentation:
# https://strang.smhi.se/extraction/index.php
#   117 = Global Horizontal Irradiance (W/m^2)
#   118 = Direct *Normal* Irradiance   (W/m^2)  -- already normal, no projection
#   121 = Direct beam on the horizontal plane (W/m^2)  -- used to close diffuse
# Diffuse Horizontal is therefore derived as GHI - beam_horizontal (117 - 121).
#
# Parameter 118 is available throughout supported history. Parameter 121 starts
# on April 18, 2017; ingestion projects instantaneous DNI for earlier hours.
STRANG_PARAMETERS = {
    117: "ghi",  # Global Horizontal Irradiance (W/m^2)
    118: "dni",  # Direct Normal Irradiance (W/m^2)
    121: "dirh",  # Direct beam on horizontal plane (W/m^2)
}
STRANG_HISTORICAL_PARAMETERS = {117: "ghi", 118: "dni"}
STRANG_DIRECT_HORIZONTAL_START = "2017-04-18T00:00:00Z"
STRANG_MIN_YEAR = 1999  # STRÅNG operational since Jan 1999

# Spatial resolution by era (year-based approximation; exact switch dates are
# May 2006 and Mar 29 2017).
STRANG_RESOLUTION_BY_YEAR = [
    (2017, "~2.5 × 2.5 km"),
    (2006, "~11 × 11 km"),
    (1999, "~22 × 22 km"),
]

# --------------------------------------------------------------------------- #
# Physical constants
# --------------------------------------------------------------------------- #
STEFAN_BOLTZMANN = 5.670374419e-8  # W/(m^2 K^4)
KELVIN = 273.15
SOLAR_CONSTANT = 1367.0  # W/m^2 (mean extraterrestrial irradiance)

# Solar-elevation floor only for inferred horizontal-to-normal radiation.
# cos(zenith) <= 0.087 corresponds to a solar elevation below ~5 degrees.
COS_ZENITH_FLOOR = 0.087

# Imputation policy. Short gaps are linearly interpolated; longer gaps use the
# reference day-profile method and are never synthesized beyond two days.
SHORT_GAP_HOURS = 3
MAX_GAP_HOURS = 48

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
