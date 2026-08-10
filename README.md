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
pip install -e .
```

Dependencies are limited to `numpy`, `pandas`, and `requests`.
Python 3.11 or newer is required.

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
```

The default test suite runs fully offline using a synthetic SMHI client;
network-marked tests are skipped unless explicitly requested.

## License

MIT
