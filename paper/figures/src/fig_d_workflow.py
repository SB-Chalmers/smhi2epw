"""Fig. 2: the paired test workflow (round 2: Table 6 method names, neutral fills)."""

from __future__ import annotations

import style as S
from style import ACCENT, INK, MIN_FS, MUTED, arrow, box

S.use()
W, H = 174, 92
fig, ax = S.canvas(W, H)
B = MIN_FS
LS = 2.95  # mm between lines of 7 pt text


def t(x, y, s, **kw):
    kw.setdefault("fontsize", B)
    kw.setdefault("color", INK)
    kw.setdefault("linespacing", 1.3)
    kw.setdefault("va", "top")
    ax.text(x, y, s, **kw)


def card(x, y, w, h, n, title, body, *, fc="white", ec=INK, lw=0.8):
    box(ax, x, y, w, h, fc=fc, ec=ec, lw=lw)
    ax.text(x + 2, y + h - 2.0, n, fontsize=7.5, weight="bold", va="top", color=MUTED)
    ax.text(x + 6.2, y + h - 2.0, title, fontsize=7.5, weight="bold", va="top")
    if body:
        t(x + 2, y + h - 7.4, body)


lane_ref = (70, 90)   # y range of reference lane
lane_cand = (2, 63)  # y range of test lane

# column x positions and widths
rx, rw = 2, 27
mx, mw = 33, 27
cx, cw = 64, 46
ex, ew = 114, 27
px, pw = 145, 27

t(mx, lane_cand[1] + 4.2, "Test files: repeated for every gap pattern and filling method",
  color=MUTED, style="italic")

# 1 reference weather (feeds both lanes)
card(rx, lane_cand[0], rw, lane_ref[1] - lane_cand[0], "1", "Reference year",
     "6 regions ×\n2018, 2021, 2023\n(Kiruna 2018:\nno suitable station)\n\n"
     "≤1% of hours\nmissing, no gap\nover 48 h\n\n"
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
methods = ["Stepwise", "Stepwise, no switch", "Stepwise, patterns first", "Interpolation then patterns",
           "Nearby station (checked)", "ERA5 only", "Four-week average", "Linear interpolation only"]
top = lane_cand[1] - 12.0
for name in methods:
    step = name == "Stepwise"
    h = 5.0
    yy = top - h
    key = {"Stepwise": "gap_type_rule", "Nearby station (checked)": "donor_assessed", "ERA5 only": "era5",
           "Four-week average": "diyepw_style", "Linear interpolation only": "linear_only"}.get(name)
    mc = S.METHOD[key][1] if key else MUTED
    box(ax, cx + 1.6, yy, cw - 3.2, h, fc="#e8f1f8" if step else "white",
        ec=mc, lw=0.9 if key else 0.5, r=0.7)
    ax.text(cx + 3.0, yy + h / 2, name, fontsize=B, weight="bold" if step else "normal", va="center",
            color=ACCENT if step else INK)
    top = yy - 0.75

# 4 EnergyPlus (spans both lanes)
card(ex, lane_cand[0], ew, lane_ref[1] - lane_cand[0], "4", "Simulate",
     "EnergyPlus 24.2,\nideal heating\nand cooling\n\nsame building\nfor both files\n\n"
     "6 building types:\nhouses 1961–75\nand 2006–21,\napartments 1961–75\nand 2006–21,\noffice 2006–21,\nschool 1976–85")

# 5 paired metrics
card(px, lane_cand[0], pw, lane_ref[1] - lane_cand[0], "5", "Compare",
     "test minus\nreference\n\n"
     "yearly heating\nand cooling\n\npeak load and\nits timing\n\n"
     "monthly and\nhourly load\n\nweather events\nkept or lost")

# arrows: reference lane
yr = (lane_ref[0] + lane_ref[1]) / 2
arrow(ax, (rx + rw, yr), (ex, yr), lw=0.9, ms=6)
t((rx + rw + ex) / 2, yr + 1.0, "reference weather file, simulated once per building",
  color=MUTED, ha="center", va="bottom", style="italic")
arrow(ax, (ex + ew, yr), (px, yr), lw=0.9, ms=6)
# test lane
yc = lane_cand[0] + 48
arrow(ax, (rx + rw, yc), (mx, yc), lw=0.9, ms=6)
arrow(ax, (mx + mw, yc), (cx, yc), lw=0.9, ms=6)
arrow(ax, (cx + cw, yc), (ex, yc), lw=0.9, ms=6)
arrow(ax, (ex + ew, yc), (px, yc), lw=0.9, ms=6)

S.save(fig, "fig_d_workflow")
