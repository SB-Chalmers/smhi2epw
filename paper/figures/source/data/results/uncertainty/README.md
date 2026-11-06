# Uncertainty propagation (no new simulations)

From the corrected campaign's per-case table. Methods: `automatic` and
`gap_type_rule` (automatic for general-weather gaps up to 48 h and solar gaps
of 3 h, ERA5 otherwise), both gap types (`scope`: meteorology = temperature,
humidity, pressure and wind hidden; solar = GHI, DNI and DHI hidden). A case
is region-year x building x gap layout. Annual errors are |error| as % of the
building's reference annual demand (demand below 1 kWh/m2 excluded); peak
errors and shifts only where the reference annual peak hour is hidden.

## exceedance.csv

Share of cases whose |error| exceeds each threshold (`share_exceeding`), by
gap type, placement (`sampling`), gap length and method. Metrics and grids:
annual heating/cooling % (0.01-10 / 0.01-20 %), peak error (0.1-20 W/m2),
peak-hour shift (1-720 h). `cases` is the denominator.

## variance-split.csv

How much of the case-to-case spread in annual error each factor explains.
The response is log10(|annual error %| + 0.0001), so shares describe
multiplicative differences. For each factor: `one_way_share` = variance
explained by that factor alone; `unique_share_in_main_effects` = what is lost
when it is dropped from a model with all main effects (gap length,
placement, building, region-year and, where several methods are pooled,
method). `added_by_interaction` = what each interaction adds on top of the
main effects. `residual_share` = what the full model leaves unexplained:
the specific weather in each hidden window. Rows are given for automatic
alone and for all methods pooled.

## weather-to-load.csv

Per building and gap type, ordinary least squares of the annual load change
(kWh/m2, signed) on the signed weather error summed over the hidden hours:
temperature (K h) for general weather (also with relative humidity, %-h, as a
second predictor: `with_rh_*`), and GHI (kWh/m2) for solar. All methods are
pooled, because each method contributes different weather errors on the same
gaps. Peak rows (`*_peak`) regress the peak change (W/m2) on the mean
temperature (K) or GHI (W/m2) error over the hidden hours, on cases whose
reference peak is hidden. The temperature error at the peak hour itself is
not in the per-case table; the hidden-hour mean is used instead.

## error-budget.csv

Lookup table for real files: p50 and p95 of |annual heating| and |annual
cooling| error (kWh/m2 and %), by share of the year's hours filled
(`filled_share_bin`) and longest gap (`longest_gap_bin`).
`hidden_hours_in_bin` lists the hours actually tested in each cell: the
campaign tested 3, 12, 48 or 168 h in one block, or 12, 48, 192 or 672 h in
four seasonal blocks. Cells outside these combinations are not covered.
