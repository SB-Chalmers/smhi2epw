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
17-weather-year sensitivity campaign supports small annual-load errors for
short gaps under its tested conditions; it does not establish universal accuracy
or preservation of missing peaks.

Solar radiation
---------------

EPW radiation represents the preceding hour. Instantaneous STRÅNG samples
are averaged in adjacent pairs. GHI and DNI are requested from 1999 onward;
direct-horizontal data is requested from its 18 April 2017 availability date.
Earlier horizontal beam is projected from instantaneous DNI before averaging.
ERA5 radiation already describes the preceding-hour mean and is not averaged
again. Measured GHI, when available, scales the model DNI and horizontal beam
together; missing usable DNI uses the continuous Erbs-Driesse decomposition.

The interval balance is

.. math::

   \overline{GHI} = \overline{DHI} + \overline{DNI\cos(\theta_z)}

Supplied hourly DNI and horizontal beam retain their own means. Their
instantaneous product identity cannot be imposed using one midpoint cosine;
within-hour changes affect the projection. The reported closure residual uses
GHI minus DHI and horizontal beam.

Supplied DNI remains usable below five degrees solar elevation. That floor
applies only to an inferred horizontal-to-normal division. Geometry and
extraterrestrial caps are integrated at five-minute spacing, so a partially
sunlit interval is retained even when its midpoint is dark. Fully dark intervals
have zero solar radiation. Physical caps scale DNI and horizontal beam together,
then DHI closes the horizontal balance.

Solar position uses pvlib's NREL SPA implementation with
``method="nrel_numpy"`` and geometric (unrefracted) ``zenith``.
``delta_t=None`` lets pvlib calculate the terrestrial-time correction from
each UTC timestamp's year and month, including leap years and year-boundary
buffers. Extraterrestrial irradiance uses ``get_extra_radiation`` with
``method="asce"`` and ``solar_constant=1367`` W/m². Both strict and automatic
weather policies use these fixed methods.

The GHI-only fallback uses ``pvlib.irradiance.erbs_driesse`` with the interval
geometry and extraterrestrial inputs. It retains the approximately five-degree
inferred-DNI guard and assigns the remaining horizontal balance to DHI.
The report's existing ``strang_ghi+erbs`` and ``measured+erbs`` values remain
Erbs-family labels. Solar consistency establishes a closed component group,
not an independent validation of the supplied radiation or inferred partition.

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
8760/8784 rows validate. DATA PERIODS start/end dates include the actual year
for EnergyPlus actual-weather RunPeriods. Export comments summarize recovery and attribution;
the sidecar retains the complete warning and reconstruction record.
