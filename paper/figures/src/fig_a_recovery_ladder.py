"""Fig. 1: the stepwise method as a ladder over gap length (round 2).

x = length of the gap (log scale), one row per source. A bar shows the gap
lengths a source may fill. Sources are tried from the top; an hour that one
source cannot fill falls to the next. Solid accent = used by the stepwise
method; grey dashed = used only without the switch to ERA5 (the tested
alternatives). Switch points are vertical lines.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import style as S
from style import ACCENT, ACCENT_SEQ, INK, MIN_FS, MUTED, OTHER, RULE

S.use()
FS = MIN_FS
XMIN, XMAX = 1, 24 * 14
TICKS = [(1, "1 hour"), (3, "3 hours"), (12, "12 hours"), (24, "1 day"), (48, "2 days"),
         (168, "1 week"), (336, "2 weeks")]

H = 104
fig, (a1, a2) = plt.subplots(2, 1, figsize=(S.DOUBLE, H * S.MM),
                             gridspec_kw=dict(height_ratios=[4, 3]))
fig.subplots_adjust(left=0.305, right=0.86, top=0.87, bottom=0.09, hspace=0.95)


def bar(ax, row, x0, x1, *, used=True, light=False, label=None):
    if used:
        col = ACCENT_SEQ[0] if light else ACCENT
        ax.barh(row, np.log10(x1) - np.log10(x0), left=np.log10(x0), height=0.5,
                color=col, lw=0, zorder=3)
    else:
        ax.plot([np.log10(x0), np.log10(x1)], [row, row], color=OTHER, lw=3.2,
                ls=(0, (1.2, 0.9)), solid_capstyle="butt", zorder=2)
    if label:
        ax.text(np.log10(x1) + 0.04, row, label, fontsize=FS, va="center", ha="left",
                color=ACCENT if used and not light else MUTED, clip_on=False)


def frame(ax, rows, letter, title):
    ax.set_xlim(np.log10(XMIN), np.log10(XMAX))
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([])
    for i, (name, note) in enumerate(rows):
        ax.text(-0.012, i - 0.05, name, transform=ax.get_yaxis_transform(), ha="right",
                va="bottom", fontsize=7, weight="bold", color=INK)
        ax.text(-0.012, i + 0.07, note, transform=ax.get_yaxis_transform(), ha="right",
                va="top", fontsize=FS, color=MUTED)
    ax.set_xticks([np.log10(t) for t, _ in TICKS])
    ax.set_xticklabels([l for _, l in TICKS])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=RULE, lw=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("length of the gap")
    ax.annotate(f"{letter}  {title}", (-0.36, 1), xycoords="axes fraction", xytext=(0, 24),
                textcoords="offset points", fontsize=7.5, weight="bold", va="bottom")


def switch(ax, h, text, used, ha="center"):
    ax.axvline(np.log10(h), color=ACCENT if used else MUTED, lw=1.0 if used else 0.7,
               ls="-" if used else (0, (3, 2)), zorder=4)
    dx = {"center": 0, "left": 2, "right": -2}[ha]
    ax.annotate(text, (np.log10(h), 1), xycoords=("data", "axes fraction"), xytext=(dx, 2),
                textcoords="offset points", fontsize=FS, ha=ha, va="bottom",
                color=ACCENT if used else MUTED, weight="bold" if used else "normal")


# ------------------------------------------------------------- a general weather
rows_a = [("Linear interpolation", "between the values either side"),
          ("Nearby station", "up to 3 within 75 km, if one passes checks"),
          ("Daily pattern", "typical day from the week either side"),
          ("ERA5", "reanalysis for the same hours")]
frame(a1, rows_a, "a", "General weather: local sources up to two days, then ERA5")
bar(a1, 0, 1, 3)
bar(a1, 1, 3, 48)
bar(a1, 1, 48, XMAX, used=False, label=None)
bar(a1, 2, 3, 48, label="if no station passes")
bar(a1, 3, 1, 48, light=True)
bar(a1, 3, 48, XMAX)
a1.text(np.log10(5), 3, "any hour still empty", fontsize=FS, va="center", ha="left",
        color=INK, zorder=5)
a1.text(np.log10(60), 1.42, "without the switch", fontsize=FS, va="center", ha="left",
        color=MUTED)
switch(a1, 24, "switch at 1 day\n(tested)", False, ha="right")
switch(a1, 48, "switch at 2 days\n(used)", True, ha="left")

# ------------------------------------------------------------- b solar
rows_b = [("Linear interpolation", "follows the sun; zero at night"),
          ("Daily pattern", "typical day from the week either side"),
          ("ERA5", "all three parts together")]
frame(a2, rows_b, "b", "Solar radiation: linear interpolation up to three hours, then ERA5")
bar(a2, 0, 1, 3)
bar(a2, 1, 3, 48, used=False, label="without the switch")
bar(a2, 2, 1, 3, light=True)
bar(a2, 2, 3, XMAX)
switch(a2, 3, "switch at 3 hours\n(used)", True)
switch(a2, 12, "12 h\n(tested)", False)
switch(a2, 48, "48 h\n(tested)", False)

S.save(fig, "fig_a_recovery_ladder")
