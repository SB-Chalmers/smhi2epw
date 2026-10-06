# smhi2epw

Python utility that fetches meteorological data from the Swedish
Meteorological and Hydrological Institute (SMHI) open-data APIs and compiles it
into a valid EnergyPlus Weather (`.epw`) file for Actual Meteorological Year
(AMY) urban energy simulations.

It uses a **hybrid ingestion** approach:

- **MetObs** (`corrected-archive`) → station thermodynamics
  (temperature, humidity, pressure, wind).
- **STRÅNG** mesoscale model → grid-modeled solar irradiance
  (global / direct-horizontal / diffuse), queried at the requested coordinates.

Automatic recovery preserves usable observations, fills short gaps, assesses
nearby SMHI donors before using daily profiles, and fills unresolved required
hours with **same-year ERA5 via Open-Meteo**.
Warnings and a provenance sidecar describe the reconstruction. Use explicit
strict mode when incomplete source data should fail. Supported requests cover
completed calendar years from 1999 onward.

The source streams are synchronized on a continuous hourly **UTC** index, processed
(gap-filled, unit-converted, and augmented with derived dew point, cloud-aware
horizontal infrared, extraterrestrial radiation, and direct-normal irradiance),
shifted to **Local Standard Time**, and written out as a row-cardinality-validated
EPW file.

## Install

Install from a source checkout:

```bash
git clone https://github.com/SB-Chalmers/smhi2epw.git
cd smhi2epw
python -m pip install .
```

No release was available on PyPI when checked on 6 October 2026. The version in
this checkout is 1.1.0; confirm the checkout's commit when reproducing a study.

Python 3.11 or newer is required. Core dependencies are `numpy`, `pandas`,
`requests`, and `pvlib>=0.16.1,<0.17`. Installing the package also installs
pvlib's dependencies, including SciPy and h5py. Solar calculations work offline
once these dependencies are installed.

For the executable, student-friendly notebooks:

```bash
python -m pip install -e ".[tutorials]"
jupyter lab examples/
```

The notebooks are included in the checkout; tutorial extras install their
dependencies. Contributors can use
`python -m pip install -e ".[dev,docs,tutorials]"`. See the
[installation guide](docs/installation.rst) for virtual-environment and kernel
setup on Windows, macOS, and Linux.

## Usage

### Command line

```bash
# Explicit station id:
smhi2epw 2023 gothenburg_2023.epw --station 71420 --city Gothenburg --utc-offset 1

# Or auto-select the nearest qualifying station from coordinates:
smhi2epw 2023 gothenburg_2023.epw --lat 57.7156 --lon 11.9924 --city Gothenburg

# Force a fresh fetch, ignoring the on-disk cache:
smhi2epw 2023 gothenburg_2023.epw --station 71420 --refresh

# Retain source-coverage and gap failures:
smhi2epw 2023 gothenburg_2023.epw --station 71420 --weather-policy strict

# Change the 50 km automatic pyranometer limit:
smhi2epw 2023 gothenburg_2023.epw --station 71420 \
  --radiation-station-max-distance 25
```

The positional arguments are `year` and `output`. Provide either `--station`,
or both `--lat` and `--lon` (which also become the STRÅNG solar query point).

### Python API

```python
from smhi2epw import compile_epw
from smhi2epw.compiler import EPWConfig

result = compile_epw(
    EPWConfig(
        year=2023,
        output_path="gothenburg_2023.epw",
        station_id=71420,  # or omit and pass latitude/longitude instead
        city="Gothenburg",
        latitude=57.7156,  # nearest-station search + solar query point
        longitude=11.9924,
        utc_offset=1.0,  # Local Standard Time; DST ignored
        cache_dir=".smhi_cache",
        refresh=False,  # set True to bypass the cache
        weather_policy="automatic",  # default; strict disables ERA5 recovery
    )
)

print(result.rows, "rows,", f"{result.interpolated_fraction:.2%} interpolated")
if result.coordinate_distance_km is not None:
    print(f"{result.coordinate_distance_km:.1f} km from the primary station")
print("cloud data available:", result.report.cloud_available)
print(
    "max solar energy-balance residual:",
    result.report.energy_balance_max_residual,
    "W/m^2",
)
print("diurnally filled hours:", result.report.diurnal_filled_hours)
print("recovery warnings:", result.report.warnings)
# Automatic policy writes gothenburg_2023.epw.json by default.
```

