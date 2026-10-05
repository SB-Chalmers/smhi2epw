# smhi2epw

Lightweight Python utility that fetches meteorological data from the Swedish
Meteorological and Hydrological Institute (SMHI) open-data APIs and compiles it
into a valid EnergyPlus Weather (`.epw`) file for Actual Meteorological Year
(AMY) urban energy simulations.

It uses a **hybrid ingestion** approach:

- **MetObs** (`corrected-archive`) → station thermodynamics
  (temperature, humidity, pressure, wind).
- **STRÅNG** mesoscale model → grid-modeled solar irradiance
  (global / direct-horizontal / diffuse), queried at the requested coordinates.

The two streams are synchronized on a continuous hourly **UTC** index, processed
(gap-filled, unit-converted, and augmented with derived dew point, cloud-aware
horizontal infrared, extraterrestrial radiation, and direct-normal irradiance),
shifted to **Local Standard Time**, and written out as a row-cardinality-validated
EPW file.

## Install

```bash
python -m pip install smhi2epw
```

Dependencies are limited to `numpy`, `pandas`, and `requests`.
Python 3.11 or newer is required.

For the executable, student-friendly notebooks:

```bash
python -m pip install "smhi2epw[tutorials]"
jupyter lab
```

Contributors working from a checkout can use
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
    )
)

print(
    result.rows,
    "rows,",
    f"{result.interpolated_fraction:.2%} interpolated,",
    f"{result.coordinate_distance_km:.1f} km",
)
print("observed cloud data available:", result.report.cloud_available)
print(
    "max solar energy-balance residual:",
    result.report.energy_balance_max_residual,
    "W/m^2",
)
print("diurnally filled hours:", result.report.diurnal_filled_hours)
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
the site does not contact SMHI or OneBuilding. The generated `docs/_build/`
tree is local-only and ignored by Git.

## Pipeline

| Layer | Responsibility |
| --- | --- |
| Ingestion | Multi-threaded dual-endpoint query manager, station mapping (year-aware position), nearest-station resolver, quality-flag filtering, HTTP retry/backoff, boundary-buffer UTC grid, local caching with optional TTL/refresh |
| Processing | Linear filling for 1–3 h gaps; endpoint-adjusted previous/next-day profiles for 4–48 h gaps; circular wind interpolation; bounded solar filling; unit conversion; dew point; EnergyPlus-compatible horizontal IR; interval-midpoint solar geometry; physically closed DNI/DHI |
| Export | Exact UTC→LST constant shift, hour 1–24 formatting, standards-compliant headers and 35-field rows, strict range/cardinality validation, atomic 8760/8784-row output |

## Notes

- Required gaps of 1–3 hours are interpolated. Gaps of 4–48 hours use the
  previous/next valid daily profile with endpoint correction and 50/50 mixing.
  Longer required gaps raise `DataGapError`; optional fields degrade to EPW
  missing tokens instead of being synthesized beyond 48 hours.
- Observations are filtered by MetObs quality flag; only accepted grades
  (`G`, `Y`) are used, others are treated as gaps.
- STRÅNG `-999` missing sentinels are removed and back-filled with a
  diurnal-aware (same-hour, day-to-day) interpolation that preserves the solar
  cycle.
- When total cloud cover (MetObs parameter 16) is available, it populates total
  sky cover and acts as a documented proxy only in the longwave IR calculation.
  Opaque sky cover remains missing because SMHI does not provide it.
- Daylight Savings Time is intentionally ignored to keep solar angles
  continuous. A small UTC buffer is ingested around each year end so the LST
  shift uses real observations at the boundary.
- Raw payloads are cached on disk (`cache_dir`) so repeated compilations for the
  same station/year are idempotent and avoid redundant API load.
