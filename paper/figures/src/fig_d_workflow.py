"""Fig. D: paired sensitivity-campaign workflow (rerun on current smhi2epw)."""

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


lane_ref = (68, 90)   # y range of reference lane
lane_cand = (2, 60)   # y range of test lane

t(36, lane_cand[1] + 4.2, "Test files: repeated for every gap pattern and filling method",
  fontsize=6.3, color=MUTED, style="italic")

# 1 reference weather (feeds both lanes)
rx, rw = 2, 29
card(rx, lane_cand[0], rw, lane_ref[1] - lane_cand[0], "1", "Reference year",
     "6 regions × 2018,\n2021 and 2023\n(Kiruna 2018 had no\nsuitable station)\n\n"
     "at most 1 % of hours\nmissing and no gap\nlonger than 48 h\n\n"
     "those few gaps are\nfilled once and then\nkept fixed\n\n"
     "solar reference:\nmeasured within 50 km,\notherwise STRÅNG")

# 2 withhold
mx, mw = 36, 28
card(mx, lane_cand[0], mw, lane_cand[1] - lane_cand[0], "2", "Hide data",
     "general weather (all\nfive variables) or\nsolar radiation\n\n"
     "gaps of 3, 12, 48\nor 168 h: one per\nseason in 3 random\ndraws, or one around\na weather event\n\n"
     "only measured values\nare hidden and scored;\nthe rest of the file is\nleft unchanged")

# 3 reconstruct
cx, cw = 69, 36
card(cx, lane_cand[0], cw, lane_cand[1] - lane_cand[0], "3", "Fill the gaps",
     "hidden values stay unseen")
methods = [
    ("straight line only", "neutral", ["straight line across any gap"]),
    ("filling over time", "interp", ["straight line ≤ 3 h, daily pattern ≤ 48 h"]),
    ("nearby station", "donor", ["tested donor station"]),
    ("ERA5", "era5", ["reanalysis for every hidden hour;", "also the ERA5-only baseline"]),
    ("diyepw-style", "solar", ["straight line up to 6 h; for 7–48 h,", "the same hour averaged over the", "surrounding 4 weeks; longer: ERA5"]),
    ("smhi2epw", "primary", ["full sequence (Fig. 1)"]),
    ("smhi2epw, older order", "profile", ["daily pattern before nearby station"]),
]
top = lane_cand[1] - 10.0
for name, key, desc in methods:
    ec = RUNG.get(key, MUTED)
    h = 5.2 + 2.2 * (len(desc) - 1)
    yy = top - h
    box(ax, cx + 1.8, yy, cw - 3.6, h, fc=TINT[key], ec=ec, lw=0.6, r=0.7)
    ax.text(cx + 3.2, yy + h - 1.6, name, fontsize=5.7, weight="bold", va="center")
    for k, line in enumerate(desc):
        ax.text(cx + 3.2, yy + h - 3.8 - 2.2 * k, line, fontsize=5.0, va="center", color=INK)
    top = yy - 0.5

# 4 EnergyPlus (spans both lanes)
ex, ew = 110, 33
card(ex, lane_cand[0], ew, lane_ref[1] - lane_cand[0], "4", "Simulate",
     "EnergyPlus 24.2 with\nideal heating and cooling\n\n"
     "same buildings, software\nand ground temperature\nfor both files")
profiles = ["single-family house, 1961–75", "single-family house, 2006–21",
            "multi-family block, 1961–75", "multi-family block, 2006–21",
            "office, 2006–21, 60 % glazed", "school, 1976–85"]
yy = lane_cand[0] + 2.0
for p in profiles[::-1]:
    box(ax, ex + 1.8, yy, ew - 3.6, 4.6, p, fc=TINT["neutral"], ec=MUTED, lw=0.4,
        fs=5.3, r=0.6)
    yy += 5.4
t(ex + ew / 2, yy + 3.3, "6 Swedish building types", fontsize=5.8, color=MUTED, ha="center")

# 5 paired metrics
px, pw = 148, 24
card(px, lane_cand[0], pw, lane_ref[1] - lane_cand[0], "5", "Compare",
     "test minus reference,\nfor each building\nand gap pattern\n\n"
     "yearly heating and\ncooling demand\n\npeak heating and\ncooling load\n\n"
     "when the peak occurs\n\nhour-by-hour load\nerror\n\nweather error in\nthe hidden hours\n\n"
     "heatwaves and cold\nspells kept or lost", fc=TINT["neutral"])

# arrows: reference lane
yr = (lane_ref[0] + lane_ref[1]) / 2
arrow(ax, (rx + rw, yr), (ex, yr), lw=0.9, ms=6)
t((rx + rw + ex) / 2, yr + 1.0, "reference weather file, simulated once per building",
  fontsize=5.8, color=MUTED, ha="center", va="bottom", style="italic")
arrow(ax, (ex + ew, yr), (px, yr), lw=0.9, ms=6)
# test lane
yc = lane_cand[0] + 50
arrow(ax, (rx + rw, yc), (mx, yc), lw=0.9, ms=6)
arrow(ax, (mx + mw, yc), (cx, yc), lw=0.9, ms=6)
arrow(ax, (cx + cw, yc), (ex, yc), lw=0.9, ms=6)
arrow(ax, (ex + ew, yc), (px, yc), lw=0.9, ms=6)

S.save(fig, "fig_d_workflow")
