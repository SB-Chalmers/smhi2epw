"""Results figures for general-weather gaps (temperature, humidity, pressure,
wind) and solar-radiation gaps (GHI, DNI and DHI hidden together).

Reads paper/figures/source/data/results/*.csv. Figs 6, 7, 8 and 11 have a top
row for general-weather gaps and a bottom row for solar gaps; Figs 9 and 10
show general-weather gaps only.

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
from style import GAP_LABEL, INK, METHOD, MUTED, RULE, RUNG, SAMPLING_LABEL

S.use()
RES = Path(__file__).resolve().parents[1] / "source" / "data" / "results"
GAPS = [3, 12, 48, 168]
X = np.arange(len(GAPS))
MARK = {"linear_only": "s", "temporal": "o", "donor_assessed": "D", "era5": "v",
        "diyepw_style": "^", "automatic_legacy": "P", "automatic": "o"}
SAMP = {"random_seasonal": ("o", INK, "full"), "weather_extremes": ("D", RUNG["donor"], "none")}


SCOPES = (("meteorology", "General weather hidden (temperature, humidity, pressure, wind)"),
          ("solar", "Solar radiation hidden (global, direct and diffuse)"))


def read(name, scope="meteorology"):
    d = pd.read_csv(RES / f"{name}.csv")
    return d[d["scope"] == scope] if "scope" in d else d


def row_title(fig, ax, text, h_mm, up_mm=7.5):
    """Row heading placed up_mm above the top of the row's left panel."""
    bb = ax.get_position()
    fig.text(0.012, bb.y1 + up_mm / h_mm, text, fontsize=7.2, weight="bold",
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
def fig_annual():
    H = 122
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.99, top=0.855, bottom=0.12, wspace=0.22, hspace=0.62)
    w = 0.36
    letters = iter("abcd")
    for r, (scope, rtitle) in enumerate(SCOPES):
        ann = read("annual-errors", scope)
        for ax, mode, title in ((axes[r, 0], "heating", "Yearly heating demand"),
                                (axes[r, 1], "cooling", "Yearly cooling demand")):
            top = 0
            for k, (samp, (mk, col, fill)) in enumerate(SAMP.items()):
                a = ann[(ann.method == "automatic") & (ann.sampling == samp)].set_index("gap_hours").loc[GAPS]
                xs = X + (k - 0.5) * w
                p95 = a[f"{mode}_abs_p95_pct"].to_numpy()
                med = a[f"{mode}_abs_median_pct"].to_numpy()
                ax.bar(xs, p95, width=w * 0.9, color=col if fill == "full" else "white",
                       edgecolor=col, lw=0.8, zorder=3)
                ax.plot(xs, med, ls="", marker="_", ms=7, color="white" if fill == "full" else col,
                        mew=1.4, zorder=4)
                for xi, v in zip(xs, p95):
                    ax.text(xi, v, f"{v:.2g}", fontsize=5.4, color=INK, ha="center", va="bottom")
                top = max(top, p95.max())
            ax.set_ylim(0, top * 1.15)
            gap_axis(ax)
            panel_letter(ax, next(letters), title)
            ax.set_ylabel("error, % of yearly demand" if mode == "heating" else "")
        row_title(fig, axes[r, 0], rtitle, H)
    handles = [
        Patch(fc=INK, ec=INK, label=SAMPLING_LABEL["random_seasonal"] + " (4 per file)"),
        Patch(fc="white", ec=RUNG["donor"], label=SAMPLING_LABEL["weather_extremes"] + " (1 per file)"),
        Line2D([], [], ls="", marker="_", ms=7, mew=1.4, color=MUTED, label="median"),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=3,
               frameon=False, fontsize=6, handletextpad=0.4, columnspacing=1.6)
    fig.text(0.012, 0.975, "smhi2epw; bar = 95th percentile of the absolute error; "
             "17 region-years × 6 buildings; y-axes differ between panels", fontsize=6.3,
             color=MUTED, va="top")
    S.save(fig, "fig06_annual_error")


# ------------------------------------------------------------- Fig. 9 methods
METHOD_ORDER = ["linear_only", "temporal", "diyepw_style", "era5", "automatic_legacy",
                "donor_assessed", "automatic"]


def method_lines(ax, df, col_of, methods, scale=1.0):
    for m in methods:
        d = df[df.method == m].set_index("gap_hours").reindex(GAPS)
        if d[col_of].isna().all():
            continue
        lab, col = METHOD[m]
        ax.plot(X, d[col_of] * scale, color=col, lw=1.6 if m == "automatic" else 1.0,
                ls="--" if m == "donor_assessed" else "-", marker=MARK[m], ms=3.6,
                mfc=col, mec="white", mew=0.4, zorder=4 if m == "automatic" else 3)


