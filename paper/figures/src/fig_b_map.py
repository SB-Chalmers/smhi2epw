"""Fig. B: study strata, primary stations, donors and measured-GHI stations.

Station coordinates come from an SMHI MetObs station-metadata snapshot
(data/smhi_metobs_stations_snapshot.csv); with these coordinates the
city-to-primary distances reproduce the campaign table to 0.01 km.
Coastlines and lakes: Natural Earth 1:10m (public domain).
Projection: SWEREF 99 TM (EPSG:3006).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, PathPatch, Rectangle
from matplotlib.path import Path as MPath
from pyproj import Transformer
from shapely.geometry import shape

import style as S
from style import INK, MUTED, RULE, RUNG

S.use()
DATA = Path(__file__).resolve().parents[1] / "data"
tf = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)


def proj(lon, lat):
    x, y = tf.transform(np.asarray(lon), np.asarray(lat))
    return np.asarray(x) / 1000, np.asarray(y) / 1000  # km


LAND = "#f2f1ee"
LAND_SE = "#e6e4df"
WATER = "#ffffff"
LAKE = "#ffffff"
COAST = "#9a9893"

countries = json.loads((DATA / "nordic_countries.geojson").read_text())["features"]
lakes = json.loads((DATA / "nordic_lakes.geojson").read_text())["features"]


def geom_patches(geom, **kw):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for poly in polys:
        verts, codes = [], []
        for ring in [poly.exterior, *poly.interiors]:
            lon, lat = np.asarray(ring.coords).T
            x, y = proj(lon, lat)
            pts = np.column_stack([x, y])
            verts.extend(pts)
            codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 2) + [MPath.CLOSEPOLY])
        out.append(PathPatch(MPath(verts, codes), **kw))
    return out


def draw_base(ax, lw=0.35):
    ax.set_facecolor(WATER)
    for f in countries:
        g = shape(f["geometry"])
        fc = LAND_SE if f["properties"]["iso"] == "SWE" else LAND
        for p in geom_patches(g, fc=fc, ec=COAST, lw=lw, zorder=1):
            ax.add_patch(p)
    for f in lakes:
        for p in geom_patches(shape(f["geometry"]), fc=LAKE, ec=COAST, lw=lw * 0.6, zorder=1.5):
            ax.add_patch(p)


st = pd.read_csv(DATA / "smhi_metobs_stations_snapshot.csv").set_index("id")
sites = pd.read_csv(DATA / "campaign_sites.csv")
sites["ghi_id"] = pd.to_numeric(sites["ghi_id"], errors="coerce")
STRATA = ["Kiruna", "Luleå", "Östersund", "Stockholm", "Gothenburg", "Malmö"]


def has_param(row, p):
    return str(p) in str(row).split(",")


t_from, t_to = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-01-01")
dates_from = pd.to_datetime(st["from_date"], unit="ms")
dates_to = pd.to_datetime(st["to_date"], unit="ms")
active = (dates_from < t_to) & (dates_to >= t_from)
temp_st = st[active & st["parameters"].map(lambda r: has_param(r, 1))]
rad_st = st[active & st["parameters"].map(lambda r: has_param(r, 11))]

# ------------------------------------------------------------------ figure
FH = 160
fig = plt.figure(figsize=(S.DOUBLE, FH * S.MM))
main = fig.add_axes([0.005, 0.085, 0.405, 0.905])
draw_base(main, lw=0.3)
x, y = proj(temp_st["longitude"], temp_st["latitude"])
main.scatter(x, y, s=1.6, c=MUTED, lw=0, zorder=3, alpha=0.8)
x, y = proj(rad_st["longitude"], rad_st["latitude"])
main.scatter(x, y, s=9, marker="^", c=RUNG["solar"], ec=INK, lw=0.3, zorder=4)

HALF = 105  # km; half-width of each inset
insets = {}
for s in STRATA:
    row = sites[sites.stratum == s].iloc[0]
    cx, cy = proj(row.city_lon, row.city_lat)
    pts = []
    for _, r in sites[sites.stratum == s].iterrows():
        for col in ("primary_id", "donor_id", "ghi_id"):
            if pd.notna(r[col]):
                sr = st.loc[int(r[col])]
                pts.append(proj(sr.longitude, sr.latitude))
    pts.append((cx, cy))
    pts = np.array(pts, dtype=float)
    mx, my = (pts.min(0) + pts.max(0)) / 2
    insets[s] = (float(mx), float(my), float(cx), float(cy))
    main.add_patch(Rectangle((mx - HALF, my - HALF), 2 * HALF, 2 * HALF, fc="none",
                             ec=INK, lw=0.5, zorder=5))
    main.plot(cx, cy, marker="*", ms=6.5, mfc=INK, mec="white", mew=0.4, zorder=6)
    off = {"Gothenburg": (12, 30, "left"), "Malmö": (12, 0, "left"),
           "Stockholm": (12, -8, "left"), "Östersund": (-12, 16, "right"),
           "Luleå": (12, -4, "left"), "Kiruna": (-12, -30, "right")}[s]
    main.text(mx + (HALF + 8) * np.sign(off[0]) , my + off[1], s, ha=off[2], va="center",
              fontsize=7, weight="bold", zorder=7)

main.set_xlim(150, 960)
main.set_ylim(6040, 7660)
main.set_aspect("equal")
main.set_xticks([])
main.set_yticks([])
for sp in main.spines.values():
    sp.set_visible(True)
    sp.set_linewidth(0.5)
main.text(0.02, 0.99, "a", transform=main.transAxes, fontsize=9, weight="bold", va="top")
# scale bar
main.plot([700, 900], [6170, 6170], color=INK, lw=1.2, solid_capstyle="butt", zorder=8)
main.text(800, 6185, "200 km", ha="center", va="bottom", fontsize=6)
main.legend(handles=[
    Line2D([], [], ls="", marker="*", ms=6.5, mfc=INK, mec="white", label="stratum city"),
    Line2D([], [], ls="", marker="o", ms=2, mfc=MUTED, mec="none",
           label="SMHI air-temperature station"),
    Line2D([], [], ls="", marker="^", ms=4, mfc=RUNG["solar"], mec=INK, mew=0.3,
           label="SMHI radiation station"),
], loc="upper left", bbox_to_anchor=(0.0, 0.955), frameon=True, fontsize=5.8,
    facecolor="white", edgecolor="none", framealpha=0.85,
    handletextpad=0.3, borderaxespad=0.2, labelspacing=0.5)

# ------------------------------------------------------------------ insets
ncol, nrow = 2, 3
SIDE = 46.0  # mm
iw, ih = SIDE / 174, SIDE / FH
gx, gy = 3.0 / 174, 3.5 / FH
x0 = 1 - 0.002 - 2 * iw - gx
top = 0.99
YEARS = (2018, 2021, 2023)
LABEL = {  # station id: (dx km, dy km, ha, va)
    179960: (-6, 8, "right", "bottom"),   # Nikkaluokta
    180940: (8, 8, "left", "bottom"),     # Kiruna airport
    180760: (6, -6, "left", "top"),       # Gällivare
    162860: (8, -6, "left", "top"),       # Luleå-Kallax
    124300: (6, 6, "left", "bottom"),     # Klövsjöhöjden
    136090: (6, 6, "left", "bottom"),     # Krångede
    97400: (6, 6, "left", "bottom"),      # Arlanda
    72420: (8, 0, "left", "center"),      # Landvetter
    62040: (6, 6, "left", "bottom"),      # Helsingborg
    54290: (-4, 8, "right", "bottom"),    # Skillinge
    52240: (8, -6, "left", "top"),        # Falsterbo
}
for i, s in enumerate(STRATA):
    c, r = i % ncol, i // ncol
    ax = fig.add_axes([x0 + c * (iw + gx), top - (r + 1) * ih - r * gy, iw, ih])
    draw_base(ax, lw=0.4)
    mx, my, cx, cy = insets[s]
    rows = sites[sites.stratum == s]
    # group years sharing a primary
    groups = {}
    for _, rr in rows.iterrows():
        groups.setdefault(int(rr.primary_id), []).append(rr)
    for pid, rs in groups.items():
        p = st.loc[pid]
        px, py = proj(p.longitude, p.latitude)
        supported = any(bool(rr.supported) for rr in rs)
        ax.add_patch(Circle((px, py), 75, fc="none", ec=RUNG["donor"], lw=0.4,
                            ls=(0, (2.5, 2)), alpha=0.45, zorder=2))
        for rr in rs:
            d = st.loc[int(rr.donor_id)]
            dx, dy = proj(d.longitude, d.latitude)
            ax.plot([px, dx], [py, dy], color=RUNG["donor"], lw=0.7,
                    ls="-" if rr.supported else ":", zorder=3)
            if pd.notna(rr.ghi_id):
                g = st.loc[int(rr.ghi_id)]
                gx_, gy_ = proj(g.longitude, g.latitude)
                ax.plot([px, gx_], [py, gy_], color=RUNG["solar"], lw=0.7,
                        ls="-" if rr.supported else ":", zorder=3)
    # markers after links
    drawn = set()
    for _, rr in rows.iterrows():
        for col, mk, fc, size in (("donor_id", "D", RUNG["donor"], 3.4),
                                  ("ghi_id", "^", RUNG["solar"], 4.2)):
            if pd.isna(rr[col]) or (col, int(rr[col])) in drawn:
                continue
            drawn.add((col, int(rr[col])))
            q = st.loc[int(rr[col])]
            qx, qy = proj(q.longitude, q.latitude)
            ax.plot(qx, qy, marker=mk, ms=size, mfc=fc, mec=INK, mew=0.35, zorder=5)
    for pid, rs in groups.items():
        p = st.loc[pid]
        px, py = proj(p.longitude, p.latitude)
        ok = [rr for rr in rs if rr.supported]
        ax.plot(px, py, marker="o", ms=5.2, mfc=RUNG["primary"] if ok else "white",
                mec=INK, mew=0.6, zorder=6)
        yrs = ", ".join(str(rr.year) + ("" if rr.supported else "†") for rr in rs)
        name = p["name"].replace(" Flygplats", "").replace("Göteborg-", "").replace("Stockholm-", "")
        lab = f"{name}\n{yrs}" if len(rs) < 3 else name
        dx, dy, ha, va = LABEL.get(pid, (6, 5, "left", "bottom"))
        ax.text(px + dx, py + dy, lab, fontsize=5.6, ha=ha, va=va, zorder=7, linespacing=1.15,
                bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.4))
    ax.plot(cx, cy, marker="*", ms=7.0, mfc=INK, mec="white", mew=0.5, zorder=5.5)
    ax.set_xlim(mx - HALF, mx + HALF)
    ax.set_ylim(my - HALF, my + HALF)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.5)
    letter = "bcdefg"[i]
    allyears = len(groups) == 1
    ax.text(0.03, 0.97, f"{letter}  {s}" + ("  (all years)" if allyears else ""),
            transform=ax.transAxes, fontsize=7, weight="bold", va="top",
            bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.6))
    ax.plot([mx + HALF - 62, mx + HALF - 12], [my - HALF + 10] * 2, color=INK, lw=1.0,
            solid_capstyle="butt", zorder=8)
    ax.text(mx + HALF - 37, my - HALF + 13, "50 km", ha="center", va="bottom",
            fontsize=5.4, zorder=8)

handles = [
    Line2D([], [], ls="", marker="o", ms=5, mfc=RUNG["primary"], mec=INK, mew=0.6,
           label="primary station (reference years)"),
    Line2D([], [], color=RUNG["donor"], marker="D", ms=3.4, mfc=RUNG["donor"], mec=INK,
           mew=0.35, lw=0.7, label="fixed donor"),
    Line2D([], [], color=RUNG["solar"], marker="^", ms=4.2, mfc=RUNG["solar"], mec=INK,
           mew=0.35, lw=0.7, label="measured-GHI station (≤ 50 km)"),
    Line2D([], [], color=RUNG["donor"], lw=0.5, ls=(0, (2.5, 2)),
           label="75 km donor search radius"),
    Line2D([], [], ls="", marker="o", ms=5, mfc="white", mec=INK, mew=0.6,
           label="† Kiruna 2018: no eligible reference"),
]
fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 0.0), ncol=3,
           frameon=False, fontsize=5.8, handletextpad=0.4, columnspacing=1.2,
           labelspacing=0.4)

S.save(fig, "fig_b_map")
