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

import argparse
import json
import math
import time
from dataclasses import dataclass, asdict

import numpy as np


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
class Rod:
    """Polyline with per-vertex radius (union of round cones)."""

    def __init__(self, pts, rad, name):
        self.p = np.asarray(pts, float)
        self.r = np.broadcast_to(np.asarray(rad, float), (len(self.p),)).copy()
        self.name = name


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


# --------------------------------------------------------------------------- SDF
def _rod_kernel():
    from numba import njit

    @njit(cache=True, fastmath=True)
    def splat(S, buf, lo, h, A, Bv, ra, rb, band, k):
        nx, ny, nz = S.shape
        m = A.shape[0]
        # pass 1: hard min of this rod into buf (inf = untouched)
        for q in range(m):
            rmax = max(ra[q], rb[q]) + band
            i0 = max(int((min(A[q, 0], Bv[q, 0]) - rmax - lo[0]) / h), 0)
            i1 = min(int((max(A[q, 0], Bv[q, 0]) + rmax - lo[0]) / h) + 1, nx - 1)
            j0 = max(int((min(A[q, 1], Bv[q, 1]) - rmax - lo[1]) / h), 0)
            j1 = min(int((max(A[q, 1], Bv[q, 1]) + rmax - lo[1]) / h) + 1, ny - 1)
            l0 = max(int((min(A[q, 2], Bv[q, 2]) - rmax - lo[2]) / h), 0)
            l1 = min(int((max(A[q, 2], Bv[q, 2]) + rmax - lo[2]) / h) + 1, nz - 1)
            abx = Bv[q, 0] - A[q, 0]
            aby = Bv[q, 1] - A[q, 1]
            abz = Bv[q, 2] - A[q, 2]
            L2 = abx * abx + aby * aby + abz * abz + 1e-12
            for i in range(i0, i1 + 1):
                px = lo[0] + i * h - A[q, 0]
                for j in range(j0, j1 + 1):
                    py = lo[1] + j * h - A[q, 1]
                    for l in range(l0, l1 + 1):
                        pz = lo[2] + l * h - A[q, 2]
                        t = (px * abx + py * aby + pz * abz) / L2
                        t = min(max(t, 0.0), 1.0)
                        dx = px - t * abx
                        dy = py - t * aby
                        dz = pz - t * abz
                        d = np.sqrt(dx * dx + dy * dy + dz * dz) - (ra[q] + t * (rb[q] - ra[q]))
                        if d < band and d < buf[i, j, l]:
                            buf[i, j, l] = d
        # pass 2: exponential smooth-union into S, reset buf
        for q in range(m):
            rmax = max(ra[q], rb[q]) + band
            i0 = max(int((min(A[q, 0], Bv[q, 0]) - rmax - lo[0]) / h), 0)
            i1 = min(int((max(A[q, 0], Bv[q, 0]) + rmax - lo[0]) / h) + 1, nx - 1)
            j0 = max(int((min(A[q, 1], Bv[q, 1]) - rmax - lo[1]) / h), 0)
            j1 = min(int((max(A[q, 1], Bv[q, 1]) + rmax - lo[1]) / h) + 1, ny - 1)
            l0 = max(int((min(A[q, 2], Bv[q, 2]) - rmax - lo[2]) / h), 0)
            l1 = min(int((max(A[q, 2], Bv[q, 2]) + rmax - lo[2]) / h) + 1, nz - 1)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    for l in range(l0, l1 + 1):
                        d = buf[i, j, l]
                        if d < 1e20:
                            S[i, j, l] += np.exp(-max(d, -20.0 * k) / k)
                            buf[i, j, l] = np.inf

    return splat


def evaluate(rods, solids, p: Params):
    k = p.blend
    band = 7 * k + 0.5
    lo = np.array([-p.r_base - 9, -p.r_base - 9, -1.0 - 0.3 * p.voxel])  # no sample on z=0
    hi = np.array([p.r_base + 9, p.r_base + 9, p.height + 1.0])
    n = np.ceil((hi - lo) / p.voxel).astype(int) + 1
    S = np.zeros(n, np.float32)
    buf = np.full(n, np.inf, np.float32)
    ax = [lo[i] + p.voxel * np.arange(n[i]) for i in range(3)]
    splat = _rod_kernel()
    t0 = time.time()
    for rd in rods:
        splat(S, buf, lo, p.voxel, rd.p[:-1].copy(), rd.p[1:].copy(),
              rd.r[:-1].copy(), rd.r[1:].copy(), band, k)
    del buf
    for so in solids:
        bmin, bmax = so.bbox()
        a = np.clip(np.floor((bmin - band - lo) / p.voxel).astype(int), 0, n - 1)
        b = np.clip(np.ceil((bmax + band - lo) / p.voxel).astype(int) + 1, 0, n)
        X, Y, Z = np.meshgrid(ax[0][a[0]:b[0]], ax[1][a[1]:b[1]], ax[2][a[2]:b[2]], indexing="ij")
        d = so.sdf(X, Y, Z)
        sub = S[a[0]:b[0], a[1]:b[1], a[2]:b[2]]
        sub += np.where(d < band, np.exp(-np.maximum(d, -20 * k) / k), 0).astype(np.float32)
    print(f"  SDF accumulated in {time.time() - t0:.1f}s, grid {tuple(int(x) for x in n)}")
    with np.errstate(divide="ignore"):
        D = (-k * np.log(np.maximum(S, 1e-30))).astype(np.float32)
    del S
    Z = ax[2][None, None, :]
    np.maximum(D, (-Z).astype(np.float32), out=D)   # flat cut at the bed, z >= 0
    return D, lo


