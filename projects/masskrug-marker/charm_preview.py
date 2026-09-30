"""Preview sheet: every figure charm in print pose, overhang map and mounted (clip on the top bow, badge up)."""
import sys
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import charms as C  # noqa: E402
import generate as G  # noqa: E402
from tdg import mesh  # noqa: E402
from tdg.render import draw, overhang_colors, shade  # noqa: E402


def main(out, cols=3):
    p = G.Params()
    pc = replace(p, clip_w=p.charm_clip_w)
    d = G.derived(pc)
    r = C.Rail(clear=p.charm_clear)
    Lg = C.groove_len(pc.clip_w, r)
    T = mesh.manifold_to_trimesh
    rail = G.build_clip(pc, "rail")[0]
    charms = {"plug": C.charm_plug(Lg, r), **{n: f(Lg, r) for n, f in C.FIGURES.items()}}
    rows = -(-len(charms) // cols)
    fig = plt.figure(figsize=(3 * 2.6 * cols, 2.8 * rows))
    for i, (name, M) in enumerate(charms.items()):
        m = T(M)
        a = T((rail + C.mount_on_clip(M, d["y_face"], r.stop_len)).rotate([90, 0, 0]))
        views = [(m, shade(m, light=(0.3, 0.9, 0.6)), 12, 80, f"{name}"),
                 (m, overhang_colors(m), -15, 70, "Überhänge"),
                 (a, shade(a), 10, -30, "oben am Henkel")]
        for j, (mm, col, el, az, title) in enumerate(views):
            ax = fig.add_subplot(rows, 3 * cols, i * 3 + j + 1, projection="3d")
            draw(ax, mm, col, el, az, zoom=1.35)
            ax.set_title(title, fontsize=10 if j == 0 else 8)
    plt.tight_layout()
    fig.savefig(out, dpi=60)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out" / "charms" / "charms_overview.png"))
