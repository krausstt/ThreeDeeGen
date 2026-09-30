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


def main(out):
    p = G.Params()
    pc = replace(p, clip_w=p.charm_clip_w)
    d = G.derived(pc)
    r = C.Rail(clear=p.charm_clear)
    Lg = C.groove_len(pc.clip_w, r)
    T = mesh.manifold_to_trimesh
    rail = G.build_clip(pc, "rail")[0]
    charms = {"plug": C.charm_plug(Lg, r), **{n: f(Lg, r) for n, f in C.FIGURES.items()}}
    n = len(charms)
    fig = plt.figure(figsize=(3.0 * n, 9.5))
    for i, (name, M) in enumerate(charms.items()):
        m = T(M)
        ax = fig.add_subplot(3, n, i + 1, projection="3d")
        draw(ax, m, shade(m), 15, 70, zoom=1.35)
        ax.set_title(f"{name} (Druckpose)", fontsize=9)
        ax = fig.add_subplot(3, n, n + i + 1, projection="3d")
        draw(ax, m, overhang_colors(m), -20, 60, zoom=1.35)
        ax.set_title("Überhänge", fontsize=9)
        # clip on the top bow of the handle: badge normal (+y) points up
        a = T((rail + C.mount_on_clip(M, d["y_face"], r.stop_len)).rotate([90, 0, 0]))
        ax = fig.add_subplot(3, n, 2 * n + i + 1, projection="3d")
        draw(ax, a, shade(a), 10, -30, zoom=1.2)
        ax.set_title("am Clip, oben am Henkel", fontsize=9)
    plt.tight_layout()
    fig.savefig(out, dpi=75)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out" / "charms" / "charms_overview.png"))
