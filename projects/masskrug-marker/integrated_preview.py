"""Preview renders of the integrated clips (out/integrated/<name>_overview.png): badge front, oblique, overhangs."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import trimesh  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from tdg.render import draw, overhang_colors, shade  # noqa: E402


def main(names=("rings", "bier", "finger")):
    for name in names:
        m = trimesh.load(HERE / "out" / "integrated" / f"masskrug_clip_{name}.3mf", force="mesh")
        views = [(shade(m, light=(0.3, 0.9, 0.6)), 5, 90, "Badge frontal", 2.2),
                 (shade(m, light=(0.5, 0.8, 0.7)), 25, 60, "schräg", 1.5),
                 (overhang_colors(m), -20, 80, "Überhänge (orange >45°, rot >60°)", 1.6)]
        fig = plt.figure(figsize=(18, 6.5), facecolor="white")
        for i, (c, el, az, title, zoom) in enumerate(views):
            ax = fig.add_subplot(1, 3, i + 1, projection="3d")
            draw(ax, m, c, el, az, zoom=zoom)
            ax.set_title(title)
        plt.tight_layout()
        fig.savefig(HERE / "out" / "integrated" / f"{name}_overview.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("rings", "bier", "finger"))
