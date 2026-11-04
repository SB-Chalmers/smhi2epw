# Robustness of the gap-filling methods (general-weather gaps)

Paired analysis of the corrected campaign's per-case table; no new
simulations. Both gap types are included, in the `scope` column:
"meteorology" (temperature, humidity, pressure and wind hidden) and "solar"
(GHI, DNI and DHI hidden). Every method fills the same gap layouts, so a **case**
is region-year x building x gap layout (one weather file). Bootstrap ranges use
1,000 resamples of whole gap layouts (weather files), never single buildings.

Metrics per case: |annual heating error| and |annual cooling error| as % of the
building's reference annual demand; |annual peak error| in W/m2 and
|peak-hour shift| in hours, both only when the reference annual peak hour lies
inside a hidden block.

Floors: annual percentages only where the reference annual demand is at least
1 kWh/m2 (heating and cooling alike); peak metrics only where the reference
annual peak is at least 5 W/m2. No reference peak in the campaign is below
5 W/m2 (smallest 11.05 W/m2, cooling), so the peak floor excludes no case.

Methods: temporal, donor_assessed, era5, automatic, automatic_legacy,
linear_only, diyepw_style, and the combined rule `automatic_le48h_era5_168h`
(automatic rows for gaps up to 48 h, era5 rows for 1-week gaps).

## Files

- `headline-definitions.csv`: n, median, mean, 95th percentile and maximum of
  |annual heating/cooling error %| per scope, placement (`sampling`), gap
  length and method, pooled over buildings, gap layouts and region-years.
- `paired-era5-vs-automatic.csv`: per gap length, placement and metric: cases,
  gap layouts, median paired difference (ERA5 minus automatic), shares where
  ERA5 or automatic has the smaller error and ties (|difference| <= 1e-9), and
  95 % bootstrap ranges for the ERA5 win share, the difference of the 95th
  percentiles (`p95_diff_lo/hi`) and the difference of the medians.
- `region-year-wins.csv`: number of the 17 region-years in which each method
  has the lower 95th-percentile error.
- `regret-by-metric.csv`: regret = |error| of a method minus the smallest
  |error| of any method on the same case and metric; max, 95th percentile,
  mean and share of zero regret, per gap length, placement, metric and method.
- `regret-pooled.csv`, `regret-pooled-by-placement.csv`: pooled over metrics in
  three ways: `scaled_regret` (annual % / 100; peak W/m2 / reference peak;
  shift hours / 24 h), `scaled_regret_magnitudes_only` (the same without peak
  timing, whose shifts can span seasons), and `rank_regret` (rank of the
  method within the case minus 0, ties averaged; 0 = best).

- `worst-cases.csv`: the three largest scaled regrets per method and gap
  length, with absolute values: the method's |error|, ERA5's and automatic's
  |error|, the best |error| and best method on that case, and the reference
  peak (W/m2) or annual demand (kWh/m2). `units` gives the unit of the
  |error| columns.

`variant` in the regret files: `available` = every method on the cases where it
exists (donor_assessed exists for about 40 % of gaps; temporal has no 1-week
result); `complete` = only cases where all methods exist (so no 1-week rows);
`core_methods` = all cases, without donor_assessed and temporal.