def method_legend(fig, note):
    handles = [Line2D([], [], color=METHOD[m][1], marker=MARK[m], ms=3.6, mec="white", mew=0.4,
                      lw=1.6 if m == "automatic" else 1.0, ls="--" if m == "donor_assessed" else "-",
                      label=METHOD[m][0] + (" *" if m == "donor_assessed" else ""))
               for m in METHOD_ORDER[::-1]]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.808, 0.86), frameon=False,
               fontsize=6.2, handlelength=2.2, labelspacing=0.7)
    fig.text(0.815, 0.12, note, fontsize=5.6, color=MUTED, va="bottom", linespacing=1.25)


def fig_methods():
    H = 128
    lens = {"3 h": 3, "12 h": 12, "2 days": 48, "1 week": 168}
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.79, top=0.86, bottom=0.09, wspace=0.27, hspace=0.55)
    letters = iter("abcd")
    for r, (scope, rtitle) in enumerate(SCOPES):
        ms = read("method-steps", scope).copy()
        ms["gap_hours"] = ms["gap_length"].map(lens)
        for ax, mode, title in ((axes[r, 0], "heating", "Yearly heating demand"),
                                (axes[r, 1], "cooling", "Yearly cooling demand")):
            method_lines(ax, ms, f"{mode}_abs_p95_pct", METHOD_ORDER)
            ax.set_ylim(bottom=0)
            gap_axis(ax)
            panel_letter(ax, next(letters), title)
            ax.set_ylabel("95th percentile error,\n% of yearly demand" if mode == "heating" else "")
        row_title(fig, axes[r, 0], rtitle, H)
    method_legend(fig, "* only gaps where a nearby\nstation passed the test\n(about a third of cases)\n\n"
                       "filling over time stops at\n48 h and matches the older\norder up to 2 days\n\n"
                       "solar (c, d) has no nearby-\nstation step, so filling over\ntime matches smhi2epw up to\n2 days; above 2 days smhi2epw\n"
                       "and diyepw-style use ERA5,\nso all three match at 1 week")
    fig.text(0.012, 0.975, "random gaps, 17 region-years × 6 buildings; y-axes differ between panels",
             fontsize=6.3, color=MUTED, va="top")
    S.save(fig, "fig07_methods")


# ------------------------------------------------------------- Fig. 8 where the gap falls
def fig_position():
    H = 132
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM),
                             gridspec_kw={"width_ratios": [1.35, 1]})
    fig.subplots_adjust(left=0.08, right=0.99, top=0.86, bottom=0.12, wspace=0.18, hspace=0.6)
    letters = iter("abcd")
    for r, (scope, rtitle) in enumerate(SCOPES):
        gp = read("gap-position", scope)
        a = gp[gp.method == "automatic"]

        def sel(event, season):
            return a[(a.event_type == event) & (a.season == season)].set_index("gap_hours").reindex(GAPS)
        groups = {
            "heating": [("winter", sel("random_seasonal", "winter"), "#0072B2", "full"),
                        ("spring", sel("random_seasonal", "spring"), "#009E73", "full"),
                        ("autumn", sel("random_seasonal", "autumn"), "#D55E00", "full"),
                        ("cold spell", sel("cold_spell_coldest_hour", "winter"), "#00456b", "hatch")],
            "cooling": [("summer", sel("random_seasonal", "summer"), "#E69F00", "full"),
                        ("heatwave", sel("heatwave_hottest_hour", "summer"), "#CC79A7", "hatch")],
        }
        for ax, mode, title in ((axes[r, 0], "heating", "Heating: gaps in winter, spring, autumn and cold spells"),
                                (axes[r, 1], "cooling", "Cooling: gaps in summer and heatwaves")):
            g = groups[mode]
            w = 0.8 / len(g)
            top = 0
            for k, (name, d, col, style_) in enumerate(g):
                xs = X - 0.4 + w * (k + 0.5)
                gap = d[f"gap_{mode}_delta_kwh_m2_abs_p95"].to_numpy()
                rec = d[f"recovery_{mode}_delta_kwh_m2_abs_p95"].to_numpy()
                kw = dict(width=w * 0.88, edgecolor="white", lw=0.5, zorder=3)
                ax.bar(xs, gap, color=col, hatch="////" if style_ == "hatch" else None, **kw)
                ax.bar(xs, rec, bottom=gap, color=col, alpha=0.38, **kw)
                top = max(top, np.nanmax(gap + rec))
            ax.set_ylim(0, top * 1.08)
            gap_axis(ax)
            panel_letter(ax, next(letters), title)
            ax.set_ylabel("95th percentile load\nchange, kWh/m²" if mode == "heating" else "")
            if r == 0:
                handles = [Patch(fc=col, hatch="////" if st == "hatch" else None, ec="white", label=name)
                           for name, _, col, st in g]
                ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=6, ncol=1,
                          handlelength=1.4)
        row_title(fig, axes[r, 0], rtitle, H)
    fig.legend(handles=[Patch(fc=MUTED, label="inside the gap"),
                        Patch(fc=MUTED, alpha=0.38, label="in the following week")],
               loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=2, frameon=False, fontsize=6)
    fig.text(0.012, 0.975, "smhi2epw, 17 region-years × 6 buildings; each part is its own 95th "
             "percentile, so the stack is an upper guide; colours as in a and b; y-axes differ",
             fontsize=6.3, color=MUTED, va="top")
    S.save(fig, "fig08_gap_position")


