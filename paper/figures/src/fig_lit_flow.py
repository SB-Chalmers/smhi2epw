"""Literature search flow (Appendix B): records found, merged, screened, included."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

import style as S

FS = 7.5


def box(ax, x, y, w, h, text, *, bold=False, side=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.02",
                                fc=S.TINT["neutral"] if side else "white",
                                ec="none" if side else (S.ACCENT if bold else S.INK), lw=1.0 if bold else 0.7))
    ax.text(x, y, text, ha="center", va="center", fontsize=FS, linespacing=1.25,
            fontweight="bold" if bold else "normal")


def arr(ax, p0, p1):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=8, color=S.INK, lw=0.7,
                                 shrinkA=0, shrinkB=0))


def main() -> None:
    S.use()
    fig = plt.figure(figsize=(S.DOUBLE * 0.72, 72 * S.MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    xm, xs, w, ws, h = 0.27, 0.74, 0.44, 0.42, 0.15
    ys = [0.88, 0.63, 0.38, 0.12]
    main_txt = ["Records found: 360\nScopus 213, Web of Science 147",
                "After merging duplicates: 227",
                "After screening titles\nand abstracts: 73",
                "Included: 82"]
    for i, (y, t) in enumerate(zip(ys, main_txt)):
        box(ax, xm, y, w, h, t, bold=(i == 3))
    for i in range(3):
        arr(ax, (xm, ys[i] - h / 2), (xm, ys[i + 1] + h / 2))
    side = [((ys[0] + ys[1]) / 2, "Duplicates\nremoved: 133", -1),
            ((ys[1] + ys[2]) / 2, "Left out: 154, not about\nweather files, filling\nmethods or simulated loads", -1),
            ((ys[2] + ys[3]) / 2, "Added: 9\n(2 known papers,\n7 from reference lists)", +1)]
    for y, t, d in side:
        box(ax, xs, y, ws, 0.17, t, side=True)
        if d < 0:
            arr(ax, (xm, y), (xs - ws / 2, y))
        else:
            arr(ax, (xs - ws / 2, y), (xm, y))
    S.save(fig, "fig_lit_flow")


if __name__ == "__main__":
    main()
