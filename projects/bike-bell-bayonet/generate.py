"""
Female bayonet mount + strap for a Decathlon bike bell (replaces the original
hard-plastic receiver + silicone link band).

Frame / print orientation
-------------------------
z = 0      : bell seat face, printed ON THE BED (keyhole goes straight up)
+z         : towards the handlebar; bar axis is the Y axis
X          : perpendicular to the bar (strap wraps around the bar in the XZ plane)

Mechanism (bell = male part)
----------------------------
1. Insert bell with its two lugs aligned to the keyhole slot (X axis).
2. The spring nubs on the bell face press on the seat face.
3. Rotate 90 deg: lugs travel in the swept cavity above the plate and end up
   along Y, hooked behind the plate; the cavity outline itself is the
   rotation stop (it is exactly the swept lug volume, 0..90 deg).
4. Nubs arrive on the X axis and click into the detent recesses.

Print aware: no supports. Only horizontal overhangs are the detent-recess
ceilings (3.x mm bridges) and 45 deg knob heads.
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

from tdg import check, cli, mesh, render  # noqa: E402

SEG = 96


@dataclass
class Params:
    # --- bell (male) : measured by caliper
    shaft_d: float = 8.1          # "etwas ueber 8 mm"
    lug_w: float = 3.1            # pin width "etwas ueber 3 mm"
    lug_span: float = 11.9        # tip-to-tip incl. shaft "knapp 12 mm"
    nub_size: float = 2.9         # "knapp 3 mm an allen Seiten"
    nub_gap: float = 11.1         # inner gap between nubs "etwas ueber 11 mm"
    # --- bell (male) : ASSUMED, must be measured
    clamp_gap: float = 3.0        # bell contact face -> underside of lugs
    lug_h: float = 2.0            # axial thickness of the lugs
    head_above: float = 1.0       # anything protruding above the lugs (centre bump)
    nub_h: float = 1.0            # nub protrusion above the bell contact face
    bell_d: float = 35.0          # bell base diameter (visual + seat size)
    # --- fit (FDM)
    fit: float = 0.25             # radial clearance per side (TPU 0.25-0.3, PETG 0.2)
    fit_axial: float = 0.15       # plate is this much thinner than clamp_gap
    detent_preload: float = 0.2   # nub stays compressed by this much when locked
    lock_ccw: bool = True         # twist direction seen from the bell side
    # --- mount
    bar_d: float = 22.2           # handlebar diameter at the mounting spot
    width: float = 24.0           # along the bar
    horn_wrap: float = 0.55       # horn top height above bar bottom, in bar radii
    horn_t: float = 4.6           # horn thickness beyond the saddle edge
    corner_r: float = 4.0
    # --- strap
    strap: str = "integrated"     # integrated | separate | none
    strap_w: float = 10.0
    strap_t: float = 1.8
    knob_d: float = 4.0
    knob_head_d: float = 6.4
    hole_d: float = 3.6           # < knob_d: holes stretch over the stem, no rattle
    hole_pitch: float = 6.0
    n_holes: int = 4
    strain: float = 0.05          # pre-strain of the nominal hole on the given bar_d
    nominal_hole: int = 1         # index of the nominal hole (tighter ones before it)
    material: str = "TPU"


# ------------------------------------------------------------------ helpers
def box(x0, x1, y0, y1, z0, z1):
    return m3.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(r, z0, z1, x=0.0, y=0.0, r2=None):
    return m3.Manifold.cylinder(z1 - z0, r, r if r2 is None else r2, SEG).translate([x, y, z0])


def rect2d(cx, cy, w, h, angle=0.0):
    return m3.CrossSection.square([w, h], True).rotate(angle).translate([cx, cy])


def rounded_rect2d(w, h, r):
    return m3.CrossSection.square([w - 2 * r, h - 2 * r], True).offset(r, m3.JoinType.Round, 2.0, SEG)


def derived(p: Params):
    R = p.bar_d / 2
    t_p = p.clamp_gap - p.fit_axial                          # plate thickness
    z_s = t_p + p.fit_axial + p.lug_h + p.head_above + 0.5   # bar bottom (saddle low point)
    z_top = z_s + p.horn_wrap * R
    x_e = math.sqrt(R**2 - (R - p.horn_wrap * R) ** 2)       # saddle edge at horn top
    L = 2 * (x_e + p.horn_t)
    r_nub = p.nub_gap / 2 + p.nub_size / 2
    depth = max(p.nub_h - p.detent_preload, 0.0)
    return dict(R=R, t_p=t_p, z_s=z_s, z_top=z_top, x_e=x_e, L=L, r_nub=r_nub, depth=depth,
                x_knob=x_e + p.horn_t / 2)


def keyhole2d(p: Params, angle=0.0):
    c = m3.CrossSection.circle(p.shaft_d / 2 + p.fit, SEG)
    return c + rect2d(0, 0, p.lug_span + 2 * p.fit, p.lug_w + 2 * p.fit, angle)


def swept_lugs2d(p: Params):
    """Exact 2D footprint swept by shaft + lugs over the 0..90 deg twist."""
    sgn = 1 if p.lock_ccw else -1
    parts = [keyhole2d(p, sgn * a) for a in np.linspace(0, 90, 91)]
    return m3.CrossSection.batch_boolean(parts, m3.OpType.Add).offset(0.3, m3.JoinType.Round, 2.0, SEG)


def knob(x, y, z0, p: Params):
    stem_h = p.strap_t + 0.8
    cone_h = (p.knob_head_d - p.knob_d) / 2                    # 45 deg underside
    k = cyl(p.knob_d / 2, z0 - 0.5, z0 + stem_h, x, y)
    k += cyl(p.knob_d / 2, z0 + stem_h, z0 + stem_h + cone_h, x, y, r2=p.knob_head_d / 2)
    k += cyl(p.knob_head_d / 2, z0 + stem_h + cone_h, z0 + stem_h + cone_h + 0.6, x, y,
             r2=p.knob_head_d / 2 - 0.5)
    return k


# ------------------------------------------------------------------ strap geometry
def strap_path_length(p: Params, d, from_root: bool):
    """Centre-line length from the strap start over the bar down to the +X knob.
    from_root: integrated strap starting at (x=-L/2, z=0), running up the end face;
    else: separate strap starting at the -X knob."""
    R = d["R"] + p.strap_t / 2
    C = np.array([0.0, d["z_s"] + d["R"]])
    K = np.array([d["x_knob"], d["z_top"] + p.strap_t / 2])
    if from_root:
        A = np.array([-d["L"] / 2 - p.strap_t / 2, d["z_top"]])   # outer top edge of -X end
        pre = d["z_top"]
    else:
        A = np.array([-d["x_knob"], d["z_top"] + p.strap_t / 2])
        pre = 0.0

    def tangent(P, side):
        v = P - C
        dist = np.linalg.norm(v)
        a = math.atan2(v[1], v[0]) + side * math.acos(R / dist)
        return math.sqrt(dist**2 - R**2), a

    lA, aA = tangent(A, -1)       # left side, over the top (clockwise)
    lK, aK = tangent(K, +1)
    arc = (aA - aK) % (2 * math.pi) * R
    return pre + lA + arc + lK


def strap2d(p: Params, d, separate: bool):
    """Flat strap outline in its own frame, running along +s from s=0."""
    L0 = strap_path_length(p, d, from_root=not separate)
    s0 = p.strap_w / 2 + 1.5 if separate else 0.0          # fixed hole of the separate strap
    s_nom = s0 + L0 / (1 + p.strain)
    holes = [s_nom + (i - p.nominal_hole) * p.hole_pitch for i in range(p.n_holes)]
    strains = [round(L0 / (h - s0) - 1, 3) for h in holes]
    s_end = max(holes) + p.hole_d / 2 + 8.0                 # grip tab
    out = m3.CrossSection.square([s_end, p.strap_w], False).translate([0, -p.strap_w / 2])
    out += m3.CrossSection.circle(p.strap_w / 2, SEG).translate([s_end, 0])
    if separate:
        out += m3.CrossSection.circle(p.strap_w / 2, SEG)
        holes = [s0] + holes
    for h in holes:
        out -= m3.CrossSection.circle(p.hole_d / 2, SEG).translate([h, 0])
    info = dict(path_length_mm=round(L0, 1), hole_positions_mm=[round(h, 1) for h in holes],
                strain_per_adjust_hole=strains)
    return out, info


# ------------------------------------------------------------------ parts
def build_mount(p: Params, d, with_strap: bool):
    body = rounded_rect2d(d["L"], p.width, p.corner_r).extrude(d["z_top"])
    bar = m3.Manifold.cylinder(p.width + 2, d["R"], d["R"], 2 * SEG, True) \
        .rotate([90, 0, 0]).translate([0, 0, d["z_s"] + d["R"]])
    body -= bar
    # keyhole through plate
    body -= keyhole2d(p).extrude(d["t_p"] + 0.02).translate([0, 0, -0.01])
    # swept lug cavity: above plate, open into the saddle (no bridge)
    body -= swept_lugs2d(p).extrude(d["z_s"] + d["R"]).translate([0, 0, d["t_p"]])
    # detent recesses for the nubs in the locked pose (X axis)
    for sx in (-1, 1):
        rec = rect2d(sx * d["r_nub"], 0, p.nub_size + 2 * p.fit, p.nub_size + 2 * p.fit + 0.3)
        body -= rec.extrude(d["depth"] + 0.01).translate([0, 0, -0.01])
    # strap knobs on horn tops
    body += knob(d["x_knob"], 0, d["z_top"], p)
    if not with_strap:
        body += knob(-d["x_knob"], 0, d["z_top"], p)
    strap_info = None
    if with_strap:
        s2d, strap_info = strap2d(p, d, separate=False)
        x0 = -d["L"] / 2 + 1.0                               # 1 mm fused overlap
        strap = s2d.mirror([1, 0]).translate([x0, 0]).extrude(p.strap_t)
        root = rect2d(x0 - 1.5, 0, 3.0, p.strap_w).extrude(p.strap_t + 1.0)  # root doubler
        body = body + strap + root
    return body, strap_info


def build_strap(p: Params, d):
    s2d, info = strap2d(p, d, separate=True)
    return s2d.extrude(p.strap_t), info


def build_coupon(p: Params, d):
    """Fit-test disc: only plate + cavity + detents (prints in minutes)."""
    body = m3.CrossSection.circle(max(d["r_nub"] + 4.5, 12.0), SEG).extrude(d["z_s"])
    body -= keyhole2d(p).extrude(d["t_p"] + 0.02).translate([0, 0, -0.01])
    body -= swept_lugs2d(p).extrude(d["z_s"] + 1).translate([0, 0, d["t_p"]])
    for sx in (-1, 1):
        rec = rect2d(sx * d["r_nub"], 0, p.nub_size + 2 * p.fit, p.nub_size + 2 * p.fit + 0.3)
        body -= rec.extrude(d["depth"] + 0.01).translate([0, 0, -0.01])
    return body


def bell_dummy(p: Params, d, angle_deg):
    """Male part of the bell in mount coordinates (bell face at z=0, bell below).
    angle 0 = insertion pose (lugs on X), +-90 = locked."""
    shaft = cyl(p.shaft_d / 2, -0.5, p.clamp_gap + p.lug_h + p.head_above)
    lugs = rect2d(0, 0, p.lug_span, p.lug_w).extrude(p.lug_h).translate([0, 0, p.clamp_gap])
    nubs = m3.Manifold()
    for sy in (-1, 1):   # nubs perpendicular to lugs
        nubs += box(-p.nub_size / 2, p.nub_size / 2, sy * d["r_nub"] - p.nub_size / 2,
                    sy * d["r_nub"] + p.nub_size / 2, -0.5, p.nub_h)
    disc = cyl(p.bell_d / 2, -12.0, 0.0)
    return [(x.rotate([0, 0, angle_deg])) for x in (shaft + lugs, nubs, disc)]


# ------------------------------------------------------------------ functional test
def functional_test(p: Params, d, mount):
    sgn = 1 if p.lock_ccw else -1
    res = {}
    # 1. insertion: shaft+lugs extruded along the whole insertion path must clear the mount
    sl, _, _ = bell_dummy(p, d, 0)
    path = m3.Manifold.batch_boolean([sl.translate([0, 0, -z]) for z in np.linspace(0, p.clamp_gap + 0.5, 12)],
                                     m3.OpType.Add)
    res["insert_collision_mm3"] = round((path ^ mount).volume(), 4)
    # 2. twist 0..90 at seated height
    worst = 0.0
    for a in np.linspace(0, 90, 31):
        sl, _, _ = bell_dummy(p, d, sgn * a)
        worst = max(worst, (sl ^ mount).volume())
    res["twist_collision_mm3_max"] = round(worst, 4)
    # 3. locked pose: nub preload and retention
    sl, nubs, _ = bell_dummy(p, d, sgn * 90)
    res["locked_nub_interference_mm3"] = round((nubs ^ mount).volume(), 3)
    res["locked_nub_interference_expected_mm3"] = round(2 * p.nub_size**2 * p.detent_preload, 3)
    # 4. over-twist must collide (rotation stop works)
    sl_over, _, _ = bell_dummy(p, d, sgn * 100)
    res["overtwist_100deg_collision_mm3"] = round((sl_over ^ mount).volume(), 3)
    # 5. axial retention: lug footprint (locked) overlapping plate footprint
    lug2d = rect2d(0, 0, p.lug_span, p.lug_w, sgn * 90) - m3.CrossSection.circle(p.shaft_d / 2, SEG)
    plate2d = m3.CrossSection.square([60, 60], True) - keyhole2d(p)
    for sx in (-1, 1):
        plate2d -= rect2d(sx * d["r_nub"], 0, p.nub_size + 2 * p.fit, p.nub_size + 2 * p.fit + 0.3)
    res["locked_lug_bearing_area_mm2"] = round((lug2d ^ plate2d).area(), 2)
    res["ok"] = bool(res["insert_collision_mm3"] < 1e-3 and res["twist_collision_mm3_max"] < 1e-3
                     and res["overtwist_100deg_collision_mm3"] > 1.0 and res["locked_lug_bearing_area_mm2"] > 5)
    return res


# ------------------------------------------------------------------ pipeline
def generate(p: Params, out_dir: Path, previews=True):
    d = derived(p)
    integrated = p.strap == "integrated"
    mount, strap_info = build_mount(p, d, with_strap=integrated)
    ft = functional_test(p, d, build_mount(p, d, with_strap=False)[0])
    parts = {"mount": mount, "fit_coupon": build_coupon(p, d)}
    if p.strap == "separate":
        parts["strap"], strap_info = build_strap(p, d)
    reports = {}
    for name, M in parts.items():
        tm = mesh.manifold_to_trimesh(M)
        base = out_dir / f"bell_bayonet_{name}"
        mesh.export(tm, str(base))
        rep = check.report(tm, "TPU" if name == "strap" else p.material)
        check.assert_printable(rep)
        reports[name] = rep
        if previews and name == "mount":
            render.main(str(base) + ".stl", str(base))
    # assembly preview (mount + bell dummy locked) for visual check only
    sgn = 1 if p.lock_ccw else -1
    sl, nubs, disc = bell_dummy(p, d, sgn * 90)
    asm = mesh.manifold_to_trimesh(mount + sl + nubs + disc.translate([0, 0, -0.01]))
    asm.export(str(out_dir / "bell_bayonet_assembly_preview.stl"))
    summary = dict(params=asdict(p), derived={k: round(v, 2) for k, v in d.items()},
                   functional_test=ft, strap=strap_info, parts=reports)
    check.write(summary, str(out_dir / "bell_bayonet_report.json"))
    print({"functional_test": ft, "strap": strap_info,
           "mount": {k: reports["mount"][k] for k in ("watertight", "bodies", "bbox_mm", "volume_cm3",
                                                         "mass_g_at_100pct", "overhang_area_gt45deg_mm2")}})
    assert ft["ok"], f"functional test failed: {ft}"
    return summary


def main():
    ap = cli.parser_for(Params, out=(str, str(HERE / "out")))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    generate(cli.params_from(a, Params), out)


if __name__ == "__main__":
    main()
