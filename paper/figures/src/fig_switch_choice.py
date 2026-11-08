"""Where to switch to ERA5: worst case for the heating and cooling peak with a
one-day switch, a two-day switch and no switch (general weather gaps).

Numbers are the worst regrets reported in Section 6.6 (pooled over random and
event gaps, each event week counted once).
"""

from __future__ import annotations

import matplotlib.pyplot as plt

import style as S

OPTS = ["switch after 1 day", "switch after 2 days (used)", "no switch"]
COLS = ["#7fb0d8", S.ACCENT, S.OTHER]
DATA = {"a  Heating peak": [17, 14, 31], "b  Cooling peak": [16, 20, 85]}


def main() -> None:
    S.use()
    fig, axes = plt.subplots(1, 2, figsize=(S.DOUBLE, 40 * S.MM), sharey=True)
    fig.subplots_adjust(left=0.2, right=0.97, top=0.82, bottom=0.25, wspace=0.12)
    for ax, (title, vals) in zip(axes, DATA.items()):
        y = [2, 1, 0]
        ax.barh(y, vals, color=COLS, height=0.62)
        for yy, v in zip(y, vals):
            ax.text(v + 1.2, yy, f"{v}%", va="center", fontsize=7.5)
        ax.set_xlim(0, 95)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=8)
        ax.set_xlabel("worst case, % worse than the best method")
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color=S.RULE, lw=0.4)
        ax.set_axisbelow(True)
    axes[0].set_yticks([2, 1, 0])
    axes[0].set_yticklabels(OPTS)
    axes[0].get_yticklabels()[1].set_fontweight("bold")
    S.save(fig, "fig_switch_choice")


if __name__ == "__main__":
    main()
