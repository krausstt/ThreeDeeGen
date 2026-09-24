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
from dataclasses import asdict, dataclass, replace
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
    nub_gap: float = 11.0         # inner gap between nubs (confirmed: inner gap)
    nub_h: float = 1.0            # nub protrusion above the bell contact face "ca. 1 mm"
    lug_h: float = 3.0            # axial thickness of the lugs "ca. 3 mm" (photo 07: ~2.5)
    # --- bell (male) : resolved with the fit-coupon trio
    clamp_gap: float = 3.4        # VERIFIED by coupon trio: 3.0 "sitzt gut", 3.4 "bombenfest" -> 3.4
    head_above: float = 1.2       # centre bump above the lugs (total "etwas mehr als 6 mm")
    bell_d: float = 35.0          # bell base diameter (visual only), estimated from photo 01
    # --- fit (FDM)
    fit: float = 0.25             # radial clearance per side (TPU 0.25-0.3, PETG 0.2)
    fit_axial: float = 0.2        # plate thinner than clamp_gap; nub springs take up the play
    detent_preload: float = 0.2   # nub stays compressed by this much when locked
    lock_ccw: bool = True         # twist direction seen from the bell side
    # --- mount
    bar_d_min: float = 31.0       # bar incl. cables, measured range 31..39 mm
    bar_d_max: float = 39.0
    v_angle: float = 30.0         # V-saddle flank angle to horizontal (120 deg included)
    flank_margin: float = 3.0     # flank extends this far beyond the largest bar contact
    width: float = 24.0           # along the bar
    ridge_w: float = 1.6          # wall at the flank top before the shoulder drops
    shoulder_h: float = 3.0       # knob shoulder height above the V vertex (keeps knobs under big bars)
    corner_r: float = 4.0
    # --- strap
    strap: str = "integrated"     # integrated | separate | none
    strap_w: float = 12.0
    strap_t: float = 1.8
    knob_d: float = 4.0
    knob_head_d: float = 6.4
    hole_d: float = 3.6           # < knob_d: holes stretch over the stem, no rattle
    strain_lo: float = 0.03       # every bar in range finds a hole with strain in [lo, hi]
    strain_hi: float = 0.12
    coupon_gaps: str = "3.0,3.4,3.8"   # clamp_gap values of the fit-coupon trio
    bed: float = 180.0            # Bambu Lab A1 mini: 180 x 180 x 180 mm
    material: str = "PETG"


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
    th = math.radians(p.v_angle)
    Rmin, Rmax = p.bar_d_min / 2, p.bar_d_max / 2
    t_p = p.clamp_gap - p.fit_axial                          # plate thickness
    z_s = t_p + p.fit_axial + p.lug_h + p.head_above + 0.5   # lowest allowed bar bottom
    z_v = z_s - Rmin * (1 / math.cos(th) - 1)                # (virtual) V vertex
    x_top = Rmax * math.sin(th) + p.flank_margin
    z_top = z_v + x_top * math.tan(th)
    x_knob = x_top + p.ridge_w + p.knob_head_d / 2 + 0.3
    L = 2 * (x_knob + p.knob_head_d / 2 + 1.0)
    z_sh = z_v + p.shoulder_h
    r_nub = p.nub_gap / 2 + p.nub_size / 2
    depth = max(p.nub_h - p.detent_preload, 0.0)
    return dict(Rmin=Rmin, Rmax=Rmax, t_p=t_p, z_s=z_s, z_v=z_v, x_top=x_top, z_top=z_top, L=L,
                z_sh=z_sh, r_nub=r_nub, depth=depth, x_knob=x_knob)


def bar_center_z(p: Params, d, R):
    return d["z_v"] + R / math.cos(math.radians(p.v_angle))


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
def strap_path_length(p: Params, d, from_root: bool, R_bar: float):
    """Centre-line length from the strap start over the bar down to the +X knob.
    from_root: integrated strap starting at (x=-L/2, z=0), running up the end face;
    else: separate strap starting at the -X knob."""
    R = R_bar + p.strap_t / 2
    C = np.array([0.0, bar_center_z(p, d, R_bar)])
    K = np.array([d["x_knob"], d["z_sh"] + p.strap_t / 2])
    if from_root:
        A = np.array([-d["L"] / 2 - p.strap_t / 2, d["z_sh"]])    # outer top edge of -X end
        pre = d["z_sh"]
    else:
        A = np.array([-d["x_knob"], d["z_sh"] + p.strap_t / 2])
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
    """Flat strap outline in its own frame, running along +s from s=0.
    Holes are spaced so every bar diameter in [bar_d_min, bar_d_max] finds a hole
    with pre-strain in [strain_lo, strain_hi]."""
    Lmin = strap_path_length(p, d, not separate, d["Rmin"])
    Lmax = strap_path_length(p, d, not separate, d["Rmax"])
    s0 = p.strap_w / 2 + 1.5 if separate else 0.0          # fixed hole of the separate strap
    lo, hi = p.strain_lo, p.strain_hi
    pitch = Lmin * (hi - lo) / ((1 + hi) * (1 + lo))       # guarantees the strain window
    first = Lmin / (1 + hi)
    last = Lmax / (1 + lo)
    n = int(math.ceil((last - first) / pitch)) + 1
    holes = [s0 + first + i * pitch for i in range(n)]
    s_end = max(holes) + p.hole_d / 2 + 8.0                 # grip tab
    out = m3.CrossSection.square([s_end, p.strap_w], False).translate([0, -p.strap_w / 2])
    out += m3.CrossSection.circle(p.strap_w / 2, SEG).translate([s_end, 0])
    if separate:
        out += m3.CrossSection.circle(p.strap_w / 2, SEG)
    for h in ([s0] if separate else []) + holes:
        out -= m3.CrossSection.circle(p.hole_d / 2, SEG).translate([h, 0])
    web = pitch - p.hole_d
    info = dict(path_length_mm=[round(Lmin, 1), round(Lmax, 1)], hole_pitch_mm=round(pitch, 2),
                web_between_holes_mm=round(web, 2), n_holes=n,
                hole_positions_mm=[round(h, 1) for h in holes], strap_length_mm=round(s_end + p.strap_w / 2, 1))
    assert web >= 1.2, f"strap web {web:.2f} mm too thin, widen strain window"
    return out, info


