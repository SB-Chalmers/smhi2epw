Batch AMYs and future climate scenarios
=======================================

Generate the Cartesian product of Swedish locations and completed source years,
then optionally morph every baseline to future SSP or RCP climates. Single-file
generation retains the existing CLI and API.

This is a development integration. Real FWG climate execution remains a separate
required verification before treating the method as release-validated.

Install and prerequisites
-------------------------

Install the optional wrapper from a checkout of this feature branch::

   python -m pip install -e ".[morphing]"

Morphing uses `pyfwg 0.3 <https://pyfwg.readthedocs.io/en/latest/>`_, Java on PATH,
and a separately obtained Future Weather Generator JAR. Download the correct
JAR using the links in the `pyfwg requirements
<https://github.com/dsanchez-garcia/pyfwg#requirements>`_. Neither Java nor the
JAR is bundled or automatically downloaded. Generating AMYs without morphing
does not require these extras.

.. list-table:: Supported selections
   :header-rows: 1

   * - Family
     - Tool and major versions
     - Scenarios
     - Period labels
   * - ``ssp``
     - Global FWG 3 or 4
     - ``ssp126``, ``ssp245``, ``ssp370``, ``ssp585``
     - ``2050``, ``2080``
   * - ``rcp``
     - Europe FWG 1 or 2
     - ``rcp26``, ``rcp45``, ``rcp85``
     - ``2050``, ``2080``

Empty selections use all supported scenarios, periods or models. Models use
pyfwg's identifiers and are combined into an ensemble. This interface does not
produce separate files for individual models within one configuration.
The JAR filename must contain its version, such as ``v4.0.2``; otherwise supply
``version="4"`` in Python/JSON or ``--fwg-version 4`` on the CLI.

Python workflow
---------------

.. code-block:: python

   from smhi2epw import WeatherLocation, MorphConfig, compile_amy_batch

   result = compile_amy_batch(
       locations=[
           WeatherLocation("gothenburg", city="Gothenburg",
                           latitude=57.7089, longitude=11.9746),
           WeatherLocation("stockholm", city="Stockholm",
                           latitude=59.3293, longitude=18.0686),
       ],
       years=[2022, 2023],
       output_dir="weather-study",
       compiler_options={"cache_dir": ".smhi_cache"},
       morphing=[
           MorphConfig(
               "tools/FutureWeatherGenerator_v4.0.2.jar",
               scenarios=("ssp245", "ssp585"),
               periods=(2050, 2080),
               models=("CanESM5", "MIROC6"),
           ),
           MorphConfig(
               "tools/FutureWeatherGenerator_Europe_v2.0.2.jar",
               family="rcp", scenarios=("rcp45", "rcp85"),
               periods=(2050, 2080),
               models=("ICHEC_EC_EARTH_SMHI_RCA4",),
           ),
       ],
   )
   print(len(result.amy_results))    # 4 baselines
   print(len(result.morph_results))  # 32 future files
   print(result.manifest_path)

Omit ``morphing`` for AMYs only. ``plan_amy_batch`` accepts the same locations,
years, output directory and compiler options and returns validated EPWConfig
jobs without downloads or writes. Common compiler options use EPWConfig field
names; location, year, output and provenance settings belong to the planner.

Morph an existing AMY or TMY independently:

.. code-block:: python

   from smhi2epw import MorphConfig, morph_epw

   files = morph_epw(
       "gothenburg_2023.epw", "future-weather",
       MorphConfig("tools/FutureWeatherGenerator_v4.0.2.jar",
                   scenarios=("ssp245",), periods=(2050,)),
   )

CLI batch configuration
-----------------------

Save a JSON file such as ``study.json``:

.. code-block:: json

   {
     "locations": [
       {"name": "gothenburg", "latitude": 57.7089, "longitude": 11.9746},
       {"name": "stockholm", "latitude": 59.3293, "longitude": 18.0686}
     ],
     "years": [2022, 2023],
     "output_dir": "weather-study",
     "compiler_options": {"cache_dir": ".smhi_cache"},
     "morphing": [{
       "fwg_jar_path": "tools/FutureWeatherGenerator_v4.0.2.jar",
       "scenarios": ["ssp245", "ssp585"],
       "periods": [2050, 2080],
       "models": ["CanESM5", "MIROC6"]
     }]
   }

Preview and run::

   smhi2epw batch study.json --dry-run
   smhi2epw batch study.json

The checkout also includes ``examples/future_weather_plan.json`` with both
families: four baselines and 32 selected future files. Preview it with
``smhi2epw batch examples/future_weather_plan.json --dry-run`` and update its JAR
paths before execution.

