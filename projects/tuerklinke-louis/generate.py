"""
Türklinke Louis XV: decorative lever handle (Drückergarnitur mit Langschild) for the boiserie wall / door panels
of the user's slicer project, to be placed directly ON a panel in the slicer and printed as part of it.

Frame / print orientation
-------------------------
The panels print lying flat, relief up. So does the handle:
  z = 0  : door surface (bottom of the escutcheon, sits on the panel face)
  x      : horizontal on the door, the lever points to +x ("rechts") or -x ("links", mirrored)
  y      : vertical on the door (up)
Escutcheon centre = origin. Everything on the escutcheon is upward relief (no overhang by construction).

The lever floats ~4.4 mm above the door, which would be a 11 mm overhang. It is carried by a thin vertical
web ("Steg") under its whole length, down to the door surface: the web is 1.41 x the local lever radius wide,
i.e. it meets the round lever exactly at its 45 deg points, so the lever underside never exceeds 45 deg.
Seen from the front the web hides behind the lever; it is the price for a support-free, unbreakable lever.

Scale
-----
ANGENOMMEN: estimated from the user's screenshot (Bambu Studio grid = 10 mm): the tall door panel is about
65 x 150 mm, i.e. ~1:13 of a real 2 m door. Real Louis XV Langschild garnitures are ~290 x 74 mm with a ~145 mm
lever, 72 mm lever-to-keyhole (DIN 18251 Zimmertür) and ~66 mm projection; at 1:13.3 that is the model below.
`size` scales the whole handle uniformly (same as scaling in the slicer), the detail checks follow it.
"""
from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import manifold3d as m3  # noqa: E402

from tdg import check, cli, mesh  # noqa: E402
from tdg import sdf as S  # noqa: E402

CS = m3.CrossSection
J = m3.JoinType.Round

# real door / garniture dimensions the reference model (size = 1) is drawn from, mm
REAL = dict(door_h=2000, plate_h=290, plate_w=74, lever_l=145, key_dist=72, projection=66)


@dataclass
class Params:
    # --- ANGENOMMEN (messen!): from the screenshot grid, +-7 %
    door_panel_h: float = 150.0   # height of the door panel in the slicer
    # --- design
    size: float = 1.0             # uniform scale of the whole handle (1.0 = door_panel_h / 2000 m door)
    hand: str = "both"            # rechts (lever -> +x) | links | both
    # --- print (0.4 mm nozzle)
    nozzle: float = 0.4
    material: str = "PLA"
    voxel: float = 0.04           # SDF resolution of the lever


# ------------------------------------------------------------------ 2D helpers
def poly(pts):
    pts = [tuple(map(float, q)) for q in pts]
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return CS([pts if a > 0 else pts[::-1]])


def circ(r, x=0.0, y=0.0, seg=48):
    return CS.circle(r, seg).translate([x, y])


def ell(rx, ry, x=0.0, y=0.0, rot=0.0, seg=48):
    return CS.circle(1.0, seg).scale([rx, ry]).rotate(rot).translate([x, y])


def stroke(pts, w):
    parts = [(circ(w / 2, *a, seg=20) + circ(w / 2, *b, seg=20)).hull() for a, b in zip(pts[:-1], pts[1:])]
    return CS.batch_boolean(parts, m3.OpType.Add)


def raised(cs, z0, h, round_r=0.2, dz=0.04):
    """Upward relief of height h on z0 with a quarter-round top edge (shrinking layers -> no overhang)."""
    parts, n = [], max(int(round(h / dz)), 1)
    rr = min(round_r, h)
    for k in range(n):
        t = (k + 0.5) * dz
        u = max(t - (h - rr), 0.0) / rr if rr > 0 else 0.0
        layer = cs.offset(-rr * (1 - math.sqrt(max(1 - u * u, 0.0))), J) if u > 0 else cs
        if layer.is_empty():
            break
        parts.append(layer.extrude(dz * 1.5).translate([0, 0, z0 + k * dz]))
    M = m3.Manifold.batch_boolean(parts, m3.OpType.Add)
    return M ^ m3.Manifold.cube([200, 200, h]).translate([-100, -100, z0])


# ------------------------------------------------------------------ escutcheon (Langschild)
# half width over height: bottom finial, lower lobe, waist, boss widening, neck, top scroll ears, crest point
HALF = [(-11.0, 0.0), (-10.85, 0.45), (-10.3, 0.95), (-9.6, 1.75), (-8.8, 2.45), (-8.0, 2.65), (-7.2, 2.35),
        (-6.4, 2.15), (0.0, 2.2), (2.6, 2.35), (4.5, 2.8), (6.3, 2.55), (7.3, 2.25), (8.1, 2.55), (8.9, 2.8),
        (9.7, 2.5), (10.3, 1.7), (10.75, 0.9), (11.0, 0.0)]
