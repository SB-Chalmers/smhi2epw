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
