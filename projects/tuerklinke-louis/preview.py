"""Preview of the handle: front view (as seen on the door), oblique, side, overhang map."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import trimesh  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from tdg.render import draw, overhang_colors, shade  # noqa: E402


def main(src=HERE / "out" / "tuerklinke_louis_rechts.stl", out=HERE / "out" / "tuerklinke_louis_overview.png"):
    m = trimesh.load(src, force="mesh")
    gold = (0.80, 0.66, 0.38)
    views = [(shade(m, light=(-0.4, 0.5, 0.9), base=gold), 90, -90, "Vorderansicht (auf der Tür)", 1.45),
             (shade(m, light=(-0.3, 0.4, 0.9), base=gold), 35, -60, "schräg", 1.6),
             (shade(m, light=(0.2, -0.8, 0.6), base=gold), 2, -90, "von unten an der Tür entlang", 1.6),
             (overhang_colors(m), -25, -60, "Überhänge (orange >45°, rot >60°)", 1.6)]
    fig = plt.figure(figsize=(20, 7), facecolor="white")
    for i, (c, el, az, title, zoom) in enumerate(views):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d")
        draw(ax, m, c, el, az, zoom=zoom)
        ax.set_title(title)
    plt.tight_layout()
    fig.savefig(out, dpi=110)


if __name__ == "__main__":
    main()
