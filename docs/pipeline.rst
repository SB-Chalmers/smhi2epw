Pipeline and scientific methods
===============================

Data flow
---------

The compiler follows five explicit stages:

1. Validate configuration before network access.
2. Prefer full-year meteorological and optional radiation stations, permitting
   partial station coverage in automatic mode.
3. Retrieve MetObs and STRÅNG onto a buffered hourly UTC grid, recording source
   failures while automatic recovery continues.
4. Interpolate short gaps, assess nearby meteorological donors, use bounded
   daily profiles for remaining gaps and recover unresolved automatic-mode hours
   with same-year ERA5; derive physical fields and close the solar balance.
5. Shift to Local Standard Time, validate and atomically write the EPW, followed
   by its provenance sidecar in automatic mode.

Gap reconstruction
------------------

Required meteorological gaps of one to three hours use endpoint interpolation.
Longer gaps and unfillable short wind gaps next use assessed same-year donors.
Remaining gaps up to 48 hours use the previous and next complete 24-hour
profiles. Each profile is adjusted gradually to meet observations around the
gap; valid sides receive equal weight and a single valid side is sufficient.
Automatic mode then uses ERA5 for unresolved hours. Temporal filling never
exceeds 48 hours. Strict mode uses donors only when explicitly enabled and has
no ERA5 fallback. Solar filling remains donor-free.

Wind direction is interpolated through sine and cosine components. This avoids
the false arithmetic midpoint of 180° between 359° and 1°. Solar gaps always
use day-aware profiles so linear interpolation cannot brighten the night.

Donor assessment uses local original overlap and blocked validation. Raw transfer
and a scalar median offset compete on held-out errors; wind direction is never
rotated. See :doc:`weather_recovery` for thresholds and training requirements.
The pipeline preserves usable primary extremes and reports source-boundary
jumps. Reconstructed gaps can still alter event peaks and persistence. A
single-year sensitivity experiment motivated donor precedence; it does not
establish universal accuracy across sites and years.

Solar radiation
---------------

EPW radiation represents the preceding hour, so geometry is evaluated at the
interval midpoint. Depending on year and station availability, the pipeline
uses measured GHI with STRÅNG beam fractions, measured GHI with Erbs, all
STRÅNG components, or STRÅNG GHI with Erbs. Automatic recovery can use ERA5
solar component groups for unresolved hours. Reanalysis radiation already
describes the preceding-hour mean, so only instantaneous STRÅNG values undergo
adjacent-sample averaging.

All paths enforce

.. math::

   GHI = DHI + DNI \cos(\theta_z)

At very low solar elevation, DNI is set to zero and GHI is treated as diffuse.
DNI cannot exceed extraterrestrial direct-normal irradiance. DHI is always
recomputed after caps so the balance remains closed.

Longwave and cloud cover
------------------------

EnergyPlus sky emissivity is calculated from dew-point temperature and, when
available, a cubic cloud multiplier. SMHI supplies total rather than opaque
cloud cover. Total cover is therefore documented as an IR-only proxy and
populates total sky cover; opaque sky cover remains the EPW missing value.
ERA5 supplies missing cloud cover only at hours where it actually replaces
required meteorology or GHI. Usable existing clouds and other hours are
preserved, including when ERA5 is fetched solely for metadata.

EPW time and output safety
--------------------------

The UTC source is mapped to a constant whole-hour Local Standard Time offset.
No broad forward/backward fill is used during this shift. Each target hour must
have a complete processed value at its exact timestamp. The destination is
replaced only after eight headers, all 35 fields, physical ranges and all
8760/8784 rows validate. Export comments summarize recovery and attribution;
the sidecar retains the complete warning and reconstruction record.

