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

Interpreting diagnostics
------------------------

``solar_source`` records which of the four radiation paths was used.
``max_gap_hours`` makes the largest detected gap visible, while the linear and
diurnal dictionaries show exactly how many hours each method reconstructed.
``energy_balance_max_residual`` checks that global radiation equals diffuse
plus projected direct radiation after physical caps.

Expected failures inherit from :class:`smhi2epw.Smhi2EpwError`. Catching that
base class is appropriate at an application boundary; contributor code should
usually catch the more specific ingestion, data-gap, or validation subclass.