# ------------------------------------------------------------------ parts
def build_mount(p: Params, d, with_strap: bool):
    body = rounded_rect2d(d["L"], p.width, p.corner_r).extrude(d["z_top"])
    body -= v_prism(p, d)
    for sx in (-1, 1):   # shoulders outside the flank ridges carry the knobs low
        x0 = d["x_top"] + p.ridge_w
        body -= box(x0 if sx > 0 else -d["L"], d["L"] if sx > 0 else -x0, -p.width, p.width,
                    d["z_sh"], d["z_top"] + 1)
    # keyhole through plate
    body -= keyhole2d(p).extrude(d["t_p"] + 0.02).translate([0, 0, -0.01])
    # swept lug cavity: above plate, open into the saddle (no bridge)
    body -= swept_lugs2d(p).extrude(d["z_top"] + 5).translate([0, 0, d["t_p"]])
    # detent recesses for the nubs in the locked pose (X axis)
    for sx in (-1, 1):
        rec = rect2d(sx * d["r_nub"], 0, p.nub_size + 2 * p.fit, p.nub_size + 2 * p.fit + 0.3)
        body -= rec.extrude(d["depth"] + 0.01).translate([0, 0, -0.01])
    # strap knobs on horn tops
    body += knob(d["x_knob"], 0, d["z_sh"], p)
    if not with_strap:
        body += knob(-d["x_knob"], 0, d["z_sh"], p)
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


def v_prism(p: Params, d):
    """Material above the V flanks (removed from the mount)."""
    X = d["L"]
    t = math.tan(math.radians(p.v_angle))
    poly = [(-X, d["z_v"] + X * t), (0, d["z_v"]), (X, d["z_v"] + X * t), (X, d["z_top"] + 50), (-X, d["z_top"] + 50)]
    return m3.CrossSection([poly]).extrude(p.width + 2).rotate([90, 0, 0]).translate([0, p.width / 2 + 1, 0])


def bar(p: Params, d, R):
    return m3.Manifold.cylinder(p.width + 40, R, R, 2 * SEG, True).rotate([90, 0, 0]) \
        .translate([0, 0, bar_center_z(p, d, R)])


def build_coupon(p: Params, d, notches=0):
    """Fit-test disc: only plate + cavity + detents (prints in minutes). Notches = id."""
    rc = max(d["r_nub"] + 4.5, 12.0)
    body = m3.CrossSection.circle(rc, SEG).extrude(d["z_s"])
    for k in range(notches):
        a = math.radians(90 + (k - (notches - 1) / 2) * 14)
        body -= rect2d(rc * math.cos(a), rc * math.sin(a), 1.6, 1.6, math.degrees(a) + 45).extrude(d["z_s"] + 1) \
            .translate([0, 0, -0.5])
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
    # 6. bar range: bars touch only the flanks and never the bell head
    for tag, R in (("min", d["Rmin"]), ("max", d["Rmax"])):
        B = bar(p, d, R)
        res[f"bar_{tag}_vs_mount_mm3"] = round((B ^ mount).volume(), 3)
        res[f"bar_{tag}_vs_bell_head_mm3"] = round((B ^ sl).volume(), 3)
        res[f"bar_{tag}_head_clearance_mm"] = round(bar_center_z(p, d, R) - R
                                                   - (p.clamp_gap + p.lug_h + p.head_above), 2)
    res["ok"] = bool(res["insert_collision_mm3"] < 1e-3 and res["twist_collision_mm3_max"] < 1e-3
                     and res["overtwist_100deg_collision_mm3"] > 1.0 and res["locked_lug_bearing_area_mm2"] > 5
                     and all(res[f"bar_{t}_vs_bell_head_mm3"] < 1e-3 for t in ("min", "max"))
                     and all(res[f"bar_{t}_vs_mount_mm3"] < 1.0 for t in ("min", "max")))
    return res


# ------------------------------------------------------------------ pipeline
def generate(p: Params, out_dir: Path, previews=True):
    d = derived(p)
    integrated = p.strap == "integrated"
    mount, strap_info = build_mount(p, d, with_strap=integrated)
    ft = functional_test(p, d, build_mount(p, d, with_strap=False)[0])
    trio = m3.Manifold()
    for i, g in enumerate(float(x) for x in p.coupon_gaps.split(",")):
        pg = replace(p, clamp_gap=g)
        trio += build_coupon(pg, derived(pg), notches=i + 1).translate([i * 28.0, 0, 0])
    parts = {"mount": mount, "fit_coupons": trio}
    if p.strap == "separate":
        parts["strap"], strap_info = build_strap(p, d)
    reports = {}
    for name, M in parts.items():
        tm = mesh.manifold_to_trimesh(M)
        base = out_dir / f"bell_bayonet_{name}"
        mesh.export(tm, str(base))
        rep = check.report(tm, "TPU" if name == "strap" else p.material)
        check.assert_printable(rep, bodies=len(p.coupon_gaps.split(",")) if name == "fit_coupons" else 1)
        assert max(rep["bbox_mm"]) < p.bed - 5, f"{name} does not fit the {p.bed} mm bed"
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
