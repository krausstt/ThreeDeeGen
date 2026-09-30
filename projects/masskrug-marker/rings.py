"""
Clip with an integrated charm: two interlocking wedding rings.

Both rings stand upright on the bed (ring planes vertical, i.e. containing the print Z axis), so they print
without supports: their bottoms are flattened 0.3 mm into the bed, the inner top of each ring is a round
arch (self supporting at these sizes). Ring A ("his", larger) stands perpendicular to the badge and is fused
into it; ring B ("hers", smaller) stands parallel to the badge and is threaded through A.

Linking: A lies in the plane x = xa, B in the plane y = yb. Along their common vertical line the two
crossing heights of each ring must interleave; `link_check` verifies that numerically.

Only a fused variant exists: B touches A at the crossing (one rigid body). A print-in-place loose ring is
geometrically impossible here: with both rings standing on the bed their crossings are too close; the best
linked placement reaches 0.78 mm centre-line distance for 1.4 mm thick bands (a free ring would need
supports inside the other ring).

Ring B carries a small brilliant (45 deg pavilion, flat table) on top.
"""
from __future__ import annotations

import math

import numpy as np
import manifold3d as m3

SEG = 128


def band_profile(r_mean, width, thick, n=2.6):
    """Superellipse ring cross-section (comfort-fit look), centred at radius r_mean."""
    t = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    x = r_mean + thick / 2 * np.sign(c) * np.abs(c) ** (2 / n)
    y = width / 2 * np.sign(s) * np.abs(s) ** (2 / n)
    return m3.CrossSection([np.c_[x, y].tolist()])


def band(r_mean, width, thick):
    """Ring with axis along Z (revolve), lying in the XY plane."""
    return band_profile(r_mean, width, thick).revolve(SEG)


def ring_points(center, r, plane, n=720):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c = np.asarray(center, float)
    if plane == "yz":
        return np.c_[np.full(n, c[0]), c[1] + r * np.cos(t), c[2] + r * np.sin(t)]
    return np.c_[c[0] + r * np.cos(t), np.full(n, c[1]), c[2] + r * np.sin(t)]


def link_check(ca, ra, cb, rb):
    """A in plane x = ca.x (YZ), B in plane y = cb.y (XZ). Linked iff their crossings on the common
    vertical line (x = ca.x, y = cb.y) interleave."""
    dy = cb[1] - ca[1]
    dx = ca[0] - cb[0]
    if abs(dy) >= ra or abs(dx) >= rb:
        return False
    sa = math.sqrt(ra**2 - dy**2)
    sb = math.sqrt(rb**2 - dx**2)
    a = sorted([ca[2] - sa, ca[2] + sa])
    b = sorted([cb[2] - sb, cb[2] + sb])
    inside = [a[0] < z < a[1] for z in b]
    return inside[0] != inside[1]


def build_rings(y_face, clip_w, variant="fused", Ra=5.6, Rb=4.5, wa=2.4, ta=1.5, wb=2.1, tb=1.3,
                sink=0.3, overlap=0.3, gap=0.5, gem=True, yaw=35.0, embed=1.1):
    """Return (rings manifold in clip coordinates, info). Clip frame: badge normal +Y, z = along handle (bed)."""
    Ra_out, Rb_out = Ra + ta / 2, Rb + tb / 2
    ca = np.array([-1.3, y_face + Ra_out - 1.1, Ra_out - sink])        # A cuts 1.1 mm into the badge
    zb = Rb_out - sink
    # B: plane y = yb, centre x = xb. Search the placement whose closest centre-line distance hits the
    # target (touching with overlap, or clear by `gap`) while staying linked.
    target = (ta + tb) / 2 - overlap if variant == "fused" else (ta + tb) / 2 + gap
    pa = ring_points(ca, Ra, "yz")
    best = None
    for yb in np.linspace(ca[1] + 0.6, ca[1] + Ra - 0.8, 25):
        for xb in np.linspace(ca[0] + 0.5, ca[0] + Rb - 0.3, 40):
            cb = np.array([xb, yb, zb])
            if not link_check(ca, Ra, cb, Rb):
                continue
            pb = ring_points(cb, Rb, "xz", 360)
            dmin = np.min(np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=-1))
            score = abs(dmin - target) + 0.02 * abs(yb - (ca[1] + 0.5 * Ra))
            if best is None or score < best[0]:
                best = (score, cb, dmin)
    assert best is not None, "no linked placement found"
    _, cb, dmin = best
    A = band(Ra, wa, ta).rotate([0, 90, 0]).translate(list(ca))             # axis X -> plane YZ
    B = band(Rb, wb, tb).rotate([90, 0, 0]).translate(list(cb))             # axis Y -> plane XZ
    bed = m3.Manifold.cube([200, 200, 200], True).translate([0, 0, 100])
    A, B = A ^ bed, B ^ bed
    if gem:
        top = cb + np.array([0, 0, Rb + tb / 2 - 0.25])
        pav = m3.Manifold.cylinder(1.0, 0.25, 1.25, 8).translate(list(top))            # 45 deg pavilion
        crown = m3.Manifold.cylinder(0.55, 1.25, 0.75, 8).translate(list(top + [0, 0, 1.0]))
        B = B + pav + crown
    # turn the pair about the vertical axis so both rings show from the front, then re-seat A in the badge
    if yaw:
        piv = [ca[0], ca[1], 0]
        A = A.translate([-piv[0], -piv[1], 0]).rotate([0, 0, yaw]).translate(piv)
        B = B.translate([-piv[0], -piv[1], 0]).rotate([0, 0, yaw]).translate(piv)
        dy = (y_face - embed) - A.bounding_box()[1]
        A, B = A.translate([0, dy, 0]), B.translate([0, dy, 0])
    info = dict(variant=variant, yaw_deg=yaw,
                ring_a=dict(center=np.round(ca, 2).tolist(), r_mean=Ra, width=wa, thick=ta),
                ring_b=dict(center=np.round(cb, 2).tolist(), r_mean=Rb, width=wb, thick=tb),
                linked=bool(link_check(ca, Ra, cb, Rb)), centreline_min_dist_mm=round(float(dmin), 2),
                target_mm=round(target, 2), overlap_mm3=round((A ^ B).volume(), 3),
                height_mm=round(float(max(A.bounding_box()[5], B.bounding_box()[5])), 2),
                inner_arch_a_mm=round(2 * (Ra - ta / 2), 2), inner_arch_b_mm=round(2 * (Rb - tb / 2), 2))
    return A, B, info
