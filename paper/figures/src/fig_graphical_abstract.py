"""Graphical abstract: one question, one grid answer.

Left: the hide-and-refill test on the real Stockholm-Arlanda gap of Figure 6
(source/data/method_sketch_week.csv). Right: Table 8 of the paper as a grid,
shaded by how much the result changes (95% of cases, stepwise method).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

import style as S

DATA = Path(__file__).resolve().parents[1] / "source" / "data" / "method_sketch_week.csv"
W_MM, H_MM = 240, 100

LEVEL = {0: ("#e3edf7", S.INK), 1: ("#7fb0d8", S.INK), 2: ("#1f5a96", "white")}
COLS = ["3–12 hours", "2 days", "1 week"]
ROWS = [
    ("Annual heating", [(0, "< 0.3%"), (0, "< 0.4%"), (0, "< 1.7%")]),
    ("Annual cooling", [(0, "< 1.1%"), (0, "< 1.3%"), (1, "< 5%")]),
    ("Size of peak load", [(0, "~1 W/m²"), (1, "< 8 W/m²"), (2, "< 17 W/m²")]),
    ("Peak moved by > 1 day", [(1, "23%"), (2, "35%"), (2, "51%")]),
    ("Heatwaves lost", [(0, "none"), (1, "8%"), (2, "20%")]),
]


def main() -> None:
    S.use()
    fig = plt.figure(figsize=(W_MM * S.MM, H_MM * S.MM))

    # ---- question ----
    fig.text(0.02, 0.95, "Weather records have gaps.\nDoes filling them change\nthe energy simulation?",
             fontsize=13, fontweight="bold", va="top", linespacing=1.15)

    # ---- the test, on one real gap ----
    d = pd.read_csv(DATA, parse_dates=["time"])
    ing = d["in_gap"] == 1
    ax = fig.add_axes([0.03, 0.3, 0.30, 0.3])
    g0, g1 = d.loc[ing, "time"].min(), d.loc[ing, "time"].max()
    ax.axvspan(g0, g1, color="#ececf0", lw=0, zorder=0)
    edge = ing | ing.shift(1, fill_value=False) | ing.shift(-1, fill_value=False)
    ax.plot(d["time"], d["measured"].where(~ing), color=S.INK, lw=1.4, zorder=3)
    ax.plot(d["time"], d["measured"].where(edge), color=S.INK, lw=1.0, ls=(0, (2, 1.6)), zorder=3)
    for col, c in [("linear", S.SRC["linear"]), ("era5", S.SRC["era5"]), ("nearby_station", S.SRC["nearby"])]:
        ax.plot(d["time"], d[col].where(edge), color=c, lw=1.7, zorder=4)
    ax.set_ylim(-6, 22)
    ax.axis("off")
    mid = g0 + (g1 - g0) / 2
    ax.text(mid, 21.5, "hidden, then refilled", ha="center", va="bottom", fontsize=9, color=S.MUTED)
    fig.text(0.03, 0.235, "We hid known hours in 17 complete\nweather-years, refilled them with\n"
             "7 methods and simulated 6 buildings.", fontsize=9, va="top", linespacing=1.2)

    # ---- arrow ----
    fig.patches.append(FancyArrowPatch((0.335, 0.45), (0.37, 0.45), transform=fig.transFigure,
                                       arrowstyle="-|>", mutation_scale=16, color=S.INK, lw=1.4))

    # ---- grid ----
    gx, gy, cw, rh = 0.545, 0.80, 0.115, 0.118
    fig.text(gx + 1.5 * cw, 0.955, "length of the filled gap", ha="center", va="top", fontsize=9.5, color=S.MUTED)
    for j, c in enumerate(COLS):
        fig.text(gx + (j + 0.5) * cw, gy + 0.065, c, ha="center", va="center", fontsize=10.5, fontweight="bold")
    for i, (name, cells) in enumerate(ROWS):
        y = gy - (i + 1) * rh
        fig.text(gx - 0.012, y + rh / 2, name, ha="right", va="center", fontsize=10.5)
        for j, (lev, txt) in enumerate(cells):
            fc, tc = LEVEL[lev]
            fig.patches.append(FancyBboxPatch((gx + j * cw + 0.004, y + 0.008), cw - 0.008, rh - 0.016,
                                              boxstyle="round,pad=0,rounding_size=0.006",
                                              transform=fig.transFigure, fc=fc, ec="none"))
            fig.text(gx + (j + 0.5) * cw, y + rh / 2, txt, ha="center", va="center", fontsize=10, color=tc)

    # ---- the answer, beside the rows it covers ----
    xr = gx + 3 * cw + 0.008
    for (r0, r1), txt, col in [((0, 2), "barely", S.ACCENT), ((2, 5), "yes, for\nlong gaps", "#1f5a96")]:
        ytop, ybot = gy - r0 * rh - 0.012, gy - r1 * rh + 0.012
        fig.add_artist(plt.Line2D([xr, xr], [ybot, ytop], transform=fig.transFigure, color=S.INK, lw=1.0))
        fig.text(xr + 0.008, (ytop + ybot) / 2, txt, va="center", fontsize=11, fontweight="bold",
                 color=col, linespacing=1.05)

    # ---- advice ----
    fig.patches.append(Rectangle((0.385, 0.03), 0.6, 0.11, transform=fig.transFigure, fc="#f4f4f6", ec="none"))
    fig.text(0.395, 0.085, "Largest errors came from nearby stations that failed during extreme weeks.\n"
             "Advice: for gaps longer than 1–2 days, switch to ERA5 reanalysis.", fontsize=9.5, va="center")

    S.save(fig, "fig_graphical_abstract")


if __name__ == "__main__":
    main()
