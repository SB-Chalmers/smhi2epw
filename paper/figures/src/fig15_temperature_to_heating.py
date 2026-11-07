import sys; sys.path.insert(0, sys.argv[1])
import style as S
import numpy as np, pandas as pd, matplotlib.pyplot as plt
S.use()
FS = 7
d = pd.read_csv(sys.argv[2]); r = pd.read_csv(sys.argv[3])
d = d[d.season.str.startswith("heating")]
r = r[r.season.str.startswith("heating")].set_index("building_id")
NAMES = {"sf_se02": "single-family house, 1960s", "school_se03": "school", "mf_se02": "apartment block, 1960s",
         "office_se06_wwr60": "office, large windows", "sf_se06": "single-family house, recent", "mf_se06": "apartment block, recent"}
order = r["kwh_m2_per_day_1C_too_cold_through_zero"].sort_values(ascending=False).index.tolist()
# grey lines; one non-method hue (teal) for the steepest (dark) and the flattest (light) building
cols = {b: S.GREY["mid"] for b in order}
cols[order[0]] = "#1b4f4a"; cols[order[-1]] = "#7fbfb6"
fig, ax = plt.subplots(figsize=(S.DOUBLE, 84 * S.MM))
fig.subplots_adjust(left=0.10, right=0.68, top=0.90, bottom=0.17)
x = -d.error_degree_days; y = d.heating_change_kwh_m2
ax.scatter(x, y, s=3, c=S.GREY["light"], alpha=0.6, lw=0, zorder=2)
X = 40
ax.set_xlim(-25, X); ax.set_ylim(-1.2, 2.0)
xx = np.array([-25, X])
ends = []
for b in order:
    k = r.loc[b, "kwh_m2_per_day_1C_too_cold_through_zero"]
    ax.plot(xx, k * xx, color=cols[b], lw=1.4 if b in (order[0], order[-1]) else 1.0, zorder=3)
    ends.append((k * X, b, k))
# labels at right, spread apart
ys = [e[0] for e in ends]; lab = list(ys)
for i in range(1, len(lab)):
    lab[i] = min(lab[i], lab[i-1] - 0.19)
for (ye, b, k), yl in zip(ends, lab):
    # short elbow leader: never crosses another, never touches the text
    ax.plot([X, X + 1.0, X + 2.2], [ye, yl, yl], color=S.GREY["mid"], lw=0.5, clip_on=False, zorder=3)
    ax.text(X + 2.8, yl, f"{NAMES[b]}: {k*7:.2f} kWh/m²", fontsize=FS, color=S.INK, va="center", clip_on=False)
ax.axhline(0, color=S.RULE, lw=0.6, zorder=1); ax.axvline(0, color=S.RULE, lw=0.6, zorder=1)
ax.axvline(7, color=S.MUTED, lw=0.7, ls="--", zorder=1)
ax.text(7.6, 1.88, "one week filled\n1 °C too cold", fontsize=FS, color=S.MUTED, va="top")
fig.text(0.695, 0.905, "heating cost of one week\nfilled 1 °C too cold", fontsize=FS, color=S.MUTED, va="bottom")
ax.set_xlabel("how much too cold the filled weather was, °C × days\n(for example, 7 = one week 1 °C too cold; negative = too warm)", fontsize=FS)
ax.set_ylabel("extra heating over the gap\nand the week after, kWh/m²", fontsize=FS)
ax.tick_params(labelsize=FS)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(sys.argv[4] + ".png", dpi=600); fig.savefig(sys.argv[4] + ".pdf")
print(r["kwh_m2_per_day_1C_too_cold_through_zero"]*7)
