"""Preview of the handle: front view (as seen on the door), oblique, side, overhang map."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
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


def knobs(out_dir=HERE / "out"):
    fig = plt.figure(figsize=(14, 7), facecolor="white")
    gold = (0.80, 0.66, 0.38)
    for i, v in enumerate(("olive", "melon")):
        m = trimesh.load(out_dir / f"tuerknauf_{v}.stl", force="mesh")
        for j, (c, el, az, title) in enumerate([(shade(m, light=(-0.3, 0.4, 0.9), base=gold), 20, -60, v),
                                                 (overhang_colors(m), -25, -60, "Überhänge")]):
            ax = fig.add_subplot(1, 4, 2 * i + j + 1, projection="3d")
            draw(ax, m, c, el, az, zoom=1.5)
            ax.set_title(title)
    plt.tight_layout()
    fig.savefig(out_dir / "tuerknauf_overview.png", dpi=100)
    plt.close(fig)


def mounted(src, at, out, r=16.0):
    """Panel + handle, cropped to a window around the handle."""
    m = trimesh.load(src, force="mesh")
    t = m.triangles
    lo, hi = t.min(1), t.max(1)
    keep = np.all(hi[:, :2] >= np.asarray(at) - r, 1) & np.all(lo[:, :2] <= np.asarray(at) + r, 1)
    v, f = trimesh.remesh.subdivide_to_size(*_submesh(m, keep), max_edge=0.6)   # large slab faces -> croppable
    c = v[f].mean(1)
    keep = (abs(c[:, 0] - at[0]) < r) & (abs(c[:, 1] - at[1]) < r)
    m = trimesh.Trimesh(v, f[keep], process=False)
    fig = plt.figure(figsize=(18, 6.5), facecolor="white")
    for i, (el, az, title) in enumerate([(35, -60, "Montage schräg"), (4, -88, "seitlich, entlang der Tür"),
                                         (90, -90, "Vorderansicht")]):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        draw(ax, m, shade(m, light=(-0.3, 0.4, 0.9)), el, az, zoom=1.6)
        ax.set_title(title)
    plt.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def _submesh(m, keep):
    f = m.faces[keep]
    used, inv = np.unique(f, return_inverse=True)
    return m.vertices[used], inv.reshape(-1, 3)
