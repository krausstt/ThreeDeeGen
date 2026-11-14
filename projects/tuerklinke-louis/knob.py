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
