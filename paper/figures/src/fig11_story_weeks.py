"""Two example weeks: Malmo 2021 heatwave and Ostersund 2021 cold spell, school.

Round 7 colours: nearby station and ERA5 in their method colours, measured black.
Data: story/8-story-hourly.csv from the campaign's round-2 post-analysis
(postanalysis.story_cases in epsm_studies).

Usage::

    python fig11_story_weeks.py STYLE_DIR 8-story-hourly.csv OUT_STEM
"""
import sys; sys.path.insert(0, sys.argv[1])
import style as S
import matplotlib, matplotlib.pyplot as plt, pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
S.use()
FS = 7
NEAR, ERA5 = S.SRC["nearby"], S.SRC["era5"]


def minus(s):
    return s.replace("-", "−")


def panel_title(ax, letter, title, finding):
    ax.text(0, 1.12 + 0.075 * finding.count("\n"), f"{letter}  {title}", transform=ax.transAxes, fontsize=8,
            va="bottom")
    ax.text(0, 1.03, finding, transform=ax.transAxes, fontsize=FS, va="bottom")


d = pd.read_csv(sys.argv[2], parse_dates=["lst"])
d["lst"] = d.lst + pd.Timedelta(hours=1)  # plot at hour ending, as the peak labels
style = {"reference": ("measured", S.INK, 1.0, "-"),
         "automatic": ("nearby station (stepwise, no switch)", NEAR, 0.9, (0, (3, 1.5))),
         "era5": ("ERA5 only (what the stepwise method uses)", ERA5, 0.9, "-")}
zord = {"reference": 4, "automatic": 3, "era5": 2}
fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, 120 * S.MM), sharex="col", gridspec_kw={"height_ratios": [1, 1.15]})
fig.subplots_adjust(left=0.075, right=0.99, top=0.86, bottom=0.15, wspace=0.22, hspace=0.36)
titles = {"malmo": (("Malmö 2021 heatwave", "the nearby station overshoots the hottest hours"),
                    ("School cooling load", "the nearby station adds 21.5 W/m² to the peak"), "cooling"),
          "ostersund": (("Östersund 2021 cold spell",
                         "both fills run too cold; the nearby station's\ncoldest hour is 12 °C too low"),
                        ("School heating load", "both fills raise the peak, the nearby station most"), "heating")}
letters = iter("abcd")
for j, site in enumerate(("malmo", "ostersund")):
    g = d.loc[d.site_id.eq(site)]
    t_title, l_title, mode = titles[site]
    hidden = g.loc[g.hidden, "lst"]
    for ax in axes[:, j]:
        ax.axvspan(hidden.min() - pd.Timedelta(hours=1), hidden.max(), color=S.GREY["pale"], lw=0, zorder=0)
        ax.grid(axis="y", color=S.RULE, lw=0.4, zorder=0)
        ax.set_axisbelow(True)
    for k, (_, col, lw, ls) in style.items():
        axes[0, j].plot(g.lst, g[f"dry_bulb_{k}"], color=col, lw=lw, ls=ls, zorder=zord[k])
        axes[1, j].plot(g.lst, g[f"{mode}_w_m2_{k}"], color=col, lw=lw, ls=ls, zorder=zord[k])
    t = g.loc[g.hidden]
    ref_t = t.dry_bulb_reference.max() if mode == "cooling" else t.dry_bulb_reference.min()
    i = t.dry_bulb_automatic.idxmax() if mode == "cooling" else t.dry_bulb_automatic.idxmin()
    fill_t = g.loc[i, "dry_bulb_automatic"]
    axes[0, j].annotate(minus(f"{'hottest' if mode == 'cooling' else 'coldest'} hour: {fill_t:.1f} °C filled\n"
                              f"vs {ref_t:.1f} °C measured"), (g.loc[i, "lst"], fill_t),
                        xytext=(22, -4) if mode == "cooling" else (8, 10), textcoords="offset points",
                        fontsize=FS, color=NEAR, va="center",
                        arrowprops=dict(arrowstyle="-", color=NEAR, lw=0.5, shrinkA=1, shrinkB=0.5))
    ax = axes[1, j]
    ref_peak = g[f"{mode}_w_m2_reference"].max()
    for k in ("automatic", "era5"):
        col = f"{mode}_w_m2_{k}"
        ii = g[col].idxmax()
        x, y = g.loc[ii, "lst"], g.loc[ii, col]
        right = k == "automatic" or mode == "cooling"
        ax.plot(x, y, marker="o", ms=3, color=style[k][1], zorder=5)
        ax.annotate(minus(f"{y - ref_peak:+.1f} W/m²"), (x, y), xytext=(5, 0) if right else (-5, 0),
                    textcoords="offset points", ha="left" if right else "right", va="center", fontsize=FS,
                    color=style[k][1])
    ax.text(0.02, 0.97, minus(f"measured peak {ref_peak:.1f} W/m²") + "; labels give the filled peak minus this",
            transform=ax.transAxes, ha="left", va="top", fontsize=FS, color=S.INK)
    panel_title(axes[0, j], next(letters), *t_title)
    axes[0, j].set_ylabel("outdoor air temperature, °C")
    axes[1, j].set_ylabel(f"school {mode} load, W/m²")
    panel_title(ax, next(letters), *l_title)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=2))
    ax.set_ylim(0, g[[f"{mode}_w_m2_{k}" for k in style]].max().max() * 1.3)
handles = [Line2D([], [], color=c, lw=lw, ls=ls, label=lab) for lab, c, lw, ls in style.values()]
handles.append(Patch(fc=S.GREY["pale"], ec="none", label="hidden week (1-week gap)"))
fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=2, frameon=False, fontsize=FS,
           handlelength=2.2, columnspacing=2.5)
fig.savefig(sys.argv[3] + ".png", dpi=600, facecolor=S.PAPER); fig.savefig(sys.argv[3] + ".pdf", facecolor=S.PAPER)
