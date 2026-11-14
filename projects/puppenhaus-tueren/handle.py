"""
Puppenhaus-Drückergarnitur (Barock-Langschild mit Wellendrücker) nach Foto reference/01, Maßstab 1:12.

Frame (= Druckorientierung, liegt mit der Tür auf dem Bett)
----------------------------------------------------------
  z = 0   : Türoberfläche (Unterseite des Langschilds), z zeigt aus der Tür heraus zum Betrachter
  Ursprung: Drückerachse auf der Türoberfläche
  x       : waagerecht, der Drücker zeigt nach +x ('rechts') bzw. -x ('links', gespiegelt)
  y       : senkrecht an der Tür, nach oben

Aufbau (alles in echten mm gezeichnet und mit `scale` verkleinert; Druckmindestmaße werden danach geklemmt)
  - Langschild: barocker Wellenumriss (Bogenkopf mit Schraube, konkave Schultern mit Ecken, Verbreiterung um die
    Drückerrosette, Taille, Verbreiterung um das Schlüsselloch, gelappter Fuß mit Schraube), als Relief mit
    senkrechter Kante + Fase (exakte Minkowski-Fase), Schrauben als flache Kuppeln, Buntbart-Schlüsselloch graviert.
  - Hals: gedrehter Baluster (Unterlegring, Bauch, Kehle, Kragenring) als Rotationskörper; jede nach oben wachsende
    Flanke ist ein Kegel mit >= 50 deg zur Waagerechten, die Ringe erzeugen keinen Überhang.
  - Drücker: runde Knaufscheibe (Unterseite 50-deg-Kegel), dann das flache Wellenblatt: tangential unten aus der
    Scheibe, leichte Senke, steigt zur Spitze, verbreitert sich löffelartig und läuft in eine leicht aufgebogene
    Spitze aus. Querschnitt: flache Oberseite (Frontansicht = flaches Blatt), kurze senkrechte Kante, 50-deg-Fasen
    nach unten in einen senkrechten Steg.
  - Steg: trägt das schwebende Blatt bis zur Tür/zum Schild. Zwischen Stützpunkten spitze Bögen mit 50-deg-Flanken,
    Brücken <= bridge_max (3 mm). Der Steg ist schmaler als das Blatt und daher von vorn unsichtbar.

ANGENOMMEN (aus Foto 01/02 geschätzt, nicht gemessen): Langschild ~246 x 55 mm, Achse-Schlüsselloch 72 mm,
Drückerlänge ~132 mm, Ausladung real ~65 mm (gedruckt bewusst niedriger, lever_h). Die Lappen am Fuß und die
Schulterecken sind gegenüber dem Original etwa 2x überhöht, sonst verschwinden sie unter der 0,4-mm-Düse.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import manifold3d as m3  # noqa: E402

CS = m3.CrossSection
J = m3.JoinType.Round
OVERHANG_DEG = 50.0                       # design angle of every downward surface (to the horizontal)
RUN = 1.0 / math.tan(math.radians(OVERHANG_DEG))   # horizontal growth per mm height (0.839)
WEB_FLANK_DEG = 55.0                      # arch flanks steeper: on the outside of a path bend the flank gets longer

# ------------------------------------------------------------------ real dimensions (mm, ANGENOMMEN from photo 01)
REAL = dict(plate_h=206.0, plate_w=46.0, key_dist=72.0, lever_len=124.0, projection=65.0, plate_t=4.0)

# escutcheon half width over y (lever axis = 0), top -> bottom, proportions from photo 02 (nearly frontal) and 01.
# Shoulder ears and the lobes at the foot are exaggerated (see docstring).
HALF = [(84.0, 0.0), (83.0, 5.0), (80.0, 9.5), (75.5, 13.0), (71.0, 15.8), (68.0, 17.5), (65.0, 14.0),
        (57.0, 12.4), (45.0, 11.5), (32.0, 12.4), (20.0, 15.8), (9.0, 20.5), (0.0, 23.0), (-8.0, 21.5),
        (-17.0, 16.5), (-27.0, 14.0), (-38.0, 14.8), (-50.0, 17.2), (-61.0, 18.6), (-72.0, 18.6), (-80.0, 17.0),
        (-85.5, 13.6), (-90.0, 15.2), (-95.5, 11.8), (-100.0, 12.4), (-105.0, 9.0), (-109.5, 9.6),
        (-115.0, 8.0), (-119.5, 5.0), (-122.0, 0.0)]
SCREWS = [(0.0, 74.0), (0.0, -111.0)]
KEY_Y = -72.0

# lever centre line (rechts, real mm, relative to the axis) and front width of the blade at each point (photo 02):
# leaves the knuckle downwards, lowest point ~35 mm out, then a widening flare rising to a pointed, upturned tip
PATH = [(0.0, -5.0), (11.0, -14.0), (24.0, -20.0), (37.0, -19.5), (51.0, -13.0), (66.0, -5.0), (82.0, 2.5),
        (97.0, 8.0), (110.0, 11.5), (120.0, 14.0), (128.0, 16.5)]
WIDTH = [17.0, 14.0, 13.0, 14.0, 16.5, 19.0, 21.0, 21.0, 18.0, 12.0, 6.0]
DISC_R = 15.0          # knuckle disc radius (real)
NECK_R = dict(washer=12.5, groove=8.0, bulb=12.0, waist=7.5, ring=10.0, shaft=8.0)

# printing minima for a 0.4 mm nozzle
MIN = dict(plate_t=0.6, bevel=0.3, wall=0.9, web=0.8, key_d=0.9, key_slot=0.5, screw_d=0.8, neck_r=0.6,
           lever_w=1.1, lever_t=1.0, disc_r=1.2)


# ------------------------------------------------------------------ 2D helpers
def poly(pts):
    pts = [tuple(map(float, q)) for q in pts]
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return CS([pts if a > 0 else pts[::-1]])


def catmull(pts, n=12):
    """Centripetal-free uniform Catmull-Rom through pts (open), n samples per span."""
    p = np.asarray(pts, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2])
    return np.array(out)


def outline(k):
    """Escutcheon outline (CrossSection, printed mm, origin = lever axis)."""
    yh = np.array(HALF)
    sm = catmull(yh, 8)                                     # smooth the wave through the table points
    right = [(hw * k, y * k) for y, hw in sm]
    left = [(-hw * k, y * k) for y, hw in sm[::-1][1:-1]]
    r = 0.12
    return poly(right + left).offset(-r, J).offset(r, J)


# ------------------------------------------------------------------ escutcheon
def plate_dims(k):
    t = max(REAL["plate_t"] * k, MIN["plate_t"])
    bev = max(2.0 * k, MIN["bevel"])
    return t, bev


def bevelled(cs, z0, t, bev, dz=0.03):
    """Relief of height t on z0: vertical edge up to t - bev, then a 45 deg bevel (shrinking layers, no overhang)."""
    n = max(int(math.ceil(bev / dz)), 1)
    parts = [cs.extrude(t - bev + dz).translate([0, 0, z0])]
    for i in range(1, n + 1):
        d = i * bev / n
        layer = cs.offset(-d, J)
        if layer.is_empty():
            break
        parts.append(layer.extrude(bev / n + (dz if i < n else 0.0)).translate([0, 0, z0 + t - bev + (i - 1) * bev / n
                                                                                + dz * 0]))
    M = m3.Manifold.batch_boolean(parts, m3.OpType.Add)
    return M ^ m3.Manifold.cube([1000, 1000, t]).translate([-500, -500, z0])


def escutcheon(k, z0=0.0):
    t, bev = plate_dims(k)
    o = outline(k)
    plate = bevelled(o, z0, t, bev)
    top = z0 + t
    # screw heads: flat domes, clipped to the plate top (no part hangs below over the bevel)
    sd = max(8.0 * k, MIN["screw_d"])
    clip = m3.Manifold.cube([sd + 0.2, sd + 0.2, 1.0]).translate([-(sd + 0.2) / 2, -(sd + 0.2) / 2, top - 0.02])
    for x, y in SCREWS:
        dome = m3.Manifold.sphere(sd / 2, 32).scale([1, 1, 0.55]).translate([0, 0, top - 0.02])
        plate += (dome ^ clip).translate([x * k, y * k, 0])
    # Buntbart keyhole, engraved down to 0.2 mm above the door
    kd = max(10.0 * k, MIN["key_d"])
    ks = max(6.0 * k, MIN["key_slot"])
    ky = KEY_Y * k
    kl = max(20.0 * k, 2.0 * kd)
    kh = CS.circle(kd / 2, 40).translate([0, ky + (kl - kd) / 2]) + poly(
        [(-ks / 2, ky + (kl - kd) / 2), (ks / 2, ky + (kl - kd) / 2), (ks * 0.62, ky - kl / 2),
         (-ks * 0.62, ky - kl / 2)])
    plate -= kh.extrude(t).translate([0, 0, z0 + min(0.2, t / 3)])
    return plate, dict(plate_t=t, bevel=bev, screw_d=sd, key_d=kd, key_slot=ks, key_len=kl)


# ------------------------------------------------------------------ neck (baluster) + knuckle disc
def neck_profile(k, z_plate, z_top):
    """(r, z) polygon of the turned neck + disc. Rising flanks are fixed at OVERHANG_DEG, the rest stretches."""
    R = {n: max(v * k, MIN["neck_r"]) for n, v in NECK_R.items()}
    R["bulb"] = max(R["bulb"], R["groove"] + 0.15)
    R["ring"] = max(R["ring"], R["waist"] + 0.12)
    rd = max(DISC_R * k, MIN["disc_r"])
    edge, cham = 0.35, 0.12
    # (radius at end of segment, base height, kind) kind: 'v' vertical/flex, 'up' rising (fixed slope), 'dn' flex
    seg = [(R["washer"], 0.15, "v"), (R["groove"], 0.08, "dn"), (R["bulb"], 0.0, "up"), (R["bulb"], 0.12, "v"),
           (R["waist"], 0.55, "dn"), (R["ring"], 0.0, "up"), (R["ring"], 0.08, "v"), (R["shaft"], 0.12, "dn"),
           (R["shaft"], 0.1, "v"), (rd, 0.0, "up"), (rd, edge, "v"), (rd - cham, cham, "dn")]
    r0 = R["washer"]
    fixed, flex = 0.0, 0.0
    rr = r0
    for r, h, kind in seg:
        if kind == "up":
            fixed += (r - rr) / RUN
        elif kind == "dn" and h == cham and r == rd - cham:
            fixed += h
        else:
            flex += h
        rr = r
    avail = z_top - z_plate - fixed
    if avail < 0.5 * flex:
        raise ValueError(f"lever_h too low for the neck: need >= {z_plate + fixed + 0.5 * flex:.2f} mm")
    f = avail / flex
    pts = [(0.0, z_plate - 0.05), (r0, z_plate - 0.05)]
    z, rr = z_plate, r0
    pts.append((r0, z))
    for i, (r, h, kind) in enumerate(seg):
        if kind == "up":
            z += (r - rr) / RUN
        elif i == len(seg) - 1:
            z += h
        else:
            z += h * f
        pts.append((r, z))
        rr = r
    pts.append((0.0, z))
    return pts, dict(neck_min_r=min(R["groove"], R["waist"], R["shaft"]), disc_r=rd, disc_top=z)


def neck(k, z_plate, z_top):
    pts, info = neck_profile(k, z_plate, z_top)
    return m3.Manifold.revolve(CS([pts]), 96), info


# ------------------------------------------------------------------ blade + web
def _runs(mask):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def solve_web(s, L, H, bridge_max=3.0, cant_max=0.6, touch=0.3, slope=math.tan(math.radians(WEB_FLANK_DEG)),
              eps=0.02):
    """Minimal support web under a floating lever (after projects/tuerklinke-louis/mount.py, slope parameter added).

    s arc length, L web top (lever underside), H surface below. Supports where the web reaches the surface: s = 0
    (neck), where the lever already touches, plus as many as needed so that every web-free stretch is a bridge
    <= bridge_max and the free end cantilevers <= cant_max. Web bottom b = max(H, min_t(h_t + slope*|s - t|)),
    i.e. pointed arches whose flanks stand at atan(slope) to the horizontal.
    """
    sup = {0: float(L[0])}
    for i in np.nonzero(L - H <= touch)[0]:
        sup[int(i)] = float(H[i])
    for _ in range(300):
        ts = np.array(list(sup.keys()))
        hs = np.array(list(sup.values()))
        b = np.maximum(H, np.min(hs[None, :] + slope * np.abs(s[:, None] - s[ts][None, :]), axis=1))
        free = b >= L - eps
        added = False
        for i0, i1 in _runs(free):
            span = s[i1] - s[i0]
            if i1 == len(s) - 1 and span > cant_max:
                sup[len(s) - 1] = float(H[-1])
                added = True
            elif i1 < len(s) - 1 and span > bridge_max:
                mid = 0.5 * (s[i0] + s[i1])
                score = (L - H)[i0:i1 + 1] + 1e-3 * np.abs(s[i0:i1 + 1] - mid)
                i = i0 + int(np.argmin(score))
                sup[i] = float(H[i])
                added = True
        if not added:
            break
    free = b >= L - eps
    bridges = [s[i1] - s[i0] for i0, i1 in _runs(free) if i1 < len(s) - 1]
    end = [s[i1] - s[i0] for i0, i1 in _runs(free) if i1 == len(s) - 1]
    hgt = np.maximum(L - b, 0)
    metrics = dict(supports=len(sup), max_bridge=float(max(bridges + [0.0])), cantilever=float(max(end + [0.0])),
                   web_area=float((hgt * np.gradient(s)).sum()), max_web_h=float(hgt.max()))
    return b, sup, metrics


def blade_samples(k, step=0.06):
    """Resampled lever path (printed mm): columns x, y, nx, ny, w, s."""
    P = catmull(np.array(PATH) * k, 16)
    W = np.interp(np.linspace(0, len(WIDTH) - 1, len(P)), np.arange(len(WIDTH)), np.array(WIDTH) * k)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s0 = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, s0[-1], int(s0[-1] / step) + 2)
    x, y = np.interp(s, s0, P[:, 0]), np.interp(s, s0, P[:, 1])
    tip = s > 0.9 * s[-1]                                   # the pointed tip may taper below the minimum width
    w = np.where(tip, np.interp(s, s0, W), np.maximum(np.interp(s, s0, W), MIN["lever_w"]))
    w = np.maximum(w, 0.5)
    # round tip cap: semicircle over the last w_end/2 of the path
    re = w[-1] / 2
    u = np.clip((s - (s[-1] - re)) / re, 0, 1)
    w = w * np.sqrt(np.maximum(1 - u * u, 0.0))
    w[-1] = 0.05
    tx, ty = np.gradient(x), np.gradient(y)
    n = np.hypot(tx, ty)
    return np.c_[x, y, -ty / n, tx / n, w, s]


def lever_and_web(k, z_top, H_fn, ww, t_lever, bridge_max):
    step = 0.06
    P = blade_samples(k, step)
    w = P[:, 4]
    wb = np.minimum(ww, w)                                  # web / blade-bottom width
    cham = np.maximum(w - wb, 0) / 2 / RUN                  # depth of the 50 deg chamfer
    e = np.maximum(t_lever - cham, 0.25)                    # vertical front edge
    L = z_top - e - cham                                    # blade underside = web top
    H = H_fn(P[:, :2])
    b, sup, met = solve_web(P[:, 5], L, H, bridge_max=bridge_max)
    parts = []
    secs, webs = [], []
    for i in range(len(P)):
        x, y, nx, ny = P[i, :4]
        prof = [(w[i] / 2, z_top), (w[i] / 2, z_top - e[i]), (wb[i] / 2, L[i]), (wb[i] / 2, L[i] - 0.001)]
        secs.append(np.array([(x + sg * u * nx, y + sg * u * ny, z) for sg in (1, -1) for u, z in prof]))
        # sampled arch tips would be flattened by the linear interpolation: within one step of the tip the web
        # stops (its flank becomes steeper, never flatter than OVERHANG_DEG)
        # likewise every other sampled arch tip (two flanks meeting below the blade) is lifted by one step
        sl = step * math.tan(math.radians(WEB_FLANK_DEG))
        zb = b[i] - 0.01 if b[i] < L[i] - 1.25 * sl else L[i] + 0.0499
        if 0 < i < len(P) - 1 and b[i] > H[i] + 1e-3 and b[i] >= b[i - 1] and b[i] >= b[i + 1]:
            zb = min(zb + sl, L[i] + 0.0499)
        webs.append(np.array([(x + sg * wb[i] / 2 * nx, y + sg * wb[i] / 2 * ny, z) for sg in (1, -1)
                              for z in (zb, L[i] + 0.05)]))
    # blade: hulls over 3 sections (overlapping, no internal slivers); web: hulls over 2 sections (keeps the
    # 50 deg arch flanks exact, a 3-section hull would flatten the arch tips into steep facets)
    for i in range(len(secs) - 1):
        hp = m3.Manifold.hull_points(np.vstack(secs[i:i + 3]))
        if hp.volume() > 1e-6:
            parts.append(hp)
        if min(webs[i][0, 2], webs[i + 1][0, 2]) < L[i] + 0.04:
            hw = m3.Manifold.hull_points(np.vstack(webs[i:i + 2]))
            if hw.volume() > 1e-7:
                parts.append(hw)
    M = m3.Manifold.batch_boolean(parts, m3.OpType.Add)
    # bridges as built (the web stops one step before each sampled arch tip)
    free = np.array([wz[0, 2] >= L[i] + 0.04 for i, wz in enumerate(webs)])
    built = [P[i1, 5] - P[i0, 5] + step for i0, i1 in _runs(free) if i1 < len(P) - 1]
    met["max_bridge"] = max(met["max_bridge"], float(max(built + [0.0])))
    comps = sorted(M.decompose(), key=lambda q: -abs(q.volume()))
    assert all(abs(q.volume()) < 1e-4 for q in comps[1:]), [q.volume() for q in comps]
    M = comps[0]                                            # drop numerically empty slivers / voids
    met.update(lever_w_min=float(w[P[:, 5] <= 0.9 * P[-1, 5]].min()), tip_w=float(w[P[:, 5] <= 0.97 * P[-1, 5]][-1]),
               lever_t=float((z_top - L).min()),
               web_w=float(ww), lever_len_path=float(P[-1, 5]))
    return M, met, P, L, b


# ------------------------------------------------------------------ assembly
def _inside(cs, xy):
    from matplotlib.path import Path as MPath
    res = np.zeros(len(xy), bool)
    for pg in cs.to_polygons():
        res ^= MPath(np.asarray(pg)).contains_points(xy)
    return res


def overhang_check(M, surface=None, bed_eps=0.3):
    """Downward faces above the bed (or above the door surface): area steeper than 45 deg, split into horizontal
    bridges and the rest."""
    from tdg import mesh
    tm = mesh.manifold_to_trimesh(M)
    n, a = tm.face_normals, tm.area_faces
    c = tm.triangles_center
    zc = c[:, 2] - (surface(c[:, :2]) if surface else tm.bounds[0, 2])
    down = (n[:, 2] < -math.cos(math.radians(45)) + 1e-6) & (zc > bed_eps)
    down &= a > 1e-6                                        # numerically empty faces of the layer stack
    flat = down & (n[:, 2] < -0.97)                        # bridge (within 14 deg of horizontal)
    rest = down & ~flat
    worst = round(math.degrees(math.acos(min(1.0, float(-n[rest, 2].min())))), 2) if rest.any() else None
    return dict(over45_mm2=round(float(a[down].sum()), 4), bridge_mm2=round(float(a[flat].sum()), 4),
                over45_non_bridge_mm2=round(float(a[rest].sum()), 4), flattest_non_bridge_deg_to_horizontal=worst)


def build_handle(scale=1 / 12, hand="rechts", lever_h=None, surface=None, bridge_max=3.0):
    """Dollhouse lever handle. Returns (Manifold, info); frame see module docstring.

    lever_h: height of the blade top above the door (printed mm), default 0.75 x real projection, >= 3.6.
    surface: optional f(xy[N,2]) -> door height (printed mm) for non-flat doors; the escutcheon sits on the highest
    point of its footprint and is filled down to the lowest one, the web reaches down to the surface.
    """
    k = float(scale)
    if hand not in ("rechts", "links"):
        raise ValueError("hand must be 'rechts' or 'links'")
    surf = surface or (lambda xy: np.zeros(len(np.atleast_2d(xy))))
    o = outline(k)
    # base height on non-flat doors
    bb = o.bounds()
    gx, gy = np.meshgrid(np.linspace(bb[0], bb[2], 25), np.linspace(bb[1], bb[3], 80))
    g = np.c_[gx.ravel(), gy.ravel()]
    g = g[_inside(o, g)]
    sx = -1.0 if hand == "links" else 1.0
    hz = surf(g * [sx, 1])
    z0 = float(hz.max()) if surface else 0.0
    E, einfo = escutcheon(k, z0)
    if surface and hz.max() - hz.min() > 0.01:
        gap = float(hz.max() - hz.min())
        E += o.extrude(gap + 0.05).translate([0, 0, z0 - gap - 0.05])
    t_plate = einfo["plate_t"]
    if lever_h is None:
        lever_h = max(0.75 * REAL["projection"] * k, 3.6)
    z_top = z0 + lever_h
    N, ninfo = neck(k, z0 + t_plate, z_top + 0.1)
    inner = o.offset(-einfo["bevel"] - 0.05, J)

    def H_fn(xy):
        return surf(xy * [sx, 1]) + np.where(_inside(inner, xy), z0 + t_plate - surf(xy * [sx, 1]), 0.0) * 1.0

    t_lever = MIN["lever_t"]
    ww = MIN["web"]
    B, met, P, L, b = lever_and_web(k, z_top, H_fn, ww, t_lever, bridge_max)
    M = m3.Manifold.batch_boolean([E, N, B], m3.OpType.Add)
    if not surface:                                         # flat door: nothing below the door surface
        M = M ^ m3.Manifold.cube([200, 200, 100]).translate([-100, -100, 0])
    comps = M.decompose()
    assert len(comps) == 1, f"handle falls apart into {len(comps)} bodies"
    if hand == "links":
        M = M.mirror([1, 0, 0])
    box = M.bounding_box()
    ob = o.bounds()
    oc = overhang_check(M, surface)
    info = dict(
        scale=f"1:{1 / k:.0f}" if abs(1 / k - round(1 / k)) < 1e-6 else round(k, 5), hand=hand,
        escutcheon_bbox_mm=[round(min(sx * ob[0], sx * ob[2]), 3), round(ob[1], 3),
                            round(max(sx * ob[0], sx * ob[2]), 3), round(ob[3], 3)],
        escutcheon_size_mm=[round(ob[2] - ob[0], 2), round(ob[3] - ob[1], 2)],
        lever_len_mm=round(max(abs(box[0]), abs(box[3])), 2), projection_mm=round(box[5], 2),
        lever_top_mm=round(z_top, 3), key_dist_mm=round(-KEY_Y * k, 2), bbox_mm=[round(v, 3) for v in box],
        min_features_mm=dict(plate_t=round(t_plate, 2), bevel=round(einfo["bevel"], 2),
                             screw_d=round(einfo["screw_d"], 2), keyhole_d=round(einfo["key_d"], 2),
                             keyhole_slot=round(einfo["key_slot"], 2), neck_d=round(2 * ninfo["neck_min_r"], 2),
                             disc_d=round(2 * ninfo["disc_r"], 2), lever_w=round(met["lever_w_min"], 2),
                             lever_t=round(met["lever_t"], 2), lever_tip_w=round(met["tip_w"], 2),
                             web=round(met["web_w"], 2)),
        web=dict(supports=met["supports"], max_bridge_mm=round(met["max_bridge"], 2),
                 cantilever_mm=round(met["cantilever"], 2), web_area_mm2=round(met["web_area"], 2),
                 max_web_h_mm=round(met["max_web_h"], 2), bridge_max_mm=bridge_max),
        overhang=dict(design_deg=OVERHANG_DEG, **oc),
        volume_mm3=round(M.volume(), 2),
    )
    return M, info


def details_ok(info, nozzle=0.4):
    f = info["min_features_mm"]
    return dict(plate=f["plate_t"] >= 1.5 * nozzle - 1e-9, screw=f["screw_d"] >= 1.25 * nozzle,
                keyhole=f["keyhole_slot"] >= 1.1 * nozzle and f["keyhole_d"] >= 2 * nozzle,
                neck=f["neck_d"] >= 3 * nozzle, lever_w=f["lever_w"] >= 2.5 * nozzle,
                lever_t=f["lever_t"] >= 0.9, web=f["web"] >= 2 * nozzle,
                bridge=info["web"]["max_bridge_mm"] <= info["web"]["bridge_max_mm"] + 1e-6,
                cantilever=info["web"]["cantilever_mm"] <= 0.6 + 1e-6,
                overhang=info["overhang"]["over45_non_bridge_mm2"] <= 0.05)


def probe(R, L, size=30.0, t=1.2):
    """Both handles on a 30 x 30 x 1.2 test plate (chamfered top edge)."""
    blk = m3.Manifold.batch_hull([m3.Manifold.cube([size, size, t - 0.4]).translate([-size / 2, -size / 2, 0]),
                                  m3.Manifold.cube([size - 0.8, size - 0.8, t]).translate(
                                      [-size / 2 + 0.4, -size / 2 + 0.4, 0])])
    rb, lb = R.bounding_box(), L.bounding_box()
    dy = -(rb[1] + rb[4]) / 2
    xr = -size / 2 + 0.9 - rb[0]
    xl = size / 2 - 0.9 - lb[3]
    return blk + R.translate([xr, dy, t - 0.05]) + L.translate([xl, dy, t - 0.05])


# ------------------------------------------------------------------ outputs
def generate(out_dir: Path, scale=1 / 12, material="PLA", previews=True, render_path=None):
    from tdg import check, mesh
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    R, info_r = build_handle(scale, "rechts")
    L, info_l = build_handle(scale, "links")
    ok = details_ok(info_r)
    assert all(ok.values()), f"handle not printable with a 0.4 mm nozzle: {ok} {info_r}"
    reps = {}
    for name, M, inf in (("griff_rechts", R, info_r), ("griff_links", L, info_l)):
        tm = mesh.manifold_to_trimesh(M)
        mesh.export(tm, str(out_dir / name))
        rep = check.report(tm, material, extra=dict(handle=inf))
        check.assert_printable(rep)
        reps[name] = rep
    T = mesh.manifold_to_trimesh(probe(R, L))
    mesh.export(T, str(out_dir / "griff_probe"), formats=("3mf",))
    rep_t = check.report(T, material)
    check.assert_printable(rep_t)
    reps["griff_probe"] = rep_t
    summary = dict(handle=info_r, details_ok=ok, parts=reps)
    check.write(summary, str(out_dir / "griff_report.json"))
    if previews:
        render(R, render_path or (out_dir / "griff_vorschau.png"))
    return summary


def render(M, path, compare=True):
    """Front (as seen on the door) next to the reference photos, oblique, side and overhang map."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from tdg import mesh
    from tdg.render import draw, overhang_colors, shade
    tm = mesh.manifold_to_trimesh(M)
    tl = mesh.manifold_to_trimesh(M.mirror([1, 0, 0]))
    light = (0.25, 0.45, 0.85)
    fig = plt.figure(figsize=(20, 11), facecolor="white")
    ref = HERE / "reference"
    tiles = []
    if compare:
        from PIL import Image
        p2 = Image.open(ref / "02_wohnungstuer_spion_briefschlitz.jpg").crop((500, 1090, 680, 1300))
        p1 = Image.open(ref / "01_drueckergarnitur_barock.jpg").crop((100, 440, 960, 1500))
        tiles += [("img", p2, "Foto 02 (fast frontal)"), ("3d", (tm, 90, -90, False), "Modell rechts, Front"),
                  ("img", p1, "Foto 01 (schräg)"), ("3d", (tl, 38, -125, False), "Modell links, schräg wie Foto 01")]
    tiles += [("3d", (tm, 35, -60, False), "schräg"), ("3d", (tm, 0, -90, False), "Seite (Ausladung, Steg)"),
              ("3d", (tm, -35, -60, True), "Überhänge von unten (orange > 45°, rot > 60°)"),
              ("3d", (tm, 90, -90, True), "Überhänge, Front")]
    for i, (kind, obj, title) in enumerate(tiles):
        if kind == "img":
            ax = fig.add_subplot(2, 4, i + 1)
            ax.imshow(obj)
            ax.set_axis_off()
        else:
            m, el, az, ov = obj
            ax = fig.add_subplot(2, 4, i + 1, projection="3d")
            draw(ax, m, overhang_colors(m) if ov else shade(m, light=light), el, az, zoom=1.25)
        ax.set_title(title)
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    import json
    s = generate(HERE / "out", render_path=sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(dict(handle=s["handle"], ok=s["details_ok"]), indent=1))
