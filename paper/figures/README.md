# Figures for the gap-filling sensitivity paper

Vector figures (PDF with embedded fonts, editable-text SVG) plus 600 dpi PNG
previews in `out/`. Scripts in `src/` regenerate them:

    pip install matplotlib numpy pandas shapely pyproj
    cd src && for f in fig_*.py; do python "$f"; done

| Figure | Script | Content |
| --- | --- | --- |
| A | `fig_a_recovery_ladder.py` | AMY assembly and missing-weather recovery ladder (docs/weather_recovery.rst) |
| B | `fig_b_map.py` | Strata, primary stations, fixed donors and measured-GHI stations per year |
| C | `fig_c_masking.py` | Synthetic outage design: seasonal random blocks and event-centred blocks |
| D | `fig_d_workflow.py` | Paired campaign workflow from reference AMY to compared metrics |

Colours are shared across figures: each recovery rung keeps the same colour
(`src/style.py`), so result plots can reuse `RUNG`.

## Data

- `data/campaign_sites.csv`: station identities per stratum and year, from the
  campaign table in epsm_workflows `archive/2026-10-14/docs/weather-imputation-campaign.md`.
- `data/smhi_metobs_stations_snapshot.csv`: SMHI MetObs station metadata
  (snapshot to April 2025, via a public GitHub copy of the SMHI station list,
  `jenslars/thesis-pvt-predictive-model`). City-to-primary distances computed
  from it reproduce the campaign table to 0.01 km. Replace with a fresh pull of
  `opendata-download-metobs.smhi.se` before submission if possible.
- `data/nordic_countries.geojson`, `data/nordic_lakes.geojson`: Natural Earth
  1:10m, public domain.
- `data/mask_example.json`: block positions from the campaign's own
  `campaign_design.generate_panels` on a fully observed Stockholm 2021 calendar
  (`src/make_mask_example.py /path/to/epsm_workflows`). Real positions can
  differ slightly because references may miss up to 1 % of cells.
