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


def charm_heart(Lg, r: Rail = Rail(), size=12.0, t=1.6):
    """Heart plate on a base (see charm_flat)."""
    import icons
    M = charm_flat(Lg, icons.heart_curve(0.215), size=size, t=t + 0.6, dome=0.6, r=r)
    return M, dict(height=round(M.bounding_box()[5], 2))


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


# ================================================================== back-plate charms (figures stand upright)
# Figures should stand upright on the mug, i.e. their "up" runs ALONG the handle = the slide axis.
# So these charms have a vertical BACK PLATE with a vertical dovetail groove, and the figure stands on
# the bed in front of it. Local frame: X across the rail, Y out of the badge (plate at 0..t, figure at
# y >= t), Z = slide axis = figure up. Mounting is a pure translation.
PLATE_T = 3.0


def groove_vertical(Lg, r: Rail = Rail()):
    c = r.clear
    w0, w1, h = r.root_w + 2 * c, r.top_w + 2 * c, r.h + c
    prof = m3.CrossSection([[(-w0 / 2, -0.01), (w0 / 2, -0.01), (w1 / 2, h), (-w1 / 2, h)]])
    return prof.extrude(Lg + 2).translate([0, 0, -1])


def back_plate(Lg, width=10.0, t=PLATE_T, r: Rail = Rail()):
    foot = m3.CrossSection.square([width, t]).translate([-width / 2, 0]).offset(-0.6).offset(0.6, m3.JoinType.Round)
    plate = foot.extrude(Lg - 0.5) + m3.Manifold.batch_hull(
        [foot.extrude(0.01).translate([0, 0, Lg - 0.51]),
         foot.offset(-0.5, m3.JoinType.Round).extrude(0.01).translate([0, 0, Lg - 0.01])])
    return plate - groove_vertical(Lg, r)


def mount_back(M, y_face, stop_len):
    return M.translate([0, y_face, stop_len])


def extrude_xz(cs, y0, y1):
    """2D shape in the (x, z) plane extruded along y from y0 to y1 (proper rotation)."""
    return cs.extrude(y1 - y0).transform([[1, 0, 0, 0], [0, 0, -1, y1], [0, 1, 0, 0]])


def revolve_at(profile_rz, x=0.0, y=0.0, seg=SEG):
    pts = [(max(float(rr), 0.0), float(zz)) for rr, zz in profile_rz]
    return m3.CrossSection([pts]).revolve(seg).translate([x, y, 0])


def capsule(a, b, r, seg=32):
    return m3.Manifold.batch_hull([m3.Manifold.sphere(r, seg).translate(list(a)),
                                   m3.Manifold.sphere(r, seg).translate(list(b))])


def bed_cut(M):
    return M ^ m3.Manifold.cube([200, 200, 200], True).translate([0, 0, 100])


def charm_mass(Lg, r: Rail = Rail()):
    """Mini Maßkrug standing upright: dimpled body, 45-deg handle, foam crown."""
    t, R, H = PLATE_T, 3.4, 9.5
    cy = t + R - 0.6
    body = m3.Manifold.cylinder(H, R, R, SEG).translate([0, cy, 0])
    for z in (2.2, 4.6, 7.0):
        for a in np.radians([-70, -35, 0, 35, 70]):
            body -= m3.Manifold.sphere(0.9, 24).translate([(R + 0.45) * math.sin(a), cy + (R + 0.45) * math.cos(a), z])
    foam = [m3.Manifold.sphere(1.6, 32).translate([0, cy, H + 0.6])]
    foam += [m3.Manifold.sphere(1.25, 24).translate([2.15 * math.cos(a), cy + 2.15 * math.sin(a), H + 0.35])
             for a in np.radians(np.arange(0, 360, 60) + 15)]
    handle2d = m3.CrossSection([[(3.0, 1.4), (6.6, 5.0), (6.6, 7.8), (5.8, 8.8), (3.0, 8.8)]]) - m3.CrossSection(
        [[(4.2, 5.4), (4.95, 4.65), (5.7, 5.4), (5.7, 7.0), (4.95, 7.75), (4.2, 7.0)]])
    handle = extrude_xz(handle2d, cy - 1.0, cy + 1.0)
    fig = m3.Manifold.batch_boolean([body, handle] + foam, m3.OpType.Add)
    return back_plate(Lg, r=r) + fig


