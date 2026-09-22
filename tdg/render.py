"""Shaded preview renders + overhang map for a mesh (matplotlib, headless)."""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def shade(m, light=(0.4, -0.6, 0.7), base=(0.80, 0.62, 0.42)):
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    lam = np.clip(m.face_normals @ L, 0, 1)
    c = np.asarray(base)[None] * (0.28 + 0.72 * lam[:, None])
    return np.clip(c, 0, 1)


def overhang_colors(m):
    nz = m.face_normals[:, 2]
    zc = m.triangles_center[:, 2]
    c = np.tile([0.72, 0.74, 0.78], (len(nz), 1))
    c[(nz < -np.cos(np.radians(45))) & (zc > 0.3)] = [0.95, 0.55, 0.1]
    c[(nz < -np.cos(np.radians(30))) & (zc > 0.3)] = [0.85, 0.1, 0.1]
    return c


def draw(ax, m, colors, elev, azim, zoom=1.0):
    pc = Poly3DCollection(m.triangles, facecolors=colors, linewidths=0)
    ax.add_collection3d(pc)
    e = m.bounds
    ctr = e.mean(0)
    half = (e[1] - e[0]).max() / 2
    ax.set_xlim(ctr[0] - half, ctr[0] + half)
    ax.set_ylim(ctr[1] - half, ctr[1] + half)
    ax.set_zlim(ctr[2] - half, ctr[2] + half)
    ax.set_box_aspect((1, 1, 1), zoom=zoom)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def main(path, out_prefix, faces=160_000):
    m = trimesh.load(path)
    if len(m.faces) > faces:
        import fast_simplification
        v, f = fast_simplification.simplify(m.vertices, m.faces, 1 - faces / len(m.faces))
        m = trimesh.Trimesh(v, f)
    views = [(8, -60, "front"), (25, -20, "three_quarter"), (80, -45, "top")]
    fig = plt.figure(figsize=(18, 10), facecolor="white")
    for i, (el, az, name) in enumerate(views):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d")
        draw(ax, m, shade(m), el, az, zoom=1.6)
        ax.set_title(name)
    ax = fig.add_subplot(1, 4, 4, projection="3d")
    draw(ax, m, overhang_colors(m), -15, -60, zoom=1.6)
    ax.set_title("overhangs (orange >45°, red >60°)")
    plt.tight_layout()
    fig.savefig(out_prefix + "_overview.png", dpi=110)
    fig = plt.figure(figsize=(9, 14), facecolor="white")
    ax = fig.add_subplot(1, 1, 1, projection="3d")
    draw(ax, m, shade(m), 12, -52, zoom=1.55)
    plt.tight_layout()
    fig.savefig(out_prefix + "_hero.png", dpi=130)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
