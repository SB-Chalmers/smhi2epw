"""Graphical abstract: hide known hours, refill them, and see what changes.

Panel 1 uses the real Stockholm-Arlanda gap of Figure 6
(source/data/method_sketch_week.csv). Numbers in panel 3 are from the abstract.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

import style as S

DATA = Path(__file__).resolve().parents[1] / "source" / "data" / "method_sketch_week.csv"
W_MM, H_MM = 240, 96


def heading(fig, x, y, n, text):
    fig.text(x, y, f"{n}", fontsize=13, fontweight="bold", color=S.ACCENT, va="top")
    fig.text(x + 0.022, y - 0.004, text, fontsize=11.5, fontweight="bold", va="top")


def main() -> None:
    S.use()
    fig = plt.figure(figsize=(W_MM * S.MM, H_MM * S.MM))

    # ---------------- 1 hide known hours ----------------
    heading(fig, 0.015, 0.965, 1, "Hide known hours")
    d = pd.read_csv(DATA, parse_dates=["time"])
    ing = d["in_gap"] == 1
    ax = fig.add_axes([0.045, 0.22, 0.26, 0.58])
    g0, g1 = d.loc[ing, "time"].min(), d.loc[ing, "time"].max()
    ax.axvspan(g0, g1, color="#ececf0", lw=0, zorder=0)
    ax.plot(d["time"], d["measured"].where(~ing), color=S.INK, lw=1.3, zorder=3)
    ax.plot(d["time"], d["measured"].where(ing | ing.shift(1, fill_value=False) | ing.shift(-1, fill_value=False)),
            color=S.INK, lw=1.0, ls=(0, (2, 1.6)), zorder=3)
    for col, c in [("linear", S.SRC["linear"]), ("era5", S.SRC["era5"]), ("nearby_station", S.SRC["nearby"])]:
        ax.plot(d["time"], d[col].where(ing), color=c, lw=1.6, zorder=4)
    ax.set_ylim(-9, 25)
    ax.set_yticks([0, 10, 20])
    ax.set_ylabel("air temperature, °C", fontsize=8.5)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d Apr"))
    ax.tick_params(labelsize=8)
    mid = g0 + (g1 - g0) / 2
    ax.text(mid, 23.2, "48 hours hidden", ha="center", fontsize=8.5, color=S.MUTED)
    ax.text(d["time"].iloc[2], 23.2, "measured", fontsize=8.5)
    ax.text(mid, -7.5, "true values (dashed)", ha="center", fontsize=8, color=S.MUTED)
    fig.text(0.045, 0.085, "Stockholm-Arlanda, April 2023: three of the\nseven methods filling one real gap",
             fontsize=8.5, color=S.MUTED, va="bottom")

    # ---------------- 2 refill and simulate ----------------
    heading(fig, 0.338, 0.965, 2, "Refill and simulate")
    meths = [("Linear interpolation", S.SRC["linear"]), ("Daily patterns", S.SRC["patterns"]),
             ("Four-week average", S.SRC["fourweek"]), ("Nearby station", S.SRC["nearby"]),
             ("ERA5 reanalysis", S.SRC["era5"]), ("Stepwise, with and\nwithout ERA5 switch", S.ACCENT)]
    x0, y = 0.343, 0.83
    hgt = 0.085
    for name, c in meths:
        fig.patches.append(FancyBboxPatch((x0, y - hgt), 0.125, hgt - 0.015, boxstyle="round,pad=0,rounding_size=0.008",
                                          transform=fig.transFigure, fc="white", ec=c, lw=1.6))
        fig.text(x0 + 0.0625, y - hgt / 2 - 0.007, name, ha="center", va="center", fontsize=8,
                 fontweight="bold" if c == S.ACCENT else "normal", linespacing=0.95)
        y -= hgt
    fig.text(x0 + 0.0625, 0.085, "seven methods", ha="center", fontsize=8.5, color=S.MUTED, va="bottom")
    # arrow to buildings
    fig.patches.append(plt.matplotlib.patches.FancyArrowPatch((0.475, 0.55), (0.497, 0.55), transform=fig.transFigure,
                                                               arrowstyle="-|>", mutation_scale=12, color=S.INK, lw=1.0))
    bx = 0.505
    rows = [("17", "weather-years,\n6 Swedish regions"), ("3 h to\n1 week", "gaps, at random or\nin heatwaves and\ncold spells"),
            ("6", "buildings,\nEnergyPlus")]
    y = 0.83
    for big, small in rows:
        fig.text(bx, y, big.replace("\n", " "), fontsize=12, fontweight="bold", va="top")
        fig.text(bx, y - 0.065, small.replace("\n", " ").replace("weather-years, ", "weather-years,\n").replace("random or in ", "random or in\n"), fontsize=8.3, va="top", linespacing=1.05)
        y -= 0.24
    fig.text(bx, 0.085, "each filled file is compared\nwith the complete one", fontsize=8.5, color=S.MUTED, va="bottom")

    # divider lines
    for xv in (0.328, 0.655):
        fig.add_artist(plt.Line2D([xv, xv], [0.08, 0.95], transform=fig.transFigure, color=S.RULE, lw=0.8))

    # ---------------- 3 what changes ----------------
    heading(fig, 0.668, 0.965, 3, "What changes")
    finds = [
        ("< 0.3%", "change in annual heating\nwith 12-hour gaps,\nin 95% of cases", S.INK),
        ("½", "of heating peaks hidden by\na week-long gap move by\nmore than a day", S.INK),
        ("1–2 days", "then switch to ERA5: this avoids\nthe worst errors, from nearby\nstations failing in extreme weeks", S.ACCENT),
    ]
    y = 0.83
    for big, small, c in finds:
        fig.text(0.672, y, big, fontsize=15, fontweight="bold", va="top", color=c)
        fig.text(0.775, y + 0.005, small, fontsize=8.3, va="top", linespacing=1.05)
        y -= 0.235
    fig.patches.append(Rectangle((0.668, 0.07), 0.322, 0.115, transform=fig.transFigure, fc="#e8f1f8", ec="none"))
    fig.text(0.678, 0.127, "Quick check: extra heating ≈ heat-loss coefficient\n× temperature error summed over the gap",
             fontsize=8.3, va="center", linespacing=1.1)

    S.save(fig, "fig_graphical_abstract")


if __name__ == "__main__":
    main()
