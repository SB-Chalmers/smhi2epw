# smhi2epw

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/SB-Chalmers/smhi2epw/actions/workflows/ci.yml) [![Releases](https://img.shields.io/badge/releases-GitHub-181717?logo=github&logoColor=white)](https://github.com/SB-Chalmers/smhi2epw/releases) [![Issues](https://img.shields.io/badge/issues-GitHub-181717?logo=github&logoColor=white)](https://github.com/SB-Chalmers/smhi2epw/issues)

Build complete-year EnergyPlus weather files (`.epw`) from Swedish observations.
The package combines SMHI weather and STRÅNG solar data, recovers gaps and writes
a JSON receipt describing the sources and processing used.

## Getting started

Use Python 3.11 or newer. From a terminal on macOS or Linux:

```sh
git clone https://github.com/SB-Chalmers/smhi2epw.git
cd smhi2epw
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
smhi2epw --help
```

Create a weather file for Gothenburg:

```sh
smhi2epw 2023 gothenburg.epw --station 71420 --city Gothenburg
```

Compilation needs internet access and can use nearby stations or same-year ERA5
through Open-Meteo. Inspect the generated receipt before using recovered weather.
For Windows setup, see the [installation guide](docs/installation.rst).

## Documentation

- [Quick start and Python API](docs/quickstart.rst)
- [Command-line options](docs/cli.rst)
- [Notebook examples](examples/README.md)
- [Methods and limitations](docs/limitations.rst)
- [Project guide and development](docs/guide.md)

## License

[MIT](LICENSE). Weather sources retain their attribution and access requirements;
see [data provenance](docs/provenance.rst), including Open-Meteo's public
noncommercial service conditions.
