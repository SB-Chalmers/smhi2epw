"""Shared style for the gap-filling paper figures.

All figures are drawn with matplotlib and saved as PDF (embedded TrueType),
SVG (editable text) and a 600 dpi PNG preview. Sizes follow a two-column
journal layout: single column 84 mm, double column 174 mm.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

MM = 1 / 25.4
SINGLE = 84 * MM
DOUBLE = 174 * MM

OUT = Path(__file__).resolve().parents[1] / "out"

# Okabe-Ito based roles, kept identical across every figure so a rung has one
# colour in the method diagram and in all result plots.
INK = "#1d1d1f"
MUTED = "#6e6e73"
RULE = "#c7c7cc"
PAPER = "#ffffff"

RUNG = {
    "primary": "#4d4d4d",  # accepted SMHI observations
    "interp": "#0072B2",  # <= 3 h interpolation
    "donor": "#5B2A86",  # assessed donor stations
    "profile": "#009E73",  # <= 48 h daily profiles
    "era5": "#CC79A7",  # ERA5 via Open-Meteo
    "solar": "#a882c8",  # solar branch accent
}
TINT = {
    "primary": "#ececec",
    "interp": "#dcebf6",
    "donor": "#f9e2d3",
    "profile": "#d6f0e8",
    "era5": "#f6e4ef",
    "solar": "#fcefd6",
    "neutral": "#f4f4f6",
}
# diyepw-style gets its own Okabe-Ito sky blue, so orange keeps one meaning
# (the solar branch) across every figure.
DIYEPW = "#56B4E9"
TINT["diyepw"] = "#e1f1fb"
# Categories that are not filling methods (gap placement, seasons, event
# outcomes, peak timing) are drawn in greys, so colour always means a method.
GREY = {"dark": "#3a3a3c", "mid": "#8e8e93", "light": "#c7c7cc", "pale": "#e5e5ea"}
MIN_FS = 7.0  # smallest text size at final print size, pt

SEASON = {"DJF": "#e8e8ec", "MAM": "#f5f5f7", "JJA": "#e8e8ec", "SON": "#f5f5f7"}  # greys: seasons are not methods


def use() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 7.5,
            "axes.titlesize": 8,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "text.color": INK,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.dpi": 600,
            "figure.dpi": 150,
        }
    )


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches=None,
                    facecolor=PAPER)
    plt.close(fig)


def box(ax, x, y, w, h, text="", *, fc=TINT["neutral"], ec=INK, lw=0.7,
        fs=7, weight="normal", r=1.2, color=INK, ha="center", va="center",
        ls="-", z=2, pad_x=None):
    """Rounded box in data coordinates; (x, y) is the lower-left corner."""
    patch = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                           fc=fc, ec=ec, lw=lw, ls=ls, zorder=z, mutation_aspect=1)
    ax.add_patch(patch)
    if text:
        tx = x + w / 2 if ha == "center" else x + (pad_x if pad_x is not None else 2.0)
        ty = y + h / 2 if va == "center" else y + h - 2.0
        ax.text(tx, ty, text, ha=ha, va=va, fontsize=fs, weight=weight,
                color=color, zorder=z + 1, linespacing=1.25)
    return patch


def arrow(ax, p0, p1, *, color=INK, lw=0.8, style="-|>", ms=6, conn="arc3",
          ls="-", z=1, shrink=0):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=ms, color=color,
                        lw=lw, connectionstyle=conn, ls=ls, zorder=z,
                        shrinkA=shrink, shrinkB=shrink)
    ax.add_patch(a)
    return a


def canvas(width_mm, height_mm):
    """Figure whose data coordinates are millimetres from the lower-left corner."""
    fig = plt.figure(figsize=(width_mm * MM, height_mm * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width_mm)
    ax.set_ylim(0, height_mm)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


# Filling methods (round 7): one Okabe-Ito colour per method, the same in every
# figure; colour-blind safe. Stepwise is blue and always drawn strongest.
# The stepwise variants (sensitivity tests) are grey.
ACCENT = "#0072B2"            # Stepwise
ACCENT_SEQ = ["#d6e6f3", "#7fb0d8", ACCENT]   # light to dark blue, for ordered shares
SRC = {"linear": "#E69F00", "nearby": "#D55E00", "patterns": "#009E73", "era5": "#56B4E9",
       "fourweek": "#CC79A7", "stepwise": ACCENT}
OTHER = "#8e8e93"              # variants and non-method marks
OTHER_DARK = "#636366"
METHOD = {
    "gap_type_rule": ("Stepwise", ACCENT),
    "automatic": ("Stepwise, no switch", OTHER),
    "automatic_legacy": ("Stepwise, patterns first", OTHER),
    "temporal": ("Interpolation then patterns", OTHER),
    "donor_assessed": ("Nearby station", SRC["nearby"]),
    "era5": ("ERA5 only", SRC["era5"]),
    "diyepw_style": ("Four-week average", SRC["fourweek"]),
    "linear_only": ("Linear interpolation only", SRC["linear"]),
}
GAP_LABEL = {3: "3 hours", 12: "12 hours", 48: "48 hours", 168: "1 week"}
SAMPLING_LABEL = {"random_seasonal": "random gaps", "weather_extremes": "gaps at weather events"}

# Season colours, shared with the backgrounds of Fig. 4 (gap layout).
SEASON_COL = {"winter": ACCENT, "spring": ACCENT, "summer": ACCENT, "autumn": ACCENT}
SEASON_TINT = {"winter": "#e3ebf5", "spring": "#e4f1e6", "summer": "#fbefd6", "autumn": "#f3e3da"}
SEASON_NAME = {"DJF": "winter", "MAM": "spring", "JJA": "summer", "SON": "autumn"}

# Buildings: one hue, light for recent construction, dark for the 1960s.
BUILDING_ERA_COL = {"SE.06": "#9fcfc9", "SE.03": "#3f8a84", "SE.02": "#17433f"}


def end_labels(ax, items, x, *, min_gap, fs=6.5, dx=0.08):
    """Direct labels at the right end of lines, nudged apart vertically.

    items: list of (y, text, colour, weight). min_gap in data units.
    """
    items = sorted([i for i in items if i[0] == i[0]], key=lambda t: t[0])
    ys = [i[0] for i in items]
    for k in range(1, len(ys)):
        ys[k] = max(ys[k], ys[k - 1] + min_gap)
    # shift the whole stack down if it overflows the top
    top = ax.get_ylim()[1]
    over = ys[-1] - top if ys else 0
    if over > 0:
        ys = [y - over for y in ys]
        for k in range(len(ys) - 2, -1, -1):
            ys[k] = min(ys[k], ys[k + 1] - min_gap)
    for (y0, txt, col, w), y in zip(items, ys):
        ax.text(x + dx, y, txt, fontsize=fs, color=col, weight=w, va="center", ha="left",
                clip_on=False)


# Banded sequential scale for heat maps (light to dark, safe in greyscale print).
BANDS = [0, 1, 5, 20, 1e9]
BAND_COL = ["#eff3f8", "#c6dbef", "#6baed6", "#1f5a96"]
BAND_LAB = ["under 1%", "1–5%", "5–20%", "over 20%"]


def sig2(v):
    """Two significant figures, as used in every table cell."""
    v = float(v)
    return f"{v:.2f}" if v < 1 else (f"{v:.1f}" if v < 10 else f"{v:.0f}")
