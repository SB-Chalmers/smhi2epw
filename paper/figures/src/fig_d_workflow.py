"""Fig. 2: the paired test workflow (round 2: Table 6 method names, neutral fills)."""

from __future__ import annotations

import style as S
from style import ACCENT, INK, MIN_FS, MUTED, arrow, box

S.use()
W, H = 174, 125
fig, ax = S.canvas(W, H)
B = MIN_FS
LS = 2.75  # mm between lines of 6.5 pt text


def t(x, y, s, **kw):
    kw.setdefault("fontsize", B)
    kw.setdefault("color", INK)
    kw.setdefault("linespacing", 1.3)
    kw.setdefault("va", "top")
    ax.text(x, y, s, **kw)


def card(x, y, w, h, n, title, body, *, fc="white", ec=INK, lw=0.8):
    box(ax, x, y, w, h, fc=fc, ec=ec, lw=lw)
    ax.text(x + 2, y + h - 2.0, n, fontsize=7.5, weight="bold", va="top", color=MUTED)
    ax.text(x + 6.2, y + h - 2.0, title, fontsize=7.2, weight="bold", va="top")
    if body:
        t(x + 2, y + h - 7.4, body)


lane_ref = (99, 123)   # y range of reference lane
lane_cand = (2, 93.5)  # y range of test lane

# column x positions and widths
rx, rw = 2, 27
mx, mw = 33, 27
cx, cw = 64, 46
ex, ew = 114, 27
px, pw = 145, 27

t(mx, lane_cand[1] + 4.6, "Test files: repeated for every gap pattern and filling method",
  color=MUTED, style="italic")

# 1 reference weather (feeds both lanes)
card(rx, lane_cand[0], rw, lane_ref[1] - lane_cand[0], "1", "Reference year",
     "6 regions ×\n2018, 2021, 2023\n(Kiruna 2018:\nno suitable station)\n\n"
     "≤ 1 % of hours\nmissing, no gap\nover 48 h\n\n"
     "solar: measured\nwithin 50 km,\notherwise STRÅNG")

# 2 withhold
card(mx, lane_cand[0], mw, lane_cand[1] - lane_cand[0], "2", "Hide data",
     "general weather\nor solar radiation\n\n"
     "gaps of 3 h, 12 h,\n48 h or 1 week\n\n"
     "one per season\n(3 random draws)\nor one at a\nweather event\n\n"
     "only measured\nhours are hidden\nand scored")

# 3 reconstruct
card(cx, lane_cand[0], cw, lane_cand[1] - lane_cand[0], "3", "Fill the gaps",
     "hidden values stay unseen")
methods = [  # Table 6 names
    ("Stepwise", True, ["Fig. 1: ERA5 after 2 days", "(solar: after 3 h)"]),
    ("Stepwise, no switch", False, ["nearby station at any length;", "solar daily pattern ≤ 48 h"]),
    ("Stepwise, patterns first", False, ["daily pattern before", "nearby station"]),
    ("Line then patterns", False, ["straight line ≤ 3 h,", "daily pattern ≤ 48 h"]),
    ("Nearby station", False, ["tested nearby station only"]),
    ("ERA5 only", False, ["reanalysis for every hour"]),
    ("diyepw-style", False, ["line ≤ 6 h; 7–48 h: 4-week", "same-hour mean; then ERA5"]),
    ("Straight line only", False, ["straight line across any gap"]),
]
top = lane_cand[1] - 10.2
for name, step, desc in methods:
    h = 6.6 + LS * (len(desc) - 1)
    yy = top - h
    box(ax, cx + 1.6, yy, cw - 3.2, h, fc="#f1ebf6" if step else "#f2f2f4",
        ec=ACCENT if step else MUTED, lw=0.8 if step else 0.5, r=0.7)
    ax.text(cx + 3.0, yy + h - 1.7, name, fontsize=6.8, weight="bold", va="center",
            color=ACCENT if step else INK)
    for k, line in enumerate(desc):
        ax.text(cx + 3.0, yy + h - 4.5 - LS * k, line, fontsize=B, va="center", color=INK)
    top = yy - 0.5

# 4 EnergyPlus (spans both lanes)
card(ex, lane_cand[0], ew, lane_ref[1] - lane_cand[0], "4", "Simulate",
     "EnergyPlus 24.2,\nideal heating\nand cooling\n\nsame building\nfor both files")
profiles = ["house, 1961–75", "house, 2006–21", "flats, 1961–75", "flats, 2006–21",
            "office, 2006–21", "school, 1976–85"]
yy = lane_cand[0] + 2.0
for p in profiles[::-1]:
    hp = 5.0
    box(ax, ex + 1.6, yy, ew - 3.2, hp, p, fc="#f2f2f4", ec=MUTED, lw=0.4, fs=B, r=0.6)
    yy += hp + 0.8
t(ex + ew / 2, yy + 3.6, "6 building types", color=MUTED, ha="center")

# 5 paired metrics
card(px, lane_cand[0], pw, lane_ref[1] - lane_cand[0], "5", "Compare",
     "test minus\nreference\n\n"
     "yearly heating\nand cooling\n\npeak load and\nits timing\n\n"
     "monthly and\nhourly load\n\nweather events\nkept or lost", fc="#f2f2f4")

# arrows: reference lane
yr = (lane_ref[0] + lane_ref[1]) / 2
arrow(ax, (rx + rw, yr), (ex, yr), lw=0.9, ms=6)
t((rx + rw + ex) / 2, yr + 1.0, "reference weather file, simulated once per building",
  color=MUTED, ha="center", va="bottom", style="italic")
arrow(ax, (ex + ew, yr), (px, yr), lw=0.9, ms=6)
# test lane
yc = lane_cand[0] + 80
arrow(ax, (rx + rw, yc), (mx, yc), lw=0.9, ms=6)
arrow(ax, (mx + mw, yc), (cx, yc), lw=0.9, ms=6)
arrow(ax, (cx + cw, yc), (ex, yc), lw=0.9, ms=6)
arrow(ax, (ex + ew, yc), (px, yc), lw=0.9, ms=6)

S.save(fig, "fig_d_workflow")
