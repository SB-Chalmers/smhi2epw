# smhi2epw tutorials

These numbered notebooks form a progressive, student-friendly course. Start
with `00_getting_started.ipynb` and continue in order. Every notebook states
its learning objectives, prerequisites, expected runtime, network use, and
outputs at the top.

Install and launch from the repository root:

```bash
python -m pip install -e ".[tutorials]"
jupyter lab examples/
```

| Notebook | Topic | Network |
| --- | --- | --- |
| `00_getting_started` | First Gothenburg AMY | SMHI; Open-Meteo if needed |
| `01_inspect_an_epw` | Headers, columns, units, plots | No, after 00 |
| `02_compare_locations` | Gothenburg, Stockholm, Malmö | SMHI; Open-Meteo if needed |
| `03_compare_years` | 2016, leap-year 2020, 2023 | SMHI; Open-Meteo if needed |
| `04_identify_heatwaves` | Swedish heat-wave definition | SMHI; Open-Meteo if needed |
| `05_compare_amy_to_tmy` | AMY versus Gothenburg TMYx | OneBuilding once |
| `06_data_quality_and_gap_filling` | 3/4/48/49-hour gaps | No |
| `07_solar_components` | GHI, DNI, DHI and closure | No |
| `08_batch_generation` | Reproducible batch workflows | SMHI; Open-Meteo if needed |
| `09_run_energyplus` | Standalone annual simulation and ideal loads | No; local EPW and EnergyPlus required |

Generated EPWs, figures, and tables are written to `examples/output/`, which
is ignored by Git. Live examples use `.smhi_cache` so reruns avoid unnecessary
SMHI and Open-Meteo traffic. Automatic recovery may contact Open-Meteo; inspect
source fractions, reconstruction warnings, and the JSON receipt before using
files in calibration or event analysis. Notebook 05 downloads its explicitly
linked OneBuilding TMYx archive on first execution, safely extracts only the EPW, and reuses the local
copy afterward. Set ``SMHI2EPW_TMY_PATH`` to use another lawfully obtained TMY
or to run the lesson without that download.

## Completion evidence and applications

Notebook 08 includes an offline reading of the
[5 October 2026 completeness summary](data/completeness_2026-10-05.json):
32/85 historical temporal-only jobs, 124/128 with the earlier opt-in donor
policy, and 128/128 with assessed donors plus ERA5. The first denominator differs;
the results are not a paired weather-only comparison. All 128 current outputs
were rechecked, and all used some reconstruction. The manifest records its
extent, source shares, warnings and receipt path for new runs.

Use 01 and 08 for simulation-input quality checks; 02 and 03 for geographic and
actual-year comparisons; 04 for event screening; 05 for AMY/TMY interpretation;
and 06/07 for isolated method demonstrations. Notebook 09 hands a local EPW to
EnergyPlus 24.2.0 build 94a887817b and plots the shared single-zone fixture's
temperature and ideal-load response. Set `ENERGYPLUS_EXE` when the engine is not
on `PATH`, `SMHI2EPW_EPW_PATH` for another local EPW, and
`SMHI2EPW_EXAMPLES_DIR` when running outside this checkout. Engine installation
is separate from the tutorial extra. See [the validation guide](../docs/energyplus.rst).

These lessons do not independently validate building-site accuracy or
reconstructed event peaks. They do not run a calibrated building model or supply
precipitation, snow or illuminance inputs.
