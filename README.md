# smhi2epw

[![CI](https://github.com/SB-Chalmers/smhi2epw/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SB-Chalmers/smhi2epw/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![MIT license](https://img.shields.io/github/license/SB-Chalmers/smhi2epw)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://sb-chalmers.github.io/smhi2epw/)

Build complete-year EnergyPlus weather files (`.epw`) from Swedish weather data.
`smhi2epw` combines SMHI station observations and STRÅNG solar data, fills gaps,
and can use nearby stations or same-year ERA5 when needed. Each automatic run
writes a JSON receipt describing its sources and recovery steps.

## Install

Python 3.11 or newer is required. Until the PyPI package is available, install
from the repository:

```bash
git clone https://github.com/SB-Chalmers/smhi2epw.git
cd smhi2epw
python -m pip install .
```

Creating a weather file needs internet access to SMHI and may use Open-Meteo for
ERA5 recovery. Reading an existing EPW works offline.

## Use

```bash
smhi2epw 2023 gothenburg.epw --station 71420 --city Gothenburg
```

Or use the Python API:

```python
from smhi2epw import EPWConfig, compile_epw

result = compile_epw(EPWConfig(
    year=2023,
    output_path="gothenburg.epw",
    station_id=71420,
    city="Gothenburg",
))
print(result.report.warnings)
```

Automatic recovery is the default. Use `--weather-policy strict` to stop when
required source data are missing. See the [quick start](docs/quickstart.rst) and [CLI guide](docs/cli.rst) for
options and the [method limitations](docs/limitations.rst) before using
reconstructed weather in calibration or event analysis.

## Docs and examples

The [online documentation](https://sb-chalmers.github.io/smhi2epw/) covers the API,
methods, and limitations. The [notebook course](examples/README.md) covers EPW
inspection, comparisons, heat waves, gap filling, solar components, batch runs,
and EnergyPlus. Start it with:

```bash
python -m pip install -e ".[tutorials]"
jupyter lab examples/
```

## Completeness evidence

The archived EPSM runs covered jobs from 2017–2024. Their recorded results were:

| Run | Recovery policy | Completed |
| --- | --- | ---: |
| v1 | Temporal filling | 32 / 85 |
| v2 | Opt-in station donors | 124 / 128 |
| v3 | Assessed donors and ERA5 | **128 / 128** |

All 128 v3 files were rechecked for calendar, row, field, range, and dew-point
validity. They all used some reconstruction; completeness does not establish
local weather accuracy. The archived results predate the pvlib solar refactor.
See the [run summary](examples/data/completeness_2026-10-05.json) and
[notebook 08](examples/08_batch_generation.ipynb) for details and limitations.

## Related SMHI packages

Thanks to the maintainers of [`smhi-open-data`](https://pypi.org/project/smhi-open-data/),
[`smhi-weather`](https://pypi.org/project/smhi-weather/),
[`smhi-pkg`](https://pypi.org/project/smhi-pkg/), and
[`ifk-smhi`](https://pypi.org/project/ifk-smhi/). These projects provide SMHI
API clients and forecast access; `smhi2epw` focuses on complete-year weather
files for EnergyPlus.

## Development

```bash
python -m pip install -e ".[dev,docs,tutorials]"
pytest -m "not network and not energyplus"
ruff check src tests examples docs
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

The [CI workflow](.github/workflows/ci.yml) also checks minimum dependencies,
installed wheels, notebooks, and required EnergyPlus cases. Live provider tests
run separately on the weekly schedule.

## License

[MIT](LICENSE)
