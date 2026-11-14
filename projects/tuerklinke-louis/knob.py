"""
Royal door knobs (boutons de porte) for the wall panels, printed upright like everything else (z = out of the
wall). The silhouette is the classic ogive knob: narrow neck, 45 deg widening bulb, pointed dome with a finial,
on a rosette with pearl beading. Because the bulb widens at >= 45 deg to the horizontal, it prints without
supports (same rule as the plug charm of masskrug-marker).

Real models: rosette ~70 mm, knob ~55 mm, projection ~65 mm; at 1:13.3 that is Ø 5.4 / 4.3 / 4.9 mm.
Variants:
  olive  : smooth ogive with collar and finial
  melon  : the same with 10 gadroons (vertical grooves) on the bulb, like gilded Louis XV knobs
"""
from __future__ import annotations

import math

import manifold3d as m3
import numpy as np

CS = m3.CrossSection
J = m3.JoinType.Round
ROSETTE_R, ROSETTE_T = 2.7, 0.7

# (r, z) of the knob above the rosette top; every widening step has dz >= dr (>= 45 deg)
PROFILE = [(0.0, 0.0), (0.95, 0.0), (0.95, 0.12), (1.2, 0.37), (1.2, 0.5), (0.8, 0.9), (0.72, 1.15),
           (1.85, 2.28), (1.95, 2.5), (1.95, 2.75), (1.85, 3.2), (1.6, 3.75), (1.25, 4.3), (0.85, 4.8),
           (0.5, 5.2), (0.32, 5.45), (0.42, 5.55), (0.45, 5.7), (0.3, 5.9), (0.0, 5.98)]


def knob_body():
    pts = [(max(r, 0.0), z) for r, z in PROFILE]
    return CS([pts]).revolve(96)


def check_profile():
    """Smallest angle to the horizontal of all downward-facing (widening) profile segments, degrees."""
    worst = 90.0
    for (r0, z0), (r1, z1) in zip(PROFILE[1:], PROFILE[2:]):
        if r1 > r0 + 1e-9:
            worst = min(worst, math.degrees(math.atan2(z1 - z0, r1 - r0)))
    return round(worst, 1)


def rosette():
    import generate as G
    o = G.circ(ROSETTE_R, seg=96)
    M = G.raised(o, 0.0, ROSETTE_T, round_r=0.25)
    top = ROSETTE_T - 0.02
    n = int(2 * math.pi * (ROSETTE_R - 0.5) / 0.86)
    M += m3.Manifold.batch_boolean([m3.Manifold.sphere(G.PEARL_R, 20).translate(
        [(ROSETTE_R - 0.5) * math.cos(a), (ROSETTE_R - 0.5) * math.sin(a), top - 0.08])
        for a in np.linspace(0, 2 * math.pi, n, endpoint=False)], m3.OpType.Add)
    # small leaf ring between pearls and knob: 8 radial petals
    petals = CS.batch_boolean([G.ell(0.32, 0.55, 1.62 * math.cos(a), 1.62 * math.sin(a), math.degrees(a) - 90)
                               for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)], m3.OpType.Add)
    M += G.raised(petals, top, 0.25, round_r=0.12)
    return M, n


def knob(variant="olive"):
    """Rosette + knob, base at z = 0. Returns (manifold, info)."""
    R, n_pearls = rosette()
    K = knob_body().translate([0, 0, ROSETTE_T - 0.05])
    if variant == "melon":   # 10 gadroons: capsule channels following the bulb from the equator to the tip
        z0 = ROSETTE_T - 0.05
        zs = np.linspace(2.1, 4.9, 10)
        rs = np.interp(zs, [z for _, z in PROFILE[7:15]], [r for r, _ in PROFILE[7:15]])
        ch = []
        for a in np.linspace(0, 360, 10, endpoint=False):
            balls = [m3.Manifold.sphere(0.27 * min(1.0, r / 1.2), 16).translate([r + 0.08, 0, z0 + z])
                     for r, z in zip(rs, zs)]
            ch += [m3.Manifold.batch_hull([b0, b1]).rotate([0, 0, a]) for b0, b1 in zip(balls, balls[1:])]
        K -= m3.Manifold.batch_boolean(ch, m3.OpType.Add)
    M = R + K
    info = dict(variant=variant, rosette_d_mm=2 * ROSETTE_R, knob_d_mm=round(2 * max(r for r, _ in PROFILE), 2),
                projection_mm=round(M.bounding_box()[5], 2), bulb_underside_deg=check_profile(), pearls=n_pearls)
    return M, info


