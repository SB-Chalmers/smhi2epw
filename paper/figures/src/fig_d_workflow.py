"""Fig. D: paired sensitivity-campaign workflow (rerun on current smhi2epw)."""

from __future__ import annotations

import style as S
from style import DIYEPW, INK, MIN_FS, MUTED, RUNG, TINT, arrow, box

S.use()
W, H = 174, 112
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


lane_ref = (86, 110)   # y range of reference lane
lane_cand = (2, 80.5)  # y range of test lane

# column x positions and widths
rx, rw = 2, 28
mx, mw = 34, 27
cx, cw = 65, 44
ex, ew = 113, 32
px, pw = 149, 23

t(mx, lane_cand[1] + 4.6, "Test files: repeated for every gap pattern and filling method",
  color=MUTED, style="italic")

# 1 reference weather (feeds both lanes)
card(rx, lane_cand[0], rw, lane_ref[1] - lane_cand[0], "1", "Reference year",
     "6 regions × 2018,\n2021 and 2023\n(Kiruna 2018 had\nno suitable station)\n\n"
     "at most 1 % of hours\nmissing and no gap\nlonger than 48 h\n\n"
     "those few gaps are\nfilled once and then\nkept fixed\n\n"
     "solar reference:\nmeasured within\n50 km, otherwise\nSTRÅNG")

# 2 withhold
card(mx, lane_cand[0], mw, lane_cand[1] - lane_cand[0], "2", "Hide data",
     "general weather\n(all five variables)\nor solar radiation\n\n"
     "gaps of 3, 12, 48\nor 168 h: one per\nseason in 3 random\ndraws, or one at a\nweather event\n\n"
     "only measured\nvalues are hidden\nand scored; the rest\nof the file is left\nunchanged")

# 3 reconstruct
card(cx, lane_cand[0], cw, lane_cand[1] - lane_cand[0], "3", "Fill the gaps",
     "hidden values stay unseen")
methods = [
    ("straight line only", "neutral", ["straight line across any gap"]),
    ("filling over time", "interp", ["straight line ≤ 3 h,", "daily pattern ≤ 48 h"]),
    ("nearby station", "donor", ["tested donor station"]),
    ("ERA5", "era5", ["reanalysis for each hidden hour;", "also the ERA5-only baseline"]),
    ("diyepw-style", "diyepw", ["straight line up to 6 h;", "7–48 h: the same hour averaged",
                                "over the surrounding 4 weeks;", "longer: ERA5"]),
    ("smhi2epw", "primary", ["full sequence (Fig. 1)"]),
    ("smhi2epw, older order", "profile", ["daily pattern before", "nearby station"]),
]
EDGE = dict(RUNG, diyepw=DIYEPW)
top = lane_cand[1] - 10.2
for name, key, desc in methods:
    ec = EDGE.get(key, MUTED)
    h = 6.6 + LS * (len(desc) - 1)
    yy = top - h
    box(ax, cx + 1.6, yy, cw - 3.2, h, fc=TINT[key], ec=ec, lw=0.6, r=0.7)
    ax.text(cx + 3.0, yy + h - 1.7, name, fontsize=6.8, weight="bold", va="center")
    for k, line in enumerate(desc):
        ax.text(cx + 3.0, yy + h - 4.5 - LS * k, line, fontsize=B, va="center", color=INK)
    top = yy - 0.5

# 4 EnergyPlus (spans both lanes)
card(ex, lane_cand[0], ew, lane_ref[1] - lane_cand[0], "4", "Simulate",
     "EnergyPlus 24.2 with\nideal heating and\ncooling\n\n"
     "same buildings,\nsoftware and ground\ntemperature for\nboth files")
profiles = ["single-family house,\n1961–75", "single-family house,\n2006–21",
            "multi-family block,\n1961–75", "multi-family block,\n2006–21",
            "office, 2006–21,\n60 % glazed", "school, 1976–85"]
yy = lane_cand[0] + 2.0
for p in profiles[::-1]:
    hp = 7.4 if "\n" in p else 5.0
    box(ax, ex + 1.6, yy, ew - 3.2, hp, p, fc=TINT["neutral"], ec=MUTED, lw=0.4,
        fs=B, r=0.6)
    yy += hp + 0.8
t(ex + ew / 2, yy + 3.6, "6 Swedish building types", color=MUTED, ha="center")

# 5 paired metrics
card(px, lane_cand[0], pw, lane_ref[1] - lane_cand[0], "5", "Compare",
     "test minus\nreference, for\neach building and\ngap pattern\n\n"
     "yearly heating\nand cooling\ndemand\n\npeak heating and\ncooling load\n\n"
     "when the peak\noccurs\n\nhour-by-hour\nload error\n\nweather error in\nthe hidden hours\n\n"
     "heatwaves and\ncold spells kept\nor lost", fc=TINT["neutral"])

# arrows: reference lane
yr = (lane_ref[0] + lane_ref[1]) / 2
arrow(ax, (rx + rw, yr), (ex, yr), lw=0.9, ms=6)
t((rx + rw + ex) / 2, yr + 1.0, "reference weather file, simulated once per building",
  color=MUTED, ha="center", va="bottom", style="italic")
arrow(ax, (ex + ew, yr), (px, yr), lw=0.9, ms=6)
# test lane
yc = lane_cand[0] + 68
arrow(ax, (rx + rw, yc), (mx, yc), lw=0.9, ms=6)
arrow(ax, (mx + mw, yc), (cx, yc), lw=0.9, ms=6)
arrow(ax, (cx + cw, yc), (ex, yc), lw=0.9, ms=6)
arrow(ax, (ex + ew, yc), (px, yc), lw=0.9, ms=6)

S.save(fig, "fig_d_workflow")