The dry run checks local configuration and prints jobs and morphing settings.
It does not require pyfwg, Java, a JAR or provider access; model availability and
runtime prerequisites are checked when executing. Relative output, explicit
cache and JAR paths in JSON resolve against the configuration file's directory.
Python API paths resolve against the current working directory.

Existing-file CLI morphing::

   smhi2epw morph gothenburg_2023.epw --output-dir future-weather \
       --jar tools/FutureWeatherGenerator_v4.0.2.jar \
       --scenarios ssp245 ssp585 --periods 2050 2080 --models CanESM5 MIROC6

For RCP use ``--family rcp`` with the Europe JAR and RCM-pair identifiers.
``--log-level OFF`` disables package status logs.

Outputs and interpretation
--------------------------

Files retain both the observed source year and future climate period::

   weather-study/manifest.json
   weather-study/gothenburg/2023/gothenburg_2023.epw
   weather-study/gothenburg/2023/gothenburg_2023.epw.json
   weather-study/gothenburg/2023/future/ssp/gothenburg_2023_ssp245_2050.epw
   weather-study/gothenburg/2023/future/ssp/gothenburg_2023_ssp245_2050.epw.json

The manifest records progress and failures; completed baselines remain available
after a later failure. Existing outputs are rejected. Choose a new output root
for a rerun. There is at most one configuration per climate family in a batch.
Runs execute sequentially to avoid nested Java process oversubscription.

Each future-file receipt records the source and output hashes, source calendar
years, climate family, scenario, future period, ensemble models, pyfwg version,
JAR version/hash and source receipt link/hash. FWG STAT companions are retained
when present. Missing requested outputs and invalid EPWs fail the operation.
All selected EPWs are validated before publishing any selected file. The
external FWG computes all scenarios internally; selection filters saved outputs.

Morphing applies climate changes to the source year's weather sequence.
``2050`` and ``2080`` are climate period labels, not predictions of hourly
weather in those individual years. The source calendar is not rewritten.
An unusually hot AMY can therefore remain an unusually hot morphed baseline.
Review the source year against FWG's reference climate period before interpreting
absolute future conditions: this wrapper does not rebase climate deltas to each
AMY year. Baseline gap filling and reanalysis limitations still apply.

Urban heat island modification is explicitly disabled. Other physical settings
use pyfwg defaults, with ensemble creation enabled. Output validation checks
file structure and physical ranges; it does not establish climate accuracy.

Development scope and verification
-----------------------------------

Owner: ``smhi2epw`` owns explicit weather acquisition, local batch generation,
EPW validation and the new pyfwg adapter requested for this feature. This extends
the previously historical-only weather methods; it does not introduce study
scheduling, checkpoint/resume, building simulation or study retention policy.
Those remain with their existing EPSM owners.

Inputs and outputs: named locations, completed historical years and explicit
climate settings produce baseline EPWs, selected future EPWs and JSON receipts.
The batch manifest is a weather-generation inventory, not a general Study or
Workflow implementation. Java climate calculations are delegated to FWG through
pyfwg's public API. The original weather and source receipts are preserved.

Acceptance scenarios cover multiple locations/years, both climate families,
selection, invalid settings, missing dependencies, missing/malformed generated
files, collision-safe publication and retained batch failures. The offline
adapter check runs real pyfwg with a simulated Java boundary. It verifies the
Python integration and timestamp staging; it does not verify FWG calculations.
The :download:`dated verification record <morphing-verification.json>` records
the tested environment, artifact identities and outstanding integration check.

Run ordinary offline checks with::

   pytest -m "not network and not energyplus and not fwg"

To execute the separate real-FWG gate, supply both real JAR paths::

   export SMHI2EPW_GLOBAL_FWG_JAR=/absolute/path/FutureWeatherGenerator_v4.0.2.jar
   export SMHI2EPW_EUROPE_FWG_JAR=/absolute/path/FutureWeatherGenerator_Europe_v2.0.2.jar
   pytest -m fwg tests/test_batch_morphing.py

Selecting this gate without its prerequisites fails explicitly. It establishes
that real FWG produces valid weather for the supplied synthetic test baseline;
it does not validate climate projections against observations. The notebook
``10_future_weather`` independently checks the offline planning API.

FWG, pyfwg and provider datasets retain their own licenses and data terms.
This feature calls an installed pyfwg dependency and does not bundle their code,
JARs or climate datasets. smhi2epw's MIT license does not license weather data.