def mesh_from_sdf(D, lo, p: Params):
    from skimage.measure import marching_cubes
    import trimesh
    v, f, _, _ = marching_cubes(D, 0.0, spacing=(p.voxel,) * 3, allow_degenerate=False)
    v += lo
    m = trimesh.Trimesh(v, f[:, ::-1], process=True)
    if m.volume < 0:
        m.invert()
    m.apply_translation([0, 0, -m.bounds[0, 2]])   # sit exactly on the bed
    return m


def report(m, rods, meta, p: Params):
    import trimesh
    comps = m.split(only_watertight=False)
    n = m.face_normals
    zc = m.triangles_center[:, 2]
    area = m.area_faces
    down = (n[:, 2] < -math.cos(math.radians(45))) & (zc > 0.3)
    down60 = (n[:, 2] < -math.cos(math.radians(30))) & (zc > 0.3)
    ang = strut_angles(rods)
    worst = sorted(ang.items(), key=lambda x: x[1])[:5]
    r = dict(
        watertight=bool(m.is_watertight),
        winding_consistent=bool(m.is_winding_consistent),
        bodies=len(comps),
        faces=int(len(m.faces)),
        bbox_mm=[round(float(x), 2) for x in m.extents],
        volume_cm3=round(float(m.volume) / 1000, 2),
        pla_mass_g_at_100pct=round(float(m.volume) / 1000 * 1.24, 1),
        overhang_area_gt45deg_pct=round(100 * float(area[down].sum() / area.sum()), 3),
        overhang_area_gt60deg_pct=round(100 * float(area[down60].sum() / area.sum()), 3),
        min_strut_angle_deg=round(worst[0][1], 1),
        worst_struts={k: round(v, 1) for k, v in worst},
        rod_diameter_mm=[p.d_rod_top, p.d_rod_base],
        **{k: round(float(v), 2) for k, v in meta.items()},
    )
    return r


def main():
    ap = argparse.ArgumentParser()
    for f, v in asdict(P).items():
        ap.add_argument("--" + f.replace("_", "-"), type=type(v), default=v)
    ap.add_argument("--out", default="out/mae_west_eiffel")
    ap.add_argument("--simplify-eps", type=float, default=0.02)
    a = ap.parse_args()
    p = Params(**{f: getattr(a, f) for f in asdict(P)})
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

    print("building primitives ...")
    rods, solids, meta = build(p)
    ang = strut_angles(rods)
    print(f"  {len(rods)} rods, {len(solids)} solids, min strut angle {min(ang.values()):.1f} deg")
    print("evaluating SDF ...")
    D, lo = evaluate(rods, solids, p)
    print("marching cubes ...")
    m = mesh_from_sdf(D, lo, p)
    del D
    print(f"  raw mesh {len(m.faces)} faces")
    if a.simplify_eps > 0:
        # manifold-preserving decimation (max deviation simplify_eps mm)
        import manifold3d as m3
        import trimesh
        M = m3.Manifold(m3.Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                                tri_verts=np.asarray(m.faces, np.uint32)))
        mm = M.simplify(a.simplify_eps).to_mesh()
        m = trimesh.Trimesh(mm.vert_properties[:, :3], mm.tri_verts, process=True)
        print(f"  simplified to {len(m.faces)} faces (eps {a.simplify_eps} mm)")
    rep = report(m, rods, meta, p)
    rep["params"] = asdict(p)
    m.export(a.out + ".stl")
    m.export(a.out + ".3mf")
    with open(a.out + "_report.json", "w") as fh:
        json.dump(rep, fh, indent=2)
    print(json.dumps({k: v for k, v in rep.items() if k != "params"}, indent=2))
    assert rep["watertight"] and rep["bodies"] == 1, "mesh is not a single watertight body"


if __name__ == "__main__":
    main()