BOSS_Y = 4.5          # lever axis
KEY_Y = BOSS_Y - 5.4  # keyhole centre, 72 mm real
PLATE_T = 0.8
PEARL_R = 0.33      # pearl beading like the panels, Ø 0.66 mm (>= 1.5 nozzle widths)


def outline():
    right = [(hw, y) for y, hw in HALF]
    left = [(-hw, y) for y, hw in reversed(HALF[1:-1])]
    return poly(right + left).offset(-0.25, J).offset(0.25, J)


def resample(poly_pts, step):
    p = np.asarray(poly_pts, float)
    p = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(int(s[-1] / step), 3)
    t = np.linspace(0, s[-1], n, endpoint=False)
    return np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])]


def ornaments():
    """2D ornament layers on the plate: (cross-section, height) pairs."""
    # crest shell (rocaille fan) in the top lobe, ribs on a flat fan
    c = (0.0, 7.45)
    fan = poly([c] + [(c[0] + 1.85 * math.cos(math.radians(a)), c[1] + 1.85 * math.sin(math.radians(a)))
                      for a in np.linspace(32, 148, 15)])
    def ray(a, r):
        return c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a))

    ribs = CS.batch_boolean([stroke([ray(a, 0.35), ray(a, 1.75)], 0.5) for a in (40, 65, 90, 115, 140)],
                            m3.OpType.Add)
    # C-scroll ears beside the crest
    ears = []
    for sx in (-1, 1):
        th = np.radians(np.linspace(-40, 250, 16))
        ears.append(stroke([(sx * (1.55 + 0.5 * math.cos(t)), 9.45 + 0.5 * math.sin(t)) for t in th], 0.45))
    # Louis XVI husk garland under the keyhole (bell flowers), decreasing
    husks = [ell(0.48 * s, 0.72 * s, 0.0, y) for y, s in ((-3.35, 1.0), (-4.75, 0.9), (-6.0, 0.8))]
    stem = stroke([(0, -2.5), (0, -6.6)], 0.4)
    # acanthus drop at the bottom finial: centre leaf + two side leaflets
    drop = CS.batch_boolean([ell(0.62, 1.15, 0, -8.85), ell(0.42, 0.85, -0.85, -8.3, -35),
                             ell(0.42, 0.85, 0.85, -8.3, 35)], m3.OpType.Add)
    # keyhole surround (small raised oval)
    surround = ell(1.15, 1.6, 0, KEY_Y)
    return [(fan, 0.18), (ribs, 0.38), (CS.batch_boolean(ears, m3.OpType.Add), 0.32),
            (CS.batch_boolean(husks + [stem], m3.OpType.Add), 0.32), (drop, 0.32), (surround, 0.28)]


def escutcheon():
    o = outline()
    M = raised(o, 0.0, PLATE_T, round_r=0.3)
    top = PLATE_T - 0.02
    # pearl border, like the pearl beading of the panels
    ring = o.offset(-0.55, J).to_polygons()[0]
    pearls = [m3.Manifold.sphere(PEARL_R, 20).translate([x, y, top - 0.08]) for x, y in resample(ring, 0.86)
              if math.hypot(x, y - BOSS_Y) > 2.25]
    M += m3.Manifold.batch_boolean(pearls, m3.OpType.Add)
    for cs, h in ornaments():
        M += raised(cs, top, h, round_r=min(0.15, h))
    # rosette boss around the lever neck: disc + bead ring + dome
    M += raised(circ(1.75, 0, BOSS_Y, 64), top, 0.22, round_r=0.12)
    M += raised(circ(1.62, 0, BOSS_Y, 64) - circ(1.22, 0, BOSS_Y, 64), top + 0.2, 0.22, round_r=0.11)
    M += m3.Manifold.sphere(1.2, 48).scale([1, 1, 0.45]).translate([0, BOSS_Y, top + 0.2])
    # keyhole (engraved, every part >= 0.45 mm wide)
    kh = circ(0.5, 0, KEY_Y + 0.4, 32) + poly([(-0.26, KEY_Y + 0.3), (0.26, KEY_Y + 0.3), (0.36, KEY_Y - 1.0),
                                               (-0.36, KEY_Y - 1.0)])
    M -= kh.extrude(2).translate([0, 0, 0.25])
    return M, len(pearls)


