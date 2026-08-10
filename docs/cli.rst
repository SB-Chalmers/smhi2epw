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
   Require measured GHI from a specific SMHI Sol station. Failure is fatal.

``--no-radiation``
   Disable automatic Sol-station discovery and use STRÅNG solar fields.

``--radiation-station-max-distance``
   Change the default 50 km automatic pyranometer radius.

The CLI returns zero on success, one for handled package failures, and two for
invalid command syntax. Error messages are written to standard error, making
the command suitable for scripts and CI jobs.

