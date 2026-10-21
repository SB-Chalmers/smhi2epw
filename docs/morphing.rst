Batch AMYs and future climate scenarios
=======================================

Generate the Cartesian product of Swedish locations and completed source years,
then optionally morph every baseline to future SSP or RCP climates. Single-file
generation retains the existing CLI and API.

This is a development integration. The real-FWG checks exercise executable
compatibility and weather-file integrity; they do not establish climate accuracy
or constitute a package release.

Install and prerequisites
-------------------------

Install the optional wrapper from a checkout of this feature branch::

   python -m pip install -e ".[morphing]"

Morphing uses `pyfwg 0.4 <https://pyfwg.readthedocs.io/en/latest/>`_, Java on PATH,
and a separately obtained Future Weather Generator JAR. Download the correct
JAR using the links in the `pyfwg requirements
<https://github.com/dsanchez-garcia/pyfwg#requirements>`_. Neither Java nor the
JAR is bundled or automatically downloaded. Generating AMYs without morphing
does not require these extras.

The current official downloads are:

* `Global 5.2.0 JAR (SSP)
  <https://future-weather-generator.adai.pt/app_releases/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar>`_.
* `Europe 3.2.0 JAR (RCP)
  <https://future-weather-generator.adai.pt/app_releases/FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar>`_.

These links come from the `official download page
<https://future-weather-generator.adai.pt/download/>`_. The pyfwg GitHub
releases contain the Python wrapper; they do not distribute the FWG JARs.
The FWG download page identifies its license as CC BY-NC-SA 4.0. Keep the
authors' attribution and its noncommercial terms with any downloaded tools;
they are separate from smhi2epw's MIT software license.

Recreate the tested setup
-------------------------

Run these commands from this feature checkout's root. The development code
still uses package metadata version ``1.2.0``; that version alone does not
identify this feature. Record ``git rev-parse HEAD`` as well as the environment.

The tested setup uses Python **3.12.3**, pyfwg **0.4.0**, and Homebrew OpenJDK
**21.0.10** on macOS arm64. The FWG distributions are Global **5.2.0** and
Europe **3.2.0**. Both JARs report engine **1.1.0**; consult the real-FWG
verification record below for each downloaded binary's identity and test status.
These are explicit reproduction versions, not minimum-version claims.

Install `Python 3.12.3 <https://www.python.org/downloads/release/python-3123/>`_
and a Java 21 JDK separately, and put their executables on PATH. On macOS with
Homebrew, Java 21 can be installed using the `official formula
<https://formulae.brew.sh/formula/openjdk@21>`_::

   brew install openjdk@21
   export PATH="$(brew --prefix openjdk@21)/bin:$PATH"
   java -version

Homebrew installs its available Java 21 patch release, which can differ from
the tested 21.0.10. For exact Java patch reproduction or Windows/Linux setup,
use a vendor's matching JDK archive and `installation instructions
<https://adoptium.net/installation/>`_. Record the actual vendor and version;
other JDK builds have not been established by this snapshot.

Verify Python with ``python3.12 --version``, then create the environment::

   python3.12 -m venv .venv
   source .venv/bin/activate
   python -m pip install -c constraints/morphing-py312-2026-10-21.txt -e ".[morphing,test]"
   python -m pip check
   python -c "import smhi2epw, pyfwg; print(smhi2epw.__version__, pyfwg.__version__)"

On Windows, create the environment with ``py -3.12 -m venv .venv`` and use
``.venv\Scripts\Activate.ps1`` to activate it. Check that the selected Python
patch version matches the desired reproduction environment.

The :download:`dated dependency constraints
<../constraints/morphing-py312-2026-10-21.txt>` pin the runtime and pytest
dependency closure used here, including NumPy **2.5.4**, pandas **3.0.6**,
requests **2.34.2**, pvlib **0.16.1**, SciPy **1.18.1**, h5py **3.16.0**,
openpyxl **3.1.5**, and pytest **9.1.1**. This is a tested macOS/Python 3.12
snapshot, not a cross-platform or build-tool lock. Other operating systems may
need additional platform dependencies. The ordinary dependency ranges remain
in ``pyproject.toml``. Optional notebook and documentation tools are installed
separately with ``python -m pip install -e ".[tutorials,docs,dev]"``.

Download both JARs from the links above using a browser. They contain large
climate archives and can take substantial time. The website may return HTTP 403
to scripted downloads. Wait until each download has its final ``.jar`` filename;
an unfinished ``.crdownload`` file cannot be used. Create ``tools/`` and move
the completed downloads there with these names (remove browser suffixes such
as `` (1)``)::

   tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar
   tools/FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar

