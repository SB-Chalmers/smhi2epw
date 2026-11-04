"""Results figures for general-weather gaps (temperature, humidity, pressure,
wind) and solar-radiation gaps (GHI, DNI and DHI hidden together).

Reads paper/figures/source/data/results/*.csv. Figs 6, 7, 8 and 11 have a top
row for general-weather gaps and a bottom row for solar gaps; Figs 9 and 10
show general-weather gaps only. Captions (with the notes that used to sit in
the figures) are in paper/figures/CAPTIONS.md.

Colour rule: colour means a filling method (as in Fig. 1); everything else
(gap placement, season, event outcome, peak timing) is grey. No text is
smaller than style.MIN_FS at print size.

    python fig_results.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import style as S
from style import GAP_LABEL, GREY, INK, METHOD, MIN_FS, RULE

S.use()
RES = Path(__file__).resolve().parents[1] / "source" / "data" / "results"
GAPS = [3, 12, 48, 168]
X = np.arange(len(GAPS))
FS = MIN_FS          # small labels
FS_AX = 7.0          # tick labels and axis titles
MARK = {"linear_only": "s", "temporal": "o", "donor_assessed": "D", "era5": "v",
        "diyepw_style": "^", "automatic_legacy": "P", "automatic": "o"}
# gap placement: random = dark grey, at weather events = light grey with dark edge
SAMP = {"random_seasonal": dict(fc=GREY["dark"], ec=GREY["dark"], med="white", label="random gaps (4 per file)"),
        "weather_extremes": dict(fc=GREY["light"], ec=GREY["dark"], med=INK, label="gaps at weather events (1 per file)")}
N_MIN = 10           # no percentile or share is drawn from fewer cases than this

SCOPES = (("meteorology", "General weather hidden (temperature, humidity, pressure, wind)"),
          ("solar", "Solar radiation hidden (global, direct and diffuse)"))

plt.rcParams.update({"xtick.labelsize": FS_AX, "ytick.labelsize": FS_AX,
                     "axes.labelsize": FS_AX, "legend.fontsize": FS_AX})


def read(name, scope="meteorology"):
    d = pd.read_csv(RES / f"{name}.csv")
    return d[d["scope"] == scope] if "scope" in d else d


def row_title(fig, ax, text, h_mm, up_mm=7.5):
    """Row heading placed up_mm above the top of the row's left panel."""
    bb = ax.get_position()
    fig.text(0.012, bb.y1 + up_mm / h_mm, text, fontsize=7.5, weight="bold",
             color=INK, va="bottom")


def gap_axis(ax, xlabel=True):
    ax.set_xticks(X)
    ax.set_xticklabels([GAP_LABEL[g] for g in GAPS])
    ax.set_xlim(-0.5, len(GAPS) - 0.5)
    if xlabel:
        ax.set_xlabel("length of each gap")
    ax.grid(axis="y", color=RULE, lw=0.4, zorder=0)
    ax.set_axisbelow(True)


def panel_letter(ax, letter, title):
    ax.text(0, 1.04, f"{letter}  {title}", transform=ax.transAxes, fontsize=8,
            weight="bold", va="bottom")


# ------------------------------------------------------------- Fig. 6 annual error
EVENT_FOR = {"heating": ("cold_spell_coldest_hour", "cold spell"),
             "cooling": ("heatwave_hottest_hour", "heatwave")}


