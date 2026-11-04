# Campaign result tables

Gap-filling sensitivity results: 17 Swedish region-years (6 regions; 2018, 2021, 2023;
Kiruna 2018 has no eligible reference), 6 catalogue building profiles, EnergyPlus 24.2
ideal loads. 15,390 unique simulations, 34,236 labelled building rows; no severe or fatal
errors. Errors are against the same building simulated with the reference weather.

All tables come from the corrected campaign run. Its temperature, humidity, pressure and wind results are identical to the first run. Solar gaps now hide diffuse irradiance (DHI) together with GHI and DNI, as the first run did not. smhi2epw includes the fix that sends solar outages over 48 h to ERA5 (smhi2epw commit 23279a7). The linear-only and diyepw-style solar fills are bounded by extraterrestrial horizontal irradiance.

## annual-errors.csv

Absolute change in annual sensible heating/cooling demand caused by gap filling, against the same building on the reference weather.

- `scope`: meteorology = temperature, humidity, pressure and wind hidden; solar = GHI/DNI/DHI hidden
- `sampling`: random_seasonal = one block in each season (4 per file); weather_extremes = one block at a weather event
- `method`: gap-filling method
- `gap_hours / gap_length`: length of each hidden block
- `building_rows / gap_files / region_years`: cases behind each statistic
- `*_abs_median_kwh_m2, *_abs_p95_kwh_m2`: median and 95th percentile of |error|, kWh per m2 floor area per year
- `*_abs_median_pct, *_abs_p95_pct`: same as % of the building's reference annual demand (cases with demand below 1 kWh/m2 excluded)

## peak-errors.csv

Annual peak load when the reference annual peak hour lies inside a hidden block (hourly mean peaks).

- `*_peak_hidden_share`: share of building rows whose reference annual peak hour is hidden
- `*_exposed_rows`: building rows with the reference peak hidden (denominator for the columns below)
- `*_peak_abs_err_median_w_m2, *_p95`: |annual peak - reference annual peak|, W per m2 floor area
- `*_peak_hour_kept_share`: share where the set of annual peak hours is unchanged
- `*_peak_moved_over_24h_share`: share where the nearest new peak hour is more than 24 h from the reference peak

## event-preservation-3day.csv

Weather events hidden by a gap: kept, moved/split or lost after filling. Study rules: heatwave = 3+ days with daily max >= 25 C; cold spell = 3+ days with daily min <= -10 C; warm/relative cold spells = 3+ days beyond the reference's May-Sep 95th / Oct-Apr 5th daily percentile.

- `reference_exposed_events`: reference events with at least one hidden hour
- `kept_exact_share`: same start and end day
- `changed_bounds_share`: still overlapping but start/end moved, shortened or split
- `lost_share`: no overlapping event after filling
- `new_candidate_event_count`: events present only after filling (includes split fragments)
- `exposed_events_exact_bounds_and_peak_fraction`: same bounds and same peak temperature

## method-steps.csv

Random seasonal gaps, 95th-percentile annual error for each method in order: linear only; temporal (<=3 h linear then daily profiles <=48 h); previous automatic (profiles, donor, ERA5); current automatic (<=3 h linear, assessed donor, profiles, ERA5); ERA5 only; diyepw-style; assessed donor alone (subset of gaps with a qualifying donor).

- `*_p95_kwh_m2 / *_p95_pct`: 95th percentile of |annual error|

## gap-position.csv

Per hidden block: load error inside the block and in the following 168 h, and weather error in the filled hours, by season (random) or event anchor.

- `event_type`: random_seasonal or the event anchor (warmest/coldest original hour, heatwave hottest hour, cold-spell coldest hour)
- `season`: winter Dec-Feb, spring Mar-May, summer Jun-Aug, autumn Sep-Nov (same calendar year)
- `n`: hidden blocks x buildings
- `gap_*_delta_kwh_m2_abs_*`: |load change inside the block|, kWh/m2
- `recovery_*_delta_kwh_m2_abs_*`: |load change in the 168 h after the block|, kWh/m2
- `weather_<variable>_mae_abs_*`: mean absolute weather error over the filled hours

## seasonal-load-shares.csv

Reference share of annual heating and cooling in each season, per building and region-year.


## extreme-vs-random.csv

Annual and peak errors and peak preservation by placement (random seasonal vs event anchors) for each method and gap length.


## gap-window-decomposition-check.csv

Check that per-block windows (block + 168 h) add up to the annual error of a file (all gap types pooled).


## peak-exposure.csv

Share of rows whose reference annual peak is hidden (automatic method).


## p95-bootstrap.csv

95th-percentile annual errors with case counts and a 95 % range from 1000 resamples of whole gap files.


## spell-preservation-summary.csv

Heatwave/cold-spell days kept after filling, including the SMHI rule (5+ days with daily max >= 25 C) and the study 3-day rules.


## reference-spell-days.csv

Reference heatwave and cold-spell days per region-year under each rule.


## monthly-error.csv

Error in each calendar month that holds a hidden block, against the reference month; compare with ASHRAE Guideline 14's +/-5 % monthly bias for calibrated models. Months with less than 5 % of the building's largest monthly demand are excluded.

- `*_month_abs_pct_median / p95`: |monthly error|, % of reference monthly demand
- `*_months_within_5pct`: share of evaluated months within +/-5 %

## strang-vs-era5-ghi.csv

Hourly global horizontal irradiance from SMHI STRÅNG and from ERA5 (both
sampled at the primary weather station's coordinates) against measured SMHI
GHI, for the 12 region-years with a measured-GHI station within 50 km.
Daytime hours with measured GHI above 5 W/m2 and all three series present.
The last row is the mean over region-years.

- `radiation_station_id`, `radiation_station_name`, `radiation_station_distance_km`: the measuring station and its distance from the sampling point
- `daytime_hours`, `measured_mean_w_m2`: hours compared and mean measured GHI
- `strang_*`, `era5_*`: hourly mean absolute error, mean bias (model minus measured) and RMSE in W/m2; daily-total mean absolute error in kWh/m2