### Reading and analysing EPW files

```python
from smhi2epw import read_epw

weather = read_epw("gothenburg_2023.epw")
print(weather[["dry_bulb", "ghi", "wind_speed"]].describe())
print(weather.attrs["location"])
```

`read_epw()` names all 35 fields, recognizes field-specific missing tokens, and
accepts both chronological AMYs and composite-year TMYs. The original eight
headers remain available in `weather.attrs["header"]`.

## Tutorials and documentation

The [numbered notebook curriculum](examples/README.md) starts with one minimal
weather file, then covers EPW inspection, location/year comparisons, heat-wave
detection, AMY-versus-TMY analysis, gap filling, solar components, and batch
generation. Network and external-data requirements are stated at the top of
every notebook.

### Build and view the documentation locally

From a source checkout, install the documentation and tutorial dependencies
into your active virtual environment:

```bash
python -m pip install -e ".[docs,tutorials]"
```

Build the complete Sphinx site, including the API reference and rendered
notebooks, with warnings treated as errors:

```bash
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

The generated home page is `docs/_build/html/index.html`. For the most reliable
navigation and search behavior, serve the directory over a local HTTP server:

```bash
python -m http.server 8000 --directory docs/_build/html
```

Then open [http://localhost:8000](http://localhost:8000) in a browser. Stop the
server with <kbd>Ctrl</kbd>+<kbd>C</kbd>. You can also open the HTML file directly
with `open docs/_build/html/index.html` on macOS, `xdg-open
docs/_build/html/index.html` on Linux, or `start docs\_build\html\index.html` in
Windows Command Prompt.

Notebook outputs are not executed during the documentation build, so building
the site does not contact SMHI, Open-Meteo or OneBuilding. The generated
`docs/_build/` tree is local-only and ignored by Git.

## Pipeline

| Layer | Responsibility |
| --- | --- |
| Ingestion | Concurrent primary-source retrieval, year-aware station metadata, quality filtering, request retries, buffered hourly UTC grid, local caching, same-year ERA5 fallback |
| Processing | Short interpolation, assessed donor transfer with optional median bias correction, bounded daily profiles, circular winds, source warnings and physical checks, pressure conversion, dew point and longwave derivation, closed solar components |
| Export | Exact UTC→LST constant shift, hour 1–24 formatting, standards-compliant headers and 35-field rows, strict range/calendar validation, atomic 8760/8784-row output, recovery comments and JSON provenance |

## Notes

- Required gaps of 1–3 hours use interpolation, circularly for wind direction.
  Longer gaps and unfillable short wind gaps first use assessed same-year
  donors. Remaining gaps up to 48 hours use previous/next valid daily profiles
  with endpoint correction and 50/50 mixing, then automatic mode uses ERA5.
  Strict mode permits donors only when explicitly enabled and has no ERA5
  fallback. Neither policy extends temporal filling beyond 48 hours.
  Solar recovery has no donor stage.
- Observations are filtered by MetObs quality flag; only accepted grades
  (`G`, `Y`) are used, others are treated as gaps.
- STRÅNG `-999` missing sentinels are removed and back-filled with a
  diurnal-aware (same-hour, day-to-day) interpolation that preserves the solar
  cycle.
- When total cloud cover (MetObs parameter 16) is available, it populates total
  sky cover and acts as a documented proxy only in the longwave IR calculation.
  Opaque sky cover remains missing because SMHI does not provide it. ERA5 can
  supply missing cloud cover only at hours where it replaces required
  meteorology or GHI; usable cloud values and other hours are preserved.
- Daylight Savings Time is intentionally ignored to keep solar angles
  continuous. A small UTC buffer is ingested around each year end so the LST
  shift uses real observations at the boundary.
- Raw payloads are cached on disk (`cache_dir`) so repeated compilations for the
  same station/year are idempotent and avoid redundant API load.
- STRÅNG parameter semantics are resolved against the live `strang1g` v1 API:
  `117` = global horizontal, `118` = direct *normal*, `121` = direct beam on
  the horizontal plane; diffuse horizontal is derived as `117 − 121`.
  Direct-horizontal parameter 121 starts on 18 April 2017; parameter 118
  (DNI) is requested throughout the supported history from 1999. Before
  parameter 121 is available, horizontal beam is projected from instantaneous
  DNI before adjacent-sample averaging. The continuous Erbs-Driesse form of
  the Erbs (1982) model is used only when usable direct components are absent;
  see the
  [SMHI extraction guide](https://strang.smhi.se/extraction/index.php).
- STRÅNG values are instantaneous irradiance at the full hour. The pipeline
  converts them to EPW interval-averaged irradiance (preceding-hour mean) by
  averaging adjacent samples. Supplied DNI and horizontal beam retain their
  separate interval means, including below five degrees solar elevation.
  The five-degree guard applies only when DNI must be inferred by dividing
  horizontal radiation by solar geometry. Interval closure is `GHI = DHI +
  horizontal beam`; mean DNI times a midpoint cosine is an approximation.
- Solar geometry uses pvlib's NREL SPA `nrel_numpy` method and geometric
  (unrefracted) zenith. `delta_t=None` lets pvlib calculate the terrestrial-time
  correction for each UTC year/month. Extraterrestrial irradiance uses pvlib's
  `asce` method with a 1367 W/m² solar constant. Five-minute integration over
  the preceding hour supplies interval geometry and caps. Both weather
  policies use these fixed solar methods.
- `result.report.solar_source` reports which solar path was used:
  `"strang"` (supplied STRÅNG DNI and supplied/projected horizontal beam),
  `"measured+strang_partition"` (nearby Sol station GHI with the STRÅNG partition),
  `"strang_ghi+erbs"` (Erbs-Driesse on STRÅNG GHI when direct components are absent),
  `"measured+erbs"` (Erbs-Driesse on measured GHI), `"era5"` (ERA5 solar fallback),
  or `"mixed"` (multiple solar sources). The `+erbs` labels retain their existing
  spelling as Erbs-family identifiers. New JSON sidecars include top-level
  `pvlib_version` alongside the package version and source hashes.
- Automatic pyranometer discovery is limited to 50 km by default. If its data
  cannot satisfy the 48-hour policy, compilation falls back to STRÅNG.
  Explicitly requested radiation stations fail in strict mode; automatic mode
  records the failure and continues solar recovery.
- Only whole-hour Local Standard Time offsets are supported. This covers the
  Nordic STRÅNG region without silently resampling hourly source data.
- A warning is logged when the solar query point is outside Sweden (~55–69.5°N,
  10–24.5°E), where STRÅNG accuracy degrades (RMSD up to 30–40% for GHI).

## Validation of the pvlib solar methods

On **6 October 2026**, the rebuilt wheel with pvlib 0.16.1 passed **261 offline
checks**, including notebook 07, and **7 required EnergyPlus tests**. Notebook 09
also completed all **8,760 hours with zero engine warnings**. The Python 3.11
minimum-dependency run passed 257 checks; four optional notebook tests were
skipped there and executed in the full wheel environment. Static checks and the
HTML documentation build passed, with 68 documentation doctests and no warnings.
Explicit timestamp keywords keep the declared pandas 1.5.3 floor working.

Six paired engineering cases used identical provider payloads, building models,
and the pinned EnergyPlus engine. Five cases had identical annual heating,
cooling and window-solar totals. For historical 2016 data, SPA changed the
horizontal beam projected from instantaneous DNI: annual heating changed by
**−0.1154%**, cooling by **−0.1385%**, and window solar by **−0.1235%**. GHI and DNI
were unchanged; the largest hourly DHI change was 4 Wh/m². Separate tests compare
classic Erbs and Erbs-Driesse at identical geometry, confirming a maximum
**0.000429 diffuse-fraction difference**, below the documented 0.0005 bound.

Warm annual geometry calls on this machine took about **17 ms** for zenith and
**224–226 ms** for preceding-hour integration, versus about 0.8 ms and 13 ms
previously. The existing five-minute integration is retained without caching.

The [portable validation summary](examples/data/pvlib_validation_2026-10-06.json)
records wheel/source/input identities, all six cases, and runtime measurements.
The rebuilt wheel generated byte-identical weather for the paired comparison;
its consumer checks were also run separately. These are numerical and consumer
regressions, not independent evidence of site-weather accuracy. GitHub-hosted CI,
including its Linux engine and Python matrix, remains required before release.


## Completeness-run results

The EPSM national measurement-year weather runs on **5 October 2026** covered
requested municipality/year jobs from **2017–2024**:

| Run | Weather policy / source commit | Completed | Failed |
| --- | --- | ---: | ---: |
| v1 | Historical bounded temporal filling; Git commit unrecorded | 32 / 85 | 53 |
| v2 | Opt-in raw nearby observations, `4861f9e`; no ERA5 | 124 / 128 | 4 |
| v3 | Automatic assessed donors + ERA5, `5930c07` | **128 / 128** | **0** |

Preparation expanded the job set from 85 to 128; v2 and v3 use the same job
manifest. V1/v2 figures are retained historical status counts; their EPWs are
no longer available locally. On 6 October, all 128 v3 files were independently
rechecked against recorded hashes, exact ordered calendars, 35-field rows,
finite required fields, export ranges and dew-point consistency. They contain
112 common-year and 16 leap-year files: **1,121,664 exported hours**.

Completeness includes reconstruction. All 128 v3 files are
`mixed_reconstructed`: 101 use donor meteorology, 35 use ERA5 meteorology, and
126 use temporal filling. These groups overlap. **25 / 128** reconstruct more
than 5% of required meteorological cells; the fraction ranges from 0.0114% to
100%. This statistic uses five meteorological variables on the buffered UTC
grid and excludes solar; exported-hour source shares are reported separately.
Five percent is a reporting aid, not a validated acceptance threshold. Review
source fractions and warnings before calibration or extreme-event analysis.
Successful export establishes complete weather inputs, not local weather accuracy.
The archived outputs predate the solar and actual-year header corrections and
the pvlib implementation. Their counts describe the recorded source revisions.
Regenerate inputs in a new directory to apply the current solar methods and
EnergyPlus acceptance checks.

The [portable evidence summary](examples/data/completeness_2026-10-05.json)
includes policies, source identities, artifact hashes, warning counts and
validation definitions. [Notebook 08](examples/08_batch_generation.ipynb)
reads it offline and records reconstruction diagnostics for new batches. The
[recovery guide](docs/weather_recovery.rst) explains the separate earlier
52-of-53 failed-job replay and the current run's limitations.

## Recorded pre-pvlib sensitivity check

A recorded check on **6 October 2026**, after the solar fixes (`050d195`) and
before the pvlib implementation, rebuilt references and two outage cases for
each selected weather-year. All **9 annual
EnergyPlus simulations** completed with zero warnings; paired models and
unmasked EPW rows were identical. One fixed, illustrative 100 m² ideal-load
building was used. Changes below are signed differences from its corrected
reference, not national uncertainty bounds or HVAC electricity.

| Weather-year | 168 h solar outage: annual sensible cooling change | 48 h meteorology outage at temperature maximum: cooling change | Temperature MAE in hidden hours |
| --- | ---: | ---: | ---: |
| Gothenburg 2016 | +0.900 kWh/m² (+4.06%) | +0.102% | 0.923 °C |
| Luleå 2023 | +0.618 kWh/m² (+3.04%) | +0.094% | 1.142 °C |
| Gothenburg 2024 | +1.259 kWh/m² (+6.79%) | −0.166% | 0.856 °C |

Nighttime zeros split the solar outages into daylight gaps filled by daily
profiles. Meteorology used assessed fixed donors, with circular temporal wind
recovery where a donor was rejected. None of these six outages selected ERA5;
its transport and recovery are covered separately by deterministic integration
tests. The reference solar partition still includes modelled STRÅNG radiation.
These results describe the selected weather, model and masks; they do not
independently validate DNI/DHI or establish a universal donor accuracy.

The [portable sensitivity summary](examples/data/solar_validation_2026-10-06.json)
contains assumptions, recovery decisions, source/model hashes and validation
checks. Notebook 08 reads its results offline alongside completeness evidence.
Both evidence JSON files and all reported numbers retain their recorded source
identities. They have not been regenerated with pvlib. The earlier frozen
campaign is also retained with its original source identity.

## Run the weather in EnergyPlus

[Notebook 09](examples/09_run_energyplus.ipynb) runs a generated AMY in a small,
standalone single-zone model and inspects temperatures, solar gains, ideal loads,
and engine diagnostics. It uses a local EPW and requires **EnergyPlus 24.2.0
build 94a887817b**; set `ENERGYPLUS_EXE` to its executable if it is outside `PATH`.
The engine is a separate optional installation, with official platform archives
at the [24.2.0 bug-fix release](https://github.com/NatLabRockies/EnergyPlus/releases/tag/v24.2.0a).
The notebook performs no provider requests and needs no EPSM package.

CI requires deterministic provider-to-EnergyPlus tests against the built wheel,
including common and leap-year calendars and recovery cases. Missing engines,
severe/fatal errors, unexpected warnings, and incomplete hourly outputs fail the
gate. Release tags validate the same wheel that is published after all required
checks succeed. Live provider checks run separately on the weekly schedule.
See the [EnergyPlus validation guide](docs/energyplus.rst) for the engine pin,
warning policy, distribution checks, and publication setup. Engine acceptance
establishes consumer compatibility, not local weather accuracy or calibration.

## Development

```bash
pip install -e ".[dev]"
pytest -m "not network and not energyplus"  # offline Python suite
pytest -m energyplus    # requires the pinned engine; provider requests are offline
pytest -m network    # live integration tests against weather-source endpoints
ruff check src tests examples
ruff format --check src tests examples
mypy src/smhi2epw
python -m build && twine check dist/*
pytest --doctest-modules src/smhi2epw
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Use `pytest -m "not network and not energyplus"` for the Python-only offline
suite. Plain `pytest` also selects live and engine integration tests; markers
do not skip them by themselves.
Provider access and quotas apply to live SMHI and Open-Meteo requests.

## License

MIT

### Target elevation and pressure correction

`EPWConfig.target_elevation_m` / `--target-elevation-m` sets the EPW site height;
omitting it uses station elevation. SMHI parameter 9 supplies sea-level QFF, so
the compiler now derives surface pressure using the inverse SMHI reduction.
`CompileResult` retains target coordinates, target elevation, the pressure method
and the original observation-station metadata separately. Rebuild weather files
when adopting this correction; see `docs/provenance.rst` for assumptions.


### Actual-year EPW calendar headers

Exports declare leap-day observation as `Yes` for Gregorian leap years (8784
hours) and `No` for common years (8760 hours). The data-period start weekday
matches January 1 of the measurement year. `write_epw` rejects contradictory
calendar headers before replacing an output file. Downstream workflows do not
need to patch headers after compilation. Previously exported or pinned study
files are not modified; regenerate in a fresh directory when migrating.


### Automatic recovery, warnings and provenance

`EPWConfig.weather_policy="automatic"` and CLI `--weather-policy automatic`
are the defaults. Preserve usable primary data, interpolate gaps up to three
hours, assess at most three nearby stations within 75 km for longer or unfillable
short wind gaps, then use bounded daily profiles through 48 hours. Same-year
ERA5 at the requested point recovers required hours still missing. Source failures
and recovery decisions are visible in `result.report.warnings` and the CLI summary.
Valid primary extreme temperatures are retained; physically impossible values are
recovered, and abrupt source transitions produce warnings. Hourly solar inputs
outside 0–2,000 W/m² are discarded as broadly implausible; this engineering guard
does not clip plausible heatwave temperatures. When ERA5 is used, overlap with
original observations is reported and substantial disagreement produces warnings
without rejecting otherwise usable primary extremes. Recovery cannot guarantee
an event's peak intensity or persistence. The sensitivity campaign covered
17 weather-years, six regions and six building profiles. Short-gap annual-load
errors were generally small, while long solar gaps and missing event peaks were
more sensitive. These are conditional comparisons against the campaign's own
reference weather: shared solar processing can hide a common error, and multiple
building profiles do not create independent weather samples. They establish
neither building-site accuracy nor universal donor superiority. See
[the method limitations](docs/limitations.rst).

Donors are checked against original same-variable overlap near each gap, using
held-out complete days. A scalar median offset is applied only when it improves
validation MAE by at least 10%; wind directions are assessed without rotation.
Insufficient overlap and excessive error reject a donor. These checks establish
agreement with a station during overlap, not building-site accuracy during the
outage. Model estimates may miss local microclimates and extreme intensity.

Automatic mode writes `OUTPUT.epw.json` beside the EPW. Set
`EPWConfig.provenance_path` or CLI `--provenance PATH.json` to choose its path.
The receipt records warnings, sources and recovery fractions, donor assessments,
reanalysis metadata, configuration, code identity, output checksum and hashes
of consumed responses. Cached and live payloads follow the same contract;
receipts are isolated for each compilation even when a client is reused.
`reanalysis_filled_hours` includes recovered cloud hours; `source_fractions`
currently describes required meteorology and GHI, excluding optional cloud cover.
Custom clients without scoped response receipts are marked incomplete. Paths
must differ and their parent directories must exist. Automatic mode returns the
valid EPW with a `provenance_write_failed` warning if a later sidecar-write
filesystem failure prevents saving its audit trail. Keep that warning visible.

Use `weather_policy="strict"` or `--weather-policy strict` for the earlier
failure behavior. The legacy `metobs_gap_fallback=True` / `--metobs-gap-fallback`
flag enables assessed donors in strict mode; automatic mode already uses them.
`gap_fallback_max_distance_km` and `gap_fallback_max_stations` limit donor search
in either policy. Strict mode writes a sidecar only when explicitly requested.

Automatic recovery still fails on invalid configuration, unknown coordinates,
unavailable weather from all sources, incomplete future-year data,
unrecoverable physical inconsistencies and filesystem errors. It never
substitutes another year or claims success without a complete valid calendar.
The Open-Meteo adapter uses the public noncommercial service; check
[current access limits](https://open-meteo.com/en/pricing) before batch or
commercial use, and acknowledge Open-Meteo and Copernicus Climate Change Service
ERA5. See the [Historical Weather API documentation](https://open-meteo.com/en/docs/historical-weather-api)
for source definitions.

See [the weather-recovery guide](docs/weather_recovery.rst) for assessment
thresholds, source units, diagnostic definitions, strict-mode examples,
historical replay evidence and limitations.