def fig_annual():
    H = 118
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.99, top=0.885, bottom=0.12, wspace=0.2, hspace=0.62)
    w = 0.38
    letters = iter("abcd")
    for r, (scope, rtitle) in enumerate(SCOPES):
        ann = read("annual-errors", scope)
        anc = read("annual-errors-by-anchor", scope)
        for ax, mode, title in ((axes[r, 0], "heating", "Yearly heating demand"),
                                (axes[r, 1], "cooling", "Yearly cooling demand")):
            anchor, ev_name = EVENT_FOR[mode]
            series = {
                "random_seasonal": ann[(ann.method == "automatic") & (ann.sampling == "random_seasonal")],
                "weather_extremes": anc[(anc.method == "automatic") & (anc.anchor_name == anchor)],
            }
            top = 0
            for k, (samp, st) in enumerate(SAMP.items()):
                a = series[samp].set_index("gap_hours").loc[GAPS]
                xs = X + (k - 0.5) * w
                p95 = a[f"{mode}_abs_p95_pct"].to_numpy()
                med = a[f"{mode}_abs_median_pct"].to_numpy()
                ax.bar(xs, p95, width=w * 0.92, color=st["fc"], edgecolor=st["ec"], lw=0.7, zorder=3)
                ax.plot(xs, med, ls="", marker="_", ms=7, color=st["med"], mew=1.5, zorder=4)
                for xi, v in zip(xs, p95):
                    ax.text(xi, v, f"{v:.2f}", fontsize=FS, color=INK, ha="center", va="bottom")
                top = max(top, p95.max())
            ax.set_ylim(0, top * 1.16)
            gap_axis(ax)
            panel_letter(ax, next(letters), title)
            ax.set_ylabel("error, % of yearly demand" if mode == "heating" else "")
        row_title(fig, axes[r, 0], rtitle, H)
    handles = [Patch(fc=SAMP["random_seasonal"]["fc"], ec=SAMP["random_seasonal"]["ec"], lw=0.7,
                     label="random gaps (4 per file)"),
               Patch(fc=SAMP["weather_extremes"]["fc"], ec=SAMP["weather_extremes"]["ec"], lw=0.7,
                     label="one gap at a cold spell (heating) or heatwave (cooling)"),
               Line2D([], [], ls="", marker="_", ms=7, mew=1.5, color=INK, label="median")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=3,
               frameon=False, handletextpad=0.4, columnspacing=1.6)
    S.save(fig, "fig06_annual_error")


# ------------------------------------------------------------- Fig. 9 methods
METHOD_ORDER = ["linear_only", "temporal", "diyepw_style", "era5", "automatic_legacy",
                "donor_assessed", "automatic"]
# filling over time is never visible: it lies under the older order (general
# weather) or under smhi2epw (solar) up to 2 days and has no 1-week result.
LEGEND_ORDER = [m for m in METHOD_ORDER if m != "temporal"]
LENS = {"3 h": 3, "12 h": 12, "2 days": 48, "1 week": 168}
ROWS3 = (("full", "meteorology", "General weather hidden: all gaps"),
         ("subset", "meteorology", "General weather hidden: only gaps where a nearby station passed the test (about 40 %)"),
         ("full", "solar", "Solar radiation hidden: all gaps (no nearby-station step)"))


def method_lines(ax, df, col_of, methods, scale=1.0):
    for m in methods:
        d = df[df.method == m].set_index("gap_hours").reindex(GAPS)
        if d[col_of].isna().all():
            continue
        lab, col = METHOD[m]
        donor = m == "donor_assessed"  # drawn dashed on top: it matches smhi2epw on its subset
        ax.plot(X, d[col_of] * scale, color=col, lw=1.6 if m == "automatic" else 1.1,
                ls=(0, (3, 2)) if donor else "-", marker=MARK[m], ms=3.4 if donor else 3.8,
                mfc=col, mec="white", mew=0.4,
                zorder=5 if donor else 4 if m == "automatic" else 3)


def method_legend(fig, top):
    handles = [Line2D([], [], color=METHOD[m][1], marker=MARK[m], ms=3.8, mec="white", mew=0.4,
                      lw=1.6 if m == "automatic" else 1.1,
                      ls=(0, (3, 2)) if m == "donor_assessed" else "-",
                      label=METHOD[m][0] + (" (c, d only)" if m == "donor_assessed" else ""))
               for m in LEGEND_ORDER[::-1]]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.785, top), frameon=False,
               handlelength=2.2, labelspacing=0.8)


