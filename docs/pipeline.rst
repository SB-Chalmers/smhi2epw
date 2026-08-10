Pipeline and scientific methods
===============================

Data flow
---------

The compiler follows five explicit stages:

1. Validate configuration before network access.
2. Select full-year meteorological and optional radiation stations.
3. Retrieve MetObs observations and STRÅNG solar data onto an hourly UTC grid.
4. Fill bounded gaps, derive physical fields, and close the solar balance.
5. Shift to Local Standard Time, validate, and atomically write the EPW.

Gap reconstruction
------------------

Required meteorological gaps of one to three hours use endpoint interpolation.
Gaps of four to 48 hours use the previous and next complete 24-hour profiles.
Each profile is adjusted gradually to meet observations around the gap; when
both are valid their estimates receive equal weight. A single valid side is
accepted at boundaries. Longer required gaps, or gaps without a usable profile,
raise an error rather than create undocumented synthetic weather.

Wind direction is interpolated through sine and cosine components. This avoids
the false arithmetic midpoint of 180° between 359° and 1°. Solar gaps always
use day-aware profiles so linear interpolation cannot brighten the night.

Solar radiation
---------------

EPW radiation represents the preceding hour, so geometry is evaluated at the
interval midpoint. Depending on year and station availability, the pipeline
uses measured GHI with STRÅNG beam fractions, measured GHI with Erbs, all
STRÅNG components, or STRÅNG GHI with Erbs.

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

EPW time and output safety
--------------------------

The UTC source is mapped to a constant whole-hour Local Standard Time offset.
No broad forward/backward fill is used during this shift. Each target hour must
have an exact source observation. The destination is replaced only after eight
headers, all 35 fields, physical ranges, and all 8760/8784 rows validate.