# ------------------------------------------------------------- R3 peaks
def fig_peaks():
    pk = read("peak-errors")
    a = pk[pk.method == "automatic"]
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, 100 * S.MM), sharex=True)
    fig.subplots_adjust(left=0.085, right=0.99, top=0.9, bottom=0.2, wspace=0.22, hspace=0.32)
    w = 0.36
    for j, (mode, name) in enumerate((("heating", "heating"), ("cooling", "cooling"))):
        ax = axes[0, j]
        for k, samp in enumerate(SAMP):
            d = a[a.sampling == samp].set_index("gap_hours").reindex(GAPS)
            mk, col, fill = SAMP[samp]
            xs = X + (k - 0.5) * w
            med = d[f"{mode}_peak_abs_err_median_w_m2"].to_numpy()
            p95 = d[f"{mode}_peak_abs_err_p95_w_m2"].to_numpy()
            n = d[f"{mode}_exposed_rows"].fillna(0).astype(int).to_numpy()
            ax.vlines(xs, med, p95, color=col, lw=1.0, zorder=3)
            ax.plot(xs, p95, ls="", marker=mk, ms=4.2, color=col,
                    mfc=col if fill == "full" else "white", mec=col, mew=0.9, zorder=4)
            ax.plot(xs, med, ls="", marker="_", ms=6, color=col, mew=1.2, zorder=4)
            for xi, ni, v in zip(xs, n, p95):
                ax.text(xi, (v if np.isfinite(v) else 0.2) * 1.0 + 0.6, f"n={ni}", fontsize=5.0,
                        color=MUTED, ha="center", va="bottom")
        gap_axis(ax, xlabel=False)
        ax.set_ylim(0, 22)
        panel_letter(ax, "ab"[j], f"Peak {name} load, when the peak hour was hidden")
        ax.set_ylabel("absolute error, W/m²" if j == 0 else "")
        ax = axes[1, j]
        for k, samp in enumerate(SAMP):
            d = a[a.sampling == samp].set_index("gap_hours").reindex(GAPS)
            mk, col, fill = SAMP[samp]
            xs = X + (k - 0.5) * w
            kept = d[f"{mode}_peak_hour_kept_share"].to_numpy() * 100
            moved = d[f"{mode}_peak_moved_over_24h_share"].to_numpy() * 100
            ax.bar(xs, kept, width=w * 0.9, color=col if fill == "full" else "white",
                   edgecolor=col, lw=0.8, zorder=3)
            ax.plot(xs, moved, ls="", marker="x", ms=4, color=RUNG["era5"], mew=1.1, zorder=4)
        gap_axis(ax)
        ax.set_ylim(0, 100)
        panel_letter(ax, "cd"[j], f"Timing of the peak {name} hour")
        ax.set_ylabel("% of cases" if j == 0 else "")
    handles = [
        Line2D([], [], ls="", marker="o", ms=4.2, color=INK, label=SAMPLING_LABEL["random_seasonal"]),
        Line2D([], [], ls="", marker="D", ms=4.2, mfc="white", mec=RUNG["donor"], mew=0.9,
               label=SAMPLING_LABEL["weather_extremes"]),
        Line2D([], [], ls="", marker="_", ms=6, mew=1.2, color=MUTED, label="median (dash) to 95th percentile (marker)"),
        Patch(fc="white", ec=MUTED, label="bar: same peak hour kept"),
        Line2D([], [], ls="", marker="x", ms=4, mew=1.1, color=RUNG["era5"], label="peak moved by more than 24 h"),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.0), ncol=3,
               frameon=False, fontsize=6, handletextpad=0.4, columnspacing=1.4)
    fig.text(0.085, 0.965, "smhi2epw, general-weather gaps; n = building cases whose yearly peak hour fell inside a gap",
             fontsize=6.3, color=MUTED)
    S.save(fig, "fig09_peaks")


