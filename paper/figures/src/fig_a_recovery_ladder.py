"""Fig. A: AMY assembly in smhi2epw and the missing-weather recovery ladder.

Content follows docs/weather_recovery.rst and docs/pipeline.rst (smhi2epw 1.3).
Coordinates are millimetres on a 174 mm double-column canvas.
"""

from __future__ import annotations

import style as S
from matplotlib.patches import Rectangle
from style import INK, MUTED, RUNG, TINT, arrow, box

S.use()
W, H = 174, 150
fig, ax = S.canvas(W, H)
BODY = 6.3
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
        text(x + w - 2, y + 2.0, note, va="bottom", ha="right", fontsize=5.8,
             color=MUTED, style="italic")


# ------------------------------------------------------------- column frame
CS, CSW = 2, 38      # source column
CM, CMW = 46, 72     # meteorology ladder
CQ, CQW = 124, 48    # solar ladder

text(W / 2, H - 2.5, "Inputs aligned on a buffered hourly UTC grid, then filled rung by rung",
     ha="center", va="top", fontsize=7.5, weight="bold")
for x, w, t in ((CS, CSW, "Source"),
                (CM, CMW, "Required meteorology\nT, RH, wind speed, wind direction, QFF"),
                (CQ, CQW, "Solar\nGHI, DNI, DHI")):
    first, *rest = t.split("\n")
    text(x, H - 10.5, first, fontsize=7, weight="bold", va="top")
    if rest:
        text(x, H - 14.0, rest[0], fontsize=6, color=MUTED, va="top")
    ax.plot([x, x + w], [H - 18.2] * 2, color=INK, lw=0.6)

# ------------------------------------------------------------- rows
rows = {  # name: (y_bottom, height)
    1: (112, 16),
    2: (94, 12.5),
    3: (68, 20),
    4: (49.5, 12.5),
    5: (24, 12.5),
}

sources = {
    1: ("SMHI MetObs primary station", "accepted grades G/Y; nearest\nfull-coverage station first\n+ STRÅNG solar model", "primary", "-"),
    2: ("Primary series", "temporal recovery", "neutral", "--"),
    3: ("Nearby SMHI stations", "≤ 75 km, ≤ 3 candidates,\nsame-hour G/Y values", "donor", "-"),
    4: ("Primary series", "temporal recovery", "neutral", "--"),
    5: ("ERA5 via Open-Meteo", "same year, requested\ncoordinates, UTC", "era5", "-"),
}
for n, (title, body, key, ls) in sources.items():
    y, h = rows[n]
    ec = RUNG.get(key, MUTED)
    box(ax, CS, y, CSW, h, fc="white", ec=ec, lw=0.7, ls=ls)
    text(CS + 2, y + h - 2.2, title, fontsize=6.6, weight="bold", va="top",
         color=INK if ls == "-" else MUTED)
    text(CS + 2, y + h - 6.0, body, va="top", fontsize=6.0,
         color=INK if ls == "-" else MUTED)
    arrow(ax, (CS + CSW, y + h / 2), (CM, y + h / 2), color=ec, lw=0.7, ms=5)

y, h = rows[1]
rung(CM, y, CMW, h, 1, "Primary observations",
     "valid observations are kept unchanged;\ninvalid or nonfinite values become gaps", "primary")
y, h = rows[2]
rung(CM, y, CMW, h, 2, "Interpolation, gaps ≤ 3 h",
     "endpoint linear; sine/cosine for wind direction;\none endpoint only: constant boundary value", "interp")
y, h = rows[3]
rung(CM, y, CMW, h, 3, "Assessed donor station",
     "per gap and variable, paired overlap within ±30 days;\n"
     "3 held-out days, ≥ 168 training hours over 7 dates;\n"
     "median offset kept only if held-out MAE ≥ 10 % lower;\n"
     "reject if MAE > 3 °C, 15 pp RH, 3 m/s, 45°, 5 hPa", "donor")
y, h = rows[4]
rung(CM, y, CMW, h, 4, "Daily profiles, gaps ≤ 48 h",
     "nearest 24 h profiles ≤ 7 days on each side,\nadjusted to meet both endpoints", "profile")
y, h = rows[5]
rung(CM, y, CMW, h, 5, "ERA5 reanalysis",
     "unresolved cells only; grid, model and\nresponse hashes recorded", "era5")

# solar ladder: rung 2 spans the temporal/donor rows
y1, h1 = rows[1]
rung(CQ, y1, CQW, h1, 1, "Primary radiation",
     "STRÅNG; GHI scaled by measured\nGHI ≤ 50 km; sample pairs averaged", "solar")
