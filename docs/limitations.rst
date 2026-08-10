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
  inspected when extreme events or short time scales matter.
* Daylight saving is ignored. Every file uses a fixed Local Standard Time
  offset, as expected for EPW simulation calendars.
* Only whole-hour offsets are supported. Fractional-zone resampling is outside
  the current Nordic scope.
* Many secondary EPW fields are unavailable from the selected source APIs and
  therefore use specification-defined missing tokens.

An AMY is most useful for calibrating a model against the same historical
period. It is not a climate projection and should not be treated as a typical
or design-extreme year.

