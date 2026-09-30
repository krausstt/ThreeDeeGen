"""Preview of the engraved text rings: flat layout + 3D views."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MP  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import generate as G  # noqa: E402
import textring as T  # noqa: E402
from tdg import mesh  # noqa: E402
from tdg.render import draw, shade  # noqa: E402


def main(out):
    p = G.Params()
    texts = [t for t in p.texts.split("|") if t.strip()]
    n = len(texts)
    fig = plt.figure(figsize=(3.2 * n, 7))
    for i, t in enumerate(texts):
        M, info, _, _ = G.build_text_ring(p, t)
        m = mesh.manifold_to_trimesh(M)
        ax = fig.add_subplot(2, n, i + 1, projection="3d")
        draw(ax, m, shade(m, light=(-0.5, 0.8, 0.9)), 20, 115, zoom=1.5)
        ax.set_title(t, fontsize=10)
        ax = fig.add_subplot(2, n, n + i + 1)
        cs, L, _ = T.layout_text(t, info["font"], info["cap_height_mm"])
        v, c = [], []
        for poly in cs.to_polygons():
            pts = [tuple(q) for q in poly]
            v += pts + [pts[0]]
            c += [MP.MOVETO] + [MP.LINETO] * (len(pts) - 1) + [MP.CLOSEPOLY]
        ax.add_patch(PathPatch(MP(v, c), fc="#3b2f05"))
        ax.set_xlim(-1, max(L, 20) + 1)
        ax.set_ylim(-1, 8)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"{info['font']}: {info['cap_height_mm']:.1f} mm hoch, {L:.1f} mm lang, "
                     f"{info['wrap_deg']:.0f}°", fontsize=8)
    plt.tight_layout()
    fig.savefig(out, dpi=80)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out" / "text" / "text_overview.png"))
