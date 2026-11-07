"""Round-5 figure set: fewer, simpler figures.

- fig_error_general: annual error heat map, general weather only (main text)
- fig_error_solar: the same for solar gaps (appendix)
- fig_regret_worst: worst-case regret only (main text)
- fig_monthly_general: monthly test, general weather, all gaps (main text)
- fig_monthly_appendix: monthly test, nearby-station subset and solar gaps (appendix)
- fig_guidance: the modeller's checklist as a decision flow (Section 8)
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import FancyBboxPatch

import style as S
from style import INK, MUTED, ACCENT
import fig_new as N
import fig_results as R

FS = N.FS


def fig_error_general():
    H = 82
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.21, right=0.985, top=0.80, bottom=0.07, wspace=0.08)
    N.heat(axes[0], N.G_HEAT, N.ROWS_G, N.pct, LogNorm(0.01, 6.0), "a", "Heating: all methods small up to 48 hours")
    N.heat(axes[1], N.G_COOL, N.ROWS_G, N.pct, LogNorm(0.1, 27), "b", "Cooling: linear interpolation fails at one week",
           ylabels=False)
    fig.text(0.012, 0.955, "Error in annual demand that 95% of cases stay below, % of demand; four random general "
             "weather gaps a year.", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.92, "Darker = larger (log scale). –: the method does not fill gaps this long.",
             fontsize=FS, color=MUTED)
    S.save(fig, "fig_error_general")


def fig_error_solar():
    H = 70
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.21, right=0.985, top=0.77, bottom=0.08, wspace=0.08)
    N.heat(axes[0], N.S_HEAT, N.ROWS_S, N.pct, LogNorm(0.01, 6.0), "a", "Solar gaps: heating")
    N.heat(axes[1], N.S_COOL, N.ROWS_S, N.pct, LogNorm(0.1, 27), "b", "Solar gaps: cooling", ylabels=False)
    fig.text(0.012, 0.955, "Error in annual demand that 95% of cases stay below, % of demand; four random solar "
             "gaps a year.", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.915, "Darker = larger (log scale). –: the method does not fill gaps this long.",
             fontsize=FS, color=MUTED)
    S.save(fig, "fig_error_solar")


def fig_regret_worst():
    H = 80
    fig, ax = plt.subplots(1, 1, figsize=(S.DOUBLE * 0.62, H * S.MM))
    fig.subplots_adjust(left=0.36, right=0.975, top=0.80, bottom=0.07)
    topct = lambda T: [[None if v is None else f"{float(v) * 100:.0f}" for v in r] for r in T]
    N.heat(ax, topct(N.R_WORST), N.ROWS_R, None, LogNorm(4, 90), "", "Worst case, % of the reference value")
    fig.text(0.02, 0.955, "How much worse than the best method on the same case.", fontsize=FS, color=MUTED)
    fig.text(0.02, 0.915, "General weather gaps. Darker = larger (log scale).", fontsize=FS, color=MUTED)
    S.save(fig, "fig_regret_worst")


def _monthly(rows, titles, fname, H):
    fig, axes = plt.subplots(len(rows), 2, figsize=(S.DOUBLE, H * S.MM), squeeze=False)
    top = 1 - (26 if len(rows) > 1 else 17) / H
    fig.subplots_adjust(left=0.2, right=0.95, top=top, bottom=16 / H, wspace=0.85, hspace=0.95)
    letters = iter("abcdef")
    for r, (kind, scope, rtitle) in enumerate(rows):
        if kind == "full":
            d = R.read("monthly-error", scope).copy()
            if "gap_hours" not in d:
                d["gap_hours"] = d["gap_length"].map(R.LENS)
            if "sampling" in d:
                d = d[d.sampling == "random_seasonal"]
            methods = [m for m in R.ORDER if m != "donor_assessed"]
        else:
            d = R.read("method-steps-donor-subset", scope)
            d = d[d.sampling == "random_seasonal"]
            methods = R.ORDER
        if scope == "solar":
            methods = [m for m in methods if m != "automatic_legacy"]
        for c, mode in enumerate(("heating", "cooling")):
            ax = axes[r, c]
            R.method_panel(ax, d, f"{mode}_months_outside", methods, 100.0, 60, lambda v: f"{v:.0f} %")
            ax.text(-0.62, 1.1, f"{next(letters)}  {titles[(r, mode)]}", transform=ax.transAxes,
                    fontsize=7.5, weight="bold", va="bottom")
            ax.set_xlabel("% of months outside ±5 % of the reference", fontsize=FS)
        if len(rows) > 1:
            R.row_title(fig, axes[r, 0], rtitle, H, up_mm=9)
    fig.text(0.012, 1 - 5 / H, "Open dot: 48-hour gaps.  Filled dot and number: one-week gaps.  "
             "Methods ranked by the one-week value, best at the top.", fontsize=FS, color=MUTED)
    S.save(fig, fname)


def fig_monthly_general():
    _monthly((R.ROWS3[0],),
             {(0, "heating"): "Heating: only linear interpolation fails often",
              (0, "cooling"): "Cooling: one month in five fails at one week"},
             "fig_monthly_general", 60)


def fig_monthly_appendix():
    _monthly((R.ROWS3[1], R.ROWS3[2]),
             {(0, "heating"): "Heating: almost no months fail",
              (0, "cooling"): "Cooling: nearby station fails least",
              (1, "heating"): "Heating: only linear interpolation fails often",
              (1, "cooling"): "Cooling: one month in four fails at one week"},
             "fig_monthly_appendix", 120)


# ------------------------------------------------------------------ decision flow
def _box(ax, x, y, w, h, text, fc, ec=INK, bold=False, color=INK, fs=7.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=0.7))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=color,
            weight="bold" if bold else "normal", linespacing=1.3)


def _arrow(ax, x0, y0, x1, y1, label=None, lx=0, ly=0):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.7, mutation_scale=7, shrinkA=0, shrinkB=0))
    if label:
        ax.text((x0 + x1) / 2 + lx, (y0 + y1) / 2 + ly, label, fontsize=6.8, color=MUTED, ha="center", va="center")


def fig_guidance():
    H = 118
    fig = plt.figure(figsize=(S.DOUBLE, H * S.MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 174); ax.set_ylim(0, H); ax.axis("off")
    q = "#f1ebf6"; ok = "#eef3ee"; risk = "#f7e6e6"
    ax.text(6, H - 7, "Is a filled weather file safe for my result? Five steps", fontsize=9, weight="bold", color=INK)
    ax.text(6, H - 13, "For a modeller using an actual-year file with filled gaps of up to a week.",
            fontsize=7, color=MUTED)

    w = 52; x = 6
    _box(ax, x, 86, w, 13, "1  Did the year have heatwaves\nor cold spells?", q)
    _box(ax, x, 64, w, 15, "2  List the filled gaps:\nlength, general weather or solar,\nshare of the year filled", q)
    _box(ax, x, 42, w, 15, "3  Note the season of each gap:\nwinter → heating, summer → cooling,\nspring solar → heating too", q)
    _box(ax, x, 22, w, 13, "4  Match the gaps to\nthe result you need", q, bold=True)
    _arrow(ax, x + w / 2, 86, x + w / 2, 79)
    _arrow(ax, x + w / 2, 64, x + w / 2, 57)
    _arrow(ax, x + w / 2, 42, x + w / 2, 35)

    xr = 72; wr = 46
    _box(ax, xr, 74, wr, 20, "Annual heating\n\nSafe for gaps up to a week and\nup to about 8% of the year filled;\nlikely error in Table 8 (under 2%)", ok)
    _box(ax, xr, 48, wr, 19, "Annual cooling\n\nCheck summer gaps: a week over\na heatwave can move it 6%,\nor 20% for a solar gap", ok)
    _box(ax, xr, 8, wr, 33, "Peaks, peak timing,\nheatwave studies\n\nCould a gap hide the peak?\nYes if it falls in the peak season\nnext to the coldest or hottest\nmeasured days, or the simulated\npeak lands in or near filled hours", q)
    for yy in (84, 57, 25):
        _arrow(ax, x + w, 28.5, xr, yy)

    xo = 128; wo = 41
    _box(ax, xo, 22, wo, 22, "5  Yes: report a range\n\npeak ±15% for a week-long\ngap, or re-run with a\nsecond filling method", risk, bold=False)
    _box(ax, xo, 4, wo, 12, "No: the filled file is\nsafe for this result", ok)
    _arrow(ax, xr + wr, 27, xo, 33, "yes", ly=2.5)
    _arrow(ax, xr + wr, 14, xo, 10, "no", ly=-2.5)
    S.save(fig, "fig_guidance")


if __name__ == "__main__":
    fig_error_general(); fig_error_solar(); fig_regret_worst()
    fig_monthly_general(); fig_monthly_appendix(); fig_guidance()


# ------------------------------------------------------------------ regret by result type (round 5, deduplicated events)
ROWS_RT = ["Stepwise", "Stepwise, no switch", "Stepwise, patterns first", "Interpolation then patterns",
           "ERA5 only", "Four-week average", "Linear interpolation only", "Nearby station (own subset)"]
_N = None
RT = {
 "heat": [[.02, .26, 1.21, 5.17], [.02, .26, 1.21, 5.30], [.02, .58, 1.38, 5.30], [.02, .58, 1.38, _N],
          [.10, .47, .98, 5.17], [.02, 1.19, 3.09, 5.17], [.02, .21, 1.57, 6.50], [.03, .17, .55, .54]],
 "cool": [[1.21, 2.30, 6.36, 11.2], [1.21, 2.30, 6.36, 13.7], [1.21, 8.20, 8.89, 13.7], [1.21, 8.20, 8.89, _N],
          [.88, 2.65, 4.92, 11.2], [1.21, 20.1, 26.8, 11.2], [1.21, 11.7, 20.9, 53.5], [.51, 1.48, 2.63, 13.7]],
 "hpk": [[3.0, 7.5, 13.5, 14.3], [3.0, 7.5, 13.5, 31.1], [3.0, 10.1, 13.7, 31.1], [3.0, 10.1, 13.7, _N],
         [10.5, 10.6, 16.9, 14.3], [3.0, 10.6, 15.2, 14.3], [3.0, 6.9, 11.3, 15.2], [4.4, 2.7, 2.8, 7.0]],
 "cpk": [[8.6, 11.6, 19.7, 15.8], [8.6, 11.6, 19.7, 84.7], [8.6, 12.5, 22.6, 84.7], [8.6, 12.5, 22.6, _N],
         [23.2, 15.5, 16.2, 15.8], [8.6, 29.6, 37.5, 15.8], [8.6, 25.1, 13.5, 37.7], [2.2, 5.9, 11.2, 11.8]],
}


def _fmt(T):
    return [[None if v is None else (f"{v:.2f}" if v < 1 else f"{v:.1f}" if v < 10 else f"{v:.0f}") for v in r] for r in T]


def fig_regret_by_type():
    H = 132
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.24, right=0.985, top=0.86, bottom=0.04, wspace=0.08, hspace=0.32)
    norm = LogNorm(1, 90)
    spec = [("heat", "a", "Annual heating: under 7% for all methods"),
            ("cool", "b", "Annual cooling: linear interpolation worst"),
            ("hpk", "c", "Heating peak: no switch doubles the worst case"),
            ("cpk", "d", "Cooling peak: no switch reaches 85%")]
    for k, (key, let, ttl) in enumerate(spec):
        ax = axes.flat[k]
        N.heat(ax, _fmt(RT[key]), ROWS_RT, None, norm, let, ttl, ylabels=(k % 2 == 0))
        ax.axhline(6.5, color=INK, lw=0.9)
    fig.text(0.012, 0.965, "Worst case of each method: how much worse than the best method on the same case, "
             "% of the reference value.", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.935, "General weather gaps, random and event placements, each event week counted once. "
             "Darker = larger (log scale).", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.905, "Below the line: the nearby station alone, scored only on gaps where it passed its checks, "
             "so not comparable.", fontsize=FS, color=MUTED)
    S.save(fig, "fig_regret_by_type")


# ------------------------------------------------------------------ peaks after near-tie check (round 5)
import numpy as np
from style import RULE
GAPS = N.GAPS
LIGHT = "#c9b3dc"
# stepwise, event cases with the reference peak hidden, deduplicated (round5 t1 + a1)
PK = {
 "heating": dict(n=[23, 39, 49, 49], same=[.74, .41, .37, .31], day=[.04, .36, .29, .18],
                 tie=[5 / 23, 8 / 39, 10 / 49, 12 / 49], low=[0, 1 / 39, 7 / 49, 13 / 49]),
 "cooling": dict(n=[17, 39, 55, 79], same=[.35, .51, .44, .58], day=[.47, .26, .25, .25],
                 tie=[3 / 17, 7 / 39, 14 / 55, 8 / 79], low=[0, 2 / 39, 3 / 55, 5 / 79]),
}
# stepwise, peak hidden (random and event): single-hour vs mean of 10 highest hours, W/m2 median / p95
RB = {
 "heating": dict(single=[(.37, 4.4), (.97, 7.3), (2.0, 7.6), (1.2, 12.8)], top=[(.11, .64), (.49, 2.3), (1.1, 5.4), (1.0, 10.0)]),
 "cooling": dict(single=[(.56, 1.8), (.64, 2.7), (.78, 3.5), (1.12, 6.1)], top=[(.17, 1.7), (.38, 1.4), (.41, 2.5), (.74, 5.1)]),
}


def _timing(ax, d, letter, ttl, legend=False):
    X = np.arange(4); w = 0.6
    parts = [("same hour", d["same"], "#e9e1f0"), ("within a day", d["day"], "#cdbfe0"),
             ("moved >1 day, to a day within 5 % of the peak", d["tie"], LIGHT and "#9d7fc0"),
             ("moved >1 day, to a clearly lower day", d["low"], ACCENT)]
    b = np.zeros(4)
    for lab, v, c in parts:
        v = np.array(v) * 100
        ax.bar(X, v, w, bottom=b, color=c, label=lab, edgecolor="white", lw=0.5)
        b += v
    for x, n in zip(X, d["n"]):
        ax.text(x, 102, f"n={n}", ha="center", va="bottom", fontsize=FS, color=MUTED)
    ax.set_ylim(0, 112); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_ylabel("% of hidden peaks")
    ax.set_xticks(X); ax.set_xticklabels(GAPS, fontsize=FS)
    N.title(ax, letter, ttl, y=1.06)
    if legend:
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.16), ncol=2, fontsize=FS, frameon=False)


def _robust(ax, d, letter, ttl):
    X = np.arange(4)
    for k, (key, lab, c, dx) in enumerate([("single", "single peak hour", "#9d7fc0", -0.12), ("top", "mean of the 10 highest hours", ACCENT, 0.12)]):
        med = [m for m, _ in d[key]]; p95 = [p for _, p in d[key]]
        ax.vlines(X + dx, med, p95, color=c, lw=1.2)
        ax.plot(X + dx, med, "o", color=c, ms=4.5, label=f"{lab}: median (dot) to 95th percentile")
        ax.plot(X + dx, p95, "_", color=c, ms=8, mew=1.4)
    ax.set_xticks(X); ax.set_xticklabels(GAPS, fontsize=FS); ax.set_ylabel("peak error, W/m²")
    ax.grid(axis="y", color=RULE, lw=0.4); ax.set_axisbelow(True)
    N.title(ax, letter, ttl, y=1.06)


def fig_peaks5():
    H = 150
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.985, top=0.9, bottom=0.07, wspace=0.25, hspace=0.75)
    _timing(axes[0, 0], PK["heating"], "a", "Heating peak timing: many moves are near-ties")
    _timing(axes[0, 1], PK["cooling"], "b", "Cooling peak timing", legend=False)
    _robust(axes[1, 0], RB["heating"], "c", "Heating peak size: a 10-hour peak is steadier")
    _robust(axes[1, 1], RB["cooling"], "d", "Cooling peak size")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.06, 0.535), ncol=2, fontsize=FS, frameon=False)
    h, l = axes[1, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower left", bbox_to_anchor=(0.06, -0.005), ncol=2, fontsize=FS, frameon=False)
    fig.text(0.012, 0.965, "When the year's peak hour fell inside a gap. Timing: gaps at weather events. "
             "Size: random and event gaps. Stepwise method, general weather.", fontsize=FS, color=MUTED)
    S.save(fig, "fig_peaks5")


def fig_headline5():
    heat = [0.0128367, 0.112491, 0.399888, 1.68952]
    d = PK["heating"]
    X = np.arange(4); H = 74
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.32, wspace=0.28)
    ax = axes[0]
    ax.plot(X, heat, color=ACCENT, lw=1.3, marker="o", ms=5)
    for x, v in zip(X, heat):
        ax.annotate(f"{v:.2f} %" if v >= 0.1 else "<0.1 %", (x, v), xytext=(6 if x == 0 else 0, 6),
                    textcoords="offset points", ha="center", fontsize=FS)
    ax.set_ylim(0, 2.2); ax.set_yticks([0, 0.5, 1, 1.5, 2])
    ax.set_ylabel("error in annual heating,\n% of demand (95% of cases below)")
    N.title(ax, "a", "Annual heating: under 2 % even for week-long gaps", y=1.08)
    ax = axes[1]
    tie = np.array(d["tie"]) * 100; low = np.array(d["low"]) * 100
    ax.bar(X, low, 0.55, color=ACCENT, label="to a clearly lower day")
    
    ax.bar(X, tie, 0.55, bottom=low, color="#9d7fc0", label="to a day within 5 % of the peak")
    for x, a, b, n in zip(X, tie, low, d["n"]):
        ax.text(x, a + b + 2, f"{a + b:.0f} %\n(n={n})", ha="center", va="bottom", fontsize=FS)
    ax.set_ylim(0, 75); ax.set_yticks([0, 25, 50, 75])
    ax.set_ylabel("heating peaks that moved\nby more than a day, %")
    ax.legend(loc="upper left", bbox_to_anchor=(-0.02, -0.15), ncol=1, fontsize=FS, frameon=False)
    N.title(ax, "b", "Heating peaks: half move by over a day", y=1.08)
    for ax in axes:
        ax.set_xticks(X); ax.set_xticklabels(GAPS)
        ax.grid(axis="y", color=RULE, lw=0.4); ax.set_axisbelow(True)
    S.save(fig, "fig_headline5")
