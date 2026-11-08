"""Fig. 4: where the gaps are placed.

(a) Random seasonal panels: block positions drawn by the campaign's own sampler
    (see make_mask_example.py) for an example site-year.
(b) Event-centred panels: one block per file, centred on a weather anchor.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

import style as S
from style import INK, MUTED, RULE, RUNG, SEASON

S.use()
DATA = Path(__file__).resolve().parents[1] / "data"
panels = [p for p in json.loads((DATA / "mask_example.json").read_text())
          if p["scope"] == "meteorology"]
YEAR = 2021
t0 = pd.Timestamp(f"{YEAR}-01-01", tz="UTC")
DAYS = 365
MIN_W = 1.6  # days; minimum drawn width so 3 h and 12 h blocks stay visible

DUR = (3, 12, 48, 168)
SHADE = {3: "#6fa6d4", 12: "#3f86c0", 48: "#1f6fb0", 168: "#163f6b"}  # gap length, light to dark blue

fig = plt.figure(figsize=(S.DOUBLE, 68 * S.MM))
ax = fig.add_axes([0.12, 0.1, 0.56, 0.62])
bx = fig.add_axes([0.765, 0.17, 0.215, 0.55])

# ----------------------------------------------------------- (a) seasonal
season_spans = [("DJF", 0, 59), ("MAM", 59, 151), ("JJA", 151, 243), ("SON", 243, 334),
                ("DJF", 334, 365)]
SEASON_NAME = {"DJF": "Winter", "MAM": "Spring", "JJA": "Summer", "SON": "Autumn"}
DRAW = {11: 1, 29: 2, 47: 3}
rows = []
for d in DUR:
    for seed in (11, 29, 47):
        rows.append((d, seed))
nrow = len(rows)
gap = 0.7
ypos = {}
y = 0
for i, (d, seed) in enumerate(rows):
    if i and rows[i - 1][0] != d:
        y += gap
    ypos[(d, seed)] = y
    y += 1
ymax = y
for name, a, b in season_spans:
    ax.add_patch(Rectangle((a, -0.6), b - a, ymax + 0.2, fc=SEASON[name], ec="none", zorder=0))
for name, a, b in season_spans[:4]:
    ax.text((a + b) / 2, ymax + 0.15, SEASON_NAME[name], ha="center", va="top", fontsize=7, color=MUTED)

for p in panels:
    key = (p["hours"], p["seed"])
    yy = ypos[key]
    for start, end, _ in p["blocks"]:
        s = (pd.Timestamp(start) - t0).total_seconds() / 86400
        e = (pd.Timestamp(end) - t0).total_seconds() / 86400 + 1 / 24
        w = e - s
        drawn = max(w, MIN_W)
        ax.add_patch(Rectangle((s + w / 2 - drawn / 2, yy + 0.14), drawn, 0.72,
                               fc=SHADE[p["hours"]], ec="none", zorder=3))
    ax.text(DAYS + 2, yy + 0.5, f"{DRAW[p['seed']]}", fontsize=7, color=MUTED,
            va="center", ha="left")

for d in DUR:
    ys = [ypos[(d, s)] for s in (11, 29, 47)]
    mid = (min(ys) + max(ys) + 1) / 2
    ax.text(-5, mid - 0.45, f"{d} h gaps", ha="right", va="center", fontsize=7,
            weight="bold", color=INK)
    ax.text(-5, mid + 0.6, f"{4 * d} h in total", ha="right", va="center", fontsize=7,
            color=MUTED)

month_starts = pd.date_range(f"{YEAR}-01-01", periods=12, freq="MS")
ax.set_xticks([(m - pd.Timestamp(f"{YEAR}-01-01")).days for m in month_starts])
ax.set_xticklabels([m.strftime("%b") for m in month_starts], fontsize=7)
for lab in ax.get_xticklabels():
    lab.set_horizontalalignment("left")
ax.tick_params(axis="x", length=2, pad=1.5)
ax.set_xlim(0, DAYS)
ax.set_ylim(ymax + 0.0, -0.6)
ax.set_yticks([])
for side in ("left", "right", "top"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_bounds(0, DAYS)
ax.xaxis.set_ticks_position("top")
ax.spines["bottom"].set_visible(False)
ax.spines["top"].set_visible(True)
ax.text(0, 1.27, "a  Random gaps, one per season", transform=ax.transAxes, fontsize=8,
        weight="bold", va="bottom")
ax.text(0, 1.105, "three random draws per gap length; example year 2021",
        transform=ax.transAxes, fontsize=7, color=MUTED, va="bottom")
ax.text(DAYS + 2, -0.35, "draw", fontsize=7, color=MUTED, ha="left", va="bottom")

# ----------------------------------------------------------- (b) event-centred
for i, d in enumerate(DUR[::-1]):
    yy = i
    s = -(d // 2)
    bx.add_patch(Rectangle((s, yy + 0.18), d, 0.64, fc=SHADE[d], ec="none", zorder=3))
    bx.text(s - 3, yy + 0.5, f"{d} h", ha="right", va="center", fontsize=7,
            color=INK)
bx.axvline(0, color=INK, lw=0.9, ls=(0, (2, 1.5)), zorder=4)
bx.text(3, -0.35, "event hour", color=INK, fontsize=7, ha="left",
        va="bottom")
bx.set_xlim(-108, 92)
bx.set_ylim(4.0, -0.9)
bx.set_xticks([-84, -48, 0, 48, 84])
bx.set_xlabel("hours from event hour", fontsize=7, labelpad=1.5)
bx.set_yticks([])
bx.spines["left"].set_visible(False)
bx.text(0, 1.235, "b  Gaps at weather events", transform=bx.transAxes, fontsize=8,
        weight="bold", va="bottom")
bx.text(0, 1.145, "one gap per weather file", transform=bx.transAxes,
        fontsize=7, color=MUTED, va="bottom")
S.save(fig, "fig_c_masking")