# ------------------------------------------------------------------ lever (bec de cane with a scroll end)
LEVER = [  # x, y (relative to the boss), z, radius
    (0.00, 0.00, 0.60, 0.95), (0.00, 0.00, 2.00, 0.85), (0.00, 0.00, 3.90, 0.85), (0.25, 0.00, 4.60, 0.80),
    (0.90, 0.10, 4.95, 0.75), (2.20, 0.20, 5.05, 0.70), (4.00, 0.25, 5.05, 0.68), (6.00, 0.10, 4.95, 0.70),
    (7.80, -0.25, 4.80, 0.80), (9.30, -0.70, 4.65, 0.88), (10.30, -1.35, 4.50, 0.82), (10.80, -2.20, 4.40, 0.72),
    (10.65, -3.05, 4.30, 0.62), (10.00, -3.50, 4.25, 0.55), (9.35, -3.35, 4.20, 0.52)]
KNOB = (9.10, -2.95, 4.20, 0.62)


class Ball:
    def __init__(self, c, r):
        self.c, self.r = np.asarray(c, float), r

    def bbox(self):
        return self.c - self.r, self.c + self.r

    def sdf(self, X, Y, Z):
        return np.sqrt((X - self.c[0]) ** 2 + (Y - self.c[1]) ** 2 + (Z - self.c[2]) ** 2) - self.r


def lever(voxel):
    pts = [(x, y + BOSS_Y, z) for x, y, z, _ in LEVER]
    rod = S.Rod(pts, [r for *_, r in LEVER])
    knob = Ball((KNOB[0], KNOB[1] + BOSS_Y, KNOB[2]), KNOB[3])
    lo = np.array([-1.5, BOSS_Y - 5.0, -1.0 - 0.3 * voxel])     # bed cut at z = 0 closes the neck foot
    hi = np.array([12.5, BOSS_Y + 1.6, 6.2])
    D, lo = S.evaluate([rod], [knob], lo, hi, voxel, 0.25)
    tm = mesh.simplify(S.to_mesh(D, lo, voxel, sit_on_bed=False), 0.003)
    M = mesh.trimesh_to_manifold(tm)
    M = max(M.decompose(), key=lambda q: q.volume())
    # 45 deg collar at the neck foot (bottom cone = 45 deg, top cone back to the neck)
    M += m3.Manifold.cylinder(0.35, 0.95, 1.3, 48).translate([0, BOSS_Y, 1.05])
    M += m3.Manifold.cylinder(0.25, 1.3, 0.95, 48).translate([0, BOSS_Y, 1.4])
    return M


