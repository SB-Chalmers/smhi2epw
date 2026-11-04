# Figure captions: notes moved out of the figures

These are the notes that used to sit inside the figures, as subtitles or margin notes. Fold them into the captions. Figure numbers follow the manuscript, and file names are in brackets.

Colour rule for all figures: a colour always means a filling method or recovery step, as in Figure 1 (grey = measured, blue = straight line ≤ 3 h / filling over time, vermillion = nearby station, green = daily pattern / older order, pink = ERA5, sky blue = diyepw-style, orange = solar branch). Gap placement, seasons, event outcomes and peak timing are always in greys.

**Figure 1 (fig_a_recovery_ladder).** How smhi2epw lines up the measured inputs hour by hour and then fills the gaps step by step.

**Figure 3 (fig_c_masking).** Gaps of 3 h and 12 h are drawn wider than to scale so they stay visible. General-weather and solar gaps are hidden in separate files. Winter is December to February. Event hours (b) are the warmest and the coldest measured hour, the hottest hour of a heatwave and the coldest hour of a cold spell, where these occur.

**Figure 5 (fig06_annual_error).** smhi2epw. Each bar is the 95th percentile of the absolute error, and the dash is the median. 17 region-years × 6 buildings. The y-axes differ between panels.

**Figure 6 (fig09_peaks).** smhi2epw, general-weather gaps. The numbers give the building cases whose yearly peak hour fell inside a gap. Below 10 cases, no percentile or share is drawn and only the number is shown, in grey.

**Figure 7 (fig10_events).** smhi2epw, general-weather gaps centred on weather events. The numbers above the bars are the events hit by a gap.

**Figure 8 (fig08_gap_position).** smhi2epw, 17 region-years × 6 buildings. Each part of a bar is its own 95th percentile, so the stack is an upper guide and not the 95th percentile of the sum. Hatched bars are gaps centred on a cold spell (heating) or a heatwave (cooling). The y-axes differ between panels.

**Figure 9 (fig07_methods).** Random gaps, 17 region-years × 6 buildings, with y-axes that differ between panels. * Nearby station covers only gaps where a nearby station passed the test (about a third of cases). Filling over time stops at 48 h. For general weather it matches the older order up to 2 days, and for solar it matches smhi2epw up to 2 days, so its line is hidden. Solar (c, d) has no nearby-station step. Above 2 days, smhi2epw and diyepw-style use ERA5 for solar, so all three match at 1 week.

**Figure 10 (fig11_monthly).** Random gaps. ±5 % is the monthly bias limit for calibrated models in ASHRAE Guideline 14. Months with little demand are left out. The notes on nearby station, filling over time and solar are the same as for Figure 9.
