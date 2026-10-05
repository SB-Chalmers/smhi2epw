Command-line interface
======================

The CLI and Python API execute the same compiler. Use the CLI for a single file
or shell automation, and the Python API when you need diagnostics and analysis.

Explicit station::

   smhi2epw 2023 gothenburg_2023.epw \
       --station 71420 --city Gothenburg --utc-offset 1

Automatic station selection::

   smhi2epw 2023 stockholm_2023.epw \
       --lat 59.3293 --lon 18.0686 --city Stockholm

Useful controls
---------------

``--refresh``
   Ignore cached responses for this run.

``--cache-dir``
   Choose a cache directory. An empty string disables caching.

``--radiation-station``
   Prefer measured GHI from a specific SMHI Sol station. Automatic policy
   records failures and recovers solar weather; strict policy requires it.

``--no-radiation``
   Disable automatic Sol-station discovery. STRÅNG remains the primary solar
   source and automatic policy can recover missing solar hours from ERA5.

``--radiation-station-max-distance``
   Change the default 50 km automatic pyranometer radius.

``--weather-policy automatic|strict``
   Automatic is the default. Preserve usable primary data, interpolate up to
   three hours, assess same-year donors for longer or unfillable short wind
   gaps, apply bounded daily profiles through 48 hours, then recover unresolved
   required hours from same-year ERA5. Strict has no ERA5 fallback.

``--metobs-gap-fallback``
   Permit assessed nearby meteorological donors in strict mode. Automatic
   policy already enables donor recovery. Donor-enabled strict mode uses the
   same donor-before-daily-profile precedence but does not enable reanalysis.

``--gap-fallback-max-distance-km`` and ``--gap-fallback-max-stations``
   Limit donor search to 75 km and three candidates by default.

``--provenance PATH.json``
   Choose the audit sidecar path. Automatic policy writes ``OUTPUT.epw.json``
   by default; strict policy writes a sidecar only when a path is supplied.

For example, to require the earlier failure behavior::

   smhi2epw 2023 stockholm_2023.epw --lat 59.3293 --lon 18.0686 \
       --weather-policy strict

Successful automatic compilations print a recovery summary and warnings.
Keep the sidecar with the EPW, especially when studying extremes or comparing
simulations. A complete file may include model estimates rather than local
observations; see :doc:`weather_recovery` for interpretation and source access
requirements.

The CLI returns zero on success, one for handled package failures, and two for
invalid command syntax. Error messages are written to standard error, making
the command suitable for scripts and CI jobs.
