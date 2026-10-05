Scientific and operational limitations
======================================

``smhi2epw`` creates an Actual Meteorological Year, not a measured value at the
exact building site for every field. The following limitations should be
reported alongside simulation studies:

* MetObs temperature, humidity, pressure, and wind come from a selected station;
  microclimate at the requested coordinates may differ.
* STRÅNG is a gridded model optimized for the Nordic region. Historical grid
  resolution and accuracy vary by era and location.
* Before 2018, complete direct-radiation parameters are unavailable, so direct
  and diffuse components are estimated from GHI with Erbs.
* Total cloud cover is used as an explicit proxy in longwave estimation; opaque
  cloud cover remains unknown.
* Gaps up to 48 hours may contain reconstructed values. Diagnostics must be
  inspected when extreme events or short time scales matter. Longer gaps and
  entirely missing variables can use assessed donors or same-year ERA5 under
  the default automatic policy; this does not extend temporal interpolation.
* Donor validation establishes agreement with the primary station during
  available overlap, not building-site accuracy during an outage. Reanalysis
  represents a model grid and may miss local microclimates and extreme intensity.
  Inspect source fractions, held-out errors and source-boundary warnings.
* Usable primary extremes are preserved. Reconstruction can change missing
  heatwave peaks, timing or duration; physical consistency and complete annual
  coverage do not guarantee event preservation.
* A single-year sensitivity experiment motivated trying assessed donors before
  bounded daily profiles. It does not establish universal donor accuracy or an
  acceptance threshold across locations, seasons and weather events.
* Optional ERA5 clouds fill missing values only at hours where ERA5 replaces
  required meteorology or GHI. Cloud recovery is counted separately and is not
  currently represented in required-variable/GHI source fractions.
* Hourly solar inputs outside 0--2,000 W/m² are discarded as broadly implausible.
  This engineering guard is separate from preserving plausible temperature
  extremes; it does not establish a validated local solar limit.
* Daylight saving is ignored. Every file uses a fixed Local Standard Time
  offset, as expected for EPW simulation calendars.
* Only whole-hour offsets are supported. Fractional-zone resampling is outside
  the current Nordic scope.
* Many secondary EPW fields are unavailable from the selected source APIs and
  therefore use specification-defined missing tokens.

An AMY is most useful for calibrating a model against the same historical
period. It is not a climate projection and should not be treated as a typical
or design-extreme year.

Automatic recovery still reports errors for invalid configuration, unknown
coordinates, unavailable data from all sources, incomplete future years,
unrecoverable physical values and filesystem failures. Use strict policy when
source completeness is an acceptance requirement rather than a recovery task.
Open-Meteo's public adapter requires noncommercial use within current provider
service limits; see :doc:`weather_recovery` for access and attribution details.