# ------------------------------------------------------------- R4 events
def fig_events():
    ev = read("event-preservation-3day")
    a = ev[(ev.method == "automatic") & (ev.sampling == "weather_extremes")]
    types = [("heatwave", "Heatwave\n3+ days ≥ 25 °C"), ("warm_spell", "Warm spell\n3+ days above the\nsummer 95th percentile"),
             ("cold_spell", "Cold spell\n3+ days ≤ −10 °C"), ("relative_cold_spell", "Relative cold spell\n3+ days below the\nwinter 5th percentile")]
    cols = {"kept": RUNG["primary"], "changed": RUNG["solar"], "lost": RUNG["donor"]}
    fig, axes = plt.subplots(1, 4, figsize=(S.DOUBLE, 60 * S.MM), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.74, bottom=0.2, wspace=0.12)
    for ax, (t, title) in zip(axes, types):
        d = a[a.event_type == t].set_index("gap_hours").reindex(GAPS)
        kept = d.kept_exact_share.to_numpy() * 100
        ch = d.changed_bounds_share.to_numpy() * 100
        lost = d.lost_share.to_numpy() * 100
        n = d.reference_exposed_events.to_numpy()
        ax.bar(X, kept, color=cols["kept"], width=0.68, edgecolor="white", lw=0.8, zorder=3)
        ax.bar(X, ch, bottom=kept, color=cols["changed"], width=0.68, edgecolor="white", lw=0.8, zorder=3)
        ax.bar(X, lost, bottom=kept + ch, color=cols["lost"], width=0.68, edgecolor="white", lw=0.8, zorder=3)
        for xi, ni in zip(X, n):
            ax.text(xi, 102, f"{int(ni)}", ha="center", va="bottom", fontsize=5.4, color=MUTED)
        ax.set_xticks(X)
        ax.set_xticklabels([GAP_LABEL[g] for g in GAPS], fontsize=6.2)
        ax.set_ylim(0, 112)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.text(0.5, 1.07, title, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=6.6, weight="bold", linespacing=1.15)
    axes[0].set_ylabel("% of events hit by the gap")
    fig.supxlabel("length of the gap centred on the event", fontsize=7, y=0.08)
    handles = [Patch(fc=cols["kept"], label="kept: same first and last day"),
               Patch(fc=cols["changed"], label="changed: start or end moved, shortened or split"),
               Patch(fc=cols["lost"], label="lost: no event left after filling")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, -0.01), ncol=3,
               frameon=False, fontsize=6)
    fig.text(0.07, 0.955, "smhi2epw, general-weather gaps centred on weather events; numbers above bars = events hit",
             fontsize=6.3, color=MUTED)
    S.save(fig, "fig10_events")


# ------------------------------------------------------------- Fig. 10 monthly error
def fig_monthly():
    H = 128
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.79, top=0.86, bottom=0.09, wspace=0.27, hspace=0.55)
    letters = iter("abcd")
    for r, (scope, rtitle) in enumerate(SCOPES):
        mo = read("monthly-error", scope)
        rnd = mo[mo.sampling == "random_seasonal"]
        for ax, mode, title in ((axes[r, 0], "heating", "Monthly heating demand"),
                                (axes[r, 1], "cooling", "Monthly cooling demand")):
            method_lines(ax, rnd, f"{mode}_months_within_5pct", METHOD_ORDER, scale=100)
            gap_axis(ax)
            ax.set_ylim(0, 102)
            ax.set_yticks([0, 20, 40, 60, 80, 100])
            panel_letter(ax, next(letters), title)
            ax.set_ylabel("% of months with a gap\nwithin ±5 % of the reference" if mode == "heating" else "")
        row_title(fig, axes[r, 0], rtitle, H)
    method_legend(fig, "* only gaps where a nearby\nstation passed the test\n\n"
                       "filling over time stops at\n48 h and matches the older\norder up to 2 days\n\n"
                       "solar (c, d) has no nearby-\nstation step, so filling over\ntime matches smhi2epw up to\n2 days; above 2 days smhi2epw\n"
                       "and diyepw-style use ERA5,\nso all three match at 1 week")
    fig.text(0.012, 0.975, "random gaps; ±5 % is the monthly bias limit for calibrated models in "
             "ASHRAE Guideline 14; months with little demand left out", fontsize=6.3, color=MUTED, va="top")
    S.save(fig, "fig11_monthly")


if __name__ == "__main__":
    fig_annual()
    fig_methods()
    fig_position()
    fig_peaks()
    fig_events()
    fig_monthly()