def three_rows(name_full, name_subset, value, ylabel, ylim, fname):
    H = 172
    fig, axes = plt.subplots(3, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.085, right=0.77, top=0.92, bottom=0.06, wspace=0.3, hspace=0.62)
    letters = iter("abcdef")
    for r, (kind, scope, rtitle) in enumerate(ROWS3):
        if kind == "full":
            d = read(name_full, scope).copy()
            if "gap_hours" not in d:
                d["gap_hours"] = d["gap_length"].map(LENS)
            if "sampling" in d:
                d = d[d.sampling == "random_seasonal"]
            methods = [m for m in METHOD_ORDER if m != "donor_assessed"]
        else:
            d = read(name_subset, scope)
            d = d[d.sampling == "random_seasonal"]
            methods = METHOD_ORDER
        for ax, mode in ((axes[r, 0], "heating"), (axes[r, 1], "cooling")):
            method_lines(ax, d, value.format(mode=mode), methods,
                         scale=100 if "months" in value else 1.0)
            gap_axis(ax)
            if ylim:
                ax.set_ylim(*ylim)
                ax.set_yticks([0, 20, 40, 60, 80, 100])
            else:
                ax.set_ylim(bottom=0)
            panel_letter(ax, next(letters), ylabel[1].format(mode=mode))
            ax.set_ylabel(ylabel[0] if mode == "heating" else "")
        row_title(fig, axes[r, 0], rtitle, H)
    method_legend(fig, 0.92)
    S.save(fig, fname)


def fig_methods():
    three_rows("method-steps", "method-steps-donor-subset", "{mode}_abs_p95_pct",
               ("95th percentile error,\n% of yearly demand", "Yearly {mode} demand"), None,
               "fig07_methods")


# ------------------------------------------------------------- Fig. 8 where the gap falls
SEASON_GREY = {"winter": GREY["dark"], "spring": GREY["mid"], "autumn": GREY["light"],
               "summer": GREY["mid"]}


def fig_position():
    H = 126
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM),
                             gridspec_kw={"width_ratios": [1.35, 1]})
    fig.subplots_adjust(left=0.085, right=0.99, top=0.885, bottom=0.12, wspace=0.2, hspace=0.6)
    letters = iter("abcd")
    for r, (scope, rtitle) in enumerate(SCOPES):
        gw = read("gap-window", scope)
        a = gw[gw.method == "automatic"]

        def sel(event, season, mode):
            return a[(a.event_type == event) & (a.season == season) & (a["mode"] == mode)] \
                .set_index("gap_hours").reindex(GAPS)
        groups = {
            "heating": [("winter", "random_seasonal", "winter", False),
                        ("spring", "random_seasonal", "spring", False),
                        ("autumn", "random_seasonal", "autumn", False),
                        ("cold spell", "cold_spell_coldest_hour", "winter", True)],
            "cooling": [("summer", "random_seasonal", "summer", False),
                        ("heatwave", "heatwave_hottest_hour", "summer", True)],
        }
        for ax, mode, title in ((axes[r, 0], "heating", "Heating: winter, spring, autumn, cold spells"),
                                (axes[r, 1], "cooling", "Cooling: summer and heatwaves")):
            g = groups[mode]
            w = 0.8 / len(g)
            top = 0
            for k, (name, event, season, hatch) in enumerate(g):
                d = sel(event, season, mode)
                xs = X - 0.4 + w * (k + 0.5)
                win = d["window_abs_p95_pct"].to_numpy()
                ing = d["in_gap_abs_p95_pct"].to_numpy()
                ax.bar(xs, win, width=w * 0.88, color=SEASON_GREY[season], edgecolor=INK, lw=0.4,
                       hatch="////" if hatch else None, zorder=3)
                ax.bar(xs, ing, width=w * 0.3, color="white", edgecolor=INK, lw=0.5, zorder=4)
                top = max(top, np.nanmax(np.maximum(win, ing)))
            ax.set_ylim(0, top * 1.08)
            gap_axis(ax)
            panel_letter(ax, next(letters), title)
            ax.set_ylabel("95th percentile error,\n% of yearly demand" if mode == "heating" else "")
            if r == 0:
                handles = [Patch(fc=SEASON_GREY[season], hatch="////" if h else None, ec=INK, lw=0.4,
                                 label=name) for name, _, season, h in g]
                ax.legend(handles=handles, loc="upper left", frameon=False, ncol=1,
                          handlelength=1.4)
        row_title(fig, axes[r, 0], rtitle, H)
    fig.legend(handles=[Patch(fc=GREY["light"], ec=INK, lw=0.4, label="the gap plus the following week"),
                        Patch(fc="white", ec=INK, lw=0.5, label="inside the gap only (thin white bar)")],
               loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=2, frameon=False)
    S.save(fig, "fig08_gap_position")


