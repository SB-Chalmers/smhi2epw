Data provenance and acknowledgment
==================================

Meteorological observations
---------------------------

Temperature, relative humidity, pressure, wind speed, wind direction, optional
total cloud cover, and optional measured GHI originate from SMHI MetObs
corrected archives. Only accepted quality flags are used. The selected SMHI
station identifier is written into the EPW comments; it is not substituted for
a WMO number.

Solar radiation
---------------

STRÅNG provides gridded solar radiation at the requested coordinates. The EPW
header includes the required acknowledgment:

   STRÅNG data used here are from the Swedish Meteorological and Hydrological
   Institute (SMHI), and were produced with support from the Swedish Radiation
   Protection Authority and the Swedish Environmental Agency.

Reproducibility
---------------

Archive the configuration, package version, generated EPW, diagnostics, and
source-access date with a simulation project. Raw payload caching improves
repeatability, but upstream corrected archives may legitimately be revised.
Use ``refresh`` intentionally and record when data was re-fetched.

