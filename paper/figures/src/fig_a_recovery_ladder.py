"""Fig. A: AMY assembly in smhi2epw and the missing-weather recovery ladder.

Content follows docs/weather_recovery.rst and docs/pipeline.rst (smhi2epw 1.3).
Coordinates are millimetres on a 174 mm double-column canvas.
"""

from __future__ import annotations

import style as S
from matplotlib.patches import Rectangle
from style import INK, MUTED, RUNG, TINT, arrow, box

S.use()
W, H = 174, 144
fig, ax = S.canvas(W, H)
BODY = 6.5
LINE = 1.32


def text(x, y, t, **kw):
    kw.setdefault("fontsize", BODY)
    kw.setdefault("color", INK)
    kw.setdefault("linespacing", LINE)
    ax.text(x, y, t, **kw)


def rung(x, y, w, h, n, title, body, key, *, note=None):
    box(ax, x, y, w, h, fc=TINT[key], ec=RUNG[key], lw=0.8)
    ax.add_patch(Rectangle((x, y + 0.4), 1.6, h - 0.8, fc=RUNG[key], ec="none", zorder=3))
    text(x + 3.6, y + h - 2.2, str(n), fontsize=7.5, weight="bold",
         color=RUNG[key], va="top")
    text(x + 7.4, y + h - 2.2, title, fontsize=7, weight="bold", va="top")
    text(x + 7.4, y + h - 6.4, body, va="top")
    if note:
        text(x + w - 2, y + 2.0, note, va="bottom", ha="right", fontsize=6.5,
             color=MUTED, style="italic")


# ------------------------------------------------------------- column frame
CS, CSW = 2, 38      # source column
CM, CMW = 46, 70     # meteorology ladder
CQ, CQW = 124, 48    # solar ladder

for x, w, t in ((CS, CSW, "Data source\nweather station, model or reanalysis"),
                (CM, CMW, "General weather\nair temperature, humidity, wind, air pressure"),
                (CQ, CQW, "Solar radiation\nglobal, direct and diffuse")):
    first, *rest = t.split("\n")
    text(x, H - 2.5, first, fontsize=7.2, weight="bold", va="top")
    if rest:
        text(x, H - 6.3, rest[0], fontsize=6.5, color=MUTED, va="top")
    ax.plot([x, x + w], [H - 10.8] * 2, color=INK, lw=0.6)

# ------------------------------------------------------------- rows
rows = {  # name: (y_bottom, height)
    1: (112, 16),
    2: (94, 12.5),
    3: (65, 23),
    4: (46.5, 12.5),
    5: (25.5, 12.5),
}

sources = {
    1: ("SMHI weather station", "quality-approved values;\nfull-year station preferred;\nsolar: measured, or STRÅNG", "primary", "-"),
    2: ("Same station", "its own record", "neutral", "--"),
    3: ("Nearby SMHI stations", "up to 3 within 75 km;\nsame-hour approved values", "donor", "-"),
    4: ("Same station", "its own record", "neutral", "--"),
    5: ("ERA5 via Open-Meteo", "modelled weather for the\nsame year and location", "era5", "-"),
}
for n, (title, body, key, ls) in sources.items():
    y, h = rows[n]
    ec = RUNG.get(key, MUTED)
    box(ax, CS, y, CSW, h, fc="white", ec=ec, lw=0.7, ls=ls)
    text(CS + 2, y + h - 2.2, title, fontsize=6.6, weight="bold", va="top",
         color=INK if ls == "-" else MUTED)
    text(CS + 2, y + h - 6.0, body, va="top", fontsize=6.5,
         color=INK if ls == "-" else MUTED)
    arrow(ax, (CS + CSW, y + h / 2), (CM, y + h / 2), color=ec, lw=0.7, ms=5)

y, h = rows[1]
rung(CM, y, CMW, h, 1, "Measured values",
     "valid measurements are never changed;\ninvalid values are treated as gaps", "primary")
y, h = rows[2]
rung(CM, y, CMW, h, 2, "Straight-line fill, gaps ≤ 3 h",
     "straight line between the values either side;\nwith a value on one side only, it is held", "interp")
y, h = rows[3]
rung(CM, y, CMW, h, 3, "Nearby station, gaps ≤ 48 h",
     "used only if it passes a test: the stations are\n"
     "compared within 30 days of the gap and tested\n"
     "on 3 days left out; a fixed correction is kept only\n"
     "if it cuts the error by 10 %; rejected if the average\n"
     "error exceeds 3 °C, 15 % RH, 3 m/s, 45° or 5 hPa", "donor")
y, h = rows[4]
rung(CM, y, CMW, h, 4, "Daily pattern, gaps ≤ 48 h",
     "typical 24 h pattern from up to 7 days either\nside, adjusted to meet the values at both ends", "profile")
y, h = rows[5]
rung(CM, y, CMW, h, 5, "ERA5 reanalysis",
     "only for hours still missing;\nwhich data were used is recorded", "era5")

# solar ladder: measured, STRÅNG, straight line <= 3 h, ERA5
y1, h1 = rows[1]
rung(CQ, y1, CQW, h1, 1, "Measured, then modelled",
     "solar station within 50 km;\nhours it lacks: STRÅNG model,\nscaled to that station", "solar")
