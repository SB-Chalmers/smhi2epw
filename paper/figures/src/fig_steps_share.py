"""Appendix figure (was Table A1): which step of the stepwise method fills the hours,
for 60 real station-years with little, moderate or much missing data."""
import matplotlib.pyplot as plt
import style as S

S.use()
FS = 7.0
STEPS = [("linear interpolation", "linear"), ("nearby station", "nearby"),
         ("daily pattern", "patterns"), ("ERA5", "era5")]
ROWS = [("complete enough to be\na reference year", [42, 35, 22, 0]),
        ("moderate missing data", [30, 26, 8, 37]),
        ("large missing data", [3, 4, 1, 93])]
TXT = ["#1d1d1f", "white", "white", "#1d1d1f"]

fig, ax = plt.subplots(figsize=(S.DOUBLE, 48 * S.MM))
fig.subplots_adjust(left=0.20, right=0.97, top=0.80, bottom=0.05)
for i, (lab, v) in enumerate(ROWS):
    x = 0
    tot = sum(v)
    for k, s in enumerate(v):
        w = s * 100 / tot
        if w > 0:
            ax.barh(-i, w, left=x, height=0.62, color=S.SRC[STEPS[k][1]], edgecolor="white", lw=0.8)
        if s >= 5:
            ax.text(x + w / 2, -i, f"{s}%", ha="center", va="center", fontsize=FS, color=TXT[k])
        x += w
    ax.text(-1.5, -i, lab, ha="right", va="center", fontsize=FS, color=S.INK)
x = 0
for name, key in STEPS:
    ax.add_patch(plt.Rectangle((x, 0.62), 2.6, 0.22, color=S.SRC[key], clip_on=False))
    ax.text(x + 3.4, 0.73, name, ha="left", va="center", fontsize=FS, color=S.INK)
    x += 3.4 + len(name) * 1.25 + 4
ax.set_xlim(0, 100); ax.set_ylim(-2.45, 0.9); ax.axis("off")
S.save(fig, "fig_steps_share")
