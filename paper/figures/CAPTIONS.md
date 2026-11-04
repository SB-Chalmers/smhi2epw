# Figure captions: notes moved out of the figures

These are the notes that used to sit inside the figures, as subtitles or margin notes. Fold them into the captions. Figure numbers follow the manuscript, and file names are in brackets.

Colour rule for all figures: a colour always means a filling method or recovery step, as in Figure 1 (grey = measured, blue = straight line ≤ 3 h / filling over time, vermillion = nearby station, green = daily pattern / older order, pink = ERA5, sky blue = diyepw-style, orange = solar branch). Gap placement, seasons, event outcomes and peak timing are always in greys.

**Figure 1 (fig_a_recovery_ladder).** How smhi2epw lines up the measured inputs hour by hour and then fills the gaps step by step.

**Figure 3 (fig_c_masking).** Gaps of 3 h and 12 h are drawn wider than to scale so they stay visible. General-weather and solar gaps are hidden in separate files. Winter is December to February. Event hours (b) are the warmest and the coldest measured hour, the hottest hour of a heatwave and the coldest hour of a cold spell, where these occur.

**Figure 5 (fig06_annual_error).** smhi2epw. Each bar is the 95th percentile of the absolute error, and the dash is the median. 17 region-years × 6 buildings. Light bars are one gap per file, centred on the coldest hour of a cold spell for heating and on the hottest hour of a heatwave for cooling, as in Figure 8. The y-axes differ between panels.

**Figure 6 (fig09_peaks).** smhi2epw, general-weather gaps. In a and b each dot is one building case whose yearly peak hour fell inside a gap. The numbers above give the cases. The median (solid) and 95th percentile (dashed) are drawn only where there are at least 10 cases, and the timing bars in c and d follow the same rule. Below 10 cases only the number is shown, in grey.

**Figure 7 (fig10_events).** smhi2epw, general-weather gaps centred on weather events. The numbers above the bars are the events hit by a gap.

**Figure 8 (fig08_gap_position).** smhi2epw, 17 region-years × 6 buildings, as % of the building's yearly demand (the same units as Figures 5, 9 and 10). Each wide bar is the 95th percentile of the load error over the gap plus the following week, taken as one value. The thin white bar is the 95th percentile inside the gap only. Errors inside the gap and in the following week can partly cancel, so the thin bar can be taller than the wide one, as in c for cold spells at 1 week. Hatched bars are gaps centred on a cold spell (heating) or a heatwave (cooling). The y-axes differ between panels.

**Figure 9 (fig07_methods).** Random gaps, 17 region-years × 6 buildings, with y-axes that differ between panels. a, b: all general-weather gaps. c, d: only the gaps where a nearby station passed the test (about 40 %), so every method, including nearby station alone, is compared on the same cases. On these cases nearby station matches smhi2epw, so its dashed line lies on top. e, f: solar gaps, which have no nearby-station step. Filling over time stops at 48 h, and its line is hidden: it matches the older order for general weather and smhi2epw for solar up to 2 days. Above 2 days, smhi2epw and diyepw-style use ERA5 for solar, so all three match at 1 week.

**Figure 10 (fig11_monthly).** Random gaps. ±5 % is the monthly bias limit for calibrated models in ASHRAE Guideline 14. Months with little demand are left out. The rows are the same as in Figure 9.