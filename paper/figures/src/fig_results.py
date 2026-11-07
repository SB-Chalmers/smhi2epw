"""Results figures, round 2 (manuscript Figs 5-9 and 11).

Reads paper/figures/source/data/results/*.csv.

House rules (round 2): the panel title states the finding; the stepwise
method is the one accent colour and every other method is grey; lines and
series are labelled directly, with no legends; the manuscript's method names
(Table 6); season colours as in Fig. 4. No text is smaller than
style.MIN_FS at print size. Output: vector PDF, SVG and a 600 dpi PNG.

    python fig_results.py

File names are kept from round 1; the manuscript numbers are
fig06 = Fig. 5, fig09 = Fig. 6, fig10 = Fig. 7, fig08 = Fig. 8,
fig07 = Fig. 9, fig11 = Fig. 11.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import style as S
from style import (ACCENT, ACCENT_SEQ, GAP_LABEL, GREY, INK, METHOD, MIN_FS, MUTED,
                   OTHER, RULE, SEASON_COL, end_labels)

S.use()
RES = Path(__file__).resolve().parents[1] / "source" / "data" / "results"
GAPS = [3, 12, 48, 168]
X = np.arange(len(GAPS))
FS = MIN_FS
FS_AX = 7.0
N_MIN = 10   # no percentile or share is drawn from fewer cases than this

plt.rcParams.update({"xtick.labelsize": FS_AX, "ytick.labelsize": FS_AX,
                     "axes.labelsize": FS_AX})

# The stepwise method switches to ERA5 for general-weather gaps over 48 hours
# and solar gaps over 3 hours; shorter gaps follow the no-switch order
# ("automatic"). Built from the automatic and era5 rows, as in
# robustness/gap-type-rule.csv.
ERA5_FROM = {"meteorology": 168, "solar": 12}
STEP = "gap_type_rule"
LENS = {"3 h": 3, "12 h": 12, "2 days": 48, "1 week": 168}
SCOPE_TITLE = {"meteorology": "General weather hidden (temperature, humidity, pressure, wind)",
               "solar": "Solar radiation hidden (global, direct and diffuse)"}


def add_step(d):
    if "method" not in d or "scope" not in d or (d.method == STEP).any():
        return d
    hours = d["gap_hours"] if "gap_hours" in d else d["gap_length"].map(LENS)
    use_era5 = hours >= d["scope"].map(ERA5_FROM)
    pick = ((d.method == "automatic") & ~use_era5) | ((d.method == "era5") & use_era5)
    rule = d[pick].copy()
    rule["method"] = STEP
    return pd.concat([d, rule], ignore_index=True)


def read(name, scope="meteorology"):
    d = add_step(pd.read_csv(RES / f"{name}.csv"))
    return d[d["scope"] == scope] if "scope" in d else d


def row_title(fig, ax, text, h_mm, up_mm=7.5):
    bb = ax.get_position()
    fig.text(0.012, bb.y1 + up_mm / h_mm, text, fontsize=7.5, weight="bold",
             color=INK, va="bottom")


def gap_axis(ax, xlabel=True, pad=0.5):
    ax.set_xticks(X)
    ax.set_xticklabels([GAP_LABEL[g] for g in GAPS])
    ax.set_xlim(-pad, len(GAPS) - 1 + pad)
    if xlabel:
        ax.set_xlabel("length of each gap")
    ax.grid(axis="y", color=RULE, lw=0.4, zorder=0)
    ax.set_axisbelow(True)


def title(ax, letter, text, y=1.04):
    ax.text(0, y, f"{letter}  {text}", transform=ax.transAxes, fontsize=7.5,
            weight="bold", va="bottom")


def f1(v):
    return "<0.1" if 0 <= v < 0.05 else f"{v:.1f}"


# ------------------------------------------------------------- Fig. 5 annual error
EVENT_FOR = {"heating": ("cold_spell_coldest_hour", "cold spell"),
             "cooling": ("heatwave_hottest_hour", "heatwave")}
FIG5_TITLES = {("meteorology", "heating"): "Heating: under 2 % even for a week",
               ("meteorology", "cooling"): "Cooling: 6 % when a heatwave week is hidden",
               ("solar", "heating"): "Heating: about 1 % at most",
               ("solar", "cooling"): "Cooling: 20 % for a hidden heatwave week"}


def fig_annual():
    H = 124
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.075, right=0.86, top=0.89, bottom=0.08, wspace=0.42, hspace=0.62)
    letters = iter("abcd")
    for r, scope in enumerate(("meteorology", "solar")):
        ann = read("annual-errors", scope)
        anc = read("annual-errors-by-anchor", scope)
        for ax, mode in ((axes[r, 0], "heating"), (axes[r, 1], "cooling")):
            anchor, ev = EVENT_FOR[mode]
            rnd = ann[(ann.method == STEP) & (ann.sampling == "random_seasonal")] \
                .set_index("gap_hours").loc[GAPS, f"{mode}_abs_p95_pct"].to_numpy()
            evt = anc[(anc.method == STEP) & (anc.anchor_name == anchor)] \
                .set_index("gap_hours").loc[GAPS, f"{mode}_abs_p95_pct"].to_numpy()
            ax.plot(X, rnd, color=ACCENT, lw=1.0, marker="o", ms=4.5, zorder=3)
            ax.plot(X, evt, color=ACCENT, lw=1.0, ls=(0, (2.5, 1.5)), marker="o", ms=4.5,
                    mfc="white", mec=ACCENT, mew=1.1, zorder=3)
            top = max(rnd.max(), evt.max()) * 1.18
            ax.set_ylim(-top * 0.06, top)
            for xi, a, b in zip(X, rnd, evt):
                hi, lo = (a, b) if a >= b else (b, a)
                skip = scope == "solar" and mode == "cooling" and xi == X[-1]
                ax.annotate("" if skip else f1(hi), (xi, hi), xytext=(0, 4.5), textcoords="offset points",
                            fontsize=FS, ha="center", va="bottom", color=INK)
                if hi - lo > top * 0.08:
                    ax.annotate(f1(lo), (xi, lo), xytext=(0, -4.5), textcoords="offset points",
                                fontsize=FS, ha="center", va="top", color=INK)
            end_labels(ax, [(rnd[-1], "random gaps", ACCENT, "normal"),
                            (evt[-1], f"gap at a {ev}", ACCENT, "normal")],
                       X[-1] + 0.1, min_gap=top * 0.09)
            if scope == "solar" and mode == "cooling":
                ax.annotate("20% (95th pct.)", xy=(X[-1], evt[-1]), xytext=(X[-1] - 1.25, evt[-1] * 0.93),
                            fontsize=FS, color=ACCENT, ha="right", va="center",
                            arrowprops=dict(arrowstyle="-", color=ACCENT, lw=0.6))
            gap_axis(ax, pad=0.35)
            title(ax, next(letters), FIG5_TITLES[(scope, mode)])
            ax.set_ylabel("95th percentile error,\n% of annual demand" if mode == "heating" else "")
        row_title(fig, axes[r, 0], SCOPE_TITLE[scope], H)
    S.save(fig, "fig06_annual_error")


# ------------------------------------------------------------- Fig. 6 peaks
TIMING = [("same hour", ACCENT_SEQ[0]), ("within a day", ACCENT_SEQ[1]),
          ("more than a day", ACCENT_SEQ[2])]


def fig_peaks():
    pk = read("peak-errors")
    a = pk[(pk.method == STEP) & (pk.sampling == "weather_extremes")].set_index("gap_hours").loc[GAPS]
    pc = read("peak-cases")
    pc = pc[pc.method == STEP]
    rng = np.random.default_rng(7)
    H = 116
    fig, axes = plt.subplots(2, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.08, right=0.87, top=0.92, bottom=0.1, wspace=0.3, hspace=0.6)
    titles = {"heating": ("Heating peaks: half move over a day at one week",
                          "Heating peak error: small for most, large for a few"),
              "cooling": ("Cooling peaks: a fifth to a third move over a day",
                          "Cooling peak error: mostly near 1 W/m²")}
    for j, mode in enumerate(("heating", "cooling")):
        ax = axes[0, j]
        kept = a[f"{mode}_peak_hour_kept_share"].to_numpy() * 100
        far = a[f"{mode}_peak_moved_over_24h_share"].to_numpy() * 100
        near = 100 - kept - far
        bottom = np.zeros(len(GAPS))
        for (lab, col), v in zip(TIMING, (kept, near, far)):
            ax.bar(X, v, bottom=bottom, width=0.62, color=col, edgecolor="white", lw=0.6, zorder=3)
            for xi, b0, vi in zip(X, bottom, v):
                if vi >= 9:
                    ax.text(xi, b0 + vi / 2, f"{vi:.0f}", ha="center", va="center", fontsize=FS,
                            color="white" if col == ACCENT_SEQ[2] else INK, zorder=4)
            bottom += v
        if j == 1:
            b0 = 0
            for (lab, col), v in zip(TIMING, (kept[-1], near[-1], far[-1])):
                ax.text(X[-1] + 0.4, b0 + v / 2, lab, fontsize=FS, color=INK, va="center", ha="left",
                        clip_on=False)
                b0 += v
        gap_axis(ax, pad=0.45)
        ax.set_ylim(0, 100)
        title(ax, "ab"[j], titles[mode][0])
        ax.set_ylabel("% of event gaps that\nhid the yearly peak" if j == 0 else "")

        ax = axes[1, j]
        w = 0.42
        for k, (samp, col, fill) in enumerate((("random_seasonal", OTHER, True),
                                               ("weather_extremes", ACCENT, False))):
            xs = X + (k - 0.5) * w
            for xi, g in zip(xs, GAPS):
                v = pc[(pc.sampling == samp) & (pc["mode"] == mode) & (pc.gap_hours == g)] \
                    .abs_peak_error_w_m2.to_numpy()
                jit = rng.uniform(-w * 0.32, w * 0.32, len(v))
                ax.scatter(xi + jit, v, s=4, c=col if fill else "white", edgecolors=col,
                           linewidths=0.4, alpha=0.85, zorder=3)
                if len(v) >= N_MIN:
                    med, p95 = np.median(v), np.percentile(v, 95)
                    ax.plot([xi - w * 0.42, xi + w * 0.42], [med, med], color=INK, lw=1.3, zorder=5)
                    ax.plot([xi - w * 0.42, xi + w * 0.42], [p95, p95], color=INK, lw=0.8,
                            ls=(0, (2, 1)), zorder=5)
        gap_axis(ax)
        for k, (lab, col) in enumerate((("random", OTHER), ("event", ACCENT)) if j == 0 else ()):
            xi = X[-1] + (k - 0.5) * w
            v = pc[(pc.sampling == ("random_seasonal", "weather_extremes")[k]) & (pc["mode"] == mode)
                   & (pc.gap_hours == 168)].abs_peak_error_w_m2.max()
            ax.text(xi, v + 1.0, lab, fontsize=FS, color=col, ha="center", va="bottom")
        ax.set_ylim(0, 29)
        if j == 1:
            ax.text(X[-1] + 0.5, 6.2, "95th percentile", fontsize=FS, va="center", clip_on=False)
            ax.text(X[-1] + 0.5, 1.2, "median", fontsize=FS, va="center", clip_on=False)
        title(ax, "cd"[j], titles[mode][1])
        ax.set_ylabel("peak load error, W/m²" if j == 0 else "")
    S.save(fig, "fig09_peaks")


# ------------------------------------------------------------- Fig. 7 events
OUTCOME = [("kept", GREY["dark"]), ("changed", GREY["light"]), ("lost", ACCENT)]


def fig_events():
    ev = read("event-preservation-3day")
    ev = ev[ev.sampling == "weather_extremes"]
    types = [("heatwave", "Heatwaves", "3+ days ≥ 25 °C"),
             ("warm_spell", "Warm spells", "3+ days above the summer 95th pct."),
             ("cold_spell", "Cold spells", "3+ days ≤ −10 °C"),
             ("relative_cold_spell", "Relative cold spells", "3+ days below the winter 5th pct.")]
    fig, axes = plt.subplots(1, 4, figsize=(S.DOUBLE, 70 * S.MM), sharey=True)
    fig.subplots_adjust(left=0.065, right=0.905, top=0.68, bottom=0.22, wspace=0.14)
    XX = np.array([0, 1, 2, 3, 4.3])
    for ax, (t, name, rule) in zip(axes, types):
        d = ev[ev.event_type == t]
        st = d[d.method == STEP].set_index("gap_hours").loc[GAPS]
        ln = d[(d.method == "linear_only") & (d.gap_hours == 168)].iloc[0]
        rows = [st.loc[g] for g in GAPS] + [ln]
        bottom = np.zeros(len(rows))
        for key, col in OUTCOME:
            v = np.array([r[{"kept": "kept_exact_share", "changed": "changed_bounds_share",
                             "lost": "lost_share"}[key]] for r in rows]) * 100
            ax.bar(XX, v, bottom=bottom, width=0.7, color=col, edgecolor="white", lw=0.6, zorder=3)
            bottom += v
        for x, r in zip(XX, rows):
            ax.text(x, 101.5, f"n={int(r['reference_exposed_events'])}", ha="center", va="bottom",
                    fontsize=FS - 1, color=INK)
        kept_step, kept_line = rows[3]["kept_exact_share"] * 100, ln["kept_exact_share"] * 100
        ax.set_xticks(XX)
        ax.set_xticklabels(["3 h", "12 h", "48 h", "1\nweek", "1 week,\nlinear\ninterp."], fontsize=FS)
        ax.axvline(3.65, color=RULE, lw=0.6)
        ax.set_ylim(0, 100)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.text(0.5, 1.3, name, transform=ax.transAxes, ha="center", va="bottom", fontsize=7.5,
                weight="bold")
        ax.text(0.5, 1.24, f"{kept_step:.0f} % kept at one week\n(linear interpolation: {kept_line:.0f} %)",
                transform=ax.transAxes, ha="center", va="top", fontsize=FS, linespacing=1.2)
    axes[0].set_ylabel("% of events hit by the gap")
    for (key, col), yk in zip(OUTCOME, (15, 50, 85)):
        axes[-1].scatter([XX[-1] + 0.75], [yk], s=22, marker="s", c=col, clip_on=False)
        axes[-1].text(XX[-1] + 1.0, yk, key, fontsize=FS, va="center", ha="left",
                      color=ACCENT if key == "lost" else INK, clip_on=False)
    fig.text(0.5, 0.03, "Stepwise method; gap centred on the event", ha="center", fontsize=FS_AX)
    S.save(fig, "fig10_events")


# ------------------------------------------------------------- Fig. 8 where the gap falls
ROWS8 = [("winter", "random_seasonal", "winter", "heating", False),
         ("spring", "random_seasonal", "spring", "heating", False),
         ("autumn", "random_seasonal", "autumn", "heating", False),
         ("cold spell", "cold_spell_coldest_hour", "winter", "heating", True),
         ("summer", "random_seasonal", "summer", "cooling", False),
         ("heatwave", "heatwave_hottest_hour", "summer", "cooling", True)]


def fig_position():
    H = 100
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.13, right=0.97, top=0.80, bottom=0.11, wspace=0.18)
    fig.text(0.012, 0.97, "Error that 95% of cases stay below over the gap and the following week, as % of annual heating "
             "(heating rows) or annual cooling (cooling rows).", fontsize=FS, color=MUTED)
    fig.text(0.012, 0.94, "Ringed dots: gap centred on a cold spell (heating) or a heatwave (cooling). "
             "Summer heating is below 0.1% and not shown.", fontsize=FS, color=MUTED)
    titles = {"meteorology": "General weather: winter drives heating, summer cooling",
              "solar": "Solar: a hidden heatwave week dominates"}
    global VMAX_POS
    VMAX_POS = 0
    for sc in ("meteorology", "solar"):
        g = read("gap-window", sc)
        g = g[g.method == STEP]
        for (_, event, season, mode, _) in ROWS8:
            v = g[(g.event_type == event) & (g.season == season) & (g["mode"] == mode)]["window_abs_p95_pct"]
            if len(v):
                VMAX_POS = max(VMAX_POS, float(v.max()))
    for ax, scope, letter in zip(axes, ("meteorology", "solar"), "ab"):
        gw = read("gap-window", scope)
        a = gw[gw.method == STEP]
        vals = np.full((len(ROWS8), len(GAPS)), np.nan)
        for i, (_, event, season, mode, _) in enumerate(ROWS8):
            d = a[(a.event_type == event) & (a.season == season) & (a["mode"] == mode)] \
                .set_index("gap_hours").reindex(GAPS)
            vals[i] = d["window_abs_p95_pct"].to_numpy()
        vmax = VMAX_POS
        for i, (name, event, season, mode, ring) in enumerate(ROWS8):
            for j, v in enumerate(vals[i]):
                size = 520 * np.sqrt(max(v, 0) / vmax) + 4
                ax.scatter(j, i, s=size, c=SEASON_COL[season], edgecolors=INK if ring else "white",
                           linewidths=1.3 if ring else 0.4, zorder=3)
                ax.annotate(f1(v), (j, i), xytext=(np.sqrt(size) / 2 + 2.5, 0),
                            textcoords="offset points", fontsize=FS, va="center", ha="left",
                            color=INK, zorder=4)
        ax.axhline(3.5, color=RULE, lw=0.6)
        ax.set_xticks(range(len(GAPS)))
        ax.set_xticklabels([GAP_LABEL[g] for g in GAPS])
        ax.set_yticks(range(len(ROWS8)))
        ax.set_yticklabels([r[0] for r in ROWS8] if letter == "a" else [])
        ax.tick_params(length=0)
        for side in ("left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.set_xlim(-0.5, len(GAPS) - 0.1)
        ax.set_ylim(len(ROWS8) - 0.4, -0.6)
        ax.set_xlabel("length of each gap")
        title(ax, letter, titles[scope], y=1.06)
        if letter == "a":
            ax.text(-0.3, 1.5, "heating", transform=ax.get_yaxis_transform(), rotation=90,
                    ha="center", va="center", fontsize=FS, color=MUTED)
            ax.text(-0.3, 4.5, "cooling", transform=ax.get_yaxis_transform(), rotation=90,
                    ha="center", va="center", fontsize=FS, color=MUTED)
    S.save(fig, "fig08_gap_position")


# ------------------------------------------------------------- Figs 9 and 11: methods
ORDER = ["linear_only", "diyepw_style", "era5", "automatic_legacy", "donor_assessed",
         "automatic", STEP]
ROWS3 = (("full", "meteorology", "General weather hidden: all gaps"),
         ("subset", "meteorology", "General weather hidden: only gaps where a nearby station passed the test (about 40 %)"),
         ("full", "solar", "Solar radiation hidden: all gaps (no nearby-station step)"))


def method_panel(ax, d, col, methods, scale, cap, fmt):
    """Ranked dot chart: one row per method, open dot = 48 h, filled dot = 1 week.

    Rows are sorted by the one-week value, best at the top. A value above cap
    is drawn at the axis edge with an arrow and its number.
    """
    rows = []
    for m in methods:
        s = d[d.method == m].set_index("gap_hours").reindex([48, 168])[col] * scale
        if s.isna().any():
            continue
        rows.append((m, float(s.loc[48]), float(s.loc[168])))
    rows.sort(key=lambda r: (r[2], r[1]))
    for i, (m, v48, v168) in enumerate(rows):
        lab, colr = METHOD[m]
        step = m == STEP
        c = ACCENT if step else OTHER
        if step:
            ax.axhspan(i - 0.45, i + 0.45, color="#f1ebf6", zorder=0, lw=0)
        p48, p168 = min(v48, cap), min(v168, cap)
        ax.plot([p48, p168], [i, i], color=c, lw=0.8, zorder=2)
        ax.scatter([p48], [i], s=16, facecolors="white", edgecolors=c, linewidths=0.9, zorder=3,
                   clip_on=False)
        ax.scatter([p168], [i], s=20 if step else 16, c=c, zorder=4, clip_on=False)
        for v, pv in ((v48, p48), (v168, p168)):
            if v > cap:
                ax.annotate("", xy=(cap * 1.06, i), xytext=(cap * 0.99, i),
                            arrowprops=dict(arrowstyle="-|>", color=c, lw=0.8, mutation_scale=6),
                            annotation_clip=False)
        ax.annotate(fmt(v168), (max(p168, p48), i), xytext=(9 if max(v168, v48) > cap else 4.5, 0),
                    textcoords="offset points", fontsize=FS, va="center", ha="left",
                    color=ACCENT if step else INK, weight="bold" if step else "normal",
                    annotation_clip=False)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([METHOD[r[0]][0] for r in rows], fontsize=FS)
    for t, r in zip(ax.get_yticklabels(), rows):
        if r[0] == STEP:
            t.set_color(ACCENT)
            t.set_weight("bold")
    ax.set_ylim(len(rows) - 0.5, -0.9)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, cap)
    ax.grid(axis="x", color=RULE, lw=0.4, zorder=0)
    ax.set_axisbelow(True)


def method_figure(name_full, name_subset, col, scale, caps, xlabel, titles, fname, fmt):
    H = 170
    fig, axes = plt.subplots(3, 2, figsize=(S.DOUBLE, H * S.MM))
    fig.subplots_adjust(left=0.2, right=0.95, top=0.875, bottom=0.06, wspace=0.85, hspace=0.95)
    letters = iter("abcdef")
    for r, (kind, scope, rtitle) in enumerate(ROWS3):
        if kind == "full":
            d = read(name_full, scope).copy()
            if "gap_hours" not in d:
                d["gap_hours"] = d["gap_length"].map(LENS)
            if "sampling" in d:
                d = d[d.sampling == "random_seasonal"]
            methods = [m for m in ORDER if m != "donor_assessed"]
        else:
            d = read(name_subset, scope)
            d = d[d.sampling == "random_seasonal"]
            methods = ORDER
        if scope == "solar":
            methods = [m for m in methods if m != "automatic_legacy"]
        for c, mode in enumerate(("heating", "cooling")):
            ax = axes[r, c]
            method_panel(ax, d, col.format(mode=mode), methods, scale, caps[(r, mode)], fmt)
            ax.text(-0.62, 1.13, f"{next(letters)}  {titles[(r, mode)]}", transform=ax.transAxes,
                    fontsize=7.5, weight="bold", va="bottom")
            ax.set_xlabel(xlabel, fontsize=FS)
        row_title(fig, axes[r, 0], rtitle, H, up_mm=10)
    fig.text(0.012, 0.975, "Open dot: 48-hour gaps.  Filled dot and number: one-week gaps.  "
             "Methods ranked by the one-week value, best at the top.", fontsize=FS, color=MUTED)
    S.save(fig, fname)


def fig_methods():
    caps = {(0, "heating"): 2.4, (0, "cooling"): 7, (1, "heating"): 1.6, (1, "cooling"): 7,
            (2, "heating"): 1.6, (2, "cooling"): 7}
    titles = {(0, "heating"): "Heating: methods close; linear interpolation worst",
              (0, "cooling"): "Cooling: no switch does best at one week",
              (1, "heating"): "Heating: nearby station and ERA5 only close",
              (1, "cooling"): "Cooling: nearby station best at one week",
              (2, "heating"): "Heating: Stepwise and ERA5 only lowest",
              (2, "cooling"): "Cooling: Stepwise and ERA5 only lowest"}
    method_figure("method-steps", "method-steps-donor-subset", "{mode}_abs_p95_pct", 1.0, caps,
                  "95th percentile error, % of annual demand", titles, "fig07_methods",
                  lambda v: f"{v:.1f}")


def fig_monthly():
    caps = {(r, m): 60 for r in range(3) for m in ("heating", "cooling")}
    titles = {(0, "heating"): "Heating: only linear interpolation fails often",
              (0, "cooling"): "Cooling: one month in five fails at one week",
              (1, "heating"): "Heating: almost no months fail",
              (1, "cooling"): "Cooling: nearby station fails least",
              (2, "heating"): "Heating: only linear interpolation fails often",
              (2, "cooling"): "Cooling: one month in four fails at one week"}
    method_figure("monthly-error", "method-steps-donor-subset", "{mode}_months_outside", 100.0,
                  caps, "% of months outside ±5 % of the reference", titles, "fig11_monthly",
                  lambda v: f"{v:.0f} %")


def _add_outside():
    """Share of months outside ±5 % = 1 - share within, for the monthly tables."""
    global read
    base = read

    def read2(name, scope="meteorology"):
        d = base(name, scope).copy()
        for mode in ("heating", "cooling"):
            c = f"{mode}_months_within_5pct"
            if c in d:
                d[f"{mode}_months_outside"] = 1 - d[c]
        return d
    read = read2


_add_outside()


if __name__ == "__main__":
    fig_annual()
    fig_peaks()
    fig_events()
    fig_position()
    fig_methods()
    fig_monthly()