def charm_bavaria(Lg, r: Rail = Rail()):
    """Stylised Bavaria (Theresienwiese): robed figure, raised oak wreath, sword, lion at her side."""
    t = PLATE_T
    x0, cy = 0.8, t + 2.8
    prof = [(0, 0), (3.2, 0), (3.0, 1.0), (2.2, 6.0), (1.5, 9.5), (1.6, 11.5), (1.7, 12.8), (1.0, 13.6),
            (0.7, 14.0), (0.7, 14.3), (1.3, 14.9)]
    prof += [(1.3 * math.cos(a), 15.6 + 1.3 * math.sin(a)) for a in np.radians(np.linspace(-30, 90, 12))]
    figure = revolve_at(prof, x0, cy)
    arm_up = capsule((x0 - 1.4, cy, 12.6), (x0 - 3.0, cy, 17.8), 0.55)
    wreath = m3.CrossSection.circle(0.42, 24).translate([1.2, 0]).revolve(48).rotate([90, 0, 0]) \
        .translate([x0 - 3.2, cy, 19.0])
    arm_dn = capsule((x0 + 1.4, cy, 12.4), (x0 + 2.4, cy + 0.3, 9.2), 0.5)
    sword = capsule((x0 + 2.7, cy + 0.4, 0.5), (x0 + 2.7, cy + 0.4, 10.4), 0.5) \
        + capsule((x0 + 2.1, cy + 0.4, 9.2), (x0 + 3.3, cy + 0.4, 9.2), 0.35)
    lion = m3.Manifold.sphere(1.0, 48).scale([2.0, 1.4, 1.5]).translate([x0 - 4.3, cy + 0.2, 1.2])
    lion += m3.Manifold.sphere(1.35, 32).translate([x0 - 4.9, cy + 0.6, 2.9])     # mane
    lion += m3.Manifold.sphere(1.0, 32).translate([x0 - 5.0, cy + 1.3, 2.8])      # face
    fig = bed_cut(m3.Manifold.batch_boolean([figure, arm_up, wreath, arm_dn, sword, lion], m3.OpType.Add))
    return back_plate(Lg, width=11.0, r=r) + fig


def charm_thumbsup(Lg, r: Rail = Rail()):
    """Thumbs up: fist with finger grooves facing out, thumb pointing up along the handle."""
    t = PLATE_T
    y0, y1, zt = t - 0.4, t + 5.6, 7.2
    fist2d = m3.CrossSection.square([6.8, y1 - y0]).translate([-3.4, y0]).offset(-1.2).offset(1.2, m3.JoinType.Round)
    fist = fist2d.extrude(zt - 1.0) + m3.Manifold.batch_hull(
        [fist2d.extrude(0.01).translate([0, 0, zt - 1.01]),
         fist2d.offset(-1.0, m3.JoinType.Round).extrude(0.01).translate([0, 0, zt - 0.01])])
    for z in (1.8, 3.6, 5.4):
        fist -= m3.Manifold.cube([6.2, 1.2, 0.5]).translate([-3.1, y1 - 0.6, z - 0.25])
    thumb = capsule((-1.4, t + 2.0, 5.5), (-1.7, t + 2.3, 12.4), 1.35)
    nail = m3.Manifold.cube([1.6, 0.5, 1.8]).translate([-2.5, t + 3.35, 10.6])
    return back_plate(Lg, r=r) + fist + thumb - nail


