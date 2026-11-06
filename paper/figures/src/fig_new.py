"""Final-revision figures: method diagram, two-panel headline, error and regret heat maps."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
import style as S
from style import INK, MUTED, RULE, ACCENT, ACCENT_SEQ, OTHER, box, arrow

S.use()
FS = 6.8
PURPLES = LinearSegmentedColormap.from_list("p", ["#f7f3fb", "#d9c8ea", "#a882c8", "#7a4aa6", ACCENT, "#2e1047"])
GAPS = ["3 hours", "12 hours", "48 hours", "1 week"]


def title(ax, letter, text, y=1.04, x=0):
    ax.text(x, y, f"{letter}  {text}", transform=ax.transAxes, fontsize=7.5, weight="bold", va="bottom")


# ---------------------------------------------------------------- method diagram
def fig_method_diagram():
    rng = np.random.default_rng(4)
    t = np.arange(0, 24 * 5)                       # five days, hourly
    g0, g1 = 50, 86                                 # 36-hour gap
    base = -4 + 0.02 * t
    true = base + 4 * np.sin((t - 9) / 24 * 2 * np.pi) + np.cumsum(rng.normal(0, 0.25, t.size))
    true[g0:g1] -= np.linspace(0, 1, g1 - g0) * 0 + 2.5 * np.sin(np.linspace(0, np.pi, g1 - g0))  # a cold dip
    gap = np.arange(g0, g1)
    a, b = true[g0 - 1], true[g1]

    lin = np.interp(gap, [g0 - 1, g1], [a, b])
    # daily pattern: mean shape of the days either side, adjusted to meet both ends
    shape = 4 * np.sin((gap - 9) / 24 * 2 * np.pi)
    trend = np.interp(gap, [g0 - 1, g1], [a - 4 * np.sin((g0 - 1 - 9) / 24 * 2 * np.pi),
                                         b - 4 * np.sin((g1 - 9) / 24 * 2 * np.pi)])
    patt = shape + trend
    # four-week average of the same hour: weaker cycle, month-mean level
    four = -2.2 + 2.6 * np.sin((gap - 9) / 24 * 2 * np.pi)
    # nearby station: same weather, own local quirks (bias that grows at the extreme)
    near = true[g0:g1] + 0.6 - 1.4 * np.sin(np.linspace(0, np.pi, g1 - g0)) + rng.normal(0, 0.3, g1 - g0)
    # ERA5: smooth grid average, smaller daily range
    era = base[g0:g1] - 1.6 * np.sin(np.linspace(0, np.pi, g1 - g0)) + 2.6 * np.sin((gap - 10) / 24 * 2 * np.pi)

    panels = [
        ("Linear interpolation", "A straight line between the last value\nbefore and the first value after the gap", lin, None),
        ("Daily patterns", "The shape of the days either side,\nadjusted to meet both ends of the gap", patt, None),
        ("Four-week average (as in diyepw)", "The average of the same hour of day\nover the four weeks around the gap", four, None),
        ("Nearby station", "The same hours from a nearby station,\nchecked against the main station first", near, "near"),
        ("ERA5", "The same hours from a global weather\nmodel; smooth, misses local extremes", era, "era"),
    ]
    H = 104
    fig = plt.figure(figsize=(S.DOUBLE, H * S.MM))
    gs = fig.add_gridspec(2, 3, left=0.05, right=0.98, top=0.86, bottom=0.08, wspace=0.18, hspace=0.95)
    letters = iter("abcdef")
    for k, (name, desc, fill, src) in enumerate(panels):
        ax = fig.add_subplot(gs[k // 3, k % 3])
        ax.axvspan(g0 - 0.5, g1 - 0.5, color="#ebe3f3", lw=0, zorder=0)
        ax.plot(t[:g0], true[:g0], color=INK, lw=0.9)
        ax.plot(t[g1:], true[g1:], color=INK, lw=0.9)
        ax.plot(gap, true[g0:g1], color=MUTED, lw=0.8, ls=(0, (2, 1.5)))
        if src == "near":
            ax.plot(t[:g0], true[:g0] + 0.5 + rng.normal(0, 0.25, g0), color=OTHER, lw=0.6, alpha=0.8)
            ax.plot(t[g1:], true[g1:] + 0.5 + rng.normal(0, 0.25, t.size - g1), color=OTHER, lw=0.6, alpha=0.8)
        if src == "era":
            eraf = base - 1.6 * np.interp(t, gap, np.sin(np.linspace(0, np.pi, g1 - g0)), left=0, right=0) \
                + 2.6 * np.sin((t - 10) / 24 * 2 * np.pi)
            ax.plot(t[:g0], eraf[:g0], color=OTHER, lw=0.6, alpha=0.8)
            ax.plot(t[g1:], eraf[g1:], color=OTHER, lw=0.6, alpha=0.8)
        ax.plot(gap, fill, color=ACCENT, lw=1.6)
        ax.set_xlim(0, t[-1]); ax.set_ylim(-13, 8)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ("left", "bottom"):
            ax.spines[s].set_color(RULE)
        title(ax, next(letters), name, y=1.30)
        ax.text(0, 1.04, desc, transform=ax.transAxes, fontsize=FS, color=MUTED, va="bottom", linespacing=1.15)
        if k == 0:
            ax.text((g0 + g1) / 2, 6.6, "gap", ha="center", fontsize=FS, color=ACCENT)
            ax.text(4, 6.6, "measured", fontsize=FS, color=INK)
            ax.annotate("hidden true values", xy=(g0 + 20, true[g0 + 20]), xytext=(g0 + 2, -12.3),
                        fontsize=FS, color=MUTED, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5))
        if src:
            ax.text(1, -12.3, "grey: that source outside the gap", fontsize=FS - 0.4, color=OTHER)
    # f: the stepwise method
    ax = fig.add_subplot(gs[1, 2]); ax.axis("off")
    ax.set_xlim(0, 60); ax.set_ylim(0, 44)
    title(ax, "f", "Stepwise", y=1.30)
    ax.text(0, 1.04, "Tries the sources in order; long gaps\ngo straight to ERA5 (Figure 1)",
            transform=ax.transAxes, fontsize=FS, color=MUTED, va="bottom", linespacing=1.15)
    steps = [("linear interpolation", "up to 3 hours"), ("nearby station", "if one passes the check"),
             ("daily patterns", "up to 48 hours"), ("ERA5", "anything left")]
    for i, (s1, s2) in enumerate(steps):
        y = 38 - i * 10.5
        box(ax, 1, y - 4.2, 36, 8.4, "", fc="#f1ebf6" if i < 3 else "#e4d8ef", ec=ACCENT, lw=0.6, r=1.0)
        ax.text(3, y + 1.7, s1, fontsize=FS, weight="bold", va="center", color=INK)
        ax.text(3, y - 2.0, s2, fontsize=FS - 0.4, va="center", color=MUTED)
        if i < 3:
            arrow(ax, (18, y - 4.4), (18, y - 6.1), color=ACCENT, lw=0.7, ms=5)
    ax.text(40.5, 30, "longer gaps\ngo straight\nto ERA5", fontsize=FS - 0.4,
            color=ACCENT, va="center", linespacing=1.15)
    arrow(ax, (45, 24.5), (37.5, 6.5), color=ACCENT, lw=0.7, ms=5, conn="arc3,rad=-0.25")
    S.save(fig, "fig_methods_diagram")


# ---------------------------------------------------------------- headline, two panels
def fig_headline():
    gaps = [3, 12, 48, 168]
    heat = [0.0128367, 0.112491, 0.399888, 1.68952]
    moved = [26.3158, 26.8657, 39.5349, 53.4884]
    n = [(10, 38), (18, 67), (34, 86), (46, 86)]
    X = np.arange(4)
    H = 66
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.17, wspace=0.28)
    ax = axes[0]
    ax.plot(X, heat, color=ACCENT, lw=1.3, marker="o", ms=5)
    for x, v in zip(X, heat):
        ax.annotate(f"{v:.2f} %" if v >= 0.1 else "<0.1 %", (x, v), xytext=(6 if x == 0 else 0, 6), textcoords="offset points",
                    ha="center", fontsize=FS)
    ax.set_ylim(0, 2.2); ax.set_yticks([0, 0.5, 1, 1.5, 2])
    ax.set_ylabel("error in annual heating,\n% of demand (95% of cases below)")
    title(ax, "a", "Annual heating: under 2 % even for week-long gaps", y=1.08)
    ax = axes[1]
    ax.bar(X, moved, width=0.55, color=ACCENT)
    for x, v, (k, m) in zip(X, moved, n):
        ax.text(x, v + 2, f"{v:.0f} %\n({k} of {m})", ha="center", va="bottom", fontsize=FS)
    ax.set_ylim(0, 75); ax.set_yticks([0, 25, 50, 75])
    ax.set_ylabel("heating peaks that moved\nby more than a day, %")
    title(ax, "b", "Heating peaks: half move by more than a day", y=1.08)
    for ax in axes:
        ax.set_xticks(X); ax.set_xticklabels(GAPS); ax.set_xlabel("length of each gap")
        ax.grid(axis="y", color=RULE, lw=0.4); ax.set_axisbelow(True)
    S.save(fig, "fig_headline")


# ---------------------------------------------------------------- heat maps
def heat(ax, vals, rows, fmt, norm, letter, ttl, ylabels=True):
    L = vals
    V = np.array([[np.nan if v is None else float(v) for v in r] for r in vals], dtype=float)
    M = np.ma.masked_invalid(V)
    cm = PURPLES.copy(); cm.set_bad("#ffffff")
    ax.imshow(np.clip(M, norm.vmin, None), cmap=cm, norm=norm, aspect="auto")
    for i in range(V.shape[0]):
        for j in range(V.shape[1]):
            v = V[i, j]
            if np.isnan(v):
                ax.text(j, i, "–", ha="center", va="center", fontsize=FS, color=MUTED)
                continue
            dark = norm(max(v, norm.vmin)) > 0.55
            ax.text(j, i, L[i][j], ha="center", va="center", fontsize=FS, color="white" if dark else INK,
                    weight="bold" if rows[i] == "Stepwise" else "normal")
    ax.set_xticks(range(len(GAPS))); ax.set_xticklabels(GAPS, fontsize=FS)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows if ylabels else [], fontsize=FS)
    for lab in ax.get_yticklabels():
        if lab.get_text() == "Stepwise":
            lab.set_weight("bold"); lab.set_color(ACCENT)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 4, 1), minor=True); ax.set_yticks(np.arange(-0.5, len(rows), 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.2); ax.tick_params(which="minor", length=0)
    title(ax, letter, ttl, y=1.03)


ROWS_G = ["Stepwise", "Stepwise, no switch", "Stepwise, patterns first", "Interpolation then patterns",
          "ERA5 only", "Four-week average", "Linear interpolation only", "Nearby station (40% of gaps)"]
# Table 8 (general weather) heating / cooling, Table 10 (solar)
G_HEAT = [["0.01", "0.11", "0.40", "1.7"], ["0.01", "0.11", "0.40", "1.8"], ["0.01", "0.13", "0.61", "1.8"], ["0.01", "0.13", "0.61", None],
          ["0.03", "0.11", "0.51", "1.7"], ["0.01", "0.28", "1.13", "1.7"], ["0.01", "0.09", "0.66", "3.2"], ["0.02", "0.08", "0.38", "0.65"]]
G_COOL = [["0.1", "1.1", "1.3", "5.0"], ["0.1", "1.1", "1.3", "4.1"], ["0.1", "0.6", "2.4", "4.1"], ["0.1", "0.6", "2.4", None],
          ["0.1", "0.6", "1.2", "5.0"], ["0.1", "1.0", "4.9", "5.0"], ["0.1", "0.8", "5.7", "18.1"], ["0.1", "0.2", "0.4", "2.2"]]
ROWS_S = ["Stepwise", "Stepwise, no switch", "Interpolation then patterns", "ERA5 only", "Four-week average",
          "Linear interpolation only"]
S_HEAT = [["0.08", "0.20", "0.58", "1.03"], ["0.08", "0.30", "0.95", "1.03"], ["0.08", "0.30", "0.95", None], ["0.07", "0.20", "0.58", "1.03"],
          ["0.07", "0.33", "0.89", "1.03"], ["0.07", "0.58", "1.84", "6.0"]]
S_COOL = [["0.28", "0.56", "1.6", "4.9"], ["0.28", "0.91", "2.5", "4.9"], ["0.28", "0.91", "2.5", None], ["0.25", "0.56", "1.6", "4.9"],
          ["0.24", "1.0", "4.8", "4.9"], ["0.24", "1.9", "10.5", "26.8"]]


def pct(v):
    return f"{v:.2f}" if v < 0.1 else (f"{v:.1f}" if v < 10 else f"{v:.0f}")


def fig_error_heatmap():
    H = 150
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM),
                             gridspec_kw=dict(height_ratios=[8, 6]))
    fig.subplots_adjust(left=0.21, right=0.985, top=0.9, bottom=0.04, wspace=0.08, hspace=0.32)
    nh = LogNorm(0.01, 6.0); nc = LogNorm(0.1, 27)
    heat(axes[0, 0], G_HEAT, ROWS_G, pct, nh, "a", "General weather gaps: heating")
    heat(axes[0, 1], G_COOL, ROWS_G, pct, nc, "b", "General weather gaps: cooling", ylabels=False)
    heat(axes[1, 0], S_HEAT, ROWS_S, pct, nh, "c", "Solar gaps: heating")
    heat(axes[1, 1], S_COOL, ROWS_S, pct, nc, "d", "Solar gaps: cooling", ylabels=False)
    fig.text(0.012, 0.965, "Error in annual demand that 95% of cases stay below, % of demand; four random gaps a year. "
             "Darker = larger (log scale).", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.945, "–: the method does not fill gaps this long. Heating and cooling panels share one colour scale each.",
             fontsize=FS, color=MUTED)
    S.save(fig, "fig_error_heatmap")


ROWS_R = ["Stepwise", "Stepwise, no switch", "Stepwise, patterns first", "Interpolation then patterns",
          "ERA5 only", "Four-week average", "Linear interpolation only", "Nearby station (40% of gaps)"]
R_WORST = [["0.086", "0.116", "0.197", "0.158"], ["0.086", "0.116", "0.197", "0.847"], ["0.086", "0.125", "0.226", "0.847"],
           ["0.086", "0.125", "0.226", None], ["0.232", "0.154", "0.169", "0.158"], ["0.086", "0.296", "0.375", "0.158"],
           ["0.086", "0.251", "0.209", "0.535"], ["0.044", "0.059", "0.112", "0.137"]]
R_P95 = [["0.001", "0.005", "0.018", "0.042"], ["0.001", "0.005", "0.018", "0.039"], ["0.001", "0.027", "0.046", "0.039"],
         ["0.001", "0.027", "0.046", None], ["0.001", "0.012", "0.022", "0.042"], ["0.001", "0.043", "0.081", "0.042"],
         ["0.001", "0.028", "0.051", "0.190"], ["0.002", "0.003", "0.013", "0.028"]]


def fig_regret_heatmap():
    H = 82
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.21, right=0.985, top=0.80, bottom=0.06, wspace=0.08)
    f3 = lambda v: f"{v:.3f}" if v < 0.1 else f"{v:.2f}"
    heat(axes[0], R_WORST, ROWS_R, f3, LogNorm(0.04, 0.9), "a", "Worst case: rare large errors")
    heat(axes[1], R_P95, ROWS_R, f3, LogNorm(0.001, 0.2), "b", "95th percentile: typical bad case", ylabels=False)
    fig.text(0.012, 0.955, "Regret: how much worse than the best method on the same case, as a share of the reference "
             "(0.1 = 10%). General weather gaps.", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.92, "Darker = larger (log scale). –: the method does not fill gaps this long.", fontsize=FS, color=MUTED)
    S.save(fig, "fig_regret_heatmap")


if __name__ == "__main__":
    fig_method_diagram(); fig_headline(); fig_error_heatmap(); fig_regret_heatmap()