def web(min_w=1.0, step=0.25, arch=(1.4, 8.4), arch_top=0.35):
    """Vertical web under the lever arm, scroll and knob, from the door (z = 0) up to the lever's 45 deg points.
    Under the straight arm it is opened by a pointed arch (45 deg flanks = support free), so only a bracket at
    the neck and the curved wall under the scroll reach the door; above the arch apex `arch_top` mm remain."""
    arm = np.array([(x, y + BOSS_Y, z, r) for x, y, z, r in LEVER[3:]] +
                   [(KNOB[0], KNOB[1] + BOSS_Y, KNOB[2], KNOB[3])])
    seg = np.linalg.norm(np.diff(arm[:, :2], axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.unique(np.concatenate([np.linspace(0, s[-1], int(s[-1] / step) + 2), arch, arch]))
    P = np.c_[[np.interp(t, s, arm[:, i]) for i in range(4)]].T
    top = P[:, 2] - P[:, 3] / math.sqrt(2) + 0.08
    sa, sb = arch
    mid = (sa + sb) / 2
    apex = np.interp(mid, t, top) - arch_top
    inside = (t > sa + 1e-6) & (t < sb - 1e-6)
    bot = np.where(inside, np.maximum(apex - np.abs(t - mid), 0.0), 0.0)
    w = np.minimum(np.maximum(math.sqrt(2) * P[:, 3], min_w), 1.9 * P[:, 3])
    parts = []
    for i in range(len(t) - 1):
        if t[i] == t[i + 1]:
            continue
        b0 = bot[i] if inside[i] or not inside[i + 1] else bot[i + 1]      # vertical arch jambs at sa / sb
        b1 = bot[i + 1] if inside[i + 1] or not inside[i] else bot[i]
        cyl = [m3.Manifold.cylinder(top[j] - b, w[j] / 2, w[j] / 2, 16).translate([P[j, 0], P[j, 1], b])
               for j, b in ((i, b0), (i + 1, b1))]
        parts.append(m3.Manifold.batch_hull(cyl))
    info = dict(web_min=float(w.min()), arch_span=round(sb - sa, 2), arch_apex_z=round(float(apex), 2),
                arch_flank_deg=45.0)
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add), info


def build(p: Params):
    k = p.size * (p.door_panel_h / REAL["door_h"]) / 0.075        # reference model is drawn at 1:13.33
    E, n_pearls = escutcheon()
    W, winfo = web()
    M = E + lever(p.voxel / max(k, 1e-6)) + W
    M = M.scale([k, k, k])
    b = M.bounding_box()
    info = dict(scale_factor=round(k, 3), model_scale=f"1:{REAL['door_h'] / (p.door_panel_h * p.size):.1f}",
                plate_mm=[round(5.6 * k, 2), round(22.0 * k, 2)], lever_len_mm=round(b[3], 2),
                projection_mm=round(b[5], 2), lever_to_keyhole_mm=round((BOSS_Y - KEY_Y) * k, 2),
                pearls=n_pearls, pearl_d_mm=round(2 * PEARL_R * k, 2), web_min_mm=round(winfo['web_min'] * k, 2),
                web_arch_span_mm=round(winfo['arch_span'] * k, 2), web_arch_flank_deg=winfo['arch_flank_deg'],
                lever_min_d_mm=round(2 * min(r for *_, r in LEVER) * k, 2),
                keyhole_slot_min_mm=round(0.52 * k, 2), plate_t_mm=round(PLATE_T * k, 2))
    return M, info


def details_ok(info, nozzle):
    """Smallest printable features with this nozzle (0.4: lines >= 0.45 mm, pearls >= 0.6 mm)."""
    return dict(web=info["web_min_mm"] >= 2.2 * nozzle, lever=info["lever_min_d_mm"] >= 2.4 * nozzle,
                pearls=info["pearl_d_mm"] >= 1.5 * nozzle, keyhole=info["keyhole_slot_min_mm"] >= 1.1 * nozzle,
                plate=info["plate_t_mm"] >= 1.5 * nozzle)


def test_block(R, L, k):
    """Both handles on a small chamfered block: quick test print for size and detail."""
    w, h, t = 40 * k, 30 * k, 1.2
    blk = m3.Manifold.batch_hull([m3.Manifold.cube([w, h, t - 0.4]).translate([-w / 2, -h / 2, 0]),
                                  m3.Manifold.cube([w - 0.8, h - 0.8, t]).translate([-w / 2 + 0.4, -h / 2 + 0.4, 0])])
    return blk + R.translate([-14 * k, 0, t - 0.1]) + L.translate([14 * k, 0, t - 0.1])


def generate(p: Params, out_dir: Path, previews=True):
    R, info = build(p)
    ok = details_ok(info, p.nozzle)
    assert all(ok.values()), f"details too small for a {p.nozzle} mm nozzle at size {p.size}: {ok} {info}"
    L = R.mirror([1, 0, 0])
    parts = {"rechts": R, "links": L} if p.hand == "both" else {p.hand: R if p.hand == "rechts" else L}
    reps = {}
    for name, M in parts.items():
        tm = mesh.manifold_to_trimesh(M)
        base = out_dir / f"tuerklinke_louis_{name}"
        mesh.export(tm, str(base))
        rep = check.report(tm, p.material)
        check.assert_printable(rep)
        reps[name] = rep
    k = info["scale_factor"]
    T = mesh.manifold_to_trimesh(test_block(R, L, k))
    mesh.export(T, str(out_dir / "tuerklinke_louis_probe"), formats=("3mf",))
    rep_t = check.report(T, p.material)
    check.assert_printable(rep_t)
    summary = dict(params=asdict(p), handle=info, details_ok=ok, parts=reps, probe=rep_t)
    check.write(summary, str(out_dir / "tuerklinke_louis_report.json"))
    if previews and "rechts" in parts:
        sys.path.insert(0, str(HERE))
        import preview
        preview.main(out_dir / "tuerklinke_louis_rechts.stl", out_dir / "tuerklinke_louis_overview.png")
    return summary


def main():
    a = cli.parser_for(Params, out=(str, str(HERE / "out"))).parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    s = generate(cli.params_from(a, Params), out)
    print(s["handle"], {k: (v["bbox_mm"], v["overhang_area_gt45deg_mm2"]) for k, v in s["parts"].items()})


if __name__ == "__main__":
    main()
