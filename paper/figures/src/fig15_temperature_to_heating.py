import sys; sys.path.insert(0, sys.argv[1])
import style as S
import numpy as np, pandas as pd, matplotlib.pyplot as plt
S.use()
FS = 7
d = pd.read_csv(sys.argv[2]); r = pd.read_csv(sys.argv[3])
d = d[d.season.str.startswith("heating")]
r = r[r.season.str.startswith("heating")].set_index("building_id")
NAMES = {"sf_se02": "Single-family house, 1960s", "school_se03": "School", "mf_se02": "Apartment block, 1960s",
         "office_se06_wwr60": "Office, large windows", "sf_se06": "Single-family house, recent", "mf_se06": "Apartment block, recent"}
order = r["kwh_m2_per_day_1C_too_cold_through_zero"].sort_values(ascending=False).index.tolist()
cols = dict(zip(order, ["#2e1145", "#5B2A86", "#7a4aa8", "#9a72c0", "#b99ad6", "#d3bfe6"]))
fig, ax = plt.subplots(figsize=(S.DOUBLE, 92 * S.MM))
fig.subplots_adjust(left=0.09, right=0.70, top=0.86, bottom=0.14)
x = -d.error_degree_days; y = d.heating_change_kwh_m2
ax.scatter(x, y, s=3, c=[cols[b] for b in d.building_id], alpha=0.35, lw=0, zorder=2)
X = 40
ax.set_xlim(-25, X); ax.set_ylim(-1.2, 2.0)
xx = np.array([-25, X])
ends = []
for b in order:
    k = r.loc[b, "kwh_m2_per_day_1C_too_cold_through_zero"]
    ax.plot(xx, k * xx, color=cols[b], lw=1.4, zorder=3)
    ends.append((k * X, b, k))
# labels at right, spread apart
ys = [e[0] for e in ends]; lab = list(ys)
for i in range(1, len(lab)):
    lab[i] = min(lab[i], lab[i-1] - 0.17)
for (ye, b, k), yl in zip(ends, lab):
    ax.annotate(f"{NAMES[b]}: {k*7:.2f} kWh/m²", xy=(X, ye), xytext=(X + 2.5, yl), textcoords="data",
                fontsize=FS, color=S.INK, va="center", annotation_clip=False,
                arrowprops=dict(arrowstyle="-", color=cols[b], lw=0.6, shrinkA=0, shrinkB=0))
ax.axhline(0, color=S.RULE, lw=0.6, zorder=1); ax.axvline(0, color=S.RULE, lw=0.6, zorder=1)
ax.axvline(7, color=S.MUTED, lw=0.7, ls="--", zorder=1)
ax.text(7.6, 1.88, "one week filled\n1 °C too cold", fontsize=FS, color=S.MUTED, va="top")
ax.text(X + 2.5, ends[0][0] + 0.38, "Heating cost of one week\nfilled 1 °C too cold", fontsize=FS, color=S.MUTED,
        weight="bold", va="bottom", annotation_clip=False) if False else None
fig.text(0.71, 0.865, "Heating cost of one week\nfilled 1 °C too cold", fontsize=FS, color=S.INK, weight="bold", va="bottom")
ax.set_xlabel("How much too cold the filled weather was, °C × days\n(for example, 7 = one week 1 °C too cold; negative = too warm)", fontsize=FS)
ax.set_ylabel("Extra heating over the gap\nand the week after, kWh/m²", fontsize=FS)
ax.tick_params(labelsize=FS)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.text(0.012, 0.955, "The heating cost of filling a gap 1 °C too cold: up to 0.29 kWh/m² per week, most in buildings that lose the most heat",
         fontsize=8, weight="bold", color=S.INK)
fig.text(0.012, 0.915, "Each dot is one hidden gap of two days or one week that starts in October to April; each line is one building.",
         fontsize=FS, color=S.MUTED)
fig.savefig(sys.argv[4] + ".png", dpi=600); fig.savefig(sys.argv[4] + ".pdf")
print(r["kwh_m2_per_day_1C_too_cold_through_zero"]*7)
