"""
Organic 3D charms (round, "swung" shapes) built with the SDF toolkit + a few CSG details.

Every figure is modelled standing (up = +Z, front = +Y), bottom at z = 0, and gets a fillet into the base:
a slab just below z = 0 is part of the SDF blend, the exponential smooth union grows a concave flare
where the figure meets it, then the bed cut removes the slab. on_base() (charms.py) centres it on the
grooved charm base.

Design rules (0.4 mm nozzle, printed standing, no supports):
  walls / struts >= 0.8 mm, recessed details >= 0.7 mm, undercut flanks <= 45 deg, bridges <= ~5 mm.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import manifold3d as m3

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from tdg import mesh as tmesh  # noqa: E402
from tdg import sdf as S  # noqa: E402

import charms as C  # noqa: E402

VOXEL = 0.1


# ------------------------------------------------------------------ SDF primitives
class Ellip:
    """Ellipsoid, optional rotation R (columns = local axes in world)."""

    def __init__(self, c, r, R=None):
        self.c, self.r = np.asarray(c, float), np.asarray(r, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)

    def bbox(self):
        e = self.r.max()
        return self.c - e, self.c + e

    def sdf(self, X, Y, Z):
        P = np.stack([X - self.c[0], Y - self.c[1], Z - self.c[2]], -1) @ self.R
        k0 = np.linalg.norm(P / self.r, axis=-1)
        k1 = np.linalg.norm(P / self.r**2, axis=-1)
        return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


class RBox:
    def __init__(self, c, half, rr=0.0):
        self.c, self.b, self.rr = np.asarray(c, float), np.asarray(half, float), rr

    def bbox(self):
        return self.c - self.b, self.c + self.b

    def sdf(self, X, Y, Z):
        q = np.stack([np.abs(X - self.c[0]), np.abs(Y - self.c[1]), np.abs(Z - self.c[2])], -1) - self.b + self.rr
        return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - self.rr


class Func:
    """Arbitrary SDF given as a vectorised function on a bounding box."""

    def __init__(self, lo, hi, fn):
        self.lo, self.hi, self.fn = np.asarray(lo, float), np.asarray(hi, float), fn

    def bbox(self):
        return self.lo, self.hi

    def sdf(self, X, Y, Z):
        return self.fn(X, Y, Z)


def rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def fillet_slab(half_x=5.0, half_y=3.8):
    return RBox((0, 0, -0.6), (half_x, half_y, 0.6))


def sdf_figure(rods, solids, blend=0.4, voxel=VOXEL, pad=1.5, simplify=0.004):
    """Evaluate, mesh, simplify and convert to a manifold (bed cut at z = 0)."""
    los, his = [], []
    for r in rods:
        los.append(r.p.min(0) - r.r.max())
        his.append(r.p.max(0) + r.r.max())
    for s in solids:
        a, b = s.bbox()
        los.append(a)
        his.append(b)
    lo = np.min(los, 0) - pad
    hi = np.max(his, 0) + pad
    lo[2] = -1.0 - 0.3 * voxel
    D, lo = S.evaluate(rods, solids, lo, hi, voxel, blend)
    tm = S.to_mesh(D, lo, voxel, sit_on_bed=False)
    tm = tmesh.simplify(tm, simplify)
    M = tmesh.trimesh_to_manifold(tm)
    assert M.status() == m3.Error.NoError, M.status()
    parts = M.decompose()
    return max(parts, key=lambda q: q.volume())   # drop specks from the removed slab


# ------------------------------------------------------------------ heart v3 (stable, swung stem)
def heart_v3(w=11.0):
    """Crisp puffy heart (two ellipsoid lobes hulled to a point, flanks ~44 deg) on a swung S-stem that
    flares into the base with a fillet. The stem (>= 2.6 mm) runs 3 mm up into the heart body."""
    k = w / 11.6
    lobe = m3.Manifold.sphere(3.3 * k, 64).scale([1.0, 0.72, 1.0])
    tip = m3.Manifold.sphere(0.8 * k, 24).translate([0, 0, 0.8 * k])
    lobes = [lobe.translate([sx * 2.5 * k, 0, 8.0 * k]) for sx in (-1, 1)]
    heart = m3.Manifold.batch_hull([lobes[0], tip]) + m3.Manifold.batch_hull([lobes[1], tip])
    lift = 4.2
    stem = S.Rod([(0, 0, -0.8), (0, 0, 0.5), (-0.75, 0, 1.7), (0.55, 0, 3.1), (0, 0, lift + 1.2), (0, 0, lift + 3.0)],
                 [2.9, 2.0, 1.55, 1.4, 1.35, 1.3])
    return sdf_figure([stem], [fillet_slab()], blend=0.5) + heart.translate([0, 0, lift])

# ------------------------------------------------------------------ filigree heart (image: red ornament hearts)
def heart_filigree(width=12.0, t=2.4):
    import icons
    h = icons.heart_curve(1.0)
    b = h.bounds()
    s = width / (b[2] - b[0])
    lift = 2.2
    h = h.translate([-(b[0] + b[2]) / 2, -b[1]]).scale([s, s]).translate([0, lift])
    b = h.bounds()
    H = b[3] - b[1]
    ring = h - h.offset(-1.0, m3.JoinType.Round)
    parts = [ring]
    for sx in (-1, 1):
        c = np.array([sx * 0.25 * width, lift + 0.62 * H])
        a = np.linspace(0, 1.05 * 2 * np.pi, 90)
        rr = 0.55 + (2.25 - 0.55) * a / a[-1]
        ang = (math.pi / 2 + a) * (-sx)                           # curl inwards towards the centre
        pts = [(c[0] + r_ * math.cos(g) * sx, c[1] + r_ * math.sin(g)) for r_, g in zip(rr, ang)]
        parts.append(C_stroke(pts, 0.9))
    parts.append(C_stroke([(0, lift + 0.4), (0, lift + 0.42 * H)], 1.0))
    parts.append(C_stroke([(0, lift + 0.42 * H), (-0.9, lift + 0.55 * H), (-1.5, lift + 0.5 * H)], 0.9))
    parts.append(C_stroke([(0, lift + 0.42 * H), (0.9, lift + 0.55 * H), (1.5, lift + 0.5 * H)], 0.9))
    fil = m3.CrossSection.batch_boolean(parts, m3.OpType.Add) ^ h
    # concave flare foot so the tip sits on 2 x 2.4 mm of solid instead of a point
    foot = m3.CrossSection([[(-3.4, 0), (3.4, 0), (1.0, lift + 0.6), (-1.0, lift + 0.6)]])
    foot = foot - m3.CrossSection.circle(2.6, 64).translate([3.9, lift + 0.6]) \
        - m3.CrossSection.circle(2.6, 64).translate([-3.9, lift + 0.6])
    shape = fil + foot
    core = C.extrude_xz(shape, -t / 2, t / 2)
    face = C.extrude_xz(shape.offset(-0.3, m3.JoinType.Round), -t / 2 - 0.3, t / 2 + 0.3)
    return core + face


def C_stroke(pts, w):
    import icons
    return icons.stroke(pts, w)


# ------------------------------------------------------------------ cuckoo clock v2 (solid carved back board)
def cuckoo_v2(Lg=8.3, r=None):
    body = C.charm_cuckoo(Lg)
    t = C.PLATE_T
    y0 = t - 0.4
    board2d = m3.CrossSection([[(-4.3, 0), (4.3, 0), (3.5, 2.4), (2.1, 4.7), (1.1, 6.2), (4.5, 10.8), (-4.5, 10.8),
                                (-1.1, 6.2), (-2.1, 4.7), (-3.5, 2.4)]])
    # carved scroll holes in the board (arched tops = self supporting)
    for sx in (-1, 1):
        board2d -= m3.CrossSection([[(sx * 1.0, 1.2), (sx * 2.6, 1.2), (sx * 2.2, 2.4), (sx * 1.6, 3.2),
                                     (sx * 1.0, 2.4)]][::sx])
    board = C.extrude_xz(board2d, y0, y0 + 2.0)
    return C.bed_cut(body + board)


# ------------------------------------------------------------------ rocket (image: blue retro rocket)
def rocket():
    zs = [-0.6, 0.8, 1.6, 3.5, 6.0, 9.0, 11.5, 13.5, 15.2, 16.1]
    rs = [1.9, 1.9, 2.35, 2.7, 2.8, 2.6, 2.1, 1.4, 0.65, 0.3]
    body = S.Rod([(0, 0, z) for z in zs], rs)
    th = np.linspace(0, 2 * np.pi, 49)
    port = S.Rod([(0.95 * math.cos(a), 2.55, 9.3 + 0.95 * math.sin(a)) for a in th], 0.38)
    M = sdf_figure([body, port], [fillet_slab(3.2, 3.2)], blend=0.3)
    fin2d = m3.CrossSection([[(1.4, 0), (4.1, 0), (4.1, 1.8), (2.1, 7.2), (1.4, 7.2)]])
    fin = C.extrude_xz(fin2d, -0.5, 0.5)
    fin = fin - m3.Manifold.cube([10, 10, 10], True).translate([0, 0, -5])
    for ang in (30, 150, 270):
        M += fin.rotate([0, 0, ang])
    M -= m3.Manifold.sphere(0.6, 24).translate([0, 2.95, 9.3])       # window pane recess
    return M


# ------------------------------------------------------------------ pretzel v2 (image: round dough ropes)
def brezn_rope(s=1.35):
    belly = [(-3.6, 0.6), (-3.1, -1.9), (-1.6, -3.1), (0, -3.3), (1.6, -3.1), (3.1, -1.9), (3.6, 0.6)]
    left = [(-3.6, 0.6), (-3.5, 2.4), (-2.3, 3.3), (-0.9, 2.9), (0.2, 1.2), (1.2, -1.1), (1.6, -2.7)]
    z0 = 3.3 + 1.35 / s                                            # belly bottom on the bed
    dy = {1.2: 0.55, 0.2: 0.55}                                    # left arm passes in front at the crossing

    def path(pts, front):
        out = []
        for x, z in pts:
            y = (0.6 if abs(x) < 1.0 and z > -1.5 else 0.0) * (1 if front else -1)
            out.append((x * s, y, (z + z0) * s / s * s))
        return out

    rods = [S.Rod(path(belly, True), 1.35),
            S.Rod(path(left, True), 0.95),
            S.Rod(path([(-x, z) for x, z in left], False), 0.95)]
    salt = [Ellip((x * s, 1.25, (z + z0) * s), (0.42, 0.42, 0.42)) for x, z in
            [(-2.4, -2.3), (-0.9, -3.0), (0.8, -3.0), (2.3, -2.4), (-2.9, 1.9), (2.9, 1.9)]]
    del dy
    return sdf_figure(rods, salt + [fillet_slab()], blend=0.35)


# ------------------------------------------------------------------ edelweiss (image: white flower, lying)
def edelweiss(n=9):
    """Edelweiss lying face-up: 9 pointed, domed bracts (flat underside), inner ring, raised floret cluster."""
    parts = []
    for k in range(n):
        R = rot("z", k * 360 / n)
        c = R @ np.array([3.3, 0, 0.0])                             # centred on the bed: flat underside,
        parts.append(Ellip(c, (2.9, 0.95, 1.2), R))                 # domed top, fully supported
    for k in range(6):
        R = rot("z", k * 60 + 20)
        parts.append(Ellip(R @ np.array([1.6, 0, 0.9]), (1.5, 0.8, 0.9), R))
    for x, y in [(0, 0)] + [(1.0 * math.cos(math.radians(a)), 1.0 * math.sin(math.radians(a)))
                            for a in range(0, 360, 60)]:
        parts.append(Ellip((x, y, 2.15), (0.62, 0.62, 0.62)))
    return sdf_figure([], parts, blend=0.18)

# ------------------------------------------------------------------ poop v2 (image: googly eyes, big smile)
def poop_v2():
    prof = [(4.3, 0), (4.6, 0.8), (4.5, 1.8), (3.9, 2.6), (3.4, 2.9), (3.9, 3.4), (4.0, 4.1), (3.6, 5.0),
            (2.7, 5.5), (3.1, 5.9), (3.1, 6.6), (2.6, 7.4), (1.8, 7.9), (2.0, 8.1), (1.8, 8.9), (1.0, 9.8),
            (0.45, 10.8), (0.2, 11.2)]
    body = S.Rod([(0, 0, z) for _, z in prof], [r - 0.35 for r, _ in prof])
    eyes = []
    for sx in (-1, 1):
        a = math.radians(sx * 26)
        eyes.append(Ellip((3.55 * math.sin(a), 3.55 * math.cos(a), 4.35), (1.3, 1.15, 1.3)))
    M = sdf_figure([body], eyes + [fillet_slab(4.2, 3.9)], blend=0.4)
    for sx in (-1, 1):
        a = math.radians(sx * 26)
        M -= m3.Manifold.sphere(0.55, 24).translate([4.55 * math.sin(a) * 0.98, 4.55 * math.cos(a), 4.25])
    th = np.radians(np.linspace(-34, 34, 15))
    for a in th:
        dz = 0.45 * (1 - (a / th[-1]) ** 2)
        M -= m3.Manifold.sphere(0.45, 16).translate([4.45 * math.sin(a), 4.45 * math.cos(a), 1.55 - dz])
    return M


# ------------------------------------------------------------------ thumbs up v2 (image: yellow emoji thumb)
def thumbsup_v2():
    """Emoji thumbs up: four clearly separated finger rolls facing out, thick thumb with a nail."""
    palm = RBox((0.1, -0.9, 4.4), (2.8, 1.8, 4.4), rr=1.5)
    fingers = [S.Rod([(-2.6, 1.25, z), (2.35 - 0.3 * i, 1.25, z)], 1.15) for i, z in enumerate((1.2, 3.35, 5.5, 7.6))]
    thumb = S.Rod([(-1.2, -0.6, 7.6), (-1.4, -0.5, 10.6), (-1.0, -0.3, 12.6)], [1.75, 1.65, 1.5])
    M = sdf_figure(fingers + [thumb], [palm, fillet_slab(4.0, 3.2)], blend=0.28)
    M -= m3.Manifold.cube([1.9, 1.0, 2.0]).translate([-2.0, 0.85, 11.0])       # thumb nail (0.3 mm step)
    return M

# ------------------------------------------------------------------ geodesic cage (image: grey wireframe)
def icosa_cage(R=5.3, strut=0.62, node=0.9):
    phi = (1 + 5 ** 0.5) / 2
    V = np.array([(-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0), (0, -1, phi), (0, 1, phi),
                  (0, -1, -phi), (0, 1, -phi), (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1)], float)
    V *= R / np.linalg.norm(V[0])
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    n = np.cross(V[F[0][1]] - V[F[0][0]], V[F[0][2]] - V[F[0][0]])
    n /= np.linalg.norm(n)
    if np.dot(n, V[list(F[0])].mean(0)) < 0:
        n = -n
    # rotate so face 0 points down (-z), i.e. the cage stands on a face
    tgt = np.array([0, 0, -1.0])
    v = np.cross(n, tgt)
    c = np.dot(n, tgt)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    Rm = np.eye(3) + K + K @ K * (1 / (1 + c))
    V = V @ Rm.T
    V[:, 2] -= V[:, 2].min() - strut * 0.6
    E = set()
    for f in F:
        for i in range(3):
            E.add(tuple(sorted((f[i], f[(i + 1) % 3]))))
    parts = [C.capsule(V[a], V[b], strut, 20) for a, b in E] + [m3.Manifold.sphere(node, 24).translate(list(p))
                                                                for p in V]
    M = C.bed_cut(m3.Manifold.batch_boolean(parts, m3.OpType.Add))
    ang = [math.degrees(math.atan2(abs(V[b][2] - V[a][2]), np.hypot(*(V[b][:2] - V[a][:2])))) for a, b in E]
    return M, dict(edges=len(E), edge_len=round(float(np.linalg.norm(V[0] - V[1])), 2),
                   min_strut_angle_deg=round(min(ang), 1), horizontal_bridges=int(sum(a < 5 for a in ang)))


# ------------------------------------------------------------------ voronoi egg (image: gold lattice egg)
def voronoi_egg(seed=11, cell=2.7, strut=1.1, shell=1.0):
    from scipy.spatial import cKDTree
    z_c, r_b, r_m, h_top = 3.2, 1.6, 4.8, 10.0

    def radius(z):
        z = np.asarray(z, float)
        lower = r_b + np.clip(z, 0, z_c) * (r_m - r_b) / z_c          # 45 deg cone
        u = np.clip((z - z_c) / h_top, 0, 1)
        upper = r_m * np.sqrt(np.maximum(1 - u**2, 0))
        return np.where(z < z_c, lower, upper)

    # seeds on the surface, Poisson-disc by rejection
    rng = np.random.default_rng(seed)
    zz = np.linspace(0, z_c + h_top, 400)
    rr = radius(zz)
    ds = np.hypot(np.diff(zz), np.diff(rr))
    w = np.concatenate([[0], np.cumsum(ds * 0.5 * (rr[1:] + rr[:-1]))])
    seeds = []
    for _ in range(6000):
        z = np.interp(rng.random() * w[-1], w, zz)
        a = rng.random() * 2 * np.pi
        p = np.array([radius(z) * math.cos(a), radius(z) * math.sin(a), z])
        if all(np.linalg.norm(p - q) > cell for q in seeds):
            seeds.append(p)
    seeds = np.array(seeds)
    tree = cKDTree(seeds)

    def fn(X, Y, Z):
        rho = np.hypot(X, Y)
        dz = 1e-3
        slope = (radius(Z + dz) - radius(Z - dz)) / (2 * dz)
        d_prof = (rho - radius(Z)) / np.sqrt(1 + slope**2)
        top = Z - (z_c + h_top)
        d_prof = np.maximum(d_prof, top)
        d_shell = np.abs(d_prof) - shell / 2
        pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], -1)
        dd, _ = tree.query(pts, k=2)
        edge = ((dd[:, 1] - dd[:, 0]) / 2).reshape(X.shape) - strut / 2
        d = np.maximum(d_shell, edge)
        ring = np.maximum(d_shell, Z - 1.0)                            # solid foot ring for bed contact
        return np.minimum(d, ring)

    e = r_m + 1
    solid = Func((-e, -e, -0.5), (e, e, z_c + h_top + 1), fn)
    M = sdf_figure([], [solid], blend=0.12)
    return M, dict(seeds=len(seeds), cell_mm=cell, strut_mm=strut, shell_mm=shell)


# ------------------------------------------------------------------ coin (image: gold coin with slot)
def coin(r=6.0, t=2.2):
    zc = r + 0.4
    disc = m3.CrossSection.circle(r, 96).translate([0, zc])
    stand = m3.CrossSection.batch_hull([disc, m3.CrossSection.square([6.0, 0.3], True).translate([0, 0.15])])
    body = C.extrude_xz(stand, -t / 2, t / 2)
    rim = m3.CrossSection.circle(r, 96).translate([0, zc]) - m3.CrossSection.circle(r - 0.9, 96).translate([0, zc])
    body += C.extrude_xz(rim, -t / 2 - 0.45, t / 2 + 0.45)
    slot = m3.CrossSection.square([1.5, 5.2], True).offset(0.1, m3.JoinType.Round).translate([0, zc])
    body -= C.extrude_xz(slot, t / 2 - 0.6, t / 2 + 1)
    body -= C.extrude_xz(slot, -t / 2 - 1, -t / 2 + 0.6)
    return body


# ------------------------------------------------------------------ registry
def _on(fn):
    def build(Lg, r=C.Rail()):
        M = fn()
        if isinstance(M, tuple):
            M = M[0]
        return C.on_base(M, Lg, r)
    return build


FIGURES = {
    "heart": _on(heart_v3),
    "heart_filigree": _on(heart_filigree),
    "cuckoo": lambda Lg, r=C.Rail(): C.on_base(cuckoo_v2(Lg, r), Lg, r),
    "brezn": _on(brezn_rope),
    "poop": _on(poop_v2),
    "rocket": _on(rocket),
    "edelweiss": _on(edelweiss),
    "thumbsup": _on(thumbsup_v2),
    "icosa": _on(icosa_cage),
    "voronoi_egg": _on(voronoi_egg),
    "coin": _on(coin),
}