# =====================================================================================================================
# Functional plug-in knobs at real cabinet size (Steckknauf). Unlike the 1:13 wall-panel knobs above, these are
# full-size knobs (bulb 9-18 mm) printed separately and pressed onto a pin ("Steckstift") that goes through a
# d3.4 hole in the door. Coordinates: z = 0 is the rosette bottom = print bed = door front.
#
# Geometry is built from two height fields, which makes the printability rule a property of the construction:
#  * rosette: polar height field z = H(r, theta) over a flat bottom -> only upward or vertical faces;
#  * knob body: radius field r = R(theta, z) up to a pole; after modelling, every column is clamped upward
#    (R[k] <= R[k-1] + SLOPE_MAX * dz), so no face of the body widens faster than 1 : 0.9 (>= 48 deg to the
#    horizontal, proof: |n_z| = R_z / sqrt(1 + (R_theta/R)^2 + R_z^2) <= 0.9 / sqrt(1.81) = 0.669 < cos 45).
#    Textures (scales, pearls, leaves) are therefore free to be modelled naturally; where a bead or scale rim
#    would overhang it is bevelled at 48 deg automatically.
# =====================================================================================================================
SOCKET_D, SOCKET_RIB_D, SOCKET_DEPTH, SOCKET_ROOF_DEG, SOCKET_RIBS = 3.3, 2.8, 7.5, 50.0, 4
PIN_D, PIN_HEAD_D, PIN_HEAD_T, PIN_ENGAGE, PIN_TIP = 3.0, 6.5, 1.0, 7.0, 0.4
HOLE_D = 3.4            # through-hole in the door (0.2 mm radial clearance on the d3.0 pin)
WALL_MIN = 1.2          # >= 3 lines at 0.4 mm
SLOPE_MAX = 0.9         # widening dr/dz limit of the body field (48 deg to the horizontal)
LEAD_SLOPE = 0.84       # socket lead-in: dr/dz of the 50 deg entry cone
VARIANTS = ("olive", "melon", "perle", "eichel", "zapfen", "krone")
RES = {"fine": (320, 0.06, 420, 0.06), "coarse": (160, 0.12, 200, 0.12)}   # body n_theta, dz, rosette n_theta, dr