y2, h2 = rows[2]
rung(CQ, y2, CQW, h2, 2, "Straight line, gaps ≤ 3 h",
     "sun position every 5 min;\nzero when the sun is down", "interp")
ytop, ybot = y2 + h2, y2
text(CQ + 13, ybot - 4, "gaps over 3 h go to ERA5\n\nnever taken from a nearby\nstation: solar stays tied\nto the chosen location",
     ha="left", va="top", fontsize=6.5, color=MUTED, style="italic")
y5, h5 = rows[5]
rung(CQ, y5, CQW, h5, 3, "ERA5 radiation",
     "all three parts together;\nalready hourly averages", "era5")

# general weather: gaps over 48 h skip the nearby station and daily pattern
xb = CM + CMW + 3.2
yb2 = rows[2][0] + rows[2][1] / 2
yb5 = rows[5][0] + rows[5][1] / 2
ax.plot([CM + CMW, xb, xb], [yb2, yb2, yb5 + 1.5], color=INK, lw=0.7)
arrow(ax, (xb, yb5 + 1.5), (CM + CMW, yb5 + 1.5), lw=0.7, ms=5)
text(xb + 0.7, (rows[3][0] + rows[3][1] + rows[4][0]) / 2, "gaps over 48 h", rotation=90,
     ha="left", va="center", fontsize=6.5, color=MUTED, style="italic")

# "remaining gaps" connectors
def down(x, y0, y1, label=True):
    arrow(ax, (x, y0), (x, y1), lw=0.7, ms=5)
    if label:
        text(x + 1.2, (y0 + y1) / 2, "gaps left", fontsize=6.5, color=MUTED,
             style="italic", va="center")

for a, b in ((1, 2), (2, 3), (3, 4), (4, 5)):
    down(CM + 10, rows[a][0], rows[b][0] + rows[b][1], label=b != 5)
down(CQ + 10, rows[1][0], ytop)
down(CQ + 10, ybot, y5 + h5, label=False)

# strict-policy boundary
ys = (rows[4][0] + rows[5][0] + rows[5][1]) / 2
ax.plot([CM - 2, W - 1], [ys, ys], color=INK, lw=0.6, ls=(0, (3, 2)), zorder=0)
text(CM + 12, ys + 0.8, "strict setting stops here and reports the gaps left",
     ha="left", va="bottom", fontsize=6.5, color=MUTED, style="italic")
text(CM + 12, ys - 0.8, "default setting continues to ERA5",
     ha="left", va="top", fontsize=6.5, color=MUTED, style="italic")

# ------------------------------------------------------------- finalise row
yb = 2.0
hb = 19.6
ytie = 23.4
ax.plot([CM + CMW / 2, CM + CMW / 2], [rows[5][0], ytie], color=INK, lw=0.7)
ax.plot([CQ + CQW / 2, CQ + CQW / 2], [rows[5][0], ytie], color=INK, lw=0.7)
ax.plot([CS + 8, CQ + CQW / 2], [ytie, ytie], color=INK, lw=0.7)
arrow(ax, (CS + 8, ytie), (CS + 8, yb + hb), lw=0.7, ms=5)

steps = [
    ("Derive", "dew point and sky\nradiation; cloud cover\nused only for sky\nradiation", 27),
    ("Check", "every hour present,\nvalues in range, dew\npoint ≤ air temperature,\nsolar parts add up", 29.5),
    ("Flag", "jumps where sources\nmeet: > 10 °C, 40 %\nRH, 15 m/s, 10 hPa;\nfor review only", 27.5),
    ("Shift", "to local standard\ntime (UTC+1),\nno summer time", 21),
]
x = CS
for t, b, w in steps:
    box(ax, x, yb, w, hb, fc=TINT["neutral"], ec=INK, lw=0.6)
    text(x + 2, yb + hb - 2.2, t, fontsize=6.8, weight="bold", va="top")
    text(x + 2, yb + hb - 6.0, b, va="top", fontsize=6.5)
    x2 = x + w + 3.2
    arrow(ax, (x + w, yb + hb / 2), (x2, yb + hb / 2), lw=0.7, ms=5)
    x = x2
wf = W - 1 - x
box(ax, x, yb, wf, hb, fc="white", ec=INK, lw=1.0)
text(x + 2, yb + hb - 2.2, "Weather file + record file", fontsize=6.8, weight="bold", va="top")
text(x + 2, yb + hb - 6.0, "EPW for one actual year; a JSON\nrecord of settings, stations used,\ntest errors and share by source:",
     va="top", fontsize=6.5)
cx = x + 2
for key, t, cw in (("primary", "measured", 12.8), ("interp", "own record", 14.8), ("donor", "nearby", 10.4),
                   ("era5", "ERA5", 8.4)):
    box(ax, cx, yb + 1.6, cw, 3.6, t, fc=TINT[key], ec=RUNG[key], lw=0.5, fs=6.5, r=0.6)
    cx += cw + 0.8

S.save(fig, "fig_a_recovery_ladder")
