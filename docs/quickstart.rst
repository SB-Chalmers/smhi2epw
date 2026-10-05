Quick start
===========

The smallest useful compilation identifies a full-year station, a year, and an
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

This contacts MetObs and STRÅNG on the first run. Responses are cached under
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

The station supplies temperature, humidity, sea-level pressure, and wind.
The requested coordinates control STRÅNG, solar geometry, and the EPW
``LOCATION`` header. Set ``target_elevation_m`` (CLI: ``--target-elevation-m``)
to use a common elevation for paired weather comparisons; otherwise the station
height is used. Surface pressure is derived from sea-level QFF at that height. If ``station_id`` is omitted, the same coordinates
also select the nearest station covering every required parameter for the full
year.

Read the result
---------------

.. code-block:: python

   from smhi2epw import read_epw

   weather = read_epw("gothenburg_2023.epw")
   print(weather[["dry_bulb", "ghi", "wind_speed"]].describe())
   print(weather.attrs["location"])

The frame preserves EPW month, day, and hour fields. Hour 1 describes the
00:00--01:00 interval; hour 24 describes 23:00--24:00 in Local Standard Time.

