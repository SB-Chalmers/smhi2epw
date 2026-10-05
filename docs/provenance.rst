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


Target elevation and derived pressure
-------------------------------------

SMHI MetObs parameter 9 is sea-level-reduced pressure (QFF), not station
pressure. The compiler estimates surface pressure at ``target_elevation_m``
using the inverse SMHI reduction, with hourly observed temperature and target
latitude. The result records ``pressure_method=smhi_qff_inverse_v1`` and resolved
target coordinates/elevation separately from ``result.station``.

This estimate uses target elevation as barometer height and nearby observed
temperature as representative of the target. It is not a direct pressure
observation at the building; temperature inversions and station separation can
introduce uncertainty. Original API payloads remain unchanged in the cache.

Reference: https://www.smhi.se/kunskapsbanken/meteorologi/lufttryck/hur-mats-lufttryck

Generated pressure values intentionally differ from releases that treated QFF
as station pressure. Regenerate EPWs and update simulation identities rather
than modifying an existing dataset in place.
