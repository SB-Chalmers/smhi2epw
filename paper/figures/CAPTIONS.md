# Figure captions: notes moved out of the figures

These are the notes that used to sit inside the figures, as subtitles or margin notes. Fold them into the captions. Figure numbers follow the manuscript, and file names are in brackets.

Colour rule for all figures: a colour always means a filling method or recovery step, as in Figure 1. Grey means measured, blue straight line ≤ 3 h (and filling over time), vermillion nearby station, green daily pattern (and Stepwise, patterns first), pink ERA5, sky blue diyepw-style and orange the solar branch. Black is Stepwise and dark grey dotted is Stepwise, no length limit. Gap placement, seasons, event outcomes and peak timing are always grey.

"Stepwise" in every results figure is the method of Figure 1. General-weather gaps over 48 h and solar gaps over 3 h go to ERA5. "Stepwise, no length limit" uses a nearby station for general-weather gaps of any length and solar daily patterns up to 48 h. The two give identical results for general-weather gaps up to 2 days and solar gaps of 3 h. "Stepwise, patterns first" tries the daily pattern before the nearby station.

**Figure 1 (fig_a_recovery_ladder).** How the stepwise method lines up the measured inputs hour by hour and then fills the gaps step by step. For general weather, a nearby station is tried only for gaps of up to 48 h, and longer gaps go straight to ERA5. Where a solar station lies within 50 km, its measured total radiation is used, and STRÅNG's direct and diffuse split is scaled to match it. In hours the station lacks, STRÅNG is used as it is. Gaps that remain are filled with a straight line up to 3 h and then with ERA5. Solar is never taken from a nearby station.

**Figure 2 (fig_d_workflow).** The campaign workflow. Every filling method fills the same gap patterns in the same reference years.

**Figure 3 (fig_c_masking).** Gaps of 3 h and 12 h are drawn wider than to scale so they stay visible. General-weather and solar gaps are hidden in separate files. Winter is December to February. Event hours (b) are the warmest and the coldest measured hour, the hottest hour of a heatwave and the coldest hour of a cold spell, where these occur.

**Figure 5 (fig06_annual_error).** Stepwise. Each bar is the 95th percentile of the absolute error, and the dash is the median. 17 region-years × 6 buildings. Light bars are one gap per file, centred on the coldest hour of a cold spell for heating and on the hottest hour of a heatwave for cooling, as in Figure 8. The y-axes differ between panels.

**Figure 6 (fig09_peaks).** Stepwise, general-weather gaps. In a and b each dot is one building case whose yearly peak hour fell inside a gap, and the numbers above give the cases. The median (solid) and 95th percentile (dashed) are drawn only where there are at least 10 cases, and the timing bars in c and d follow the same rule. Below 10 cases only the number is shown, in grey.

**Figure 7 (fig10_events).** Stepwise, general-weather gaps centred on weather events. The numbers above the bars are the events hit by a gap.

**Figure 8 (fig08_gap_position).** Stepwise, 17 region-years × 6 buildings, as % of the building's yearly demand (the same units as Figures 5, 9 and 10). Each wide bar is the 95th percentile of the load error over the gap plus the following week, taken as one value. The thin white bar is the 95th percentile inside the gap only. Errors inside the gap and in the following week can partly cancel, so the thin bar can be taller than the wide one. Hatched bars are gaps centred on a cold spell (heating) or a heatwave (cooling). The y-axes differ between panels.

**Figure 9 (fig07_methods).** Random gaps, 17 region-years × 6 buildings, with y-axes that differ between panels. a, b: all general-weather gaps. c, d: only the gaps where a nearby station passed the test (about 40 %), so every method, including nearby station alone, is compared on the same cases. e, f: solar gaps, which have no nearby-station step. Stepwise matches ERA5 at 1 week for general weather and from 12 h for solar, so the ERA5 line lies under it there. Stepwise, no length limit (dotted) matches Stepwise up to 2 days for general weather and at 3 h for solar. On the subset in c and d, nearby station (dashed) matches Stepwise, no length limit. Filling over time is not drawn, because it stops at 48 h and up to 2 days matches Stepwise, patterns first (general weather) or Stepwise, no length limit (solar).

**Figure 10 (fig11_monthly).** Random gaps. ±5 % is the monthly bias limit for calibrated models in ASHRAE Guideline 14, and months with little demand are left out. The rows and lines are the same as in Figure 9.
