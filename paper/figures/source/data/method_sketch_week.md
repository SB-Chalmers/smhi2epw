# method_sketch_week.csv

Source data for the method sketch figure: hourly dry-bulb temperature (°C) for a 5-day window centred on one real hidden 48-hour gap from the v6 catalogue campaign.

- Station: Stockholm-Arlanda Flygplats (SMHI 97400), 2023.
- Case: meteorology, random seasonal, 48 h, seed 29, evidence `outage-89277dcc190cb875307e86ad`, spring (MAM) block.
- Gap: 2023-04-20 08:00 to 2023-04-22 07:00 UTC (09:00 20 April to 08:00 22 April local standard time, UTC+1), 48 hours.
- Window: 2023-04-18 19:00 to 2023-04-23 18:00 UTC, 120 hours.
- `time` is local standard time (UTC+1, as in the EPW); `time_utc` is UTC; `in_gap` is 1 inside the gap.

Columns:

- `measured`: the station's reference temperature, including the hidden hours (all original observations in this window).
- `linear`, `daily_patterns`, `four_week_average`, `stepwise`: the campaign methods `linear_only`, `temporal`, `diyepw_style` and `automatic`, values inside the gap only.
- `nearby_station`: Stockholm-Bromma Flygplats (SMHI 97200, 30 km) own raw temperature for the whole window, no offset.
- `era5`: ERA5 2 m temperature (Open-Meteo archive, grid point 59.75 N, 18.0 E) for the whole window.

For this gap the stepwise method used the nearby station: its check accepted it and the fitted offset was -0.9 °C, so `stepwise` = `nearby_station` - 0.9 throughout the gap (identical to the `donor_assessed` method).

How it was made: the fills were rerun with the campaign's own pinned code and sources (`weather-imputation-campaign-2026-11-v6-catalogue/runtime`, `weather.reconstruct`, with the panel's full four-block mask from `case-catalogue.json`). The rerun reproduces the campaign's recorded temperature MAE over all 192 hidden hours for every method (linear 4.391, stepwise 0.660, ERA5 0.910, four-week average 2.832; daily patterns 1.967 against 1.966 recorded, an EPW rounding difference). Values are rounded to 0.01 °C.
