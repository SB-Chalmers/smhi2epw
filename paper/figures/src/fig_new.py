"""Final-revision figures: method diagram, two-panel headline, error and regret heat maps."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
import style as S
from style import INK, MUTED, RULE, ACCENT, ACCENT_SEQ, OTHER, box, arrow

S.use()
FS = 7.0
PURPLES = LinearSegmentedColormap.from_list("p", ["#f7f3fb", "#d9c8ea", "#a882c8", "#7a4aa6", ACCENT, "#2e1047"])
GAPS = ["3 hours", "12 hours", "48 hours", "1 week"]


def title(ax, letter, text, y=1.04, x=0):
    ax.text(x, y, f"{letter}  {text}", transform=ax.transAxes, fontsize=7.5, weight="bold", va="bottom")


# ---------------------------------------------------------------- method diagram
def fig_method_diagram():
    """Fig 5: how each method fills one real 48-hour gap (Stockholm-Arlanda, April 2023).

    Data: source/data/method_sketch_week.csv, fills rerun with the campaign's own code.
    """
    import pandas as pd
    from pathlib import Path
    d = pd.read_csv(Path(__file__).resolve().parents[1] / "source" / "data" / "method_sketch_week.csv",
                    parse_dates=["time"])
    t = d.time
    ing = d.in_gap == 1
    i0, i1 = np.flatnonzero(ing)[[0, -1]]
    g0, g1 = t.iloc[i0] - pd.Timedelta(minutes=30), t.iloc[i1] + pd.Timedelta(minutes=30)
    # draw the measured line through the gap edges so fills join it
    pre = d.index <= i0 - 1
    post = d.index >= i1 + 1
    panels = [
        ("Linear interpolation", "A straight line between the last value\nbefore and the first value after the gap",
         "linear", None, "linear"),
        ("Daily patterns", "The shape of the days either side,\nadjusted to meet both ends of the gap",
         "daily_patterns", None, "patterns"),
        ("Four-week average (as in diyepw)", "The average of the same hour of day over\nfour weeks; here too cold",
         "four_week_average", None, "fourweek"),
        ("Nearby station", "The same hours from a station 30 km away,\nchecked and shifted to match the main station",
         "stepwise", "nearby_station", "nearby"),
        ("ERA5", "The same hours from a global weather\nmodel (reanalysis)",
         "era5", "era5", "era5"),
        ("Stepwise", "Takes the first source that works: here the\nnearby station passed its checks (Figure 1)",
         "stepwise", None, "stepwise"),
    ]
    H = 96
    fig = plt.figure(figsize=(S.DOUBLE, H * S.MM))
    gs = fig.add_gridspec(2, 3, left=0.06, right=0.985, top=0.87, bottom=0.07, wspace=0.16, hspace=0.70)
    letters = iter("abcdef")
    SRCC = "#c7c7cc"
    import matplotlib.dates as mdates
    for k, (name, desc, col, src, ckey) in enumerate(panels):
        ax = fig.add_subplot(gs[k // 3, k % 3])
        ax.axvspan(g0, g1, color="#ececef", lw=0, zorder=0)
        if src:
            ax.plot(t, d[src].where(~ing), color=SRCC, lw=0.8, zorder=1)
        ax.plot(t[pre | (d.index == i0 - 1)], d.measured[pre], color=INK, lw=0.9, zorder=2)
        ax.plot(t[post], d.measured[post], color=INK, lw=0.9, zorder=2)
        # hidden truth, joined to the measured ends
        jt = d.index[(d.index >= i0 - 1) & (d.index <= i1 + 1)]
        ax.plot(t[jt], d.measured[jt], color=MUTED, lw=0.8, ls=(0, (2, 1.5)), zorder=2)
        fill = d[col].where(ing)
        ax.plot(t, fill, color=S.SRC[ckey], lw=1.6, zorder=3)
        mae = (d[col][ing] - d.measured[ing]).abs().mean()
        ax.text(t.iloc[-1], -7, f"mean error in the gap: {mae:.1f} °C", ha="right",
                va="bottom", fontsize=FS, color=S.SRC[ckey] if ckey != "fourweek" else "#b0558e",
                weight="bold" if ckey == "stepwise" else "normal")
        ax.set_ylim(-9, 26)
        ax.set_yticks([0, 10, 20])
        ax.set_xlim(t.iloc[0], t.iloc[-1])
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d Apr"))
        ax.tick_params(labelsize=FS, length=2)
        if k % 3:
            ax.set_yticklabels([])
        if k < 3:
            ax.set_xticklabels([])
        ax.grid(axis="y", color=RULE, lw=0.4, zorder=0)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(RULE)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        title(ax, next(letters), name, y=1.30)
        ax.text(0, 1.04, desc, transform=ax.transAxes, fontsize=FS, color=MUTED, va="bottom", linespacing=1.15)
        if k == 0:
            ax.text(g0 + (g1 - g0) / 2, 24, "gap", ha="center", va="center", fontsize=FS, color=MUTED)
            ax.text(t.iloc[2], 24, "measured", va="center", fontsize=FS, color=INK)
            j = i0 + 24 + int(np.argmax(d.measured.values[i0 + 24:i1]))
            ax.annotate("hidden true values", xy=(t.iloc[j], d.measured.iloc[j] + 0.3),
                        xytext=(t.iloc[i1 + 3], 24), fontsize=FS, color=MUTED, va="center",
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5, shrinkA=1, shrinkB=1))
        if src:
            j = i1 + 8 + int(np.argmax(d[src].values[i1 + 8:i1 + 20]))
            ax.annotate("nearby station" if src == "nearby_station" else "ERA5", xy=(t.iloc[j], d[src].iloc[j] + 0.3),
                        xytext=(t.iloc[i1 + 14], 24), fontsize=FS, color="#8e8e93", va="center",
                        arrowprops=dict(arrowstyle="-", color=SRCC, lw=0.5))
        if k % 3 == 0:
            ax.set_ylabel("air temperature, °C", fontsize=FS, color=INK, labelpad=2)
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
def heat(ax, vals, rows, fmt, norm, letter, ttl, ylabels=True, sep=None):
    """Heat map in four grey bands (style.BANDS); numbers printed in every cell.

    The Stepwise row is outlined in the accent colour. sep: draw a rule below this row index.
    """
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Rectangle
    V = np.array([[np.nan if v is None else float(v) for v in r] for r in vals], dtype=float)
    M = np.ma.masked_invalid(V)
    cm = ListedColormap(S.BAND_COL); cm.set_bad("#ffffff")
    bn = BoundaryNorm(S.BANDS, cm.N)
    ax.imshow(M, cmap=cm, norm=bn, aspect="auto")
    for i in range(V.shape[0]):
        for j in range(V.shape[1]):
            v = V[i, j]
            if np.isnan(v):
                ax.text(j, i, "–", ha="center", va="center", fontsize=FS, color=MUTED)
                continue
            dark = v >= S.BANDS[3]
            ax.text(j, i, cell(vals[i][j]), ha="center", va="center", fontsize=FS, color="white" if dark else INK,
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
    if "Stepwise" in rows:
        i = rows.index("Stepwise")
        ax.add_patch(Rectangle((-0.47, i - 0.47), V.shape[1] - 0.06, 0.94, fill=False, ec=INK, lw=1.0,
                               zorder=5, clip_on=False))
    if sep is not None:
        ax.axhline(sep + 0.5, color=INK, lw=0.9)
    title(ax, letter, ttl, y=1.03)


def band_key(fig, x, y, what="error"):
    """Key for the four grey bands, in figure coordinates (x = left edge, y = centre)."""
    from matplotlib.patches import Rectangle
    r = fig.canvas.get_renderer()
    W = fig.get_figwidth() * fig.dpi
    def put(xx, txt, col):
        t = fig.text(xx, y, txt, fontsize=FS, color=col, va="center", ha="left")
        return xx + t.get_window_extent(r).width / W
    x = put(x, what, MUTED) + 0.015
    sw = 0.02
    for c, lab in zip(S.BAND_COL, S.BAND_LAB):
        fig.patches.append(Rectangle((x, y - 0.011), sw, 0.022, transform=fig.transFigure, fc=c,
                                     ec=RULE, lw=0.4, figure=fig))
        x = put(x + sw + 0.006, lab, INK) + 0.02


def cell(v):
    """Two significant figures, never more decimals than the source value has."""
    if v is None:
        return None
    sv = str(v)
    src_dec = len(sv.split(".")[1]) if "." in sv and isinstance(v, str) else 9
    f = float(v)
    dec = 2 if f < 1 else (1 if f < 10 else 0)
    dec = min(dec, src_dec)
    return f"{round(f, dec):.{dec}f}"


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
    topct = lambda T: [[None if v is None else f"{float(v) * 100:.1f}" for v in r] for r in T]
    heat(axes[0], topct(R_WORST), ROWS_R, None, LogNorm(4, 90), "a", "Worst case: rare large errors")
    heat(axes[1], topct(R_P95), ROWS_R, None, LogNorm(0.1, 20), "b", "95th percentile", ylabels=False)
    fig.text(0.012, 0.955, "Regret: how much worse than the best method on the same case, as % of the reference "
             "value. General weather gaps.", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.92, "Darker = larger (log scale). –: the method does not fill gaps this long.", fontsize=FS, color=MUTED)
    S.save(fig, "fig_regret_heatmap")


if __name__ == "__main__":
    fig_method_diagram(); fig_headline(); fig_error_heatmap(); fig_regret_heatmap()