def charm_poop(Lg, r: Rail = Rail()):
    """Poop emoji: three soft-serve tiers (every undercut flank <= 45 deg), eyes and smile."""
    t = PLATE_T
    cy = t + 4.1
    prof = [(0, 0), (4.3, 0), (4.6, 0.8), (4.5, 1.8), (3.9, 2.6), (3.4, 2.9), (3.9, 3.4), (4.0, 4.1),
            (3.6, 5.0), (2.7, 5.5), (3.1, 5.9), (3.1, 6.6), (2.6, 7.4), (1.8, 7.9), (2.0, 8.1), (1.8, 8.9),
            (1.0, 9.8), (0.45, 10.8), (0.0, 11.3)]
    poo = revolve_at(prof, 0, cy)
    for a in (-24, 24):
        s = math.radians(a)
        poo -= m3.Manifold.sphere(0.75, 24).translate([3.95 * math.sin(s), cy + 3.95 * math.cos(s), 4.15])
    for a in np.linspace(-32, 32, 9):
        s = math.radians(a)
        dz = 0.35 * (1 - (a / 32) ** 2)
        poo -= m3.Manifold.sphere(0.45, 16).translate([4.55 * math.sin(s), cy + 4.55 * math.cos(s), 1.35 - dz])
    return back_plate(Lg, r=r) + poo


def charm_flat(Lg, shape2d, size=14.0, t=2.6, dome=0.9, r: Rail = Rail(), dz=0.2):
    """Generic flat charm (like the heart): shape grows out of the base at 45 deg above the stop height,
    top edge domed. Face points out of the badge, shape 'up' runs along the handle."""
    b = shape2d.bounds()
    s = size / max(b[2] - b[0], b[3] - b[1])
    h = shape2d.translate([-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2]).scale([s, s]).translate([0, Lg / 2 + 1.0])
    foot = m3.CrossSection.square([9.0, Lg], True).offset(-1.0).offset(1.0, m3.JoinType.Round).translate([0, Lg / 2])
    z0 = r.h + 0.5
    parts = [foot.extrude(z0)]
    z = z0
    while True:
        # grow only inside the shape (keeps holes open), 0.9 mm per mm height = 42 deg overhang
        layer = h ^ foot.offset(0.9 * (z - z0 + dz), m3.JoinType.Round)
        parts.append(layer.extrude(dz).translate([0, 0, z]))
        z += dz
        if (h - layer).area() < 1e-3 or z > 14:
            break
    body_top = z + t - dome
    parts.append(h.extrude(body_top - z).translate([0, 0, z]))
    zz = body_top
    while zz < body_top + dome - 1e-9:
        u = zz + dz / 2 - body_top
        off = dome - math.sqrt(max(dome**2 - u**2, 0))
        layer = h.offset(-off, m3.JoinType.Round)
        if layer.is_empty():
            break
        parts.append(layer.extrude(dz).translate([0, 0, zz]))
        zz += dz
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add) - groove(Lg, r)


def charm_brezn(Lg, r: Rail = Rail()):
    import icons
    return charm_flat(Lg, icons.brezn(), size=14.0, t=2.8, dome=1.0, r=r)


def charm_frauenkirche(Lg, r: Rail = Rail()):
    """Frauenkirche west front: two square towers with 'welsche Hauben' (every flank <= 45 deg),
    pointed-arch windows, steep nave roof between/behind the towers."""
    t = PLATE_T
    tw, th = 3.4, 13.0                                   # tower width, tower height
    y0 = t - 0.4
    parts = []
    dome = [(0, 0), (1.7, 0), (1.9, 0.4), (1.8, 1.2), (1.3, 2.0), (0.6, 2.5), (0.35, 2.8), (0.35, 3.3),
            (0.5, 3.5), (0.2, 4.1), (0, 4.5)]
    for sx in (-1, 1):
        cx = sx * 2.6
        tower = m3.Manifold.cube([tw, tw, th]).translate([cx - tw / 2, y0, 0])
        for z in (6.0, 9.6):                              # pointed-arch windows (45 deg tops)
            win = m3.CrossSection([[(-0.45, 0), (0.45, 0), (0.45, 1.6), (0, 2.05), (-0.45, 1.6)]]).translate([cx, z])
            tower -= extrude_xz(win, y0 + tw - 0.5, y0 + tw + 0.1)
        parts += [tower, revolve_at(dome, cx, y0 + tw / 2).translate([0, 0, th - 0.05])]
    gable = m3.CrossSection([[(-1.0, 0), (1.0, 0), (1.0, 7.0), (0, 10.5), (-1.0, 7.0)]])
    parts.append(extrude_xz(gable, y0, y0 + tw - 0.3))
    portal = m3.CrossSection([[(-0.55, 0), (0.55, 0), (0.55, 1.8), (0, 2.35), (-0.55, 1.8)]])
    body = m3.Manifold.batch_boolean(parts, m3.OpType.Add) - extrude_xz(portal, y0 + tw - 0.8, y0 + tw + 0.1)
    return back_plate(Lg, r=r) + body


