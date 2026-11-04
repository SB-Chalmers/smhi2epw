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
    "donor": "#D55E00",  # assessed donor stations
    "profile": "#009E73",  # <= 48 h daily profiles
    "era5": "#CC79A7",  # ERA5 via Open-Meteo
    "solar": "#E69F00",  # solar branch accent
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
MIN_FS = 6.5  # smallest text size at final print size, pt

SEASON = {"DJF": "#e8eef7", "MAM": "#eaf4ea", "JJA": "#fbf1df", "SON": "#f5e9e1"}


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


# Filling methods in result plots: plain labels and colours tied to the rungs.
METHOD = {
    "linear_only": ("straight line only", "#a1a1a6"),
    "temporal": ("filling over time", RUNG["interp"]),
    "donor_assessed": ("nearby station", RUNG["donor"]),
    "era5": ("ERA5 only", RUNG["era5"]),
    "diyepw_style": ("diyepw-style", DIYEPW),
    "automatic_legacy": ("smhi2epw, older order", RUNG["profile"]),
    "automatic": ("smhi2epw 1.3", "#636366"),
    "gap_type_rule": ("smhi2epw", INK),
}
GAP_LABEL = {3: "3 h", 12: "12 h", 48: "2 days", 168: "1 week"}
SAMPLING_LABEL = {"random_seasonal": "random gaps", "weather_extremes": "gaps at weather events"}