JARs and partial downloads are ignored by Git everywhere in the checkout and
explicitly excluded from source packages. Do not force-add them. Only setup
instructions, dependency constraints, and verification receipts belong in Git.
Verify the ignore rules and preview the supplied location/year/scenario plan::

   git check-ignore tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar
   git check-ignore tools/FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar
   smhi2epw batch examples/future_weather_plan.json --dry-run

The example resolves JARs from the repository's ``tools/``, uses
``.smhi_cache/``, and writes into the ignored ``examples/output/future-weather/``.
Its four AMYs and 32 future files can then be generated with::

   smhi2epw batch examples/future_weather_plan.json

Use a new output directory for another run. To repeat the real integration
checks with these local tools::

   export SMHI2EPW_GLOBAL_FWG_JAR="$PWD/tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar"
   export SMHI2EPW_EUROPE_FWG_JAR="$PWD/tools/FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar"
   python -m pytest -m fwg tests/test_batch_morphing.py

Keep the binaries' SHA-256 hashes and ``java -version`` output with a study.
The package's morphing receipts record JAR hashes automatically; the dated
verification record below provides the hashes used for the actual checks.

.. list-table:: Supported selections
   :header-rows: 1

   * - Family
     - Tool and major versions
     - Scenarios
     - Period labels
   * - ``ssp``
     - Global FWG 3, 4 or 5
     - ``ssp126``, ``ssp245``, ``ssp370``, ``ssp585``
     - ``2050``, ``2080``
   * - ``rcp``
     - Europe FWG 1, 2 or 3
     - ``rcp26``, ``rcp45``, ``rcp85``
     - ``2050``, ``2080``

Empty selections use all supported scenarios, periods or models. Models use
pyfwg's identifiers and are combined into an ensemble. This interface does not
produce separate files for individual models within one configuration.
With one selected model, current engines return that model's weather and pyfwg
disables ensemble generation; the receipt records that effective setting.
The JAR filename must contain its version, such as ``v5.2.0``; otherwise supply
``version="5"`` in Python/JSON or ``--fwg-version 5`` on the CLI. Current
engines also validate models and distribution family against the JAR metadata.

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
               "tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar",
               scenarios=("ssp245", "ssp585"),
               periods=(2050, 2080),
               models=("CanESM5", "MIROC6"),
           ),
           MorphConfig(
               "tools/FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar",
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
       MorphConfig("tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar",
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
       "fwg_jar_path": "tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar",
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
       --jar tools/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar \
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
current Global 5/Europe 3 engines receive scenario and period selections
directly. Legacy engines compute all scenarios before filtering saved outputs.

Current engines require month/day dates in the temporary ``DATA PERIODS``
header, so the adapter removes years from that staged header only. FWG may also
prefix generated filenames and label output rows with the future period year.
The adapter selects an unambiguous scenario/period product, verifies that its
month/day/hour sequence matches the source, then restores source year/minute
labels and calendar headers before publication. Missing or shifted intervals
fail validation. Receipts include the native filename and output hash before
calendar restoration. Current FWG applies its default SolarQC preprocessing;
future output differences can therefore include baseline solar corrections.

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
The :download:`current-engine download and verification record
<morphing-download-verification.json>` adds pyfwg 0.4 checks and four AMYs
generated using live provider data. Downloads were incomplete at those
snapshots; neither historical record establishes real FWG execution. The
:download:`real-FWG verification record <morphing-real-fwg-verification.json>`
records subsequent executable checks, live AMY morphing, and remaining limits.

Run ordinary offline checks with::

   pytest -m "not network and not energyplus and not fwg"

To execute the separate real-FWG gate, supply both real JAR paths::

   export SMHI2EPW_GLOBAL_FWG_JAR=/absolute/path/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar
   export SMHI2EPW_EUROPE_FWG_JAR=/absolute/path/FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar
   pytest -m fwg tests/test_batch_morphing.py

Selecting this gate without its prerequisites fails explicitly. It establishes
that real FWG produces valid weather for the supplied synthetic test baseline;
it does not validate climate projections against observations. The notebook
``10_future_weather`` independently checks the offline planning API.

FWG, pyfwg and provider datasets retain their own licenses and data terms.
This feature calls an installed pyfwg dependency and does not bundle their code,
JARs or climate datasets. smhi2epw's MIT license does not license weather data.