ytop = rows[2][0] + rows[2][1]
ybot = rows[4][0]
rung(CQ, ybot, CQW, ytop - ybot, 2, "Bounded solar filling",
     "day-aware profiles, or GHI\ndecomposed to DNI and DHI\n(Erbs–Driesse, pvlib);\n"
     "geometry integrated at 5 min;\nzero in fully dark intervals", "solar")
text(CQ + CQW / 2, ytop - 33, "no donor transfer:\nsolar stays tied to the\nrequested coordinates",
     ha="center", va="top", fontsize=5.8, color=RUNG["donor"], style="italic")
y5, h5 = rows[5]
rung(CQ, y5, CQW, h5, 3, "ERA5 GHI",
     "complete component groups;\nalready preceding-hour means", "era5")

# "remaining gaps" connectors
def down(x, y0, y1, label=True):
    arrow(ax, (x, y0), (x, y1), lw=0.7, ms=5)
    if label:
        text(x + 1.2, (y0 + y1) / 2, "remaining gaps", fontsize=5.6, color=MUTED,
             style="italic", va="center")

for a, b in ((1, 2), (2, 3), (3, 4), (4, 5)):
    down(CM + 10, rows[a][0], rows[b][0] + rows[b][1], label=b != 5)
down(CQ + 10, rows[1][0], ytop)
down(CQ + 10, ybot, y5 + h5, label=False)

# strict-policy boundary
ys = (rows[4][0] + rows[5][0] + rows[5][1]) / 2
ax.plot([CM - 2, W - 1], [ys, ys], color=INK, lw=0.6, ls=(0, (3, 2)), zorder=0)
text(CM + 12, ys + 0.8, "strict policy stops here and reports remaining gaps",
     ha="left", va="bottom", fontsize=5.8, color=MUTED, style="italic")
text(CM + 12, ys - 0.8, "automatic policy (default) continues to ERA5",
     ha="left", va="top", fontsize=5.8, color=MUTED, style="italic")

# ------------------------------------------------------------- finalise row
yb = 2.0
hb = 17.6
ytie = 22.2
ax.plot([CM + CMW / 2, CM + CMW / 2], [rows[5][0], ytie], color=INK, lw=0.7)
ax.plot([CQ + CQW / 2, CQ + CQW / 2], [rows[5][0], ytie], color=INK, lw=0.7)
ax.plot([CS + 8, CQ + CQW / 2], [ytie, ytie], color=INK, lw=0.7)
arrow(ax, (CS + 8, ytie), (CS + 8, yb + hb), lw=0.7, ms=5)

steps = [
    ("Derive", "dew point, longwave;\ncloud as IR proxy", 28),
    ("Check", "ordered complete hours,\nranges, Td ≤ T, solar\nclosure, dark = 0", 30),
    ("Warn", "source-boundary jumps\n>10 °C, 40 pp, 15 m/s,\n1,000 Pa (review)", 30),
    ("Shift", "fixed whole-hour\nLST, no DST", 22),
]
x = CS
for t, b, w in steps:
    box(ax, x, yb, w, hb, fc=TINT["neutral"], ec=INK, lw=0.6)
    text(x + 2, yb + hb - 2.2, t, fontsize=6.8, weight="bold", va="top")
    text(x + 2, yb + hb - 6.0, b, va="top", fontsize=5.9)
    x2 = x + w + 3.2
    arrow(ax, (x + w, yb + hb / 2), (x2, yb + hb / 2), lw=0.7, ms=5)
    x = x2
wf = W - 1 - x
box(ax, x, yb, wf, hb, fc="white", ec=INK, lw=1.0)
text(x + 2, yb + hb - 2.2, "AMY EPW + JSON sidecar", fontsize=6.8, weight="bold", va="top")
text(x + 2, yb + hb - 6.0, "config, hashes, donors and held-out\nerrors, ERA5 overlap; source share:",
     va="top", fontsize=5.9)
cx = x + 2
for key, t, cw in (("primary", "primary", 9.8), ("interp", "temporal", 11), ("donor", "donor", 8.2),
                   ("era5", "reanalysis", 12.6)):
    box(ax, cx, yb + 1.6, cw, 3.6, t, fc=TINT[key], ec=RUNG[key], lw=0.5, fs=5.6, r=0.6)
    cx += cw + 0.8

S.save(fig, "fig_a_recovery_ladder")
