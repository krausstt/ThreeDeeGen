"""
Ring clip with text engraved around its outer surface (variant 3).

The ring is the plain C-profile (no badge). Text is set flat in (u, v) with the stroke font, u = arc length
along the OUTER contour of the ring, v = height along the handle, then wrapped onto the curved surface:
every vertex (u, v, d) is moved to  P(u) + d * N(u),  z = v  (P = outer contour point, N = outward normal).
u grows counter-clockwise seen from +z, i.e. left-to-right for a reader outside the ring, so the text reads
correctly without mirroring.

The text is centred on the flat outer face of the handle loop (+Y) and slides round towards the far side
(-X) when it is too long; it never runs into the snap lips.
"""
from __future__ import annotations

import math

import numpy as np

import icons

# additional glyphs on the same 3 x 5 grid (x 0..2, y 0..4); WIDTH = grid width if not 2
GLYPHS_EXTRA = {
    "B": [[(0, 0), (0, 4), (1.4, 4), (2, 3.4), (2, 2.6), (1.4, 2), (0, 2)], [(1.4, 2), (2, 1.4), (2, 0.6), (1.4, 0),
                                                                          (0, 0)]],
    "E": [[(2, 4), (0, 4), (0, 0), (2, 0)], [(0, 2), (1.5, 2)]],
    "F": [[(2, 4), (0, 4), (0, 0)], [(0, 2), (1.5, 2)]],
    "H": [[(0, 0), (0, 4)], [(2, 0), (2, 4)], [(0, 2), (2, 2)]],
    "I": [[(0, 0), (0, 4)]],
    "K": [[(0, 0), (0, 4)], [(2, 4), (0, 1.8)], [(0.8, 2.7), (2, 0)]],
    "N": [[(0, 0), (0, 4), (2, 0), (2, 4)]],
    "O": [[(0.6, 0), (1.4, 0), (2, 0.6), (2, 3.4), (1.4, 4), (0.6, 4), (0, 3.4), (0, 0.6), (0.6, 0)]],
    "S": [[(2, 3.4), (1.4, 4), (0.6, 4), (0, 3.4), (0, 2.6), (0.6, 2), (1.4, 2), (2, 1.4), (2, 0.6), (1.4, 0),
           (0.6, 0), (0, 0.6)]],
    "T": [[(0, 4), (2, 4)], [(1, 4), (1, 0)]],
    "V": [[(0, 4), (1, 0), (2, 4)]],
    "W": [[(0, 4), (0.7, 0), (1.5, 2.6), (2.3, 0), (3, 4)]],
    "Z": [[(0, 4), (2, 4), (0, 0), (2, 0)]],
    "D": [[(0, 0), (0, 4), (1.2, 4), (2, 3.2), (2, 0.8), (1.2, 0), (0, 0)]],
    "G": [[(2, 3.4), (1.4, 4), (0.6, 4), (0, 3.4), (0, 0.6), (0.6, 0), (1.4, 0), (2, 0.6), (2, 1.8), (1.1, 1.8)]],
    "J": [[(2, 4), (2, 0.6), (1.4, 0), (0.6, 0), (0, 0.6)]],
    "L": [[(0, 4), (0, 0), (2, 0)]],
    "Q": [[(0.6, 0), (1.4, 0), (2, 0.6), (2, 3.4), (1.4, 4), (0.6, 4), (0, 3.4), (0, 0.6), (0.6, 0)],
          [(1.2, 0.9), (2.1, -0.1)]],
    "X": [[(0, 0), (2, 4)], [(0, 4), (2, 0)]],
    "Y": [[(0, 4), (1, 2), (2, 4)], [(1, 2), (1, 0)]],
    "2": [[(0, 3.4), (0.6, 4), (1.4, 4), (2, 3.4), (2, 2.6), (0, 0), (2, 0)]],
    "3": [[(0, 4), (2, 4), (1, 2.4), (1.4, 2.4), (2, 1.8), (2, 0.6), (1.4, 0), (0, 0)]],
    "4": [[(1.6, 0), (1.6, 4), (0, 1.2), (2, 1.2)]],
    "'": [[(0, 4), (0, 3)]],
    "-": [[(0, 2), (1.6, 2)]],
    " ": [],
}
WIDTH = {"I": 0, "'": 0, " ": 1.0, "W": 3, "-": 1.6}
GLYPHS = {**icons.GLYPHS, **GLYPHS_EXTRA}


