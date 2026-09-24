"""Render a contact sheet of all badge icons (recess = dark)."""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch, FancyBboxPatch  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

import icons as I  # noqa: E402


def draw(ax, cs, title):
    ax.add_patch(FancyBboxPatch((-6, -4.2), 12, 8.4, boxstyle="round,pad=0,rounding_size=0.8",
                                fc="#e8c547", ec="#7a6414", lw=1))
    verts, codes = [], []
    for poly in cs.to_polygons():
        pts = [tuple(p) for p in poly]
        verts += pts + [pts[0]]
        codes += [MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 1) + [MPath.CLOSEPOLY]
    if verts:
        ax.add_patch(PathPatch(MPath(verts, codes), fc="#3b2f05", ec="none"))
    ax.set_xlim(-6.5, 6.5)
    ax.set_ylim(-4.7, 4.7)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9)


def main(out):
    names = list(I.ICONS)
    cols = 8
    rows = -(-len(names) // cols)
    fig, axs = plt.subplots(rows, cols, figsize=(cols * 2.2, rows * 1.9))
    for ax in axs.flat:
        ax.axis("off")
    for ax, n in zip(axs.flat, names):
        draw(ax, I.get(n), f"{n} ({I.ICONS[n][0]})")
    plt.tight_layout()
    fig.savefig(out, dpi=110)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/icons_sheet.png")
