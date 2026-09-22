"""
Mae West x Eiffel  -  generative, print-aware fusion sculpture.

Design DNA
----------
Mae West (Rita McBride, Effnerplatz Muenchen, 2011):
    52 m high rod lattice shaped as a hyperboloid of revolution,
    diameter 32 m at the foot, ~7.5 m at the waist, 19.5 m at the top.
    Straight rods on such a hyperboloid sweep ~143 deg in azimuth
    (derived: atan(sqrt(16^2-3.75^2)/3.75) + atan(sqrt(9.75^2-3.75^2)/3.75)).
Eiffel Tower (Paris, 1889):
    four legs on a square base, arches between the legs, platforms
    at 57 / 115 / 276 m of the 300 m structure, antenna spire (330 m total).

Fusion
------
* Two families of rods (+/- twist) follow hyperboloid kinematics
  (dphi/dz = C / r(z)^2, the exact law for straight rulings) on a
  profile that blends an Eiffel-style concave power curve into a
  Mae-West hyperbola above the waist.
* Below z_leg the rods are gathered into four Eiffel legs and fan
  out smoothly into the Mae West lattice.
* Pointed "Eiffel" arches are grown with the steepest-allowed rule:
  their slope is solved so that no segment is flatter than the
  overhang limit.
* All parts are merged with an exponential smooth-union, which gives
  bone-like fillets at every node (organic look + stress relief).

Print awareness (FDM, 0.4 mm nozzle, upright, no supports)
----------------------------------------------------------
* every strut centreline >= MIN_ANGLE from horizontal (checked)
* rings / lantern use a diamond cross-section with >= 50 deg flanks
* min strut diameter >= 2.0 mm, tapering thicker towards the base
* flat bed contact: foot pads + base ring, model cut at z = 0
* single watertight body (checked after meshing)
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from tdg import check, cli, mesh, render, sdf  # noqa: E402
from tdg.sdf import Rod  # noqa: E402


# --------------------------------------------------------------------------- params
@dataclass
class Params:
    height: float = 180.0          # total height incl. spire [mm]
    r_base: float = 40.0           # leg-corner radius at z=0
    r_waist: float = 14.0          # waist radius (rod centreline)
    waist_frac: float = 0.62       # waist height / crown height
    crown_frac: float = 0.84       # crown height / total height
    crown_ratio: float = 0.61      # r_crown / r_base (Mae West 19.5/32)
    twist_deg: float = 143.0       # Mae West azimuth sweep of one rod
    n_rods: int = 16               # rods per twist direction
    leg_frac: float = 0.36         # rods gathered into legs below this * crown
    leg_gather: float = 0.14       # remaining angular spread of a leg at z=0
    d_rod_top: float = 2.0         # rod diameter at crown [mm]
    d_rod_base: float = 3.0        # rod diameter at base [mm]
    blend: float = 0.35            # smooth-union radius k [mm]
    min_angle: float = 50.0        # design limit for strut angle to horizontal
    voxel: float = 0.25            # SDF grid size [mm]


P = Params()


# --------------------------------------------------------------------------- profile
def derived(p: Params):
    z_c = p.crown_frac * p.height
    z_w = p.waist_frac * z_c
    r_c = p.crown_ratio * p.r_base
    z_leg = p.leg_frac * z_c
    return z_c, z_w, r_c, z_leg


def radius(z, p: Params):
    """Rod-centreline radius r(z): Eiffel power curve -> hyperbola."""
    z_c, z_w, r_c, _ = derived(p)
    z = np.asarray(z, dtype=float)
    rw, rb = p.r_waist, p.r_base
    b_lo = math.sqrt(rb**2 - rw**2) / z_w
    b_hi = math.sqrt(r_c**2 - rw**2) / (z_c - z_w)
    hyp_lo = np.sqrt(rw**2 + ((z_w - z) * b_lo) ** 2)
    eif_lo = rw + (rb - rw) * np.clip((z_w - z) / z_w, 0, None) ** 2.0
    e = np.clip(1 - z / z_w, 0, 1) ** 1.2          # Eiffel weight, 1 at foot
    lo = e * eif_lo + (1 - e) * hyp_lo
    hi = np.sqrt(rw**2 + ((z - z_w) * b_hi) ** 2)
    return np.where(z < z_w, lo, hi)


def twist_integral(z, p: Params):
    """Phi(z) = C * int_0^z dz / r^2  (hyperboloid kinematics), Phi(z_c)=twist."""
    z_c = derived(p)[0]
    zz = np.linspace(0, z_c, 4001)
    f = 1.0 / radius(zz, p) ** 2
    cum = np.concatenate([[0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(zz))])
    cum *= math.radians(p.twist_deg) / cum[-1]
    return np.interp(z, zz, cum)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# --------------------------------------------------------------------------- primitives
class DiamondRing:
    """Torus with rhombic cross-section: |rho-R|/w + |z-z0|/h <= 1."""

    def __init__(self, z0, R, w, h, name):
        self.z0, self.R, self.w, self.h, self.name = z0, R, w, h, name

    def bbox(self):
        e = self.R + self.w
        return np.array([-e, -e, self.z0 - self.h]), np.array([e, e, self.z0 + self.h])

    def sdf(self, X, Y, Z):
        rho = np.sqrt(X * X + Y * Y)
        a = np.abs(rho - self.R) / self.w + np.abs(Z - self.z0) / self.h - 1
        return a * (self.w * self.h / math.hypot(self.w, self.h))


class Pad:
    """Flat cylinder standing on the bed."""

    def __init__(self, cx, cy, R, t, name):
        self.cx, self.cy, self.R, self.t, self.name = cx, cy, R, t, name

    def bbox(self):
        return (np.array([self.cx - self.R, self.cy - self.R, -1.0]),
                np.array([self.cx + self.R, self.cy + self.R, self.t]))

    def sdf(self, X, Y, Z):
        dr = np.sqrt((X - self.cx) ** 2 + (Y - self.cy) ** 2) - self.R
        dz = Z - self.t
        out = np.sqrt(np.maximum(dr, 0) ** 2 + np.maximum(dz, 0) ** 2)
        return out + np.minimum(np.maximum(dr, dz), 0)


def rod_diameter(z, p: Params):
    z_c = derived(p)[0]
    t = np.clip(1 - z / z_c, 0, 1)
    return p.d_rod_top + (p.d_rod_base - p.d_rod_top) * t**1.5


def build(p: Params):
    z_c, z_w, r_c, z_leg = derived(p)
    corners = np.pi / 4 + np.arange(4) * np.pi / 2
    rods, solids = [], []

    # --- lattice rods (Mae West) gathered into legs (Eiffel)
    z = np.linspace(-1.0, z_c, 320)
    zc = np.clip(z, 0, None)
    r = radius(zc, p)
    Phi = twist_integral(zc, p)
    Phi_L = twist_integral(z_leg, p)
    B = p.leg_gather + (1 - p.leg_gather) * smoothstep(zc / z_leg)
    for s in (+1, -1):
        for i in range(p.n_rods):
            theta = np.pi / 4 + (i + 0.5) * 2 * np.pi / p.n_rods
            lat = theta + s * (Phi - Phi_L)
            k = np.round((theta - np.pi / 4) / (np.pi / 2))
            c = np.pi / 4 + k * np.pi / 2
            phi = c + B * (lat - c)
            pts = np.c_[r * np.cos(phi), r * np.sin(phi), z]
            rods.append(Rod(pts, rod_diameter(zc, p) / 2, f"rod{'+' if s > 0 else '-'}{i}"))

    # --- pointed Eiffel arches, steepest-allowed growth
    kmax = 1 / math.tan(math.radians(p.min_angle))
    zz = np.linspace(0, z_c, 6000)
    rr = radius(zz, p)
    dr = np.gradient(rr, zz)
    target = np.pi / 4

    def arch_phi(zA):
        kz = kmax * np.clip(zz / zA, 0, 1) ** 0.6
        kz = np.maximum(kz, np.abs(dr) * 1.0001)
        kz = np.minimum(kz, kmax)
        dphi = np.sqrt(np.maximum(kz**2 - dr**2, 0)) / rr
        cum = np.concatenate([[0], np.cumsum(0.5 * (dphi[1:] + dphi[:-1]) * np.diff(zz))])
        return cum

    lo, hi = 5.0, z_w
    for _ in range(60):                          # solve apex height
        zA = 0.5 * (lo + hi)
        cum = arch_phi(zA)
        if np.interp(zA, zz, cum) > target:
            hi = zA
        else:
            lo = zA
    zA = 0.5 * (lo + hi)
    cum = arch_phi(zA)
    m = zz <= zA
    za, pa = zz[m], cum[m] / np.interp(zA, zz, cum) * target
    ra = radius(za, p)
    arch_r = 0.5 * rod_diameter(za, p) * 0.85
    for kc, c in enumerate(corners):
        for side in (+1, -1):
            phi = c + side * pa
            pts = np.c_[ra * np.cos(phi), ra * np.sin(phi), za]
            pts[0, 2] = -1.0
            rods.append(Rod(pts, arch_r, f"arch{kc}{'ab'[side < 0]}"))

    # --- rings (platforms / waist / crown) with printable diamond sections
    solids.append(DiamondRing(0.0, p.r_base, 1.8, 1.8, "base_ring"))
    solids.append(DiamondRing(zA, float(radius(zA, p)), 1.3, 1.7, "platform1"))
    z2 = 0.5 * (zA + z_w)
    solids.append(DiamondRing(z2, float(radius(z2, p)), 1.2, 1.6, "platform2"))
    solids.append(DiamondRing(z_w, p.r_waist, 1.4, 1.9, "waist_ring"))
    solids.append(DiamondRing(z_c, r_c, 1.7, 2.2, "crown_ring"))
    for kc, c in enumerate(corners):
        solids.append(Pad(p.r_base * math.cos(c), p.r_base * math.sin(c), 7.0, 1.0, f"pad{kc}"))

    # --- spire: spokes + mast + lantern (Eiffel top on Mae West crown)
    t55 = math.tan(math.radians(55))
    z_m0 = z_w + p.r_waist * t55
    for kc, c in enumerate(corners):
        a = np.array([p.r_waist * math.cos(c), p.r_waist * math.sin(c), z_w])
        b = np.array([0, 0, z_m0])
        rods.append(Rod(np.linspace(a, b, 20), np.linspace(1.1, 1.3, 20), f"spoke_lo{kc}"))
    t50 = math.tan(math.radians(p.min_angle))
    z_m1 = z_c - r_c * t50
    for kc, c in enumerate(corners + np.pi / 4):
        a = np.array([0, 0, z_m1])
        b = np.array([r_c * math.cos(c), r_c * math.sin(c), z_c])
        rods.append(Rod(np.linspace(a, b, 30), np.linspace(1.2, 1.0, 30), f"spoke_hi{kc}"))
    zm = np.linspace(z_m0, p.height - 0.8, 120)
    rm = np.interp(zm, [z_m0, p.height], [1.7, 0.8])
    rods.append(Rod(np.c_[0 * zm, 0 * zm, zm], rm, "mast"))
    z3 = z_c + 0.45 * (p.height - z_c)
    solids.append(DiamondRing(z3, 0.0, 2.6, 3.4, "lantern"))

    meta = dict(z_crown=z_c, z_waist=z_w, r_crown=r_c, z_leg=z_leg,
                z_arch_apex=zA, z_platform2=z2, z_lantern=z3,
                z_mast0=z_m0, z_spoke_hi=z_m1)
    return rods, solids, meta


# --------------------------------------------------------------------------- checks
def strut_angles(rods):
    out = {}
    for rd in rods:
        d = np.diff(rd.p[rd.p[:, 2] >= 0.0], axis=0)
        h = np.hypot(d[:, 0], d[:, 1])
        ang = np.degrees(np.arctan2(d[:, 2], h + 1e-12))
        out[rd.name] = float(np.min(np.abs(ang)))
    return out


# --------------------------------------------------------------------------- pipeline
def generate(p: Params, out: Path, simplify_eps=0.02, previews=True):
    print("building primitives ...")
    rods, solids, meta = build(p)
    ang = strut_angles(rods)
    print(f"  {len(rods)} rods, {len(solids)} solids, min strut angle {min(ang.values()):.1f} deg")
    print("evaluating SDF ...")
    lo = [-p.r_base - 9, -p.r_base - 9, -1.0 - 0.3 * p.voxel]   # no sample on z=0
    hi = [p.r_base + 9, p.r_base + 9, p.height + 1.0]
    D, lo = sdf.evaluate(rods, solids, lo, hi, p.voxel, p.blend)
    print("marching cubes ...")
    m = sdf.to_mesh(D, lo, p.voxel)
    del D
    print(f"  raw mesh {len(m.faces)} faces")
    m = mesh.simplify(m, simplify_eps)
    print(f"  simplified to {len(m.faces)} faces (eps {simplify_eps} mm)")
    worst = sorted(ang.items(), key=lambda x: x[1])[:5]
    rep = check.report(m, "PLA", extra=dict(
        min_strut_angle_deg=round(worst[0][1], 1),
        worst_struts={k: round(v, 1) for k, v in worst},
        rod_diameter_mm=[p.d_rod_top, p.d_rod_base],
        **{k: round(float(v), 2) for k, v in meta.items()},
        params=asdict(p)))
    mesh.export(m, str(out))
    check.write(rep, str(out) + "_report.json")
    if previews:
        render.main(str(out) + ".stl", str(out))
    print({k: v for k, v in rep.items() if k != "params"})
    check.assert_printable(rep)
    return m, rep


def main():
    ap = cli.parser_for(Params, out=(str, str(HERE / "out" / "mae_west_eiffel")),
                        simplify_eps=(float, 0.02))
    a = ap.parse_args()
    generate(cli.params_from(a, Params), Path(a.out), a.simplify_eps)


if __name__ == "__main__":
    main()
