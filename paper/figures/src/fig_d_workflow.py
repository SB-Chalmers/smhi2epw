"""Fig. D: paired sensitivity-campaign workflow (epsm_workflows archive/2026-10-14)."""

from __future__ import annotations

import style as S
from style import INK, MUTED, RUNG, TINT, arrow, box

S.use()
W, H = 174, 92
fig, ax = S.canvas(W, H)
B = 6.0


def t(x, y, s, **kw):
    kw.setdefault("fontsize", B)
    kw.setdefault("color", INK)
    kw.setdefault("linespacing", 1.3)
    kw.setdefault("va", "top")
    ax.text(x, y, s, **kw)


def card(x, y, w, h, n, title, body, *, fc="white", ec=INK, lw=0.8):
    box(ax, x, y, w, h, fc=fc, ec=ec, lw=lw)
    ax.text(x + 2, y + h - 2.0, n, fontsize=7.5, weight="bold", va="top", color=MUTED)
    ax.text(x + 6.2, y + h - 2.0, title, fontsize=7, weight="bold", va="top")
    if body:
        t(x + 2, y + h - 7.2, body)


lane_ref = (66, 90)   # y range of reference lane
lane_cand = (10, 58)   # y range of candidate lane

# lane labels
t(40, lane_cand[1] + 4.2, "Candidate lane, repeated for every mask and method",
  fontsize=6.3, color=MUTED, style="italic")

# 1 reference weather (feeds both lanes)
rx, rw = 2, 33
card(rx, lane_cand[0], rw, lane_ref[1] - lane_cand[0], "1", "Reference AMY",
     "6 strata × 2018, 2021, 2023\n17 eligible site-years\n(Kiruna 2018 unsupported)\n\n"
     "≤ 1 % missing required\ncells, no native gap > 48 h\n\nnative gaps filled once\nand frozen as background\n\n"
     "hybrid solar reference:\nmeasured GHI ≤ 50 km or\nSTRÅNG; STRÅNG split")

# 2 masks
mx, mw = 41, 30
card(mx, lane_cand[0], mw, lane_cand[1] - lane_cand[0], "2", "Withhold",
     "scopes: meteorology\n(5 variables) or solar\n(GHI + direct)\n\n"
     "blocks of 3, 12, 48, 168 h\nrandom seasonal × 3 seeds\nor event-centred\n\n"
     "only original G/Y values\nare withheld and scored;\nall other cells identical\nto the reference")

# 3 reconstruct
cx, cw = 77, 33
card(cx, lane_cand[0], cw, lane_cand[1] - lane_cand[0], "3", "Reconstruct",
     "context excludes hidden cells")
methods = [("temporal", "interp", "≤ 3 h interp. + ≤ 48 h profiles"),
           ("donor (assessed)", "donor", "fixed donor, overlap test"),
           ("ERA5", "era5", "hidden cells only"),
           ("automatic", "primary", "full ladder (Fig. A)"),
           ("automatic, legacy", "profile", "profiles before donors")]
yy = lane_cand[1] - 18.0
for name, key, desc in methods:
    box(ax, cx + 2, yy, cw - 4, 6.0, fc=TINT[key], ec=RUNG[key], lw=0.6, r=0.7)
    ax.text(cx + 3.6, yy + 4.2, name, fontsize=5.9, weight="bold", va="center")
    ax.text(cx + 3.6, yy + 1.7, desc, fontsize=5.2, va="center", color=INK)
    yy -= 6.9

# 4 EnergyPlus (spans both lanes)
ex, ew = 116, 25
card(ex, lane_cand[0], ew, lane_ref[1] - lane_cand[0], "4", "Simulate",
     "EnergyPlus 24.2\nideal loads, no\nhumidity control\n\nsame models,\nengine and\nground boundary\nin both lanes")
profiles = ["detached, old, light", "detached, new, heavy", "multi-family, old",
            "multi-family, new", "office, glazed", "school, daytime"]
yy = lane_cand[0] + 2.0
for p in profiles[::-1]:
    box(ax, ex + 1.8, yy, ew - 3.6, 4.4, p, fc=TINT["neutral"], ec=MUTED, lw=0.4,
        fs=5.2, r=0.6)
    yy += 5.2
t(ex + ew / 2, yy + 3.3, "6 building profiles", fontsize=5.7, color=MUTED, ha="center")

# 5 paired metrics
px, pw = 147, 25
card(px, lane_cand[0], pw, lane_ref[1] - lane_cand[0], "5", "Compare",
     "candidate − reference\nper building and mask\n\n"
     "annual heating and\ncooling demand\n\npeak load magnitude\n(exposed peaks)\n\n"
     "peak timing shift\n\nhourly load MAE,\nmask + 168 h\n\nweather errors on\nhidden hours\n\n"
     "heatwave and cold-\nspell preservation", fc=TINT["neutral"])

# arrows: reference lane
yr = (lane_ref[0] + lane_ref[1]) / 2
arrow(ax, (rx + rw, yr), (ex, yr), lw=0.9, ms=6)
t((rx + rw + ex) / 2, yr + 1.0, "reference EPW, simulated once per profile",
  fontsize=5.8, color=MUTED, ha="center", va="bottom", style="italic")
arrow(ax, (ex + ew, yr), (px, yr), lw=0.9, ms=6)
# candidate lane
yc = lane_cand[0] + 30
arrow(ax, (rx + rw, yc), (mx, yc), lw=0.9, ms=6)
arrow(ax, (mx + mw, yc), (cx, yc), lw=0.9, ms=6)
arrow(ax, (cx + cw, yc), (ex, yc), lw=0.9, ms=6)
t((cx + cw + ex) / 2, yc + 1.0, "EPW", fontsize=5.8, color=MUTED, ha="center",
  va="bottom", style="italic")
arrow(ax, (ex + ew, yc), (px, yc), lw=0.9, ms=6)

# scale footer
t(2, 7.4, "Scale: 9,450 unique annual runs (18,366 labelled outcomes); "
  "automatic vs reference: 4,146 building comparisons over 691 masks "
  "(2,058 meteorological, 2,088 solar).\nQuantiles describe these scenarios, not population intervals.",
  fontsize=5.6, color=MUTED, va="top")

S.save(fig, "fig_d_workflow")
