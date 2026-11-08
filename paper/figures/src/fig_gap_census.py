"""Gap census: most gaps are short, but long gaps hold most missing hours.

Data: Table 4 of the manuscript (SMHI hourly records 1999-2025).
"""
import matplotlib.pyplot as plt
import style as S

S.use()
FS = 7.0
CLASSES = ["1–3 h", "4–12 h", "13–48 h", "2–7 days", "1–4 weeks", "over 4 weeks"]
ROWS = [  # label, shares in %
    ("share of all gaps", [82.1, 12.4, 3.4, 0.9, 0.6, 0.5]),
    ("share of missing hours,\nusable files", [19.1, 14.9, 13.3, 15.3, 24.7, 12.7]),
    ("share of missing hours,\nall station-years", [6.4, 5.2, 5.0, 5.6, 14.2, 63.5]),
]
# one blue scale from short (light) to long (dark) gaps
COL = ["#e3edf7", "#c2d9ee", "#9cc3e4", "#6fa6d4", "#2f74b5", "#163f6b"]
TXT = [S.INK, S.INK, S.INK, S.INK, "white", "white"]

fig, ax = plt.subplots(figsize=(S.DOUBLE, 62 * S.MM))
fig.subplots_adjust(left=0.20, right=0.83, top=0.86, bottom=0.06)
H = 0.62
for i, (lab, v) in enumerate(ROWS):
    y = -i
    x = 0
    for k, s in enumerate(v):
        ax.barh(y, s, left=x, height=H, color=COL[k], edgecolor="white", lw=0.8)
        if s >= 4.5:
            ax.text(x + s / 2, y, f"{s:.0f}%", ha="center", va="center", fontsize=FS, color=TXT[k])
        x += s
    ax.text(-1.5, y, lab, ha="right", va="center", fontsize=FS, color=S.INK)
    short = sum(v[:4])
    ax.text(101.5, y, f"{short:.0f}%", ha="left", va="center", fontsize=8, weight="bold", color=S.INK)
# legend: one swatch per gap length
x = 0
for k, c in enumerate(CLASSES):
    ax.add_patch(plt.Rectangle((x, 0.62), 2.6, 0.2, color=COL[k], ec=COL[k], lw=0.3, clip_on=False))
    ax.text(x + 3.4, 0.72, c, ha="left", va="center", fontsize=FS, color=S.INK)
    x += 3.4 + len(c) * 1.25 + 3.5
ax.text(101.5, 0.72, "gaps up to 1 week\n(the lengths tested)", ha="left", va="center", fontsize=FS, color=S.MUTED)
ax.set_xlim(0, 100); ax.set_ylim(-2.45, 0.9)
ax.axis("off")
S.save(fig, "fig_gap_census")