def _field_body(zs, R):
    """Closed solid of revolution with radius field R[k, j] (rows = zs, cols = theta). The last row is a pole."""
    nz, nt = R.shape
    th = np.linspace(0, 2 * math.pi, nt, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    ring = np.stack([R[:-1] * c, R[:-1] * s, np.repeat(zs[:-1, None], nt, 1)], -1).reshape(-1, 3)
    V = np.vstack([ring, [[0, 0, zs[0]], [0, 0, zs[-1]]]])
    bot, top = len(V) - 2, len(V) - 1
    k, j = np.meshgrid(np.arange(nz - 2), np.arange(nt), indexing="ij")
    a, b = k * nt + j, k * nt + (j + 1) % nt
    cc, d = b + nt, a + nt
    F = [np.stack([a, b, cc], -1).reshape(-1, 3), np.stack([a, cc, d], -1).reshape(-1, 3)]
    j = np.arange(nt)
    F.append(np.stack([np.full(nt, bot), (j + 1) % nt, j], -1))
    last = (nz - 2) * nt
    F.append(np.stack([last + j, last + (j + 1) % nt, np.full(nt, top)], -1))
    return m3.Manifold(m3.Mesh(vert_properties=V.astype(np.float32), tri_verts=np.vstack(F).astype(np.uint32)))


def _field_polar(rs, H, z_bot=0.0):
    """Solid under a polar height field H[i, j] (rows = rs with rs[0] = 0 -> centre, cols = theta), flat bottom."""
    nr, nt = H.shape
    th = np.linspace(0, 2 * math.pi, nt, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    top = np.stack([rs[1:, None] * c, rs[1:, None] * s, H[1:]], -1).reshape(-1, 3)
    botring = np.stack([rs[-1] * c, rs[-1] * s, np.full(nt, z_bot)], -1)
    V = np.vstack([top, botring, [[0, 0, H[0].mean()], [0, 0, z_bot]]])
    tc, bc, b0 = len(V) - 2, len(V) - 1, len(top)
    i, j = np.meshgrid(np.arange(nr - 2), np.arange(nt), indexing="ij")
    a, d = i * nt + j, i * nt + (j + 1) % nt
    b, cc = a + nt, d + nt
    F = [np.stack([a, b, cc], -1).reshape(-1, 3), np.stack([a, cc, d], -1).reshape(-1, 3)]
    j = np.arange(nt)
    F.append(np.stack([np.full(nt, tc), j, (j + 1) % nt], -1))
    o = (nr - 2) * nt
    F.append(np.stack([b0 + j, b0 + (j + 1) % nt, o + (j + 1) % nt], -1))
    F.append(np.stack([b0 + j, o + (j + 1) % nt, o + j], -1))
    F.append(np.stack([np.full(nt, bc), b0 + (j + 1) % nt, b0 + j], -1))
    return m3.Manifold(m3.Mesh(vert_properties=V.astype(np.float32), tri_verts=np.vstack(F).astype(np.uint32)))


def _revolve(pts, seg=64):
    return CS([[(max(r, 0.0), z) for r, z in pts]]).revolve(seg)


def drop_bead(r, seg=32):
    """Pearl on a 50 deg cone tangent to it (prints without support), cone apex at z = 0, centre at 1.556 r."""
    b = math.radians(40.0)                     # cone half angle from the vertical
    zc = r / math.sin(b)
    pts = [(0.0, 0.0)] + [(r * math.cos(a), zc + r * math.sin(a)) for a in np.linspace(-b, math.pi / 2, 14)]
    return _revolve(pts, seg)


def _clamp(R, dz, slope=SLOPE_MAX):
    R = R.copy()
    for k in range(1, len(R)):
        np.minimum(R[k], R[k - 1] + slope * dz, out=R[k])
    return R


def _smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _ogive(R, z0, L, r_end, n=40):
    """Tangent ogive from radius R (vertical tangent) at z0 to the point z0 + L, cut at radius r_end."""
    rho = (R * R + L * L) / (2 * R)
    t = np.linspace(0, L, n)
    r = np.sqrt(np.maximum(rho * rho - t * t, 0)) + R - rho
    keep = r >= r_end
    return list(zip(r[keep], z0 + t[keep]))


def _beads_field(th, zs, c_r, z_c, rb, n, phase=0.0):
    """Outer radius of a ring of n spheres (radius rb, centres at radius c_r, height z_c) along each ray."""
    d = 2 * math.pi / n
    rel = (th[None, :] - phase + d / 2) % d - d / 2
    e = c_r * np.sin(rel)
    along = c_r * np.cos(rel)
    q = rb * rb - e * e - (zs[:, None] - z_c) ** 2
    return np.where(q > 0, along + np.sqrt(np.maximum(q, 0)), 0.0)


# ------------------------------------------------------------------ knob profiles (reference bulb_d = 13 mm)
def _profile(variant, s, sz, rn):
    """Key points (r, z) of the revolved base shape. s scales radii, sz heights; rn = neck radius (>= socket wall).
    Returns pts, dict(z_eq = height of the largest diameter, ...)."""
    Rb = 6.5 * s
    if variant in ("olive", "melon"):
        ze = 8.4 * sz
        pts = [(rn + 0.35, 1.0), (rn + 0.35, 2.3 * sz), (rn + 0.75 * s, 2.3 * sz + 0.45 * s),
               (rn + 0.75 * s, 2.95 * sz), (rn + 0.05, 3.55 * sz), (rn, 4.2 * sz), (rn + 0.3 * s, 5.0 * sz),
               (rn + 0.25 * (Rb - rn), 5.8 * sz), (rn + 0.62 * (Rb - rn), 6.9 * sz), (Rb - 0.12 * s, 7.9 * sz),
               (Rb, ze), (Rb, ze + 0.35 * sz)]
        pts += _ogive(Rb, ze + 0.35 * sz, 8.6 * sz, 0.62 * s)[1:]
        zt = pts[-1][1]
        pts += [(0.62 * s, zt + 0.25 * s), (1.05 * s, zt + 0.65 * s), (1.12 * s, zt + 0.85 * s),
                (0.95 * s, zt + 1.25 * s), (0.55 * s, zt + 1.55 * s), (0.0, zt + 1.7 * s)]
        return pts, dict(z_eq=ze)
    if variant == "perle":
        ze, rb = 9.0 * sz, 0.62 * s
        R2 = Rb - 2 * rb - 0.05
        pts = [(rn + 0.35, 1.0), (rn + 0.35, 2.4 * sz), (rn, 2.9 * sz), (rn, 4.0 * sz),
               (rn + 0.2 * (Rb - rn), 5.6 * sz), (rn + 0.6 * (Rb - rn), 7.4 * sz), (Rb, ze), (R2, ze + 0.02)]
        for a in np.linspace(0.02, math.pi / 2 - 0.2, 36):      # pearl elongated 1.4 : 1
            pts.append((R2 * math.cos(a), ze + 1.4 * R2 * math.sin(a)))
        zt = pts[-1][1]
        pts += [(0.55 * s, zt + 0.05), (0.62 * s, zt + 0.35 * s), (0.5 * s, zt + 0.75 * s), (0.0, zt + 0.95 * s)]
        return pts, dict(z_eq=ze, bead_r=rb, R2=R2)
    if variant == "eichel":
        zc0, zr = 3.6 * sz, 8.2 * sz          # cup start, cup rim
        Rc, Rn = Rb - 0.6 * s, Rb - 1.0 * s  # cup radius (+ texture) and nut radius
        pts = [(rn + 0.35, 1.0), (rn + 0.35, 2.4 * sz), (rn, 2.9 * sz), (rn, zc0),
               (rn + 0.25 * (Rc - rn), 5.2 * sz), (rn + 0.7 * (Rc - rn), 6.9 * sz), (Rc, zr - 0.2 * sz),
               (Rc + 0.45 * s, zr + 0.25 * sz), (Rc + 0.45 * s, zr + 0.55 * sz), (Rn, zr + 0.6 * sz)]
        pts += [(Rn + 0.15 * s, zr + 1.2 * sz)]
        pts += _ogive(Rn + 0.15 * s, zr + 1.2 * sz, 8.3 * sz, 0.45 * s)[1:]
        zt = pts[-1][1]
        pts += [(0.45 * s, zt + 0.5 * s), (0.62 * s, zt + 0.75 * s), (0.5 * s, zt + 1.05 * s), (0.0, zt + 1.2 * s)]
        return pts, dict(z_eq=zr + 0.4 * sz, z_cup=(zc0, zr), Rc=Rc)
    if variant == "zapfen":
        ze = 9.4 * sz
        pts = [(rn + 0.35, 1.0), (rn + 0.35, 2.4 * sz), (rn + 0.7 * s, 2.4 * sz + 0.5 * s),
               (rn + 0.7 * s, 3.1 * sz), (rn, 3.6 * sz), (rn, 4.3 * sz), (rn + 0.3 * (Rb - rn), 6.0 * sz),
               (rn + 0.75 * (Rb - 0.6 * s - rn), 7.8 * sz), (Rb - 0.6 * s, 8.8 * sz), (Rb - 0.6 * s, ze)]
        pts += _ogive(Rb - 0.6 * s, ze, 9.4 * sz, 0.5 * s)[1:]
        zt = pts[-1][1]
        pts += [(0.5 * s, zt + 0.3 * s), (0.0, zt + 0.5 * s)]
        return pts, dict(z_eq=ze, z_leaf=(4.3 * sz, 8.6 * sz))
    if variant == "krone":
        zf, zp = 10.0 * sz, 11.0 * sz         # flare end, plateau
        pts = [(rn + 0.35, 1.0), (rn + 0.35, 2.4 * sz), (rn, 2.9 * sz), (rn, 4.4 * sz),
               (rn + 0.25 * (Rb - rn), 6.3 * sz), (rn + 0.68 * (Rb - rn), 8.4 * sz), (Rb - 0.08 * s, 9.6 * sz),
               (Rb, zf), (Rb, zp), (0.0, zp + 0.01)]
        return pts, dict(z_eq=zf, z_plateau=zp)
    raise ValueError(f"unknown variant {variant!r}, choose from {VARIANTS}")


def _interp_profile(pts, zs):
    """Radius at zs from key points (z non-decreasing; equal z = step) with shape-preserving interpolation."""
    from scipy.interpolate import PchipInterpolator
    r = np.array([p[0] for p in pts], float)
    z = np.array([p[1] for p in pts], float)
    z = np.maximum.accumulate(z)
    keep = np.r_[np.diff(z) > 1e-6, True]       # steps: the later point wins (step resolved by the grid)
    return np.maximum(PchipInterpolator(z[keep], r[keep])(np.clip(zs, z[0], z[keep][-1])), 0.0)


def _texture(variant, th, zs, R0, info, s, sz):
    """Radius field (nz, nt) = base + relief for the variant."""
    T, Z = th[None, :], zs[:, None]
    R = np.repeat(R0[:, None], len(th), 1)
    if variant == "melon":          # 12 convex gadroons with sharp valleys on the dome
        n, ze = 12, info["z_eq"]
        env = _smooth01((Z - ze + 2.2 * sz) / (1.8 * sz)) * _smooth01((15.6 * sz - Z) / (3.5 * sz))
        tw = T
        psi = ((tw * n / (2 * math.pi)) % 1.0) * 2 - 1
        R = R - 0.75 * s * env * (1 - np.sqrt(np.maximum(1 - psi * psi, 0)))
    elif variant == "perle":        # pearl ring on the equator ledge + small pearls round the neck
        rb, ze = info["bead_r"], info["z_eq"]
        n = int(2 * math.pi * (6.5 * s - rb) / (2 * rb * 1.06))
        R = np.maximum(R, _beads_field(th, zs, 6.5 * s - rb, ze + 0.05, rb, n))
        rn = R0[np.searchsorted(zs, 3.4 * sz)]
        rb2 = 0.5 * s
        n2 = int(2 * math.pi * (rn + 0.2) / (2 * rb2 * 1.1))
        R = np.maximum(R, _beads_field(th, zs, rn + 0.2, 2.5 * sz + rb2 * 0.2, rb2, n2))
    elif variant == "eichel":       # cup with offset rows of bumps (acorn cup scales), polished nut
        (z0, z1), Rc = info["z_cup"], info["Rc"]
        n, row = 17, 1.15 * sz
        u = Z - z0
        k = np.floor(u / row)
        x = (T * n / (2 * math.pi) + 0.5 * (k % 2)) % 1.0 * 2 - 1
        y = (u / row) % 1.0 * 2 - 1
        bump = np.sqrt(np.maximum(1 - x * x - y * y, 0))
        env = _smooth01((Z - z0 - 0.3) / (1.0 * sz)) * (Z < z1 + 0.2 * sz) * np.clip(R0[:, None] / Rc, 0, 1)
        R = R + 0.6 * s * bump ** 0.7 * env
    elif variant == "zapfen":       # pine cone: lozenge scales in spiral rows + acanthus calyx on the flare
        ze = info["z_eq"]
        n, row = 11, 1.25 * sz
        u = (Z - info["z_leaf"][1] + 0.6) / row
        k = np.floor(u)
        x = ((T + 0.10 * u) * n / (2 * math.pi) + 0.5 * (k % 2)) % 1.0 * 2 - 1
        y = u % 1.0 * 2 - 1                       # -1 = bottom of a scale
        dia = 1 - np.abs(x) - np.abs(y) * 0.55
        rim = np.clip(1.15 - y, 0, 2) / 2         # thicker lower lip, keel along the middle
        scale = np.maximum(dia, 0) ** 0.6 * (0.55 + 0.45 * rim) + 0.25 * np.exp(-(x / 0.12) ** 2) * (dia > 0)
        env = _smooth01((Z - info["z_leaf"][1] + 0.9) / 1.0) * np.clip(R0[:, None] / (6.2 * s), 0, 1) ** 0.7
        R = R + 0.65 * s * scale * env
        za, zb = info["z_leaf"]                   # 8 acanthus tongues rising on the flare, tips up
        nl = 8
        v = (Z - za) / (zb - za)
        x = ((T * nl / (2 * math.pi)) % 1.0) * 2 - 1
        w = 0.85 * np.sin(np.pi * np.clip(v, 0, 1)) ** 0.5 * (1 + 0.15 * np.cos(6 * np.pi * v))
        leaf = np.sqrt(np.maximum(1 - (x / np.maximum(w, 1e-3)) ** 2, 0)) * (v > 0) * (v < 1)
        leaf *= (0.35 + 0.65 * np.clip(v, 0, 1)) * (1 - 0.35 * np.exp(-(x / 0.08) ** 2))
        R = R + 0.55 * s * leaf
    return R


def _rosette_field(variant, Rr, rn, s, nt, dr):
    """Polar height field of the rosette: flat plate, beaded rim, acanthus leaves, collar round the neck."""
    rs = np.r_[0.0, np.arange(dr, Rr - 1e-6, dr), Rr]
    th = np.linspace(0, 2 * math.pi, nt, endpoint=False)
    r, T = rs[:, None], th[None, :]
    tb = float(np.clip(1.25 * s, 1.2, 1.8))
    H = np.full((len(rs), nt), tb)
    H = H - 0.55 * _smooth01((r - (Rr - 0.55)) / 0.55)                       # chamfered outer edge
    rm = Rr - 0.75 * s                                                        # half-round moulding
    H = H + 0.45 * s * np.sqrt(np.maximum(1 - ((r - rm) / (0.45 * s)) ** 2, 0))
    rp, rb = Rr - 1.75 * s, max(0.5, 0.45 * s)                                # pearl ring (half beads)
    n = int(2 * math.pi * rp / (2 * rb * 1.12))
    d = 2 * math.pi / n
    rel = (T + d / 2) % d - d / 2
    dist2 = (r * np.cos(rel) - rp) ** 2 + (r * np.sin(rel)) ** 2
    H = np.maximum(H, tb + np.sqrt(np.maximum(rb * rb - dist2, 0)))
    r0, r1 = rn + 0.25, rp - rb - 0.15                                        # acanthus leaves + darts
    if r1 - r0 > 1.2:
        nl = 8
        v = (r - r0) / (r1 - r0)
        x = (T * nl / (2 * math.pi)) % 1.0 * 2 - 1                            # leaf centred at x = 0
        half = math.pi / nl * r                                                # mm per unit of x
        w = 0.42 * np.sin(np.pi * np.clip(v, 0, 1)) ** 0.6 * (1 + 0.22 * np.cos(2 * np.pi * 2.5 * v))
        lat = np.abs(x) * half / np.maximum(w * half, 1e-3)
        leaf = np.sqrt(np.maximum(1 - lat * lat, 0)) * (v > 0) * (v < 1)
        leaf *= (0.55 + 0.45 * np.clip(v, 0, 1)) * (1 - 0.4 * np.exp(-(np.abs(x) * half / 0.13) ** 2))
        xd = np.abs(np.abs(x) - 1)                                              # dart between the leaves
        wd = 0.16 * np.clip(1 - v, 0, 1) * (v > 0.25)
        dart = np.sqrt(np.maximum(1 - (xd / np.maximum(wd, 1e-3)) ** 2, 0)) * (v < 1)
        H = H + 0.6 * s * np.maximum(leaf, 0.7 * dart)
    H = np.maximum(H, tb + 0.35 * s * _smooth01((rn + 0.6 - r) / 0.4))        # collar round the neck
    return rs, H, tb


def _socket(rib_d=SOCKET_RIB_D, depth=SOCKET_DEPTH, d=SOCKET_D):
    """Cavity solid (to subtract): d hole with 4 crush ribs (tips on rib_d), 50 deg roof, 50 deg lead-in."""
    r = d / 2
    apex = depth + r * math.tan(math.radians(SOCKET_ROOF_DEG))
    hole = _revolve([(0, -1), (r, -1), (r, depth), (0, apex)], 64)
    rt = rib_d / 2
    rib = CS([[(rt, -0.22), (r + 0.3, -0.5), (r + 0.3, 0.5), (rt, 0.22)]])
    ribs = CS.batch_boolean([rib.rotate(a) for a in np.linspace(0, 360, SOCKET_RIBS, endpoint=False)
                             + 45.0], m3.OpType.Add).extrude(depth + 2).translate([0, 0, -1.5])
    lead_r0 = r + 0.3
    lead = _revolve([(0, -1), (lead_r0 + LEAD_SLOPE, -1), (lead_r0, 0), (rt - 0.05, (lead_r0 - rt + 0.05) /
                     LEAD_SLOPE), (0, (lead_r0 - rt + 0.05) / LEAD_SLOPE)], 64)
    return (hole - ribs) + lead, apex


def _socket_profile(d=SOCKET_D, depth=SOCKET_DEPTH):
    r = d / 2
    return np.array([(r + 0.3, 0.0), (r, 0.3 / LEAD_SLOPE), (r, depth),
                     (0, depth + r * math.tan(math.radians(SOCKET_ROOF_DEG)))])


def _wall_to_socket(M):
    """Smallest distance from the outer surface (vertices of the un-socketed knob, bed face excluded) to the
    axisymmetric socket cavity. Ribs only add material, so this is the wall thickness."""
    v = np.asarray(M.to_mesh().vert_properties)[:, :3]
    v = v[v[:, 2] > 0.01]
    p = np.c_[np.hypot(v[:, 0], v[:, 1]), v[:, 2]]
    P = _socket_profile()
    best = np.full(len(p), np.inf)
    for a, b in zip(P[:-1], P[1:]):
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
        best = np.minimum(best, np.linalg.norm(p - (a + t[:, None] * ab), axis=1))
    inside = (p[:, 0] < np.interp(p[:, 1], P[1:, 1], P[1:, 0], right=0)) & (p[:, 1] < P[-1, 1])
    best[inside] = 0.0
    return float(best.min())


def pin_function_test(M, door_t=1.6, engage=PIN_ENGAGE, rib_d=SOCKET_RIB_D):
    """Pin pressed fully home in the knob socket (knob bottom on the door front at z = 0): it must squeeze the
    ribs (interference volume > 0), must not touch the socket wall or roof, and must reach its full depth."""
    pin, _ = rivet_pin(door_t, engage)
    pin = pin.translate([0, 0, -(door_t + PIN_HEAD_T)])
    r = SOCKET_D / 2
    zone = m3.Manifold.cylinder(SOCKET_DEPTH + 1, r + 1e-3, r + 1e-3, 64).translate([0, 0, -0.5])
    rib_part = M ^ zone
    v_all = (M ^ pin).volume()
    v_rib = (rib_part ^ pin).volume()
    tip = pin.bounding_box()[5]
    ok = v_rib > 0.05 and abs(v_all - v_rib) < 1e-3 and tip <= SOCKET_DEPTH - 0.5 and tip >= engage - 0.31
    return dict(ok=bool(ok), interference_mm3=round(v_rib, 3), wall_contact_mm3=round(v_all - v_rib, 4),
                insert_depth_mm=round(tip, 2), socket_depth_mm=SOCKET_DEPTH)


def plug_knob(variant="olive", bulb_d=13.0, rosette_d=None, res="fine", eps=0.005, solid=False):
    """Full-size plug-in knob. Base (rosette bottom) at z = 0, printed upright without supports.
    bulb_d = largest knob diameter, rosette_d defaults to 1.25 * bulb_d (pass the space available).
    res "fine" (print) or "coarse" (tests); eps = manifold-preserving simplification tolerance in mm (0 = off,
    0.005 keeps ~70-120k triangles, i.e. < 6 MB STL per knob). Returns (Manifold, info)."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}, choose from {VARIANTS}")
    nt, dz, nt_r, dr = RES[res]
    s = bulb_d / 13.0
    sz = max(s, 0.85)                                 # the socket (7.5 + roof) sets a minimum height
    rn = max(0.25 * bulb_d, SOCKET_D / 2 + WALL_MIN + 0.25)
    Rr = (rosette_d if rosette_d else 1.25 * bulb_d) / 2
    assert Rr >= rn + 2.0, f"rosette d{2 * Rr:.1f} too small for the neck d{2 * rn:.1f}"
    pts, pinfo = _profile(variant, s, sz, rn)
    z_top = max(z for _, z in pts)
    zs = np.r_[np.arange(1.0, z_top, dz), z_top]
    th = np.linspace(0, 2 * math.pi, nt, endpoint=False)
    R0 = _interp_profile(pts, zs)
    R = _clamp(_texture(variant, th, zs, R0, pinfo, s, sz), dz)
    R[-1] = 0.0
    body = _field_body(zs, R)
    rs, H, tb = _rosette_field(variant, Rr, rn, s, nt_r, dr)
    M = body + _field_polar(rs, H)
    if variant == "krone":
        M = M + _crown(pinfo["z_plateau"], 6.5 * s, s)
    if variant == "olive":                            # small pearl collar on the neck ring
        rb = max(0.45, 0.4 * s)
        zc = 2.3 * sz + 0.45 * s + 0.12
        n = int(2 * math.pi * (rn + 0.75 * s) / (2 * rb * 1.15))
        M = M + m3.Manifold.batch_boolean(
            [drop_bead(rb, 20).translate([(rn + 0.62 * s) * math.cos(a), (rn + 0.62 * s) * math.sin(a), zc])
             for a in np.linspace(0, 2 * math.pi, n, endpoint=False)], m3.OpType.Add)
    wall = _wall_to_socket(M)
    cav, apex = _socket()
    if not solid:                                     # solid=True: no socket, knob fused onto the door
        M = M - cav
    if eps > 0:
        M = M.simplify(eps)
    # analytic overhang of the body field: worst |n_z| over the grid
    Rz = np.diff(R, axis=0) / dz
    Rt = (np.roll(R, -1, 1) - R)[:-1] / (2 * math.pi / nt)
    eff = Rz / np.sqrt(1 + (Rt / np.maximum(R[:-1], 1e-6)) ** 2)
    worst = float(eff.max())
    zr_top = float(H.max())
    z_eq = pinfo["z_eq"]
    info = dict(variant=variant, bulb_d_mm=round(float(2 * R.max()), 2), bulb_d_nominal_mm=bulb_d,
                rosette_d_mm=round(2 * Rr, 2), rosette_top_mm=round(zr_top, 2),
                projection_mm=round(M.bounding_box()[5], 2), neck_d_mm=round(2 * rn, 2),
                finger_gap_mm=round(z_eq - zr_top, 2),
                body_underside_min_deg=round(math.degrees(math.atan2(1.0, max(worst, 1e-9))), 1),
                socket=dict(d=SOCKET_D, rib_tip_d=SOCKET_RIB_D, ribs=SOCKET_RIBS, depth=SOCKET_DEPTH,
                            roof_deg=SOCKET_ROOF_DEG, apex_mm=round(apex, 2)),
                socket_wall_min_mm=round(wall, 2))
    assert wall >= WALL_MIN, f"{variant}: socket wall {wall:.2f} < {WALL_MIN} mm"
    assert info["body_underside_min_deg"] >= 45
    if solid:
        info["socket"] = None
        return M, info
    info["function_test"] = pin_function_test(M)
    assert info["function_test"]["ok"], info["function_test"]
    return M, info


def _crown(zp, Rb, s):
    """Crown ring on the plateau rim: 5 tall + 5 short points (concave flanks) with pearl drops, centre boss."""
    t = 1.3                                            # radial band thickness (>= 3 lines)
    Ro, Ri = Rb, Rb - t
    z_v, h_tall, h_short = zp + 0.7 * s, 3.0 * s, 1.9 * s
    nt = 360
    th = np.linspace(0, 2 * math.pi, nt, endpoint=False)
    n = 10
    psi = ((th * n / (2 * math.pi)) % 1.0) * 2 - 1    # -1..1 across one point
    k = np.floor(th * n / (2 * math.pi)).astype(int)
    h = np.where(k % 2 == 0, h_tall, h_short)
    prof = np.clip(1 - np.abs(psi), 0, 1) ** 1.8
    f = z_v + h * prof
    rs = np.array([0.0, Ri - 0.5, Ri - 0.01, Ro])
    Hc = np.repeat(f[None], len(rs), 0)
    band = (_revolve([(Ri, zp - 0.3), (Ro, zp - 0.3), (Ro, zp + 6 * s), (Ri, zp + 6 * s)], nt)
            ^ _field_polar(rs, Hc, zp - 0.5))
    parts = [band]
    rc = (Ro + Ri) / 2
    for i in range(n):
        a = (i + 0.5) * 2 * math.pi / n
        hh = h_tall if i % 2 == 0 else h_short
        rb = 0.62 if i % 2 == 0 else 0.5
        parts.append(drop_bead(rb, 24).translate([rc * math.cos(a), rc * math.sin(a), z_v + hh - 0.25]))
    # centre boss: fluted dome with pearl, ring of 8 petals on the plateau
    rboss = 0.42 * Rb
    boss = [(0.0, zp - 0.2), (rboss, zp - 0.2), (rboss, zp + 0.3 * s)] + [
        (rboss * math.cos(a), zp + 0.3 * s + 1.6 * s * math.sin(a)) for a in np.linspace(0.05, math.pi / 2, 16)]
    parts.append(_revolve(boss, 96))
    parts.append(drop_bead(0.75 * s, 32).translate([0, 0, zp + 1.9 * s - 0.6 * s]))
    rr = np.r_[0.0, np.linspace(0.3, Ri - 0.05, 60)]
    T = th[None, :]
    x = ((T * 8 / (2 * math.pi)) % 1.0) * 2 - 1
    v = (rr[:, None] - rboss) / (Ri - 0.2 - rboss)
    w = 0.5 * np.sin(np.pi * np.clip(v, 0, 1)) ** 0.6
    pet = np.sqrt(np.maximum(1 - (x / np.maximum(w, 1e-3)) ** 2, 0)) * (v > 0) * (v < 1)
    parts.append(_field_polar(rr, zp + 0.5 * s * pet * (0.4 + 0.6 * (1 - np.clip(v, 0, 1))) - 0.0, zp - 0.3))
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add)


def rivet_pin(door_t, engage=PIN_ENGAGE):
    """Steckstift, printed upright head down: head d6.5 x 1.0 (0.3 top chamfer), shaft d3.0 of door_t + engage
    - 0.3 with 0.4 tip chamfer. Returns (Manifold, info)."""
    rh, r = PIN_HEAD_D / 2, PIN_D / 2
    L = door_t + engage - 0.3
    top = PIN_HEAD_T + L
    pts = [(0, 0), (rh, 0), (rh, PIN_HEAD_T - 0.3), (rh - 0.3, PIN_HEAD_T), (r, PIN_HEAD_T), (r, top - PIN_TIP),
           (r - PIN_TIP, top), (0, top)]
    M = _revolve(pts, 64)
    return M, dict(door_t_mm=door_t, shaft_len_mm=round(L, 2), engagement_mm=round(engage - 0.3, 2),
                   total_len_mm=round(top, 2), head_d_mm=PIN_HEAD_D, shaft_d_mm=PIN_D, hole_d_mm=HOLE_D)


def _dots(n, x, y, z, r=0.45):
    return [m3.Manifold.sphere(r, 16).translate([x + (i - (n - 1) / 2) * 1.3, y, z]) for i in range(n)]


def fit_coupon(door_t=1.6):
    """Prüfstück: 1.6 mm plate with door holes d3.3/3.4/3.5, three socket stubs with rib tips d2.7/2.8/2.9 and
    three pins for door_t, marked with 1/2/3 dots (half spheres on the plate top). ONE Manifold with 4 bodies
    (plate+stubs, 3 loose pins). Returns (Manifold, info)."""
    T = 1.6
    plate = m3.Manifold.cube([42, 26, T])
    holes, stubs, dots = [], [], []
    sizes_h, sizes_r = (3.3, 3.4, 3.5), (2.7, 2.8, 2.9)
    so = SOCKET_D / 2 + WALL_MIN + 0.4
    for i in range(3):
        x = 8 + 13 * i
        holes.append(m3.Manifold.cylinder(T + 2, sizes_h[i] / 2, sizes_h[i] / 2, 48).translate([x, 6, -1]))
        stubs.append(m3.Manifold.cylinder(SOCKET_DEPTH + 3.2, so, so, 64).translate([x, 18, 0]))
        dots += _dots(i + 1, x, 1.6, T) + _dots(i + 1, x, 24.4, T)
    C = plate - m3.Manifold.batch_boolean(holes, m3.OpType.Add) + m3.Manifold.batch_boolean(stubs, m3.OpType.Add)
    C = C + m3.Manifold.batch_boolean(dots, m3.OpType.Add) ^ m3.Manifold.cube([200, 200, 50]).translate([-50, -50, 0])
    for i in range(3):
        cav, _ = _socket(rib_d=sizes_r[i])
        C = C - cav.translate([8 + 13 * i, 18, 0])
    pins = []
    for i in range(3):
        p, pinfo = rivet_pin(door_t)
        pins.append(p.translate([8 + 13 * i, -7, 0]))
    M = C + m3.Manifold.batch_boolean(pins, m3.OpType.Add)
    return M, dict(bodies=4, plate_t_mm=T, holes_d_mm=list(sizes_h), rib_tip_d_mm=list(sizes_r), pin=pinfo,
                   marking="1/2/3 dots = small/nominal/large; nominal: hole 3.4, rib tips 2.8")


def knob_set_plate(variants, sizes, door_t=None, rosette_d=None, gap=4.0, bed=170.0, res="fine"):
    """Knobs (and, with door_t, one pin per knob) laid out in rows within bed x bed mm.
    sizes: one bulb_d for all, or one per variant. Returns list of (name, Manifold) in plate coordinates."""
    sizes = [sizes] * len(variants) if np.isscalar(sizes) else list(sizes)
    if len(sizes) == 1:
        sizes = sizes * len(variants)
    assert len(sizes) == len(variants)
    items = []
    for v, d in zip(variants, sizes):
        M, info = plug_knob(v, d, rosette_d, res=res)
        items.append((f"knauf_{v}_{d:g}", M, info["rosette_d_mm"]))
        if door_t is not None:
            P, _ = rivet_pin(door_t)
            items.append((f"stift_{v}_{d:g}_t{door_t:g}", P, PIN_HEAD_D))
    out, x, y, row_h = [], 0.0, 0.0, 0.0
    for name, M, w in items:
        if x + w > bed:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        out.append((name, M.translate([x + w / 2, y + w / 2, 0])))
        x, row_h = x + w + gap, max(row_h, w)
    assert y + row_h <= bed, f"set does not fit on {bed:g} x {bed:g} mm"
    return out
