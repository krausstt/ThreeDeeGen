"""Preview sheet for the charm system and the 3D plug clip."""
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
    plug_clip = T(G.build_clip(p, "plug_3d")[0])
    rail = G.build_clip(pc, "rail")[0]
    cp = C.charm_plug(Lg, r)
    ch, _ = C.charm_heart(Lg, r)
    items = [(plug_clip, 15, 60, 1.2, "Clip mit 3D-Plug (Stützen)", False),
             (plug_clip, -10, 40, 1.2, "Überhänge Druckpose", True),
             (T(rail), 25, 60, 1.3, "Clip mit Schiene", False),
             (T(cp), 20, -60, 1.4, "Plug-Charm, stehend gedruckt", False),
             (T(cp), -15, -60, 1.4, "Plug-Charm Überhänge", True),
             (T(rail + C.mount_on_clip(cp, d["y_face"], r.stop_len)), 15, 60, 1.2, "Plug-Charm aufgeschoben", False),
             (T(rail + C.mount_on_clip(ch, d["y_face"], r.stop_len)), 15, 60, 1.2, "Herz-Charm aufgeschoben", False),
             (T(ch), 60, -70, 1.3, "Herz-Charm", False)]
    fig = plt.figure(figsize=(22, 11))
    for i, (m, el, az, z, t, oh) in enumerate(items):
        ax = fig.add_subplot(2, 4, i + 1, projection="3d")
        draw(ax, m, overhang_colors(m) if oh else shade(m), el, az, zoom=z)
        ax.set_title(t)
    plt.tight_layout()
    fig.savefig(out, dpi=85)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out" / "charms" / "charms_overview.png"))
