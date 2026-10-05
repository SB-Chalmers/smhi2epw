Quick start
===========

The smallest useful compilation identifies a station, a completed year, and an
output path:

.. code-block:: python

   from smhi2epw import EPWConfig, compile_epw

   result = compile_epw(
       EPWConfig(
           year=2023,
           output_path="gothenburg_2023.epw",
           station_id=71420,
           city="Gothenburg",
       )
   )

   print(result.rows)
   print(result.report.solar_source)
   print(result.report.max_gap_hours)
   print(result.report.warnings)

This contacts MetObs and STRÅNG on the first run. With the default automatic
policy, missing required weather can also request nearby SMHI donors and
same-year ERA5 through Open-Meteo. The compiler writes an audit sidecar at
``gothenburg_2023.epw.json``. Responses are cached under
``.smhi_cache`` so subsequent runs do not repeatedly download the same raw
data. Delete the cache or pass ``refresh=True`` only when fresh source payloads
are genuinely needed.

Coordinates and stations
------------------------

For a building-specific solar point, provide coordinates even when selecting a
known station:

.. code-block:: python

   config = EPWConfig(
       year=2023,
       output_path="city_centre.epw",
       station_id=71420,
       city="Gothenburg",
       latitude=57.7089,
       longitude=11.9746,
   )

The station supplies primary temperature, humidity, sea-level pressure, and
wind. The requested coordinates control STRÅNG, ERA5 recovery, solar geometry,
and the EPW
``LOCATION`` header. Set ``target_elevation_m`` (CLI: ``--target-elevation-m``)
to use a common elevation for paired weather comparisons; otherwise the station
height is used. SMHI surface pressure is derived from sea-level QFF at that
height; ERA5 supplies surface pressure directly. If ``station_id`` is omitted,
automatic selection prefers full coverage but can use a partial station. When
station discovery is unavailable, automatic policy can proceed with reanalysis
at supplied coordinates. Use ``weather_policy="strict"`` to require the earlier
station-coverage and data-gap behavior. Review :doc:`weather_recovery` before
using a heavily reconstructed year.

Read the result
---------------

.. code-block:: python

   from smhi2epw import read_epw

   weather = read_epw("gothenburg_2023.epw")
   print(weather[["dry_bulb", "ghi", "wind_speed"]].describe())
   print(weather.attrs["location"])

The frame preserves EPW month, day, and hour fields. Hour 1 describes the
00:00--01:00 interval; hour 24 describes 23:00--24:00 in Local Standard Time.