# ------------------------------------------------------------- Fig. 6 (doc) peaks
TIMING = [("same peak hour", GREY["dark"]), ("moved up to 24 h", GREY["light"]),
          ("moved more than 24 h", "white")]


def fig_peaks():
    pk = read("peak-errors")
    a = pk[pk.method == "automatic"]
    pc = read("peak-cases")
    pc = pc[pc.method == "automatic"]
    rng = np.random.default_rng(7)
    H = 118
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.085, right=0.99, top=0.935, bottom=0.215, wspace=0.2, hspace=0.55)
    w = 0.42
    for j, mode in enumerate(("heating", "cooling")):
        ax = axes[0, j]
        for k, (samp, st) in enumerate(SAMP.items()):
            xs = X + (k - 0.5) * w
            for xi, g in zip(xs, GAPS):
                v = pc[(pc.sampling == samp) & (pc["mode"] == mode) & (pc.gap_hours == g)] \
                    .abs_peak_error_w_m2.to_numpy()
                n = len(v)
                jit = rng.uniform(-w * 0.32, w * 0.32, n)
                ax.scatter(xi + jit, v, s=4, c=st["fc"], edgecolors=st["ec"], linewidths=0.25,
                           alpha=0.8, zorder=3)
                if n >= N_MIN:
                    med, p95 = np.median(v), np.percentile(v, 95)
                    ax.plot([xi - w * 0.42, xi + w * 0.42], [med, med], color=INK, lw=1.3, zorder=5)
                    ax.plot([xi - w * 0.42, xi + w * 0.42], [p95, p95], color=INK, lw=0.8,
                            ls=(0, (2, 1)), zorder=5)
                ax.text(xi, 29.5, f"{n}", fontsize=FS, color=INK if n >= N_MIN else GREY["mid"],
                        ha="center", va="center")
        gap_axis(ax, xlabel=False)
        ax.set_ylim(0, 31)
        ax.set_yticks([0, 5, 10, 15, 20, 25])
        panel_letter(ax, "ab"[j], f"Peak {mode} load, peak hour hidden")
        ax.set_ylabel("absolute error, W/m²" if j == 0 else "")

        ax = axes[1, j]
        for k, (samp, st) in enumerate(SAMP.items()):
            d = a[a.sampling == samp].set_index("gap_hours").reindex(GAPS)
            xs = X + (k - 0.5) * w
            n = d[f"{mode}_exposed_rows"].fillna(0).astype(int).to_numpy()
            kept = d[f"{mode}_peak_hour_kept_share"].to_numpy() * 100
            far = d[f"{mode}_peak_moved_over_24h_share"].to_numpy() * 100
            near = 100 - kept - far
            ok = n >= N_MIN
            bottom = np.zeros(len(GAPS))
            for (lab, col), v in zip(TIMING, (kept, near, far)):
                vv = np.where(ok, v, 0)
                ax.bar(xs, vv, bottom=bottom, width=w * 0.92, color=col, edgecolor=INK,
                       lw=0.4, zorder=3)
                bottom += vv
            for xi, ni, good in zip(xs, n, ok):
                if not good:
                    ax.text(xi, 2, f"{ni}", fontsize=FS, color=GREY["mid"], ha="center", va="bottom")
        ax.set_xticks(np.concatenate([X - w / 2, X + w / 2]), minor=True)
        ax.set_xticklabels(["random"] * 4 + ["event"] * 4, minor=True, fontsize=FS)
        ax.tick_params(axis="x", which="minor", length=0, pad=1.5)
        gap_axis(ax)
        ax.tick_params(axis="x", which="major", length=0, pad=10)
        ax.set_ylim(0, 100)
        panel_letter(ax, "cd"[j], f"Timing of the peak {mode} hour")
        ax.set_ylabel("% of cases" if j == 0 else "")
    handles = [Line2D([], [], ls="", marker="o", ms=3.2, mfc=st["fc"], mec=st["ec"], mew=0.4,
                      label=st["label"].split(" (")[0] + " (one dot per case)") for st in SAMP.values()]
    handles += [Line2D([], [], color=INK, lw=1.3, label="median"),
                Line2D([], [], color=INK, lw=0.8, ls=(0, (2, 1)), label="95th percentile")]
    handles += [Patch(fc=col, ec=INK, lw=0.4, label=lab) for lab, col in TIMING]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=3,
               frameon=False, handletextpad=0.4, columnspacing=1.4)
    S.save(fig, "fig09_peaks")


