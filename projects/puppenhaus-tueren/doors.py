"""
Puppenhaus-Türen 1:12 nach den Fotos in reference/ (02 Wohnungstür, 03 Zimmertür mit Lüftung + Glastür), OHNE Griff.

Einseitige Druckplatten: Rückseite flach auf dem Bett (z = 0), alle Details nur oben (Ansichtsseite).
Koordinaten (Druckmaß, mm): x = Türbreite, x = 0 ist die Schlosskante (in allen Fotos links, Drücker zeigt nach
rechts zur Bandseite), y = Türhöhe, y = 0 = Unterkante Türblatt = Fußboden, z = 0 Bett/Rückseite, z = slab_t Ansicht.
Alle Positionsangaben in DoorSpec sind REALMASSE in mm (geteilt durch scale = 12), Dicken/Höhen mit Suffix _p
sind Druckmaße (nicht skaliert, weil sie durch Düse/Schicht bestimmt sind).

Griff-Hook für den Integrator: handle_mount(spec) liefert den Montagepunkt der Drückerachse auf der Türfläche
(x, y, z in Druck-mm), Hebelrichtung (+1 = nach +x) und eine Freihaltezone für das Langschild; build_door()
legt kein Feature in diese Zone (geprüft in info["handle"]["keepout_free"]).

Fotomaße: per Homographie aus den vier Türblattecken in Foto 02/03 entzerrt (siehe README). Genauigkeit etwa
+-5 % / +-30 mm, alles als ANGENOMMEN markiert.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import manifold3d as m3  # noqa: E402

from tdg import check, mesh  # noqa: E402

DOORS = ("wohnungstuer", "zimmertuer_lueftung", "zimmertuer_glas")
GLASS_MODES = ("matt", "ornament", "offen")


@dataclass
class DoorSpec:
    kind: str = "zimmertuer_lueftung"
    # --- ANGENOMMEN (messen!): Maßstab und Türblatt (DIN-Richtmaße, nicht am Objekt gemessen)
    scale: float = 12.0              # Puppenhaus-Standard 1:12
    leaf_w: float = 860.0            # Türblatt real [mm]; Zimmertür DIN 860 x 1985, Wohnungstür 985 x 2110
    leaf_h: float = 1985.0
    slab_t_p: float = 3.3            # Druckdicke (real 40 mm / 12 = 3,33)
    edge: str = "fase"               # Oberkante: "fase" (45°) | "rund" (Viertelkreis)
    edge_p: float = 0.3              # Fasen-/Rundungsmaß Druck [mm]
    # --- ANGENOMMEN (messen!): Drücker (Montagepunkt für handle.py)
    handle_h: float = 1000.0         # Achse über Boden; Foto 02: ~1010, Foto 03: ~970, Richtmaß 1050
    handle_x: float = 60.0           # Achse ab Schlosskante (Dornmaß 55-65); Foto 03: ~70
    esc_w: float = 55.0              # Langschild-Freihaltezone (Breite, oberhalb/unterhalb der Achse)
    esc_up: float = 85.0             # Foto 02 entzerrt: Schild ~ +75 / -160 um die Achse
    esc_down: float = 175.0
    # --- ANGENOMMEN (messen!): Türspion (Foto 02 entzerrt: Mitte, ~1607 über Boden, Ring ~25 mm)
    spion: bool = False
    spion_h: float = 1600.0
    spion_d: float = 26.0            # Ring außen real
    spion_ring_h_p: float = 0.45     # Ringhöhe über Türfläche (Druck)
    # --- ANGENOMMEN (messen!): Briefeinwurf (Foto 02 entzerrt: ~272 x 73, mittig, UK ~555)
    slot: bool = False
    slot_w: float = 280.0
    slot_h: float = 75.0
    slot_bottom: float = 555.0
    slot_side: float = 24.0          # seitlicher Rand der Platte bis zur Klappe (Foto: breiter als oben/unten)
    slot_tb: float = 11.0            # Rand oben/unten
    slot_t_p: float = 0.5            # Plattenhöhe über Türfläche (Druck)
    # --- ANGENOMMEN (messen!): Lüftungsgitter (Foto 03 links, stark verkürzt: ~330-380 x 100-120, UK ~85)
    vent: bool = False
    vent_w: float = 380.0
    vent_h: float = 110.0
    vent_bottom: float = 85.0
    vent_frame: float = 12.0         # Rahmenbreite real
    vent_louvres: int = 7            # Lamellen (Foto ~10; 7 hält die Teilung >= 1 mm im Druck)
    vent_frame_h_p: float = 0.45
    # --- ANGENOMMEN (messen!): Glasausschnitt (Foto 03 rechts entzerrt, mittig angenommen)
    glass: str = ""                  # "" | "matt" | "ornament" | "offen"
    bead_w_out: float = 570.0        # Glasleiste außen real (Foto: linker Rand ~145 mm)
    bead_h_out: float = 1490.0
    bead_bottom: float = 375.0       # Unterkante Glasleiste über Boden (Foto ~370-400)
    bead_w: float = 20.0             # Leistenbreite real (Foto 01/03: 15-25)
    bead_h_p: float = 0.6            # Leistenhöhe über Türfläche (Druck)
    glass_recess_p: float = 0.3      # Glasfeld unter Türfläche (Druck)
    orn_pp_p: float = 0.25           # Ornament Spitze-Spitze (<= 0.3)
    orn_sigma_p: float = 0.35        # Korngröße (Gauß-Sigma) -> Strukturen ~0,8-2 mm, >= 0.5
    orn_dx_p: float = 0.2            # Gitterweite der Textur
    orn_seed: int = 7
    # --- Passung & Druck ("offen": Klarsichtfolie + separater Leistenrahmen)
    acetate_t_p: float = 0.5         # Folie 0,3-0,5 mm; Falz ist auf das Maximum ausgelegt
    frame_insert_p: float = 0.6      # Rahmen taucht so tief in den Falz
    frame_clear_p: float = 0.15      # Spiel je Seite Rahmen <-> Falz
    material: str = "PLA"
    bed: float = 180.0               # Bambu Lab A1 mini
    bed_margin: float = 2.0

    def p(self, real):               # real mm -> Druck-mm
        return real / self.scale


def spec(kind: str, **kw) -> DoorSpec:
    """Default spec per door kind (photo-derived ANGENOMMEN values), overridable by keyword."""
    base = dict(
        wohnungstuer=dict(leaf_w=985.0, leaf_h=2110.0, edge="rund", handle_x=65.0, spion=True, slot=True),
        zimmertuer_lueftung=dict(vent=True),
        zimmertuer_glas=dict(glass="ornament"),
    )[kind]
    base.update(kw)
    s = DoorSpec(kind=kind, **base)
    assert s.glass in ("",) + GLASS_MODES, s.glass
    return s


# ----------------------------------------------------------------------------------------------- geometry helpers
def _rect_pts(x0, y0, x1, y1, inset, z):
    return [(x0 + inset, y0 + inset, z), (x1 - inset, y0 + inset, z), (x1 - inset, y1 - inset, z),
            (x0 + inset, y1 - inset, z)]


def frustum_stack(x0, y0, x1, y1, levels):
    """Mitred rectangular sweep: levels = [(z, inset)], inset < 0 grows. Union of hulls of consecutive slices,
    so non-convex profiles (e.g. the funnel of a round bead) stay exact up to the polyline."""
    parts = []
    for (za, ia), (zb, ib) in zip(levels[:-1], levels[1:]):
        parts.append(m3.Manifold.hull_points(np.array(_rect_pts(x0, y0, x1, y1, ia, za)
                                                      + _rect_pts(x0, y0, x1, y1, ib, zb), float)))
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add) if len(parts) > 1 else parts[0]


def box(x0, y0, z0, x1, y1, z1):
    return m3.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def _arc(n, r0, r1, z0, z1, inner=False):
    """Quarter ellipse from (inset r0, z0) to (r1, z1) with horizontal tangent at z1 (round bead/edge)."""
    out = []
    for k in range(1, n + 1):
        a = k / n * math.pi / 2
        out.append((z0 + (z1 - z0) * math.sin(a), r0 + (r1 - r0) * (1 - math.cos(a))))
    return out


def leaf(s: DoorSpec):
    W, H, t, e = s.p(s.leaf_w), s.p(s.leaf_h), s.slab_t_p, s.edge_p
    if s.edge == "rund":
        lv = [(0.0, 0.0), (t - e, 0.0)] + [(t - e + e * math.sin(a), e * (1 - math.cos(a)))
                                           for a in np.linspace(0, math.pi / 2, 7)[1:]]
    else:
        lv = [(0.0, 0.0), (t - e, 0.0), (t, e)]
    return m3.Manifold.hull_points(np.array(sum((_rect_pts(0, 0, W, H, i, z) for z, i in lv), []), float))


def bead_solid(x0, y0, x1, y1, bw, z_in, z_face, top, n=8):
    """Glasleiste around inner rect (x0..x1, y0..y1): inner side rises from z_in (glass level) as quarter ellipse,
    outer side falls to z_face; small flat top. Mitred corners (Gehrung)."""
    c = 0.45 * bw                     # inner rising width
    a = bw - c - 0.08                 # outer falling width (0.08 flat top)
    zi0, zo0 = z_face + 0.12, z_face + 0.08
    X0, Y0, X1, Y1 = x0 - bw, y0 - bw, x1 + bw, y1 + bw
    outer = frustum_stack(X0, Y0, X1, Y1, [(z_in - 0.3, 0.0), (zo0, 0.0)] + _arc(n, 0.0, a, zo0, top))
    hole = frustum_stack(x0, y0, x1, y1, [(z_in - 1.0, 0.0), (zi0, 0.0)]
                         + [(z, -r) for z, r in _arc(n, 0.0, c, zi0, top)] + [(top + 1.0, -c)])
    return outer - hole


def heightfield(x0, y0, hmap, dx, z_base, z_bot):
    """Watertight solid: top z = z_base + hmap[j, i] on a dx grid starting at (x0, y0), flat bottom z_bot."""
    ny, nx = hmap.shape
    X, Y = np.meshgrid(x0 + dx * np.arange(nx), y0 + dx * np.arange(ny))
    top = np.c_[X.ravel(), Y.ravel(), (z_base + hmap).ravel()]
    idx = np.arange(nx * ny).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    faces = [np.c_[a, b, c], np.c_[a, c, d]]            # CCW seen from +z
    ring = np.r_[idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]]  # CCW boundary
    nb = len(ring)
    bot = np.c_[top[ring, 0], top[ring, 1], np.full(nb, z_bot)]
    ctr = np.array([[X.mean(), Y.mean(), z_bot]])
    vb = nx * ny + np.arange(nb)
    vc = nx * ny + nb
    nxt = np.roll(np.arange(nb), -1)
    faces += [np.c_[ring, vb, vb[nxt]], np.c_[ring, vb[nxt], ring[nxt]],      # side walls (outward)
              np.c_[np.full(nb, vc), vb[nxt], vb]]                            # bottom fan (facing -z)
    V = np.r_[top, bot, ctr].astype(np.float32)
    F = np.concatenate(faces).astype(np.uint32)
    M = m3.Manifold(m3.Mesh(vert_properties=V, tri_verts=F))
    assert M.status() == m3.Error.NoError, M.status()
    return M


def ornament_map(nx, ny, s: DoorSpec):
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(s.orn_seed)
    sig = s.orn_sigma_p / s.orn_dx_p
    n = gaussian_filter(rng.standard_normal((ny, nx)), sig, mode="wrap")
    n2 = gaussian_filter(rng.standard_normal((ny, nx)), 2.6 * sig, mode="wrap")
    h = n / n.std() + 1.2 * n2 / n2.std()
    h = np.tanh(0.45 * h)                              # slightly flattened crests (crinkled cathedral glass)
    h = (h - h.min()) / (h.max() - h.min()) * s.orn_pp_p - s.orn_pp_p / 2
    return h


# ----------------------------------------------------------------------------------------------- features
def glass_rect(s: DoorSpec):
    """Visible glass field (inner edge of the bead), Druck-mm."""
    W = s.p(s.leaf_w)
    bw = s.p(s.bead_w)
    x0 = (W - s.p(s.bead_w_out)) / 2 + bw
    y0 = s.p(s.bead_bottom) + bw
    return x0, y0, W - x0, y0 + s.p(s.bead_h_out) - 2 * bw


def handle_mount(s: DoorSpec):
    """Hook for the integrator / handle.py: lever axis on the door face (Druck-mm) and escutcheon keep-out."""
    x, y = s.p(s.handle_x), s.p(s.handle_h)
    return dict(x=x, y=y, z=s.slab_t_p, lever_dir=+1, lock_edge="links (x=0)", hinge_side="rechts (+x)",
                note="Hebel zeigt zur Bandseite (+x) wie in allen Fotos; Achse senkrecht zur Türfläche (+z)",
                keepout=[x - s.p(s.esc_w) / 2, y - s.p(s.esc_down), x + s.p(s.esc_w) / 2, y + s.p(s.esc_up)])


def _spion(s, feats):
    W, t = s.p(s.leaf_w), s.slab_t_p
    cx, cy = W / 2, s.p(s.spion_h)
    R = s.p(s.spion_d) / 2
    rh, ri = s.spion_ring_h_p, max(R - 0.55, 0.45)
    ring = m3.Manifold.batch_hull([m3.Manifold.cylinder(t + rh - 0.15 - (t - 0.2), R, R, 64).translate([0, 0, t - 0.2]),
                                   m3.Manifold.cylinder(0.01, R - 0.15, R - 0.15, 64).translate([0, 0, t + rh - 0.01])])
    ring -= m3.Manifold.cylinder(1.0, ri, ri, 48).translate([0, 0, t + 0.1])
    cap_h = 0.22                                         # domed lens, top below ring rim (dark recess in photo)
    rs = (ri ** 2 + cap_h ** 2) / (2 * cap_h)
    lens = m3.Manifold.sphere(rs, 96).translate([0, 0, t + 0.1 + cap_h - rs]) ^ box(-ri, -ri, t + 0.1, ri, ri, t + 1)
    lens = lens + m3.Manifold.cylinder(0.31, ri, ri, 48).translate([0, 0, t - 0.2])
    feats.append(dict(name="spion", center=[cx, cy], d=2 * R, ring_wall=R - ri, top=t + rh, color="steel",
                      bbox=[cx - R, cy - R, cx + R, cy + R]))
    return (ring + lens).translate([cx, cy, 0])


def _slot(s, feats):
    W, t = s.p(s.leaf_w), s.slab_t_p
    w, h = s.p(s.slot_w), s.p(s.slot_h)
    x0, y0 = (W - w) / 2, s.p(s.slot_bottom)
    x1, y1 = x0 + w, y0 + h
    pt, bev = s.slot_t_p, 0.25
    plate = frustum_stack(x0, y0, x1, y1, [(t - 0.2, 0.0), (t + pt - bev, 0.0), (t + pt, bev)])
    fx0, fx1 = x0 + s.p(s.slot_side), x1 - s.p(s.slot_side)
    fy0, fy1 = y0 + s.p(s.slot_tb), y1 - s.p(s.slot_tb)
    rec = 0.22                                          # flap recessed into the plate
    plate -= box(fx0, fy0, t + pt - rec, fx1, fy1, t + pt + 1)
    # bent lower flap lip (bright strip in photo 02): wedge, steep side down, 45° ramp up from the flap
    lw, lh = 0.75, rec + 0.12
    zf = t + pt - rec
    lip = m3.Manifold.hull_points(np.array([[fx0, fy0, zf - 0.05], [fx1, fy0, zf - 0.05],
                                            [fx0, fy0 + lw, zf - 0.05], [fx1, fy0 + lw, zf - 0.05],
                                            [fx0, fy0, zf + lh], [fx1, fy0, zf + lh],
                                            [fx0, fy0 + 0.3, zf + lh], [fx1, fy0 + 0.3, zf + lh]], float))
    feats.append(dict(name="briefeinwurf", bbox=[x0, y0, x1, y1], top=t + pt + 0.12 * 0, color="steel",
                      flap=[fx0, fy0, fx1, fy1], min_border=min(s.p(s.slot_side), s.p(s.slot_tb))))
    return plate + lip


def _vent(s, feats):
    """Returns (add, cut): raised frame + louvres, and the recess inside the frame."""
    W, t = s.p(s.leaf_w), s.slab_t_p
    w, h = s.p(s.vent_w), s.p(s.vent_h)
    x0, y0 = (W - w) / 2, s.p(s.vent_bottom)
    x1, y1 = x0 + w, y0 + h
    fw, fh = s.p(s.vent_frame), s.vent_frame_h_p
    frame = frustum_stack(x0, y0, x1, y1, [(t - 0.2, 0.0), (t + fh - 0.2, 0.0), (t + fh, 0.2)])
    ix0, iy0, ix1, iy1 = x0 + fw, y0 + fw, x1 - fw, y1 - fw
    rz = t - 0.25                                       # recess floor
    cut = box(ix0, iy0, rz, ix1, iy1, t + fh + 1)
    n = s.vent_louvres
    pitch = (iy1 - iy0) / n
    lh = 0.42                                           # louvre ridge above recess floor
    louv = []
    for k in range(n):
        ya = iy0 + k * pitch
        yt = ya + 0.72 * pitch                          # crest: long ramp up (lit slat face), steep drop
        pts = []
        for xx in (ix0 - 0.05, ix1 + 0.05):  # overlap into the frame walls, no coplanar slivers
            pts += [[xx, ya, rz - 0.05], [xx, ya + pitch, rz - 0.05], [xx, yt, rz + lh], [xx, ya + pitch, rz + 0.04]]
        louv.append(m3.Manifold.hull_points(np.array(pts, float)))
    feats.append(dict(name="lueftungsgitter", bbox=[x0, y0, x1, y1], color="steel", frame_w=fw, louvres=n,
                      louvre_pitch=pitch, top=t + fh))
    return frame - cut + m3.Manifold.batch_boolean(louv, m3.OpType.Add), cut


def glass_frame(s: DoorSpec):
    """'offen': separate glazing-bead frame, printed flat side down. Returns (Manifold at z=0, info)."""
    gx0, gy0, gx1, gy1 = glass_rect(s)
    bw, c = s.p(s.bead_w), s.frame_clear_p
    # door face height inside the frame part: frame bottom at 0, door face at frame_insert_p
    zf = s.frame_insert_p
    fr = bead_solid(gx0, gy0, gx1, gy1, bw, 0.0, zf, zf + s.bead_h_p)
    fr = fr ^ box(gx0 - bw - 1, gy0 - bw - 1, 0.0, gx1 + bw + 1, gy1 + bw + 1, 50)
    # rebate = glass + (bw + c) per side, so the frame (glass + bw) has clearance c per side
    return fr, dict(footprint=[gx0 - bw, gy0 - bw, gx1 + bw, gy1 + bw], width=bw, height=zf + s.bead_h_p,
                    clearance_per_side=c)


def build_door(s: DoorSpec):
    """-> (Manifold door without handle, info). Back flat on z = 0, details on top."""
    t = s.slab_t_p
    door = leaf(s)
    feats, adds, cuts = [], [], []
    if s.spion:
        adds.append(_spion(s, feats))
    if s.slot:
        adds.append(_slot(s, feats))
    if s.vent:
        a, c = _vent(s, feats)
        cuts.append(c)
        adds.append(a)
    extra = {}
    if s.glass:
        gx0, gy0, gx1, gy1 = glass_rect(s)
        bw = s.p(s.bead_w)
        f = dict(name="glas", mode=s.glass, glass=[gx0, gy0, gx1, gy1], bbox=[gx0 - bw, gy0 - bw, gx1 + bw, gy1 + bw],
                 bead_w=bw, top=t + s.bead_h_p, color="glass")
        if s.glass in ("matt", "ornament"):
            zg = t - s.glass_recess_p
            cuts.append(box(gx0, gy0, zg, gx1, gy1, t + 2))
            adds.append(bead_solid(gx0, gy0, gx1, gy1, bw, zg, t, t + s.bead_h_p))
            if s.glass == "ornament":
                dx, ov = s.orn_dx_p, 0.1                 # overlap under the bead's steep inner flank
                nx = int(math.ceil((gx1 - gx0 + 2 * ov) / dx)) + 1
                ny = int(math.ceil((gy1 - gy0 + 2 * ov) / dx)) + 1
                hm = ornament_map(nx, ny, s)
                adds.append(heightfield(gx0 - ov, gy0 - ov, hm, dx, zg, zg - 0.4))
                f.update(ornament_pp=float(hm.max() - hm.min()), ornament_sigma=s.orn_sigma_p, grid=dx)
        else:  # offen: through opening + front rebate for acetate + separate bead frame
            lip = bw + s.frame_clear_p                   # acetate overlap on the ledge = frame width + clearance
            zl = t - s.frame_insert_p - s.acetate_t_p    # ledge height
            cuts.append(box(gx0, gy0, -1, gx1, gy1, t + 2))
            cuts.append(box(gx0 - lip, gy0 - lip, zl, gx1 + lip, gy1 + lip, t + 2))
            fr, fi = glass_frame(s)
            extra["glasleiste_rahmen"] = fr
            sheet = [round(gx1 - gx0 + 2 * lip - 0.2, 2), round(gy1 - gy0 + 2 * lip - 0.2, 2)]
            f.update(rebate=[gx0 - lip, gy0 - lip, gx1 + lip, gy1 + lip], ledge_z=zl, ledge_t=zl,
                     acetate_sheet_mm=sheet, acetate_t_max=s.acetate_t_p, frame=fi)
        feats.append(f)
    if cuts:
        door = door - m3.Manifold.batch_boolean(cuts, m3.OpType.Add)
    if adds:
        door = m3.Manifold.batch_boolean([door] + adds, m3.OpType.Add)
    hm_ = handle_mount(s)
    k = hm_["keepout"]
    clash = [f["name"] for f in feats if not (f["bbox"][2] <= k[0] or f["bbox"][0] >= k[2]
                                               or f["bbox"][3] <= k[1] or f["bbox"][1] >= k[3])]
    hm_["keepout_free"] = not clash
    hm_["keepout_clash"] = clash
    b = door.bounding_box()
    size = [b[3] - b[0], b[4] - b[1]]
    usable = s.bed - 2 * s.bed_margin
    info = dict(kind=s.kind, scale=f"1:{s.scale:g}", real_leaf_mm=[s.leaf_w, s.leaf_h],
                print_size_mm=[round(size[0], 2), round(size[1], 2), round(b[5] - b[2], 2)],
                bed_fit=dict(bed=s.bed, margin_req=s.bed_margin, fits=bool(max(size) <= usable),
                             margin_long_side=round((s.bed - max(size)) / 2, 2)),
                handle=hm_, features=feats, extra_parts=extra)
    return door, info


# ----------------------------------------------------------------------------------------------- checks + output
def assembly_check(s: DoorSpec, door, info):
    """'offen': frame in place must not collide with the door and must sit exactly on the acetate."""
    if s.glass != "offen":
        return None
    fr = info["extra_parts"]["glasleiste_rahmen"].translate([0, 0, s.slab_t_p - s.frame_insert_p])
    col = (door ^ fr).volume()
    f = next(x for x in info["features"] if x["name"] == "glas")
    gap = (s.slab_t_p - s.frame_insert_p) - f["ledge_z"]
    return dict(frame_vs_door_mm3=round(col, 4), acetate_gap_mm=round(gap, 3),
                ok=bool(col < 1e-3 and abs(gap - s.acetate_t_p) < 1e-6))


def _plate_layout(door, frame, s):
    """Door + frame side by side on the bed (frame rotated? no, both upright), centred."""
    bd, bf = door.bounding_box(), frame.bounding_box()
    gap = 4.0
    wd, wf = bd[3] - bd[0], bf[3] - bf[0]
    tot = wd + gap + wf
    ox = (s.bed - tot) / 2
    d = door.translate([ox - bd[0], (s.bed - (bd[4] - bd[1])) / 2 - bd[1], 0])
    f = frame.translate([ox + wd + gap - bf[0], (s.bed - (bf[4] - bf[1])) / 2 - bf[1], 0])
    return d, f, dict(total_w=round(tot, 2), fits=bool(tot <= s.bed - 2 * s.bed_margin))


def write_door(s: DoorSpec, out_dir: Path, name=None):
    import trimesh
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    door, info = build_door(s)
    name = name or f"{s.kind}_ohne_griff"
    tm = mesh.manifold_to_trimesh(door)
    extra = info.pop("extra_parts")
    parts = {name: check.report(tm, s.material)}
    asm = assembly_check(s, door, dict(info, extra_parts=extra))
    if extra:
        fr = extra["glasleiste_rahmen"]
        d2, f2, lay = _plate_layout(door, fr, s)
        ftm = mesh.manifold_to_trimesh(fr)
        parts["glasleiste_rahmen"] = check.report(ftm, s.material)
        sc = trimesh.Scene()
        sc.add_geometry(mesh.manifold_to_trimesh(d2), node_name="tuer", geom_name="tuer")
        sc.add_geometry(mesh.manifold_to_trimesh(f2), node_name="glasleiste_rahmen", geom_name="glasleiste_rahmen")
        sc.export(str(out_dir / f"{name}.3mf"))
        info["plate_layout"] = lay
    else:
        tm.export(str(out_dir / f"{name}.3mf"))
    rep = dict(parts=parts, door=info, spec=asdict(s), assembly_check=asm)
    check.write(rep, str(out_dir / f"{name}_report.json"))
    for r in parts.values():
        check.assert_printable(r)
    assert info["bed_fit"]["fits"], info["bed_fit"]
    assert info["handle"]["keepout_free"], info["handle"]
    if asm:
        assert asm["ok"], asm
    return door, rep


# ----------------------------------------------------------------------------------------------- preview render
COLORS = dict(door=(0.93, 0.92, 0.88), steel=(0.78, 0.79, 0.80), glass=(0.45, 0.66, 0.72),
              bead=(0.95, 0.94, 0.90))


def _raster_kernel():
    from numba import njit

    @njit(cache=True)
    def raster(P, F, zbuf, fid):
        H, W = zbuf.shape
        for f in range(F.shape[0]):
            a, b, c = F[f, 0], F[f, 1], F[f, 2]
            x0, y0, z0 = P[a, 0], P[a, 1], P[a, 2]
            x1, y1, z1 = P[b, 0], P[b, 1], P[b, 2]
            x2, y2, z2 = P[c, 0], P[c, 1], P[c, 2]
            area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if abs(area) < 1e-12:
                continue
            i0 = max(int(math.floor(min(x0, min(x1, x2)))), 0)
            i1 = min(int(math.ceil(max(x0, max(x1, x2)))), W - 1)
            j0 = max(int(math.floor(min(y0, min(y1, y2)))), 0)
            j1 = min(int(math.ceil(max(y0, max(y1, y2)))), H - 1)
            for j in range(j0, j1 + 1):
                sy = j + 0.5
                for i in range(i0, i1 + 1):
                    sx = i + 0.5
                    w0 = ((x1 - sx) * (y2 - sy) - (x2 - sx) * (y1 - sy)) / area
                    w1 = ((x2 - sx) * (y0 - sy) - (x0 - sx) * (y2 - sy)) / area
                    w2 = 1.0 - w0 - w1
                    if w0 < -1e-9 or w1 < -1e-9 or w2 < -1e-9:
                        continue
                    z = w0 * z0 + w1 * z1 + w2 * z2
                    if z > zbuf[j, i]:
                        zbuf[j, i] = z
                        fid[j, i] = f
    return raster


def render_view(tm, face_rgb, eye, center, half_w, px=900, aspect=1.0, light=(-0.45, 0.55, 0.75)):
    """Orthographic z-buffer render. eye: direction towards the camera, screen up = +y (or +z) projected."""
    d = -np.asarray(eye, float) / np.linalg.norm(eye)
    up = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.8 else np.array([0.0, 0.0, 1.0])  # section views: z up
    r = np.cross(d, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    V = np.asarray(tm.vertices) - np.asarray(center, float)
    W, H = px, int(px * aspect)
    s = W / (2 * half_w)
    P = np.c_[V @ r * s + W / 2, -(V @ u) * s + H / 2, -(V @ d)].astype(np.float64)
    zbuf = np.full((H, W), -1e30)
    fid = np.full((H, W), -1, np.int64)
    _raster_kernel()(P, np.asarray(tm.faces, np.int64), zbuf, fid)
    L = np.asarray(light, float) / np.linalg.norm(light)
    n = tm.face_normals
    hv = L - d
    hv /= np.linalg.norm(hv)
    lam = np.clip(n @ L, 0, 1)
    spec_ = np.clip(n @ hv, 0, 1) ** 40
    col = face_rgb * (0.32 + 0.68 * lam[:, None]) + 0.25 * spec_[:, None]
    img = np.ones((H, W, 3))
    m = fid >= 0
    img[m] = np.clip(col[fid[m]], 0, 1)
    return img


def face_colors(tm, info, t):
    c = np.tile(COLORS["door"], (len(tm.faces), 1))
    ctr = tm.triangles_center
    for f in info["features"]:
        x0, y0, x1, y1 = f["bbox"]
        inb = (ctr[:, 0] > x0 - 0.05) & (ctr[:, 0] < x1 + 0.05) & (ctr[:, 1] > y0 - 0.05) & (ctr[:, 1] < y1 + 0.05)
        if f["color"] == "glass":
            gx0, gy0, gx1, gy1 = f["glass"]
            ing = ((ctr[:, 0] > gx0 + 0.02) & (ctr[:, 0] < gx1 - 0.02)
                   & (ctr[:, 1] > gy0 + 0.02) & (ctr[:, 1] < gy1 - 0.02))
            c[ing & (ctr[:, 2] < t)] = COLORS["glass"]
            c[inb & ~ing & (ctr[:, 2] > t + 0.01)] = COLORS["bead"]
        else:
            c[inb & (ctr[:, 2] > t + 0.01) | inb & (ctr[:, 2] < t - 0.01)] = COLORS["steel"]
    return c


def rectified_photo(path, corners, w_real, h_real, px_per_mm=0.25):
    """Perspective-rectify a door from a photo (corners TL, TR, BR, BL in image px) to an upright image."""
    from PIL import Image
    im = Image.open(path)
    W, H = int(w_real * px_per_mm), int(h_real * px_per_mm)
    dst = [(0, 0), (W, 0), (W, H), (0, H)]
    A, bb = [], []
    for (u, v), (x, y) in zip(dst, corners):  # map output (u,v) -> input (x,y)
        A += [[u, v, 1, 0, 0, 0, -x * u, -x * v], [0, 0, 0, u, v, 1, -y * u, -y * v]]
        bb += [x, y]
    co = np.linalg.solve(np.array(A, float), np.array(bb, float))
    return np.asarray(im.transform((W, H), Image.PERSPECTIVE, tuple(co), Image.BICUBIC)) / 255.0


PHOTO_CORNERS = {  # door leaf corners TL, TR, BR, BL in the reference photos (px), picked by hand
    "wohnungstuer": ("02_wohnungstuer_spion_briefschlitz.jpg", [(440, 90), (1104, 236), (1016, 1580), (510, 1910)]),
    "zimmertuer_glas": ("03_zimmertuer_lueftung_und_glastuer.jpg", [(715, 225), (1252, 228), (1130, 1550),
                                                                    (715, 1445)]),
}


def render_overview(results, png, offen=None):
    """results: {kind: (door Manifold, info, spec)} -> one PNG with front views, photo comparison, close-ups.
    offen: optional (door, info-with-extra_parts, spec) of glass='offen', shown as assembled section."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(22, 17), facecolor="white")
    gs = fig.add_gridspec(2, 6, height_ratios=[1.35, 1])
    col = 0
    closeups = []
    for kind in DOORS:
        if kind not in results:
            continue
        door, info, s = results[kind]
        tm = mesh.manifold_to_trimesh(door)
        fc = face_colors(tm, info, s.slab_t_p)
        W, H = s.p(s.leaf_w), s.p(s.leaf_h)
        img = render_view(tm, fc, (0, 0, 1), (W / 2, H / 2, 0), W / 2 * 1.04, px=520, aspect=H / W)
        ax = fig.add_subplot(gs[0, col])
        ax.imshow(img, extent=[-0.02 * W, 1.02 * W, -0.02 * H, 1.02 * H])
        hm = info["handle"]
        k = hm["keepout"]
        ax.add_patch(plt.Rectangle((k[0], k[1]), k[2] - k[0], k[3] - k[1], fill=False, ec="red", ls="--", lw=1))
        ax.plot([hm["x"], hm["x"] + s.p(130)], [hm["y"], hm["y"]], "r-", lw=2)
        ax.plot(hm["x"], hm["y"], "ro", ms=4)
        ax.set_title(f"{kind} 1:{s.scale:g}\n{info['print_size_mm'][0]} x {info['print_size_mm'][1]} mm "
                     f"(rot: Griff-Hook)", fontsize=10)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
        col += 1
        if kind in PHOTO_CORNERS:
            fn, cs = PHOTO_CORNERS[kind]
            ph = rectified_photo(HERE / "reference" / fn, cs, s.leaf_w, s.leaf_h)
            ax = fig.add_subplot(gs[0, col])
            ax.imshow(ph, extent=[0, W, 0, H])
            ax.set_title(f"Foto {fn[:2]} entzerrt (Homographie)", fontsize=10)
            ax.set_aspect("equal")
            ax.tick_params(labelsize=7)
            col += 1
        elif kind == "zimmertuer_lueftung":
            from PIL import Image
            ph = np.asarray(Image.open(HERE / "reference" / "03_zimmertuer_lueftung_und_glastuer.jpg")
                            .crop((150, 0, 700, 1920))) / 255.0
            ax = fig.add_subplot(gs[0, col])
            ax.imshow(ph)
            ax.set_title("Foto 03 links (nicht entzerrbar,\nOberkante fehlt)", fontsize=10)
            ax.axis("off")
            col += 1
        for f in info["features"]:
            x0, y0, x1, y1 = f["bbox"]
            if f["name"] == "glas":
                cx, cy, hw = x0 + 3.5, y0 + 3.5, 5.0      # lower-left bead corner
            else:
                cx, cy, hw = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) * 0.62
            closeups.append((f"{kind}: {f['name']}", tm, fc, (cx, cy, s.slab_t_p), hw))
    if "wohnungstuer" in results:
        door, info, s = results["wohnungstuer"]
        tm = mesh.manifold_to_trimesh(door ^ box(-1, -1, -1, 6, 6, 9))
        closeups.append(("wohnungstuer: Kante rund r0.3", tm, np.tile(COLORS["door"], (len(tm.faces), 1)),
                         (2, 2, 1.6), 3.2))
    if offen is not None:
        door, info, s = offen
        g = next(f for f in info["features"] if f["name"] == "glas")
        gx0, gy0 = g["glass"][:2]
        y = gy0 + 20
        clip = box(gx0 - 6, y - 4, -1, gx0 + 4, y, 9)
        fr = info["extra_parts"]["glasleiste_rahmen"].translate([0, 0, s.slab_t_p - s.frame_insert_p])
        sheet = box(g["rebate"][0] + 0.1, g["rebate"][1] + 0.1, g["ledge_z"], g["rebate"][2] - 0.1,
                    g["rebate"][3] - 0.1, g["ledge_z"] + s.acetate_t_p - 0.02)
        parts = [(door ^ clip, COLORS["door"]), (fr ^ clip, (0.85, 0.55, 0.30)), (sheet ^ clip, COLORS["glass"])]
        tms = [(mesh.manifold_to_trimesh(m), c) for m, c in parts if not m.is_empty()]
        import trimesh
        tm = trimesh.util.concatenate([t_ for t_, _ in tms])
        fc = np.concatenate([np.tile(c, (len(t_.faces), 1)) for t_, c in tms])
        closeups.append(("glas offen: Schnitt Tür+Folie+Rahmen", tm, fc, (gx0 - 1, y - 2, 1.6), 5.0))
    for i, (title, tm, fc, ctr, hw) in enumerate(closeups[:6]):
        ax = fig.add_subplot(gs[1, i])
        eye = (0.12, -1.0, 0.18) if title.startswith("glas offen") else (0.45, -0.75, 0.9)
        lt = (0.3, -1.0, 0.6) if title.startswith("glas offen") else (-0.45, 0.55, 0.75)
        ax.imshow(render_view(tm, fc, eye, ctr, hw, px=700, aspect=0.8, light=lt))
        ax.set_title(title + f" (Ausschnitt ~{2 * hw:.0f} mm)", fontsize=10)
        ax.axis("off")
    fig.suptitle("Puppenhaus-Türen 1:12 ohne Griff, einseitig (Rückseite flach auf dem Bett). Generated by AI",
                 fontsize=13)
    plt.tight_layout()
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=80)
    plt.close(fig)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--doors", default=",".join(DOORS))
    ap.add_argument("--glass", default="ornament", choices=GLASS_MODES)
    ap.add_argument("--glass-variants", default="offen", help="extra glass files, e.g. 'offen,matt' or ''")
    ap.add_argument("--png", default="")
    a = ap.parse_args()
    res, summary = {}, {}
    for kind in a.doors.split(","):
        s = spec(kind, glass=a.glass) if kind == "zimmertuer_glas" else spec(kind)
        door, rep = write_door(s, a.out)
        res[kind] = (door, rep["door"], s)
        summary[kind] = dict(size=rep["door"]["print_size_mm"], bed=rep["door"]["bed_fit"],
                             faces=rep["parts"][f"{kind}_ohne_griff"]["faces"])
    offen = None
    if "zimmertuer_glas" in a.doors:
        for g in filter(None, a.glass_variants.split(",")):
            if g != a.glass:
                sg = spec("zimmertuer_glas", glass=g)
                door, rep = write_door(sg, a.out, name=f"zimmertuer_glas_{g}_ohne_griff")
                summary[f"zimmertuer_glas_{g}"] = dict(asm=rep["assembly_check"], parts=list(rep["parts"]))
                if g == "offen":
                    offen = (door,) + build_door(sg)[1:] + (sg,)
    if a.png:
        render_overview(res, a.png, offen)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
