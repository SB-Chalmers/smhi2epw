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
    H = 80
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.21, right=0.985, top=0.86, bottom=0.17, wspace=0.08)
    N.heat(axes[0], N.G_HEAT, N.ROWS_G, None, None, "a", "Heating: all methods small up to 48 hours", sep=6)
    N.heat(axes[1], N.G_COOL, N.ROWS_G, None, None, "b", "Cooling: linear interpolation fails at one week",
           ylabels=False, sep=6)
    N.band_key(fig, 0.21, 0.035, "error, % of annual demand")
    S.save(fig, "fig_error_general")


def fig_error_solar():
    H = 66
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.21, right=0.985, top=0.86, bottom=0.2, wspace=0.08)
    N.heat(axes[0], N.S_HEAT, N.ROWS_S, None, None, "a", "Solar gaps: heating")
    N.heat(axes[1], N.S_COOL, N.ROWS_S, None, None, "b", "Solar gaps: cooling", ylabels=False)
    N.band_key(fig, 0.21, 0.04, "error, % of annual demand")
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
    top = 1 - (16 if len(rows) > 1 else 8) / H
    fig.subplots_adjust(left=0.2, right=0.95, top=top, bottom=17 / H, wspace=0.85, hspace=0.95)
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
            R.method_panel(ax, d, f"{mode}_months_outside", methods, 100.0, 80, lambda v: f"{v:.0f}%")
            ax.text(-0.62, 1.1, f"{next(letters)}  {titles[(r, mode)]}", transform=ax.transAxes,
                    fontsize=7.5, weight="bold", va="bottom")
            ax.set_xlabel("% of months outside ±5% of the reference", fontsize=FS)
        if len(rows) > 1:
            R.row_title(fig, axes[r, 0], rtitle, H, up_mm=9)
    _dot_key(fig, H)
    S.save(fig, fname)


def _dot_key(fig, H):
    """Open/filled dot key under the panels (replaces the old grey header line)."""
    from matplotlib.lines import Line2D
    h = [Line2D([], [], ls="", marker="o", mfc="white", mec=S.OTHER, ms=4.5, label="48-hour gaps"),
         Line2D([], [], ls="", marker="o", mfc=S.OTHER, mec=S.OTHER, ms=4.5, label="one-week gaps (number)")]
    fig.legend(handles=h, loc="lower left", bbox_to_anchor=(0.2, 0.0), ncol=2, fontsize=FS, frameon=False,
               handletextpad=0.3, columnspacing=1.5)


def fig_monthly_general():
    _monthly((R.ROWS3[0],),
             {(0, "heating"): "Heating: only linear interpolation fails often",
              (0, "cooling"): "Cooling: one month in five fails at one week"},
             "fig_monthly_general", 54)


def fig_monthly_appendix():
    _monthly((R.ROWS3[1], R.ROWS3[2]),
             {(0, "heating"): "Heating: almost no months fail",
              (0, "cooling"): "Cooling: nearby station fails least",
              (1, "heating"): "Heating: only linear interpolation fails often",
              (1, "cooling"): "Cooling: one month in four fails at one week"},
             "fig_monthly_appendix", 116)


# ------------------------------------------------------------------ decision flow
def _box(ax, x, y, w, h, text, fc, ec=INK, bold=False, color=INK, fs=7.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=0.7))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=color,
            weight="bold" if bold else "normal", linespacing=1.3)


def _arrow(ax, x0, y0, x1, y1, label=None, lx=0, ly=0):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.7, mutation_scale=7, shrinkA=0, shrinkB=0))
    if label:
        ax.text((x0 + x1) / 2 + lx, (y0 + y1) / 2 + ly, label, fontsize=FS, color=MUTED, ha="center", va="center")


