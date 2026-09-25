"""
Charm system for the Maßkrug clip + the 3D plug.

Mechanism
---------
The clip badge carries a dovetail RAIL running along the handle (clip Z),
with a STOP block at the bed end and a small DETENT ramp at the far end.
A charm has a matching dovetail GROOVE in its underside. It slides onto the
rail until it hits the stop; the ramp keeps it from sliding back off when the
mug is tilted for drinking.

Print orientation
-----------------
* Clip: as before (rail + stop are vertical prisms -> no overhang).
* Charm: base underside on the bed. Groove mouth on the bed, flanks lean
  outward at ~63 deg to horizontal (self supporting), groove ceiling is a
  ~5 mm bridge. Figures on top are designed to be printed standing:
  every overhang of the plug bulb is kept <= 45 deg.

Charm-local frame: X = across the rail, Y = along the slide, Z = up (away
from the badge). mount_on_clip() maps it onto the clip.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import manifold3d as m3

SEG = 96


@dataclass
class Rail:
    root_w: float = 3.0      # dovetail width at the badge face
    top_w: float = 4.6       # dovetail width at the top (undercut 0.8 per side)
    h: float = 1.6           # height above the badge face
    embed: float = 0.3       # sunk into the badge for a solid bond
    stop_len: float = 1.6    # stop block length along the slide (from the bed)
    stop_w: float = 7.0
    bump_h: float = 0.35     # detent ramp height on the rail top
    bump_len: float = 1.8    # ramp length (rise + fall)
    clear: float = 0.2       # groove clearance per side (PETG)


def groove_len(clip_w, r: Rail):
    """Charm base length that fits between stop and detent ramp."""
    return clip_w - 0.3 - r.bump_len - r.stop_len


# ------------------------------------------------------------------ clip side
def rail_on_clip(y_face, clip_w, r: Rail = Rail()):
    """Rail + stop + detent in clip coordinates (x across, y out of badge, z along handle)."""
    y0, y1 = y_face - r.embed, y_face + r.h
    prof = m3.CrossSection([[(-r.root_w / 2, y0), (r.root_w / 2, y0), (r.top_w / 2, y1), (-r.top_w / 2, y1)]])
    z1 = clip_w - 0.3
    rail = prof.extrude(z1)
    stop = m3.CrossSection.square([r.stop_w, y1 - y0]).translate([-r.stop_w / 2, y0]).extrude(r.stop_len)
    # detent ramp on the rail top: triangle in the (y, z) plane, extruded across the rail top width
    zb0, zb1 = z1 - r.bump_len, z1
    zp = zb0 + 0.6 * r.bump_len
    tri = m3.CrossSection([[(zb0, 0.0), (zb1, 0.0), (zp, r.bump_h)]])      # (z, dy), CCW
    bump = tri.extrude(r.top_w * 0.8).translate([0, 0, -r.top_w * 0.4])     # axes: x=z, y=dy, z=x
    bump = bump.transform([[0, 0, -1, 0], [0, 1, 0, y1 - 0.01], [1, 0, 0, 0]])  # -> x, y=y1+dy, z (det +1)
    return rail + stop + bump


# ------------------------------------------------------------------ charm side
def groove(Lg, r: Rail = Rail()):
    c = r.clear
    w0, w1, h = r.root_w + 2 * c, r.top_w + 2 * c, r.h + c
    prof = m3.CrossSection([[(-w0 / 2, -0.01), (w0 / 2, -0.01), (w1 / 2, h), (-w1 / 2, h)]])
    # profile in (x, z), extruded along y
    g = prof.extrude(Lg + 2).translate([0, 0, -1])                           # x, y=z_prof, z=len
    return g.transform([[1, 0, 0, 0], [0, 0, -1, Lg], [0, 1, 0, 0]])         # -> x, y=len, z=height (det +1)


def base_plate(Lg, width=10.0, t=3.0, shape="oval", r: Rail = Rail()):
    """Charm base, footprint centred at (0, Lg/2), groove underneath. Top edge chamfered 0.5."""
    if shape == "oval":
        foot = m3.CrossSection.circle(1.0, SEG).scale([width / 2, Lg / 2])
    else:
        foot = m3.CrossSection.square([width, Lg], True).offset(-1.0).offset(1.0, m3.JoinType.Round)
    foot = foot.translate([0, Lg / 2])
    plate = foot.extrude(t - 0.5) + foot.offset(-0.5, m3.JoinType.Round).extrude(0.5).translate([0, 0, t - 0.5])
    plate = plate + m3.Manifold.batch_hull([foot.extrude(0.01).translate([0, 0, t - 0.51]),
                                            foot.offset(-0.5, m3.JoinType.Round).extrude(0.01)
                                            .translate([0, 0, t - 0.01])])
    return plate - groove(Lg, r)


def mount_on_clip(M, y_face, stop_len):
    """Charm local (X, Y, Z) -> clip (x=-X, y=y_face+Z, z=stop_len+Y)  (proper rotation, det=+1)."""
    return M.transform([[-1, 0, 0, 0], [0, 0, 1, y_face], [0, 1, 0, stop_len]])


# ------------------------------------------------------------------ the plug
@dataclass
class Plug:
    length: float = 16.0      # from the flange top to the tip
    neck_r: float = 1.5
    neck_l: float = 2.2
    bulb_r: float = 4.0
    rise: float = 0.95        # dr/dz of the lower bulb (<= 1.0 keeps overhangs <= 45 deg when standing)
    tip_r: float = 0.9


def plug_profile(pl: Plug = Plug(), n=160):
    """Radius along the axis (z from flange top): neck, 45-deg lower bulb, ogive upper bulb, round tip."""
    z_b0 = pl.neck_l
    z_max = z_b0 + (pl.bulb_r - pl.neck_r) / pl.rise
    L = pl.length
    z = np.linspace(0, L, n)
    r = np.empty_like(z)
    for i, t in enumerate(z):
        if t <= z_b0:
            r[i] = pl.neck_r
        elif t <= z_max:
            r[i] = pl.neck_r + (t - z_b0) * pl.rise
        else:
            u = (t - z_max) / (L - z_max)
            r[i] = pl.bulb_r * math.sqrt(max(1 - u**1.7, 0.0))     # ogive towards the tip
    # smooth the kink at the bulb maximum (moving average over ~1 mm)
    k = max(3, int(n / L))
    sm = np.convolve(np.pad(r, (k, k), mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    near_max = np.abs(z - z_max) < 1.2                  # only round the bulb maximum, keep neck + 45 deg flank
    rs = np.where(near_max, np.minimum(sm, r), r)
    # round tip: replace the last tip_r with a sphere cap
    zt = L - pl.tip_r
    for i, t in enumerate(z):
        if t > zt:
            rs[i] = min(rs[i], math.sqrt(max(pl.tip_r**2 - (t - zt) ** 2, 0.0)) + 0.15)
    rs[-1] = 0.0
    return z, np.maximum(rs, 0.0)


def plug_body(pl: Plug = Plug()):
    """Revolved neck + bulb, axis +Z, starting at z=0 (flange top)."""
    z, r = plug_profile(pl)
    pts = [(0.0, -0.4)] + [(float(ri), float(zi)) for zi, ri in zip(z, r)] + [(0.0, float(z[-1]))]
    pts.insert(1, (float(r[0]), -0.4))
    return m3.CrossSection([pts]).revolve(SEG)


def plug_flange(width=10.0, depth=7.0, t=2.0):
    """Classic flat oval flange with rounded top edge."""
    foot = m3.CrossSection.circle(1.0, SEG).scale([width / 2, depth / 2])
    return foot.extrude(t - 0.6) + m3.Manifold.batch_hull(
        [foot.extrude(0.01).translate([0, 0, t - 0.61]),
         foot.offset(-0.6, m3.JoinType.Round).extrude(0.01).translate([0, 0, t - 0.01])])


# ------------------------------------------------------------------ charms
def charm_plug(Lg, r: Rail = Rail(), pl: Plug = Plug(), base_w=11.0):
    """Plug charm, printed standing on its flange: the flange IS the charm base."""
    t = 3.0
    base = base_plate(Lg, width=base_w, t=t, shape="oval", r=r)
    return base + plug_body(pl).translate([0, Lg / 2, t])


def charm_heart(Lg, r: Rail = Rail(), size=12.0, t=1.6, dz=0.2):
    """Heart plate on a base. The heart grows out of the base footprint at 45 deg (printable standing);
    growth only starts above the rail stop height so nothing hits the stop block."""
    import icons
    h = icons.heart_curve(0.215)
    b = h.bounds()
    s = size / (b[2] - b[0])
    h = h.translate([-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2]).scale([s, s]).translate([0, Lg / 2 + 1.0])
    base_t = 2.6
    foot = m3.CrossSection.square([9.0, Lg], True).offset(-1.0).offset(1.0, m3.JoinType.Round).translate([0, Lg / 2])
    z0 = r.h + 0.5                                   # start growing above the stop block
    parts = [foot.extrude(z0)]
    z = z0
    while True:
        layer = foot + (h ^ foot.offset(z - z0 + dz, m3.JoinType.Round))
        parts.append(layer.extrude(dz).translate([0, 0, z]))
        z += dz
        if (h - layer).area() < 1e-3 or z > 12:
            break
    parts.append(h.extrude(t).translate([0, 0, z]))
    top = z + t
    body = m3.Manifold.batch_boolean(parts, m3.OpType.Add)
    return body - groove(Lg, r), dict(height=round(top, 2), base_t=base_t)


def charm_blank(Lg, r: Rail = Rail(), width=10.0):
    """Base with a flat top: glue a mini on, or merge any STL with --charm-stl."""
    return base_plate(Lg, width=width, t=3.0, shape="rect", r=r)


def charm_from_mesh(Lg, tm, r: Rail = Rail(), max_xy=14.0, max_h=22.0, width=10.0):
    """Fuse an arbitrary (watertight) mesh onto a blank base: scaled to fit, centred, sunk 0.3 mm."""
    import trimesh  # noqa: F401
    from tdg import mesh as tmesh
    ext = tm.extents
    s = min(max_xy / max(ext[0], ext[1]), max_h / ext[2], 1.0)
    tm = tm.copy()
    tm.apply_scale(s)
    b = tm.bounds
    tm.apply_translation([-(b[0, 0] + b[1, 0]) / 2, Lg / 2 - (b[0, 1] + b[1, 1]) / 2, 3.0 - 0.3 - b[0, 2]])
    fig = tmesh.trimesh_to_manifold(tm)
    if fig.status() != m3.Error.NoError:
        raise ValueError(f"mesh is not a valid manifold ({fig.status()}); repair it first (e.g. in Bambu Studio)")
    return charm_blank(Lg, r, width) + fig, s
