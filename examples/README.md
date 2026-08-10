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
| `00_getting_started` | First Gothenburg AMY | SMHI |
| `01_inspect_an_epw` | Headers, columns, units, plots | No, after 00 |
| `02_compare_locations` | Gothenburg, Stockholm, Malmö | SMHI |
| `03_compare_years` | 2016, leap-year 2020, 2023 | SMHI |
| `04_identify_heatwaves` | Swedish heat-wave definition | SMHI |
| `05_compare_amy_to_tmy` | AMY versus Gothenburg TMYx | OneBuilding once |
| `06_data_quality_and_gap_filling` | 3/4/48/49-hour gaps | No |
| `07_solar_components` | GHI, DNI, DHI and closure | No |
| `08_batch_generation` | Reproducible batch workflows | SMHI |

Generated EPWs, figures, and tables are written to `examples/output/`, which
is ignored by Git. Live examples use `.smhi_cache` so reruns avoid unnecessary
SMHI traffic. Notebook 05 downloads its explicitly linked OneBuilding TMYx
archive on first execution, safely extracts only the EPW, and reuses the local
copy afterward. Set ``SMHI2EPW_TMY_PATH`` to use another lawfully obtained TMY
or to run the lesson without that download.