# ------------------------------------------------------------- Fig. 7 (doc) events
OUTCOME = {"kept": GREY["dark"], "changed": GREY["light"], "lost": "white"}


def fig_events():
    ev = read("event-preservation-3day")
    a = ev[(ev.method == "automatic") & (ev.sampling == "weather_extremes")]
    types = [("heatwave", "Heatwave\n3+ days ≥ 25 °C"), ("warm_spell", "Warm spell\n3+ days above the\nsummer 95th percentile"),
             ("cold_spell", "Cold spell\n3+ days ≤ −10 °C"), ("relative_cold_spell", "Relative cold spell\n3+ days below the\nwinter 5th percentile")]
    fig, axes = plt.subplots(1, 4, figsize=(S.DOUBLE, 62 * S.MM), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.76, bottom=0.3, wspace=0.12)
    for ax, (t, title) in zip(axes, types):
        d = a[a.event_type == t].set_index("gap_hours").reindex(GAPS)
        kept = d.kept_exact_share.to_numpy() * 100
        ch = d.changed_bounds_share.to_numpy() * 100
        lost = d.lost_share.to_numpy() * 100
        n = d.reference_exposed_events.to_numpy()
        kw = dict(width=0.68, edgecolor=INK, lw=0.4, zorder=3)
        ax.bar(X, kept, color=OUTCOME["kept"], **kw)
        ax.bar(X, ch, bottom=kept, color=OUTCOME["changed"], **kw)
        ax.bar(X, lost, bottom=kept + ch, color=OUTCOME["lost"], **kw)
        for xi, ni in zip(X, n):
            ax.text(xi, 102, f"{int(ni)}", ha="center", va="bottom", fontsize=FS, color=INK)
        ax.set_xticks(X)
        ax.set_xticklabels([GAP_LABEL[g] for g in GAPS], fontsize=FS)
        ax.set_ylim(0, 112)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.text(0.5, 1.07, title, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=7, weight="bold", linespacing=1.15)
    axes[0].set_ylabel("% of events hit by the gap")
    fig.supxlabel("length of the gap centred on the event", fontsize=FS_AX, y=0.13)
    handles = [Patch(fc=OUTCOME["kept"], ec=INK, lw=0.4, label="kept: same first and last day"),
               Patch(fc=OUTCOME["changed"], ec=INK, lw=0.4, label="changed: start or end moved, shortened or split"),
               Patch(fc=OUTCOME["lost"], ec=INK, lw=0.4, label="lost: no event left after filling")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, -0.01), ncol=3,
               frameon=False, columnspacing=1.2, handletextpad=0.4)
    S.save(fig, "fig10_events")


# ------------------------------------------------------------- Fig. 10 monthly error
def fig_monthly():
    three_rows("monthly-error", "method-steps-donor-subset", "{mode}_months_within_5pct",
               ("% of months with a gap\nwithin ±5 % of the reference", "Monthly {mode} demand"),
               (0, 102), "fig11_monthly")


if __name__ == "__main__":
    fig_annual()
    fig_methods()
    fig_position()
    fig_peaks()
    fig_events()
    fig_monthly()
