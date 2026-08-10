# smhi2epw

Lightweight Python utility that fetches meteorological data from the Swedish
Meteorological and Hydrological Institute (SMHI) open-data APIs and compiles it
into a valid EnergyPlus Weather (`.epw`) file for Actual Meteorological Year
(AMY) urban energy simulations.

It uses a **hybrid ingestion** approach:

- **MetObs** (`corrected-archive`) → station thermodynamics
  (temperature, humidity, pressure, wind).
- **STRÅNG** mesoscale model → grid-modeled solar irradiance
  (global / direct-horizontal / diffuse), queried by station coordinates.

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

## Usage

### Command line

```bash
# Explicit station id:
smhi2epw 2023 gothenburg_2023.epw --station 71420 --city Gothenburg --utc-offset 1

# Or auto-select the nearest qualifying station from coordinates:
smhi2epw 2023 gothenburg_2023.epw --lat 57.7156 --lon 11.9924 --city Gothenburg

# Force a fresh fetch, ignoring the on-disk cache:
smhi2epw 2023 gothenburg_2023.epw --station 71420 --refresh
```

The positional arguments are `year` and `output`. Provide either `--station`,
or both `--lat` and `--lon` (which also become the STRÅNG solar query point).

### Python API

```python
from smhi2epw import compile_epw
from smhi2epw.compiler import EPWConfig

result = compile_epw(EPWConfig(
    year=2023,
    output_path="gothenburg_2023.epw",
    station_id=71420,      # or omit and pass latitude/longitude instead
    city="Gothenburg",
    latitude=57.7156,      # nearest-station search + solar query point
    longitude=11.9924,
    utc_offset=1.0,        # Local Standard Time; DST ignored
    cache_dir=".smhi_cache",
    refresh=False,         # set True to bypass the cache
))

print(result.rows, "rows,",
      f"{result.interpolated_fraction:.2%} interpolated,",
      f"{result.coordinate_distance_km:.1f} km")
print("cloud data available:", result.report.cloud_available)
print("max solar energy-balance residual:",
      result.report.energy_balance_max_residual, "W/m^2")
```


## Pipeline

| Layer | Responsibility |
| --- | --- |
| Ingestion | Multi-threaded dual-endpoint query manager, station mapping (year-aware position), nearest-station resolver, quality-flag filtering, HTTP retry/backoff, boundary-buffer UTC grid, local caching with optional TTL/refresh |
| Processing | Required/optional imputation policy (≤ 3 h window for required fields, soft for optional), diurnal-aware solar gap filling, STRÅNG `-999` sentinel cleaning, unit conversion, dew point, cloud-aware Berdahl & Martin horizontal IR, extraterrestrial horizontal/direct-normal radiation, direct-normal from STRÅNG with a 5° solar-elevation floor, diffuse closed as `GHI − beam_horizontal` |
| Export | UTC→LST constant shift, hour 1–24 formatting, EPW field layout (incl. extraterrestrial and sky-cover columns), streaming writer, 8760/8784 row validation |

## Notes

- Gaps longer than 3 hours in **required** fields raise `DataGapError` rather
  than emitting a corrupted file. Optional fields (e.g. cloud cover) degrade
  gracefully to the EPW missing token.
- Observations are filtered by MetObs quality flag; only accepted grades
  (`G`, `Y`) are used, others are treated as gaps.
- STRÅNG `-999` missing sentinels are removed and back-filled with a
  diurnal-aware (same-hour, day-to-day) interpolation that preserves the solar
  cycle.
- When total cloud cover (MetObs parameter 16) is available, it populates the
  EPW sky-cover columns (octas → tenths) and adds the cloud-amplification term
  to the down-welling longwave (IR) model.
- Daylight Savings Time is intentionally ignored to keep solar angles
  continuous. A small UTC buffer is ingested around each year end so the LST
  shift uses real observations at the boundary.
- Raw payloads are cached on disk (`cache_dir`) so repeated compilations for the
  same station/year are idempotent and avoid redundant API load.
- STRÅNG parameter semantics are resolved against the live `strang1g` v1 API:
  `117` = global horizontal, `118` = direct *normal*, `121` = direct beam on
  the horizontal plane; diffuse horizontal is derived as `117 − 121`.
  Params 118 and 121 are only available from April 2017; for earlier years
  DNI and DHI are estimated via Erbs (1982) decomposition on GHI only.
- STRÅNG values are instantaneous irradiance at the full hour. The pipeline
  converts them to EPW interval-averaged irradiance (preceding-hour mean) by
  averaging adjacent samples, reducing hourly RMSD by ~5 pp (Lundström 2012).
- `result.report.solar_source` reports which solar path was used:
  `"strang"` (post-2017, STRÅNG all params),
  `"measured+strang_beam"` (post-2017 with Sol pyranometer station),
  `"strang_ghi+erbs"` (pre-2017, Erbs on STRÅNG GHI),
  `"measured+erbs"` (pre-2017 with Sol pyranometer station).
- A warning is logged when the solar query point is outside Sweden (~55–69.5°N,
  10–24.5°E), where STRÅNG accuracy degrades (RMSD up to 30–40% for GHI).

## Development

```bash
pip install -e ".[dev]"
pytest               # offline suite (synthetic SMHI client)
pytest -m network    # live integration tests against the SMHI endpoints
```

The default test suite runs fully offline using a synthetic SMHI client;
network-marked tests are skipped unless explicitly requested.

## License

MIT
