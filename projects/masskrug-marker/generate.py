"""
Maßkrug marker clips: coloured C-clips that snap onto the handle of a 1 l
Maßkrug. The inner contour follows the (rounded, oval) handle cross-section,
an optional badge on the outer face carries a recessed symbol (colour-blind
friendly, and lets one filament colour serve several people).

Frame / print orientation
-------------------------
XY  : handle cross-section. X = handle width (perpendicular to the loop plane),
      Y = handle thickness (in the loop plane), +Y = outside of the loop.
Z   : along the handle bar, z = 0 on the bed. The C-profile is extruded in Z,
      so the snap-bending happens along the layer lines (strong direction)
      and the whole part prints without supports.
The opening sits at +X (a lateral side of the bar): pushing the clip on
sideways only needs the gap to open to the bar THICKNESS (13.6), not width.
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

SEG = 160
SYMBOLS = ("plain", "circle", "square", "triangle", "diamond", "cross", "star", "heart")
YIELD_STRAIN = {"PLA": 0.02, "PETG": 0.025}   # rough bulk values; printed parts are lower


@dataclass
class Params:
    # --- measured (caliper photos 03 / 04)
    bar_w: float = 21.9           # handle width across the loop plane
    bar_t: float = 13.6           # handle thickness in the loop plane
    # --- ASSUMED (check with the profile gauge)
    profile_n: float = 2.5        # superellipse exponent of the cross-section (2 = ellipse)
    # --- clip
    grip: float = 0.3             # inner contour this much smaller than the bar -> preload
    band_t: float = 2.0           # wall thickness (5 lines @ 0.4 mm)
    clip_w: float = 10.0          # length along the bar
    gap_ratio: float = 0.72       # opening chord / bar_t (retention vs. snap force)
    lip_r: float = 0.7            # rounding of the lip corners = lead-in
    edge_r: float = 0.8           # rounded top edge
    edge_c: float = 0.4           # 45 deg chamfer on the bed edge (no overhang)
    # --- badge
    symbol: str = "circle"        # one of SYMBOLS or "all"
    badge_w: float = 12.0
    badge_h: float = 1.4          # badge height above the band
    symbol_depth: float = 0.8
    # --- print
    material: str = "PETG"        # PETG: dishwasher/sun safer than PLA (Tg ~80 vs ~60 deg C)
    fit_grips: str = "0.0,0.3,0.6"
    gauge_ns: str = "2.0,2.5,3.0"


# ------------------------------------------------------------------ 2D helpers
def superellipse(ax, by, n, segs=SEG):
    t = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    x = ax * np.sign(c) * np.abs(c) ** (2 / n)
    y = by * np.sign(s) * np.abs(s) ** (2 / n)
    return m3.CrossSection([np.c_[x, y].tolist()])


def rect(x0, x1, y0, y1):
    return m3.CrossSection.square([x1 - x0, y1 - y0]).translate([x0, y0])


def bar_profile(p: Params, shrink=0.0, n=None):
    return superellipse(p.bar_w / 2 - shrink, p.bar_t / 2 - shrink, n or p.profile_n)


def symbol2d(name, s=1.0):
    C = m3.CrossSection
    if name == "circle":
        return C.circle(2.6 * s, 64)
    if name == "square":
        return C.square([4.6 * s] * 2, True)
    if name == "triangle":
        r = 3.4 * s
        return C([[(r * math.cos(a), r * math.sin(a) - 0.5 * s) for a in np.radians([90, 210, 330])]])
    if name == "diamond":
        return C.square([4.2 * s] * 2, True).rotate(45)
    if name == "cross":
        return C.square([5.6 * s, 1.8 * s], True) + C.square([1.8 * s, 5.6 * s], True)
    if name == "star":
        pts = []
        for k in range(10):
            r = (3.3 if k % 2 == 0 else 1.45) * s
            a = math.radians(90 + 36 * k)
            pts.append((r * math.cos(a), r * math.sin(a)))
        return C([pts])
    if name == "heart":
        h = C.circle(1.55 * s, 48).translate([-1.3 * s, 0.9 * s]) + C.circle(1.55 * s, 48).translate([1.3 * s, 0.9 * s])
        return h + C([[(-2.75 * s, 0.55 * s), (2.75 * s, 0.55 * s), (0, -2.9 * s)]])
    return C()


def dimples2d(k):
    return m3.CrossSection.batch_boolean(
        [m3.CrossSection.circle(0.9, 32).translate([(i - (k - 1) / 2) * 3.0, 0]) for i in range(k)], m3.OpType.Add)


# ------------------------------------------------------------------ geometry
def derived(p: Params):
    ai, bi = p.bar_w / 2 - p.grip, p.bar_t / 2 - p.grip
    gap = p.gap_ratio * p.bar_t
    # x where the inner contour reaches y = gap/2 (lip corner)
    x_lip = ai * (1 - (gap / 2 / bi) ** p.profile_n) ** (1 / p.profile_n)
    y_face = bi + p.band_t + p.badge_h
    R_eff = (ai + bi) / 2 + p.band_t / 2                     # mean radius of the ring
    delta = p.bar_t - gap                                    # opening needed to snap on
    strain = delta * p.band_t / (3 * math.pi * R_eff**2)     # split-ring estimate
    return dict(ai=ai, bi=bi, gap=gap, x_lip=x_lip, y_face=y_face, R_eff=R_eff,
                snap_opening=delta, retention_per_side=(p.bar_t - gap) / 2, strain_est=strain)


def clip2d(p: Params, d, badge=True):
    inner = bar_profile(p, p.grip)
    outer = inner.offset(p.band_t, m3.JoinType.Round, 2.0, SEG)
    prof = outer
    if badge:
        prof = prof + rect(-p.badge_w / 2, p.badge_w / 2, 0, d["y_face"]).offset(-0.8, m3.JoinType.Round).offset(
            0.8, m3.JoinType.Round, 2.0, 32)
    prof = prof - inner - rect(0, p.bar_w, -d["gap"] / 2, d["gap"] / 2)
    # round every convex corner (lip ends = lead-in)
    return prof.offset(-p.lip_r, m3.JoinType.Round, 2.0, 48).offset(p.lip_r, m3.JoinType.Round, 2.0, 48)


def rounded_extrude(cs, H, r_top, c_bot, dz=0.1):
    """Extrude with a 45 deg chamfer at the bed and a rounded top edge (stair-stepped < layer height)."""
    parts = []
    z = 0.0
    while z < c_bot - 1e-9:
        parts.append(cs.offset(-(c_bot - z - dz / 2), m3.JoinType.Round).extrude(dz).translate([0, 0, z]))
        z += dz
    top0 = H - r_top
    parts.append(cs.extrude(top0 - z).translate([0, 0, z]))
    z = top0
    while z < H - 1e-9:
        u = z + dz / 2 - top0
        off = r_top - math.sqrt(max(r_top**2 - u**2, 0))
        parts.append(cs.offset(-off, m3.JoinType.Round).extrude(dz).translate([0, 0, z]))
        z += dz
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add)


def face_cut(p: Params, d, cs2d, depth):
    """Cut a 2D shape (u = x, v = z) into the badge face (+Y)."""
    return cs2d.translate([0, p.clip_w / 2]).extrude(depth + 1).rotate([90, 0, 0]).translate([0, d["y_face"] + 1, 0])


def build_clip(p: Params, symbol=None, dimples=0):
    d = derived(p)
    symbol = symbol or p.symbol
    body = rounded_extrude(clip2d(p, d, badge=True), p.clip_w, p.edge_r, p.edge_c)
    if symbol != "plain":
        body -= face_cut(p, d, symbol2d(symbol), p.symbol_depth)
    if dimples:
        body -= face_cut(p, d, dimples2d(dimples), 0.6)
    return body, d


def build_gauge(p: Params):
    """Flat profile gauge: half-profile notches for several exponents, 1..k dots as id."""
    ns = [float(x) for x in p.gauge_ns.split(",")]
    pitch = p.bar_t + 8
    Lx = pitch * len(ns) + 4
    plate = m3.CrossSection.square([Lx, p.bar_w / 2 + 8]).translate([0, -(p.bar_w / 2 + 8)])
    for i, n in enumerate(ns):
        cx = 2 + pitch * (i + 0.5)
        notch = superellipse(p.bar_t / 2, p.bar_w / 2, n).translate([cx, 0])   # opening on the plate edge y=0
        plate -= notch
        for k in range(i + 1):
            plate -= m3.CrossSection.circle(0.9, 32).translate([cx + (k - i / 2) * 3.0, -(p.bar_w / 2 + 4.5)])
    return plate.extrude(2.0), ns


# ------------------------------------------------------------------ functional test
def functional_test(p: Params, d):
    bar = bar_profile(p)
    clip = clip2d(p, d)
    ring_inner = bar_profile(p, p.grip)
    res = dict(
        preload_overlap_mm2=round((bar ^ (clip + ring_inner.offset(-0.01)) - ring_inner.offset(-0.01)).area(), 2),
        gap_mm=round(d["gap"], 2),
        snap_opening_mm=round(d["snap_opening"], 2),
        retention_per_side_mm=round(d["retention_per_side"], 2),
        strain_est_pct=round(100 * d["strain_est"], 2),
        yield_strain_pct=100 * YIELD_STRAIN.get(p.material, 0.02),
        min_wall_mm=round(p.band_t, 2),
    )
    # angular coverage of the bar contour by the clip
    t = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    ai, bi = d["ai"], d["bi"]
    x = ai * np.sign(c) * np.abs(c) ** (2 / p.profile_n)
    y = bi * np.sign(s) * np.abs(s) ** (2 / p.profile_n)
    covered = ~((x > 0) & (np.abs(y) < d["gap"] / 2))
    res["wrap_deg"] = round(float(360 * covered.mean()), 1)
    res["ok"] = bool(res["retention_per_side_mm"] >= 1.2 and d["strain_est"] < 0.6 * YIELD_STRAIN.get(p.material, 0.02)
                     and res["wrap_deg"] > 200 and res["preload_overlap_mm2"] > 0)
    return res


# ------------------------------------------------------------------ pipeline
def export(M, base, material, bodies=1, previews=False):
    tm = mesh.manifold_to_trimesh(M)
    mesh.export(tm, str(base))
    rep = check.report(tm, material)
    check.assert_printable(rep, bodies=bodies)
    if previews:
        render.main(str(base) + ".stl", str(base))
    return rep


def generate(p: Params, out_dir: Path, previews=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    d = derived(p)
    ft = functional_test(p, d)
    assert ft["ok"], f"functional test failed: {ft}"
    reports = {}
    names = SYMBOLS if p.symbol == "all" else (p.symbol,)
    plate = m3.Manifold()
    for i, s in enumerate(names):
        M, _ = build_clip(p, s)
        reports[f"clip_{s}"] = export(M, out_dir / f"masskrug_clip_{s}", p.material,
                                      previews=previews and i == 1)
        plate += M.translate([(i % 4) * 34.0, (i // 4) * 30.0, 0])
    if len(names) > 1:
        reports["clip_set"] = export(plate, out_dir / "masskrug_clip_set", p.material, bodies=len(names))
    fit = m3.Manifold()
    for i, g in enumerate(float(x) for x in p.fit_grips.split(",")):
        M, _ = build_clip(replace(p, grip=g), "plain", dimples=i + 1)
        fit += M.translate([i * 34.0, 0, 0])
    reports["fit_set"] = export(fit, out_dir / "masskrug_fit_set", p.material, bodies=len(p.fit_grips.split(",")))
    G, ns = build_gauge(p)
    reports["profile_gauge"] = export(G, out_dir / "masskrug_profile_gauge", p.material)
    summary = dict(params=asdict(p), derived={k: round(v, 3) for k, v in d.items()},
                   functional_test=ft, gauge_exponents=ns, parts=reports)
    check.write(summary, str(out_dir / "masskrug_report.json"))
    print({"functional_test": ft, "clip": {k: reports[f"clip_{names[0]}"][k]
                                           for k in ("bbox_mm", "volume_cm3", "mass_g_at_100pct",
                                                     "overhang_area_gt45deg_mm2")}})
    return summary


def main():
    a = cli.parser_for(Params, out=(str, str(HERE / "out"))).parse_args()
    generate(cli.params_from(a, Params), Path(a.out))


if __name__ == "__main__":
    main()