def text2d(s, cap_h, w=0.9, gap_frac=0.55):
    """Stroke text with cap height cap_h (incl. stroke). Returns (CrossSection, length, scale)."""
    s = s.upper()
    sc = (cap_h - w) / 4
    gap = max(gap_frac * sc, 0.75)
    x = 0.0
    parts = []
    for ch in s:
        if ch not in GLYPHS:
            raise ValueError(f"no glyph for {ch!r}; available: {''.join(sorted(GLYPHS))}")
        for line in GLYPHS[ch]:
            parts.append(icons.stroke([(x + gx * sc, gy * sc) for gx, gy in line], w))
        x += WIDTH.get(ch, 2) * sc + w + gap
    t = icons.union(*parts)
    b = t.bounds()
    return t.translate([-b[0], -b[1]]), b[2] - b[0], sc


# ------------------------------------------------------------------ outer contour of the ring
def outer_contour(ai, bi, t, n=4000):
    """Offset of the inner ellipse by t: points, outward normals, cumulative arc length (CCW from +X)."""
    th = np.linspace(0, 2 * np.pi, n + 1)
    p = np.c_[ai * np.cos(th), bi * np.sin(th)]
    nrm = np.c_[bi * np.cos(th), ai * np.sin(th)]
    nrm /= np.linalg.norm(nrm, axis=1)[:, None]
    q = p + t * nrm
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))])
    return q, nrm, s, th


def text_ring_cut(ai, bi, band_t, gap, clip_w, text, cap_h=6.5, depth=0.7, w=0.9, margin=2.2, min_cap=4.2,
                  bottom_c=0.4, top_r=0.8):
    """Engraving tool body for `text` on the ring's outer surface + layout info."""
    q, nrm, s, th = outer_contour(ai, bi, band_t)
    L_tot = s[-1]
    # usable arc: from the upper lip (just above the gap, small theta) CCW to the lower lip
    lip = np.nonzero((q[:, 0] > 0) & (np.abs(q[:, 1]) < gap / 2 + 1.0))[0]      # gap + lip rounding
    upper = lip[lip < len(q) // 2].max()
    lower = lip[lip > len(q) // 2].min()
    u0, u1 = s[upper] + margin, s[lower] - margin
    usable_h = clip_w - bottom_c - top_r - 0.6
    cap = min(cap_h, usable_h - 2.0)                         # >= 1 mm solid rim above and below
    while True:
        cs, L, sc = text2d(text, cap, w)
        if L <= u1 - u0 or cap <= min_cap:
            break
        cap = max(cap - 0.2, min_cap)
    if L > u1 - u0:
        raise ValueError(f"'{text}' is {L:.1f} mm long, only {u1 - u0:.1f} mm of ring surface available")
    apex = np.interp(math.pi / 2, th, s)                     # outer face of the loop (+Y)
    uc = min(max(apex, u0 + L / 2), u1 - L / 2)
    z0 = bottom_c + (usable_h - cap) / 2 + 0.3
    tool = cs.translate([uc - L / 2, z0]).extrude(depth + 0.4).translate([0, 0, -depth])   # (u, v, d)
    tool = tool.refine_to_length(0.35)

    def wrap(verts):
        u, v, dd = verts[:, 0], verts[:, 1], verts[:, 2]
        px, py = np.interp(u, s, q[:, 0]), np.interp(u, s, q[:, 1])
        nx, ny = np.interp(u, s, nrm[:, 0]), np.interp(u, s, nrm[:, 1])
        return np.c_[px + dd * nx, py + dd * ny, v]

    tool = tool.warp_batch(lambda v: wrap(np.asarray(v)))
    arc_deg = (np.interp(uc + L / 2, s, th) - np.interp(uc - L / 2, s, th)) * 180 / math.pi
    info = dict(text=text, cap_height_mm=round(cap, 2), stroke_mm=w, depth_mm=depth, length_mm=round(L, 1),
                usable_arc_mm=round(u1 - u0, 1), ring_perimeter_mm=round(L_tot, 1), wrap_deg=round(float(arc_deg), 1),
                centred_on_outer_face=bool(abs(uc - apex) < 1e-6))
    return tool, info, cs


def slug(text):
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_").replace("__", "_")
