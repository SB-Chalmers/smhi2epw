Python workflow
===============

Configuration
-------------

:class:`smhi2epw.EPWConfig` is intentionally explicit. Save the configuration
alongside simulation inputs so the weather file can be reproduced later.

.. code-block:: python

   from pathlib import Path
   from smhi2epw import EPWConfig, Smhi2EpwError, compile_epw

   output = Path("weather") / "gothenburg_2023.epw"
   output.parent.mkdir(exist_ok=True)

   config = EPWConfig(
       year=2023,
       output_path=str(output),
       city="Gothenburg",
       latitude=57.7156,
       longitude=11.9924,
       utc_offset=1,
   )

   try:
       result = compile_epw(config)
   except Smhi2EpwError as error:
       print(f"Compilation failed safely: {error}")
   else:
       print(result.report.linear_filled_hours)
       print(result.report.diurnal_filled_hours)
       print(result.report.warnings)

Interpreting diagnostics
------------------------

``weather_policy="automatic"`` is the default and enables assessed donor and
same-year ERA5 recovery. Use ``weather_policy="strict"`` to retain source and
data-gap failures; ``metobs_gap_fallback=True`` optionally enables assessed
donors in strict mode. Both donor-enabled policies interpolate short gaps
through three hours, try assessed donors for longer or unfillable short wind
gaps, then use bounded daily profiles through 48 hours. Strict has no ERA5 stage.
Automatic compilation writes ``OUTPUT.epw.json`` unless
``provenance_path`` selects another sidecar path.

``solar_source`` records the radiation path, including reanalysis recovery.
``max_gap_hours`` makes the largest detected gap visible, while the linear and
diurnal dictionaries show exactly how many hours each method reconstructed.
``energy_balance_max_residual`` checks that global radiation equals diffuse
plus projected direct radiation after physical caps.

``warnings`` contains structured recovery concerns. ``source_fractions`` maps
each variable to source shares. ``weather_classification`` is
``observation_based``, ``mixed_reconstructed`` or ``reanalysis_only``. The
classification includes reconstruction of required meteorology and solar GHI;
routine physical darkness zeros do not make a file mixed. Reanalysis-only
requires all required meteorology from ERA5 and solar GHI from ERA5 or physical
darkness. ``solar_source`` identifies the radiation path separately.
``reanalysis_filled_hours`` and ``reanalysis_metadata`` describe ERA5 recovery.
Cloud counts include only missing-cloud replacements at hours where ERA5 fills
required meteorology or GHI; usable existing clouds and all other hours are
preserved. ``source_fractions`` currently covers required meteorology and GHI,
excluding cloud cover. Inspect these together with donor assessments before
interpreting extremes or short time scales. The existing temporal interpolation
fraction alone does not measure all estimated weather. ``result.station`` and ``result.coordinate_distance_km`` are ``None``
when no primary station metadata could be resolved. See :doc:`weather_recovery`
for diagnostic definitions and sidecar-write warnings.

Expected failures inherit from :class:`smhi2epw.Smhi2EpwError`. Catching that
base class is appropriate at an application boundary; contributor code should
usually catch the more specific ingestion, data-gap, or validation subclass.