def charm_cuckoo(Lg, r: Rail = Rail()):
    """Black-Forest cuckoo clock: gable roof with 48-deg eave undersides, clock face with raised hands, cuckoo
    under the gable, 45-deg carved V bottom (47 deg) (no flat overhang), pendulum and two pine-cone weights
    standing on the bed."""
    t = PLATE_T
    y0, y1 = t - 0.4, t + 4.0
    house2d = m3.CrossSection([[(-0.3, 6.0), (0.3, 6.0), (4.5, 10.2), (4.5, 14.3), (-4.5, 14.3), (-4.5, 10.2)]])
    roof2d = m3.CrossSection([[(4.5, 14.2), (5.4, 15.2), (5.4, 15.6), (0, 19.6), (-5.4, 15.6), (-5.4, 15.2),
                               (-4.5, 14.2)]])                         # CCW
    house = extrude_xz(house2d, y0, y1) + extrude_xz(roof2d, y0, y1)
    # clock face: raised disc, 12 hour dots cut, hands raised again
    fc = (0.0, 11.3)
    face = extrude_xz(m3.CrossSection.circle(2.3, 64).translate(list(fc)), y1 - 0.1, y1 + 0.6)
    for k in range(12):
        a = math.radians(30 * k)
        face -= m3.Manifold.sphere(0.25, 12).translate([fc[0] + 1.85 * math.cos(a), y1 + 0.6,
                                                         fc[1] + 1.85 * math.sin(a)])
    hands = extrude_xz(m3.CrossSection.square([0.45, 1.6]).translate([-0.225, 0]).rotate(-60).translate(list(fc))
                       + m3.CrossSection.square([0.45, 1.2]).translate([-0.225, 0]).rotate(35).translate(list(fc)),
                       y1 + 0.5, y1 + 0.9)
    door = extrude_xz(m3.CrossSection([[(-0.8, 14.5), (0.8, 14.5), (0.8, 15.7), (0, 16.5), (-0.8, 15.7)]]),
                      y1 - 0.5, y1 + 0.5)
    bird = m3.Manifold.sphere(0.6, 24).translate([0, y1 - 0.2, 15.3]) \
        + m3.Manifold.cylinder(0.7, 0.3, 0.0, 16).rotate([-90, 0, 0]).translate([0, y1 + 0.3, 15.3])
    yc = (y0 + y1) / 2
    cone = [(0, 0), (1.0, 0), (1.15, 0.6), (1.1, 2.2), (0.7, 3.0), (0.4, 3.4), (0, 3.6)]
    weights = [revolve_at(cone, sx * 2.4, yc) for sx in (-1, 1)]
    chains = [m3.Manifold.cylinder(5.5, 0.4, 0.4, 16).translate([sx * 2.4, yc, 3.3]) for sx in (-1, 1)]
    disc = extrude_xz(m3.CrossSection.circle(1.3, 48).translate([0, 1.35]), yc - 0.4, yc + 0.4)
    rod = m3.Manifold.cylinder(4.0, 0.35, 0.35, 16).translate([0, yc, 2.4])
    body = m3.Manifold.batch_boolean([house - door, face, hands, bird, disc, rod] + weights + chains, m3.OpType.Add)
    return back_plate(Lg, r=r) + bed_cut(body)


# name -> (builder, kind) ; kind "flat" = groove underneath (mount_on_clip), "back" = back plate (mount_back)
FIGURES = {
    "brezn": (charm_brezn, "flat"),
    "mass": (charm_mass, "back"),
    "bavaria": (charm_bavaria, "back"),
    "thumbsup": (charm_thumbsup, "back"),
    "poop": (charm_poop, "back"),
    "frauenkirche": (charm_frauenkirche, "back"),
    "cuckoo": (charm_cuckoo, "back"),
}
