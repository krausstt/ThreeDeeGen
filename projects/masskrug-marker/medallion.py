"""
"Münchner Bier" medallion clip (after the user's photo, own simplified drawing, not the original logo).

A round plate (Ø 20 mm) with a ribbon banner, fused onto the badge of a 12 mm clip, like the flat medallion
on the handle in the photo. Printed like every clip: lying, z = along the handle, the plate stands upright on
its lower edge; the bottom of the circle is hulled to the bed with 45 deg flanks (no overhang).

Front (+Y): raised relief (rings.relief, downward flanks 50 deg in print direction): rim, banner, a drinker
with a Maß. The banner text "MÜNCHNER BIER" and "MÜNCHEN" below it are ENGRAVED (0.5 mm), because raised
strokes this thin would lose their lower flanks to the 50 deg shear.

Local frame (u, v): u = right as seen from the front, v = print z (v = 0 on the bed).
"""
from __future__ import annotations

import math

import manifold3d as m3

import icons as I
import rings
from tdg import font as tfont

CS = m3.CrossSection
CAP1, CAP2 = 2.2, 2.0                    # cap heights (mm) of banner text / city line


def to_bed_hull(disc, zc, R):
    """Circle standing on the bed: hull with the chord where its 45 deg tangents meet z = 0."""
    x = R * math.cos(math.pi / 4) - (zc - R * math.sin(math.pi / 4))
    return CS.batch_hull([disc, CS.square([2 * x, 0.01], True).translate([0, 0.005])])


def banner(zc, R, y_b, y_t, u_end):
    """Ribbon across the disc; ends outside the disc get a 45 deg underside (rises towards the tip)."""
    u_d = math.sqrt(R**2 - (y_b - zc) ** 2)                  # where the lower banner edge leaves the disc
    tip_b = y_b + (u_end - u_d)                              # 45 deg
    notch = 0.9                                              # swallow tail
    pts = [(-u_end, y_t), (-u_end + notch, (y_t + tip_b) / 2), (-u_end, tip_b), (-u_d, y_b), (u_d, y_b),
           (u_end, tip_b), (u_end - notch, (y_t + tip_b) / 2), (u_end, y_t)]
    return I.poly(pts), tip_b


def drinker(zc, s=1.0):
    """Stick figure behind the banner, raising a Maß to its mouth (strokes >= 1.1 mm, gaps >= 0.7 mm)."""
    hu, hv = -1.9, zc + 4.6
    head = I.circ(1.55 * s, hu, hv)
    torso = I.poly([(-4.4, zc + 0.3), (0.6, zc + 0.3), (0.0, zc + 2.4), (-3.8, zc + 2.4)]).offset(
        0.35, m3.JoinType.Round)
    neck = I.box(hu - 0.55, hu + 0.55, zc + 2.2, hv - 1.2)
    mug = I.beer().scale([0.6, 0.6]).rotate(-18).translate([2.9, zc + 4.5])      # handle hole 0.72 x 0.84 mm
    arm = I.stroke([(-0.2, zc + 2.1), (2.0, zc + 2.5), (2.1, zc + 3.4)], 1.15)          # hand holds the mug
    other = I.stroke([(-3.9, zc + 2.1), (-5.2, zc + 3.6), (-5.0, zc + 5.4)], 1.15)     # waving arm
    fig = I.union(head, torso, neck, other) - mug.offset(0.7, m3.JoinType.Round)
    return I.union(fig, arm, mug)


def text_cs(s, font, cap, u_c, v_b, bold=0.12):
    """Engraving outline, emboldened by `bold` so the grooves are >= 0.4 mm (nozzle) wide."""
    cs, L = tfont.text_outline(s, font, cap)
    cs = cs.offset(bold, m3.JoinType.Round)
    b = cs.bounds()
    return cs.translate([u_c - (b[0] + b[2]) / 2, v_b - b[1]]), b[2] - b[0]


def medallion(R=10.0, zc=8.2, t=1.6, h=0.6, engrave=0.5, embed=0.6, flank_deg=50.0):
    """Returns (manifold in (u, h, v) local frame -> use place(); info). Plate back at h = -embed."""
    disc = I.circ(R, 0, zc, seg=160)
    y_b, y_t = zc - 3.6, zc + 0.35
    band, tip_b = banner(zc, R, y_b, y_t, u_end=R + 2.6)
    outline = to_bed_hull(disc, zc, R) + band
    outline = outline ^ I.box(-50, 50, 0, 50)
    plate = outline.extrude(t + embed).translate([0, 0, -embed])
    rim = disc - I.circ(R - 1.4, 0, zc, seg=160)
    fig = drinker(zc) ^ I.circ(R - 1.9, 0, zc, seg=160)
    raised = I.union(rim - band.offset(0.8, m3.JoinType.Round), band, fig) ^ outline
    M = plate + rings.relief(raised, h, flank_deg, embed=0.2).translate([0, 0, t])
    # engraved text
    t1, L1 = text_cs("MÜNCHNER BIER", "bigshoulders", CAP1, 0, y_b + 0.6)
    t2, L2 = text_cs("MÜNCHEN", "bigshoulders", CAP2, 0, zc - 6.9)
    face = t + h
    for tc, top in ((t1, face), (t2, t)):
        M -= tc.extrude(engrave + 1).translate([0, 0, top - engrave])
    info = dict(diameter_mm=2 * R, width_with_banner_mm=round(2 * (R + 2.6), 1), plate_t_mm=t, relief_h_mm=h,
                engrave_mm=engrave, banner_text_cap_mm=CAP1, banner_text_len_mm=round(L1, 1),
                city_text_cap_mm=CAP2, flank_deg_to_horizontal=flank_deg, banner_tip_h_mm=round(y_t - tip_b, 2),
                groove_loss_pct_at_0_4mm=round(100 * (t1 - t1.offset(-0.2, m3.JoinType.Round).offset(
                    0.2, m3.JoinType.Round)).area() / t1.area(), 1))
    return M, info


def place(M, y_face, embed=0.0):
    """(u, v, h) -> clip (x = -u, y = y_face + h, z = v); det = +1."""
    return M.transform([[-1, 0, 0, 0], [0, 0, 1, y_face - embed], [0, 1, 0, 0]])
