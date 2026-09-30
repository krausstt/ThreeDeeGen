"""
Clip with integrated wedding rings as a RELIEF (v2).

v1 (two upright 3D rings, fused) failed in practice: thin free-standing arches on a 12 mm clip are fragile and
hard to print. v2 is 2.5D: two overlapping ring bands in the badge plane, raised as a relief with tapered
(>= 50 deg) flanks, fused over their full footprint into the badge. The interlock is shown graphically by
over/under crossings: at the upper crossing A runs over B, at the lower crossing B runs over A (the band
underneath is interrupted by a small gap), so the pair reads as linked. Ring B carries a small stone on top.

Local frame of the relief: (u, v) in the badge plane, h = height above the badge face.
"""
from __future__ import annotations

import math

import numpy as np
import manifold3d as m3

SEG = 128


def ring_band(c, r, w):
    outer = m3.CrossSection.circle(r + w / 2, SEG).translate(list(c))
    inner = m3.CrossSection.circle(r - w / 2, SEG).translate(list(c))
    return outer - inner


def rings2d(R=2.95, d=1.85, w=2.2, gap=0.45, stone=0.75):
    """Two linked ring bands (centres +-d on u) with over/under crossing gaps + a stone on ring B."""
    ca, cb = np.array([-d, 0.0]), np.array([d, 0.0])
    A, B = ring_band(ca, R, w), ring_band(cb, R, w)
    zc = math.sqrt(R**2 - d**2)                              # crossings at (0, +-zc)
    win = 1.25 * w
    top = m3.CrossSection.circle(win, 48).translate([0, zc])
    bot = m3.CrossSection.circle(win, 48).translate([0, -zc])
    A_cut = A - (B.offset(gap, m3.JoinType.Round) ^ bot)     # lower crossing: B over A
    B_cut = B - (A.offset(gap, m3.JoinType.Round) ^ top)     # upper crossing: A over B
    gem = m3.CrossSection.square([stone * 2] * 2, True).rotate(45).translate([cb[0], R + w / 2 + stone * 0.55])
    bands = A_cut + B_cut + gem
    info = dict(ring_r_mm=R, band_w_mm=w, centre_dist_mm=2 * d, crossing_gap_mm=gap,
                span_u_mm=round(2 * (d + R + w / 2), 2), span_v_mm=round(2 * (R + w / 2) + stone * 1.3, 2))
    return bands, info


def relief(cs, h=1.1, flank_deg=50.0, embed=0.3, dz=0.05, soften=0.08):
    """2.5D relief printed SIDEWAYS: the badge is vertical, h grows along +Y, v is the print Z axis.
    Downward-facing edges (-v) would be ceilings, so each layer at height t is cs intersected with cs shifted
    up by t / tan(flank_deg): every downward flank then rises at flank_deg to the horizontal, upward and
    side flanks stay near vertical (self supporting). The embedded part (below the badge face) is prismatic."""
    parts = []
    k_tan = 1 / math.tan(math.radians(flank_deg))
    n = int(round((h + embed) / dz))
    prev = cs
    for k in range(n):
        t = max((k + 0.5) * dz - embed, 0.0)
        # cumulative intersection keeps every layer inside the one below (no floating islands)
        layer = prev ^ cs.translate([0, t * k_tan]).offset(-soften * t / h, m3.JoinType.Round)
        layer = m3.CrossSection.compose([c for c in layer.decompose() if c.area() > 0.25])
        if layer.is_empty():
            break
        prev = layer
        parts.append(layer.extrude(dz * 1.5).translate([0, 0, k * dz - embed]))   # overlap -> fused layers
    clip = m3.Manifold.cube([99, 99, h + embed]).translate([-49.5, -49.5, -embed])     # trim the 1.5x overlap
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add) ^ clip


def on_badge(M_uvh, y_face, clip_w):
    """(u, v, h) -> clip (x = -u, y = y_face + h, z = clip_w/2 + v); det = +1."""
    return M_uvh.transform([[-1, 0, 0, 0], [0, 0, 1, y_face], [0, 1, 0, clip_w / 2]])


def build_rings(y_face, clip_w, h=1.1, flank_deg=50.0, embed=0.3, **kw):
    """Return (relief manifold in clip coordinates, info)."""
    cs, info = rings2d(**kw)
    M = relief(cs, h, flank_deg, embed)
    shift = h / math.tan(math.radians(flank_deg))
    info.update(relief_h_mm=h, flank_deg_to_horizontal=flank_deg,
                top_band_w_min_mm=round(info["band_w_mm"] - shift - 0.16, 2))  # band bottom, where it is horizontal
    return on_badge(M, y_face, clip_w), info
