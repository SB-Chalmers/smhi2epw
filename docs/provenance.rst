Data provenance and acknowledgment
==================================

Meteorological observations
---------------------------

Temperature, relative humidity, pressure, wind speed, wind direction, optional
total cloud cover, and optional measured GHI originate from SMHI MetObs
corrected archives. Only accepted quality flags are used. The selected SMHI
station identifier is written into the EPW comments; it is not substituted for
a WMO number. Automatic recovery can use assessed nearby stations, with filled
hours, validation results and corrections retained in the processing report.

Solar radiation
---------------

STRÅNG provides gridded solar radiation at the requested coordinates. The EPW
header includes the required acknowledgment:

   STRÅNG data used here are from the Swedish Meteorological and Hydrological
   Institute (SMHI), and were produced with support from the Swedish Radiation
   Protection Authority and the Swedish Environmental Agency.

Reanalysis fallback
-------------------

Same-year ERA5 through Open-Meteo recovers required hours that primary sources,
short interpolation, assessed donors and bounded daily profiles cannot supply. The report records
the selected model, returned grid location/elevation, source fractions and
warnings. EPW comments identify fallback use; retain the JSON sidecar for its
complete details. A mixed or reanalysis-only year remains an AMY estimate for
the requested dates, not proof of local measured conditions.

Acknowledge Open-Meteo and the Copernicus Climate Change Service ERA5 data when
using fallback estimates. Optional ERA5 cloud cover is recorded only at hours
where ERA5 replaces required meteorology or GHI; usable cloud values and other
hours are preserved. ``reanalysis_filled_hours`` includes recovered cloud hours,
while ``source_fractions`` describes required meteorology and GHI.
The adapter uses the public noncommercial endpoint;
consult `Open-Meteo service access <https://open-meteo.com/en/pricing>`_ for
current limits and commercial requirements. See :doc:`weather_recovery` for
source alignment, safeguards and limitations.

Reproducibility
---------------

Archive the configuration, package and pvlib versions, generated EPW,
diagnostics, and source-access date with a simulation project. Raw payload
caching improves repeatability, but upstream corrected archives may
legitimately be revised.
Use ``refresh`` intentionally and record when data was re-fetched.

Automatic policy writes ``OUTPUT.epw.json`` by default. Set ``provenance_path``
(CLI ``--provenance``) for another destination. Strict mode writes a receipt
only when a path is supplied. Sidecar paths must differ from the EPW and have an
existing parent directory.

The sidecar contains reconstruction settings, diagnostics, warnings, output
SHA-256, package/source identity and hashes of consumed UTF-8 responses.
Receipts belong to a single compilation: reused clients and repeated URLs do
not import unrelated earlier requests. Cached and live responses follow the
same receipt contract. A custom client without scoped response recording is
explicitly marked incomplete.

New receipts add the top-level ``pvlib_version`` field while retaining schema
version 1 and existing fields. Earlier receipts can lack this field; retain
their original source hashes and study identity. Current solar calculations
use NREL SPA ``nrel_numpy`` geometric zenith with ``delta_t=None``, ASCE
extraterrestrial irradiance with a 1367 W/m² solar constant, and the continuous
Erbs-Driesse fallback. See :doc:`pipeline` for the preceding-hour conventions
and :doc:`bibliography` for the implementations.

The completeness and sensitivity JSON files bundled with the examples describe
their recorded pre-pvlib source revisions. Their counts, hashes and load
differences remain historical evidence. Regenerate EPWs in a new directory
when adopting pvlib and preserve the new receipt with its consumer results.

EPW export and sidecar export are individually atomic. The sidecar is written
after the validated EPW. Under automatic policy, a sidecar filesystem error
returns the valid EPW with a structured ``provenance_write_failed`` warning.
Strict policy retains a reported sidecar error. A valid EPW alone does not
establish that its audit trail was successfully saved.


Target elevation and derived pressure
-------------------------------------

SMHI MetObs parameter 9 is sea-level-reduced pressure (QFF), not station
pressure. The compiler estimates surface pressure at ``target_elevation_m``
using the inverse SMHI reduction, with hourly observed temperature and target
latitude. The result records ``pressure_method=smhi_qff_inverse_v1`` and resolved
target coordinates/elevation separately from ``result.station``. This conversion
applies only to usable SMHI QFF samples. ERA5 supplies surface pressure, which
is converted from hPa to Pa and never passed through the QFF reduction again.

This estimate uses target elevation as barometer height and nearby observed
temperature as representative of the target. It is not a direct pressure
observation at the building; temperature inversions and station separation can
introduce uncertainty. Original API payloads remain unchanged in the cache.

Reference: https://www.smhi.se/kunskapsbanken/meteorologi/lufttryck/hur-mats-lufttryck

Generated pressure values intentionally differ from releases that treated QFF
as station pressure. Regenerate EPWs and update simulation identities rather
than modifying an existing dataset in place.
