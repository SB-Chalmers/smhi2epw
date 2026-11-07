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
    top = 1 - 26 / H
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
        R.row_title(fig, axes[r, 0], rtitle, H, up_mm=9)
    fig.text(0.012, 1 - 5 / H, "Open dot: 48-hour gaps.  Filled dot and number: one-week gaps.  "
             "Methods ranked by the one-week value, best at the top.", fontsize=FS, color=MUTED)
    S.save(fig, fname)


def fig_monthly_general():
    _monthly((R.ROWS3[0],),
             {(0, "heating"): "Heating: only linear interpolation fails often",
              (0, "cooling"): "Cooling: one month in five fails at one week"},
             "fig_monthly_general", 70)


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
    H = 112
    fig = plt.figure(figsize=(S.DOUBLE, H * S.MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 174); ax.set_ylim(0, H); ax.axis("off")
    q = "#f1ebf6"; ok = "#eef3ee"; risk = "#f7e6e6"
    ax.text(6, H - 7, "Is a filled weather file safe for my result?", fontsize=9, weight="bold", color=INK)
    ax.text(6, H - 13, "A simple check for a modeller using an actual-year file with filled gaps.",
            fontsize=7, color=MUTED)

    w = 50
    _box(ax, 6, 72, w, 16, "1  Find the filled gaps\nlength, general weather or solar,\nshare of the year", q)
    _box(ax, 6, 48, w, 16, "2  Note the season and events\nwinter gaps → heating, summer → cooling;\nheatwaves or cold spells?", q)
    _box(ax, 6, 24, w, 16, "3  Which result do I need?", q, bold=True)
    _arrow(ax, 31, 72, 31, 64)
    _arrow(ax, 31, 48, 31, 40)

    xr = 70; wr = 46
    _box(ax, xr, 66, wr, 18, "Annual heating\n\nSafe. Read the likely error\nfrom Table 8 (under 2%)", ok)
    _box(ax, xr, 40, wr, 18, "Annual cooling\n\nCheck summer gaps: a hidden\nheatwave week can move it 6–20%", ok)
    _box(ax, xr, 8, wr, 24, "Peaks, peak timing,\nheatwave studies\n\nDoes a gap fall in the peak season\nnext to the coldest or hottest days,\nor does the peak land in filled hours?", q)
    for yy in (75, 49, 20):
        _arrow(ax, 56, 32, xr, yy)

    xo = 126; wo = 42
    _box(ax, xo, 20, wo, 22, "Yes: report a range\n\npeak ±15% (week-long gap);\nor re-run with a second\nfilling method", risk)
    _box(ax, xo, 2, wo, 14, "No: the filled file is\nsafe for this result", ok)
    _arrow(ax, xr + wr, 24, xo, 31, "yes", ly=2.5)
    _arrow(ax, xr + wr, 14, xo, 9, "no", ly=-2.5)
    S.save(fig, "fig_guidance")


if __name__ == "__main__":
    fig_error_general(); fig_error_solar(); fig_regret_worst()
    fig_monthly_general(); fig_monthly_appendix(); fig_guidance()