def fig_guidance():
    H = 100
    fig = plt.figure(figsize=(S.DOUBLE, H * S.MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 174); ax.set_ylim(0, H); ax.axis("off")
    W = "white"; G = S.GREY["mid"]

    def bx(x, y, w, h, text, ec=G, bold=False, color=INK, lw=0.7):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=W, ec=ec, lw=lw))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=FS, color=color,
                weight="bold" if bold else "normal", linespacing=1.3)

    # left column: steps 1-4
    x, w = 4, 52
    bx(x, 80, w, 15, "1  Did the year and place have\nheatwaves or cold spells?")
    bx(x, 57, w, 16, "2  List the filled gaps:\nlength, general weather or solar,\nshare of the year filled")
    bx(x, 34, w, 16, "3  Note the season of each gap:\nwinter → heating, summer → cooling,\nspring solar → heating too")
    bx(x, 12, w, 15, "4  Match the gaps to\nthe result you need", bold=True)
    for y0, y1 in ((80, 73), (57, 50), (34, 27)):
        _arrow(ax, x + w / 2, y0, x + w / 2, y1)

    # middle column: what each result needs
    xr, wr = 68, 50
    bx(xr, 55, wr, 40, "Peaks, peak timing,\nheatwave studies\n\nCould a gap hide the peak?\nYes if it falls in the peak season\n"
       "next to the coldest or hottest\ndays, or the simulated peak\nlands in or near filled hours")
    bx(xr, 30, wr, 19, "Annual cooling\n\nCheck summer gaps: a week over\na heatwave can move it 6%,\nor 20% for a solar gap")
    bx(xr, 5, wr, 19, "Annual heating\n\nSafe for gaps up to a week and\nup to about 8% of the year filled;\nlikely error in Table 8 (under 2%)")
    _arrow(ax, x + w, 87.5, xr, 87.5, "yes", ly=2.4)
    for yy in (62, 39.5, 14.5):
        _arrow(ax, x + w, 19.5, xr, yy)

    # right column: outcome for peaks
    xo, wo = 130, 40
    bx(xo, 70, wo, 25, "5  Yes: report a range\n\npeak ±15% for a week-long\ngap, or re-run with a\nsecond filling method",
       ec=ACCENT, bold=False, lw=1.2)
    bx(xo, 48, wo, 13, "No: the filled file is\nsafe for this result")
    _arrow(ax, xr + wr, 80, xo, 82.5, "yes", ly=2.4)
    _arrow(ax, xr + wr, 62, xo, 54.5, "no", ly=-2.4)
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
    H = 128
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.24, right=0.985, top=0.93, bottom=0.1, wspace=0.08, hspace=0.32)
    spec = [("heat", "a", "Annual heating: under 7% for all methods"),
            ("cool", "b", "Annual cooling: linear interpolation worst"),
            ("hpk", "c", "Heating peak: no switch doubles the worst case"),
            ("cpk", "d", "Cooling peak: no switch reaches 85%")]
    for k, (key, let, ttl) in enumerate(spec):
        ax = axes.flat[k]
        N.heat(ax, RT[key], ROWS_RT, None, None, let, ttl, ylabels=(k % 2 == 0), sep=6)
    N.band_key(fig, 0.24, 0.025, "worst case, % of reference")
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
    parts = [("same hour", d["same"], S.GREY["pale"]), ("within a day", d["day"], S.GREY["light"]),
             ("moved >1 day, to a day within 5% of the peak", d["tie"], LIGHT),
             ("moved >1 day, to a clearly lower day", d["low"], ACCENT)]
    tot = np.sum([np.array(v) for _, v, _ in parts], axis=0)   # rounding: make each bar sum to 100
    b = np.zeros(4)
    for lab, v, c in parts:
        v = np.array(v) / tot * 100
        ax.bar(X, v, w, bottom=b, color=c, label=lab, edgecolor="white", lw=0.5)
        b += v
    for x, n in zip(X, d["n"]):
        ax.text(x, 102, f"n={n}", ha="center", va="bottom", fontsize=FS, color=MUTED)
    ax.set_ylim(0, 112); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_ylabel("% of hidden peaks")
    ax.set_xticks(X); ax.set_xticklabels(GAPS, fontsize=FS)
    N.title(ax, letter, ttl, y=1.06)


def _robust(ax, d, letter, ttl):
    X = np.arange(4)
    for k, (key, lab, c, dx) in enumerate([("single", "single peak hour", S.GREY["mid"], -0.12),
                                           ("top", "mean of the 10 highest hours", ACCENT, 0.12)]):
        med = [m for m, _ in d[key]]; p95 = [p for _, p in d[key]]
        ax.vlines(X + dx, med, p95, color=c, lw=1.2)
        ax.plot(X + dx, med, "o", color=c, ms=4.5, label=f"{lab}: median (dot) to 95th percentile")
        ax.plot(X + dx, p95, "_", color=c, ms=8, mew=1.4)
    ax.set_xticks(X); ax.set_xticklabels(GAPS, fontsize=FS); ax.set_ylabel("peak error, W/m²")
    ax.grid(axis="y", color=RULE, lw=0.4); ax.set_axisbelow(True)
    N.title(ax, letter, ttl, y=1.06)


def fig_peaks5():
    H = 132
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.085, wspace=0.25, hspace=0.62)
    _timing(axes[0, 0], PK["heating"], "a", "Heating peak timing: many moves are near-ties")
    _timing(axes[0, 1], PK["cooling"], "b", "Cooling peak timing: most stay within a day")
    _robust(axes[1, 0], RB["heating"], "c", "Heating peak size: a 10-hour peak is steadier")
    _robust(axes[1, 1], RB["cooling"], "d", "Cooling peak size: the same pattern, smaller")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.06, 0.555), ncol=2, fontsize=FS, frameon=False)
    h, l = axes[1, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower left", bbox_to_anchor=(0.06, -0.008), ncol=2, fontsize=FS, frameon=False)
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