- STRÅNG parameter semantics are resolved against the live `strang1g` v1 API:
  `117` = global horizontal, `118` = direct *normal*, `121` = direct beam on
  the horizontal plane; diffuse horizontal is derived as `117 − 121`.
  Params 118 and 121 are only available from April 2017. Because 2017 is not a
  complete direct-radiation year, full-year 2017 and earlier AMYs use Erbs
  (1982) decomposition on GHI; STRÅNG direct fields are used from 2018.
- STRÅNG values are instantaneous irradiance at the full hour. The pipeline
  converts them to EPW interval-averaged irradiance (preceding-hour mean) by
  averaging adjacent samples, reducing hourly RMSD by ~5 pp (Lundström 2012).
- `result.report.solar_source` reports which solar path was used:
  `"strang"` (2018+, STRÅNG all params),
  `"measured+strang_partition"` (2018+ with a nearby Sol station; measured GHI
  with the normalized STRÅNG beam fraction),
  `"strang_ghi+erbs"` (through 2017, Erbs on STRÅNG GHI),
  `"measured+erbs"` (through 2017 with a Sol pyranometer station).
- Automatic pyranometer discovery is limited to 50 km by default. If its data
  cannot satisfy the 48-hour policy, compilation falls back to STRÅNG.
  Explicitly requested radiation stations fail instead of falling back.
- Only whole-hour Local Standard Time offsets are supported. This covers the
  Nordic STRÅNG region without silently resampling hourly source data.
- A warning is logged when the solar query point is outside Sweden (~55–69.5°N,
  10–24.5°E), where STRÅNG accuracy degrades (RMSD up to 30–40% for GHI).

## Development

```bash
pip install -e ".[dev]"
pytest               # offline suite (synthetic SMHI client)
pytest -m network    # live integration tests against the SMHI endpoints
ruff check src tests examples
ruff format --check src tests examples
mypy src/smhi2epw
python -m build && twine check dist/*
pytest --doctest-modules src/smhi2epw
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

The default test suite runs fully offline using a synthetic SMHI client;
network-marked tests are skipped unless explicitly requested.

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


### Reproducible reconstruction provenance

Pass `--provenance PATH.json` to the CLI, or set `EPWConfig.provenance_path`, to write an atomic provenance sidecar after a successful EPW compilation. It records reconstruction configuration, package/source identity, output checksum and hashes of the actual consumed response text. Cached responses and live responses follow the same receipt contract; unrelated cache files are excluded. The output and provenance paths must differ. A custom client without response receipts is explicitly marked incomplete. This records weather reconstruction evidence without collecting additional building observations.

### Recovering missing meteorological observations

Short scalar gaps (up to 3 hours) use linear interpolation; gaps up to 48 hours
use the nearest complete daily reference within seven days. Reconstructed
humidity, wind speed and cloud cover are bounded without clipping observed values.

Opt in with `EPWConfig(metobs_gap_fallback=True)` or `--metobs-gap-fallback`.
Unfillable gaps can then use quality-filtered observations for the **same hours**
from at most three nearby stations within 75 km of the requested location.
Use `gap_fallback_max_distance_km` and `gap_fallback_max_stations` to adjust these
explicit limits. Invalid primary meteorological observations are treated as gaps
and counted. Solar data remains at the requested location. Unrecoverable gaps
still fail; the 48-hour temporal interpolation ceiling is unchanged.

The processing report records original missing/invalid hours, donor station
positions and distances, replaced UTC intervals, and overlap differences against
valid primary observations. `required_reconstructed_fraction` counts reconstructed
cells across the five required meteorological variables; the existing
`interpolated_fraction` describes subsequent temporal filling. These diagnostics
must be reviewed before using heavily reconstructed weather for qualification.
Pass `provenance_path` (CLI `--provenance`) to retain raw-response and code hashes.
Nearby observations do not guarantee identical site weather, especially for wind
and elevation-sensitive temperature; overlap diagnostics are evidence, not a
correction or accuracy guarantee. EPSM workflows opt into this policy explicitly.

See [the detailed weather-recovery guide](docs/weather_recovery.rst) for policy,
API/CLI examples, diagnostic definitions, replay evidence and limitations.
