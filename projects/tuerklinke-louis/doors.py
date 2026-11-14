"""
Real cabinet doors from the user's boiserie panels, ready-to-print Bambu Lab A1 mini plates (180 x 180 mm).

Pipeline per door: load the panel 3MF (panels.load_panels, relief up), scale non-uniformly in x/y to the door size
(z unchanged, like scaling in Bambu Studio), then either
  * knob door : find the flat knob site near the handle edge (panels.find_knob_site, rosette 1.25 x bulb), cut the
                d3.4 plug hole (panels.cut_hole) and plan a plug knob (knob.plug_knob) + rivet pin (knob.rivet_pin)
                whose shaft length follows the door thickness at the site, or
  * lever door: find the flat strip for the Langschild (panels.find_lever_site), scale the handle so that the
                escutcheon fills the strip width minus lever_strip_clear, mount it conforming to the relief
                (generate.mount_lever) and unite it with the door (one body, printed in one piece).
Plates: shelf layout centred on the bed, >= bed_margin to the bed edge and >= obj_gap between object bounding boxes;
each plate = one 3MF with separate objects + top-view preview PNG + JSON report.

LICENSE: the panels are MakerWorld Exclusive (designer cynsight). Every output of this script derives from them and
goes to out_private/ (git-ignored). Never commit those files.

Coordinates: mm, z = 0 = print bed = back of the door (inside of the cabinet), relief / knob side up.
"""
from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import manifold3d as m3  # noqa: E402

import generate as G  # noqa: E402
import knob as K  # noqa: E402
import mount  # noqa: E402
import panels  # noqa: E402

from tdg import check, cli, mesh  # noqa: E402

DEFAULT_3MF = "/root/.claude/uploads/759c5b22-262f-531f-bd38-4ebb40fa429a/c27ea80f-Four_Boisserie_Panels.3mf"


@dataclass
class Params:
    # --- gemessen (Nutzerangaben / Messung am 3MF)
    panels_3mf: str = DEFAULT_3MF
    big_w: float = 145.0          # waagrechte Tür, lange Kante horizontal
    big_h: float = 89.5
    up_w: float = 76.0            # hochkante Tür mit Klinke
    up_h: float = 121.0
    small_w: float = 81.0         # kleine waagrechte Tür
    small_h: float = 52.0
    double_w: float = 174.0       # Doppeltür, Gesamtbreite (Schranköffnung)
    double_h: float = 121.0
    # --- ANGENOMMEN (messen!)
    double_gap: float = 0.8       # Mittelfuge der Doppeltür
    knob_size_per_h: float = 0.14  # bulb_d = clamp(knob_size_per_h * door_h, knob_d_min, knob_d_max)
    knob_d_min: float = 9.0
    knob_d_max: float = 17.0
    big_variants: str = "olive,melon,perle,eichel,zapfen,krone"   # Knauf-Auswahl für die 145er-Tür
    small_variant: str = "perle"  # Knauf je 81 x 52-Tür
    double_variant: str = "olive"
    lever_k: float = 0.0          # Klinken-Skalierung, 0 = Schild füllt den flachen Streifen
    lever_strip_clear: float = 1.0  # Schildbreite = Streifenbreite - dies
    # --- Passung & Druck
    hole_d: float = K.HOLE_D
    bed: float = 180.0
    bed_margin: float = 3.0
    obj_gap: float = 4.0
    lever_voxel: float = 0.05     # SDF-Auflösung des Hebels in mm
    bridge_max: float = 3.0
    knob_res: str = "fine"
    material: str = "PLA"
    plates: str = "all"           # Auswahl, z. B. "P1,P2"
    previews: bool = True


# --------------------------------------------------------------------------------------------- doors
def bulb_for(p, door_h):
    return float(np.clip(round(2 * p.knob_size_per_h * door_h) / 2, p.knob_d_min, p.knob_d_max))


def make_door(panel, panel_name, w, h, upright=False, mirror_x=False, name=None):
    """Scaled door (dict). Scale factors relative to the laid-flat panel (long side x)."""
    tm = panels.fit(panel, w, h, upright=upright, mirror_x=mirror_x)
    ex = panel.extents
    sx, sy = (w / ex[1], h / ex[0]) if upright else (w / ex[0], h / ex[1])
    return dict(name=name or f"{panel_name}_{w:g}x{h:g}", panel=panel_name, mesh=tm, w=w, h=h, upright=upright,
                mirror_x=mirror_x, scale_x=round(sx, 4), scale_y=round(sy, 4),
                distortion=round(max(sx, sy) / min(sx, sy), 3), thickness_max=round(float(tm.extents[2]), 2))


def plan_knob(door, p, edge, variants, along=0.5):
    """Flat knob site closest to `edge` for the planned bulb (shrinks the bulb if no flat site exists)."""
    tm = door["mesh"]
    hm = panels.heightmap(tm)
    d = bulb_for(p, door["h"])                 # door height = vertical edge as mounted
    while True:
        ros = 1.25 * d
        s = panels.find_knob_site(tm, ros, edge=edge, along=along, hm=hm)
        if s is not None or d <= p.knob_d_min - 1e-9:
            break
        d -= 0.5
    assert s is not None, f"{door['name']}: no flat site for a knob rosette >= {1.25 * p.knob_d_min:.1f} mm"
    t = panels.thickness_at(tm, s["x"], s["y"])
    site = {k: s[k] for k in ("x", "y", "z", "dist_from_edge", "gap_rosette_to_edge", "ptp", "level_name",
                              "max_rosette_d_here", "edge")}
    site["strips"] = s["strips"]
    door["knob"] = dict(site=site, bulb_d=d, rosette_d=round(1.25 * d, 2), door_t=round(t, 2),
                        variants=list(variants))
    return door


def cut_knob_hole(door, p):
    s = door["knob"]["site"]
    door["mesh"], info = panels.cut_hole(door["mesh"], s["x"], s["y"], d=p.hole_d)
    door["knob"]["hole"] = info
    return door


def _clean_manifold(tm):
    M = mesh.trimesh_to_manifold(tm)
    assert M.status() == m3.Error.NoError, M.status()
    parts = [q for q in M.decompose() if q.volume() > 1e-3]
    return m3.Manifold.compose(parts) if len(parts) > 1 else parts[0]


def lever_k_for(door, p, edge="right", k_min=1.0, k_field=1.65):
    """Handle scale so that the escutcheon (5.6 x 22 reference units) fills the closest flat strip at `edge` minus
    lever_strip_clear. If that strip is too narrow for the details (k < k_min, see generate.details_ok) or there is
    only a wide field, k = k_field and the escutcheon goes into the field. Returns (k, site, how)."""
    tm = door["mesh"]
    hm = panels.heightmap(tm)
    if p.lever_k > 0:
        return p.lever_k, panels.find_lever_site(tm, 5.6 * p.lever_k, 22 * p.lever_k, edge=edge, hm=hm), \
            dict(mode="fest (lever_k)", k_strip=None, strip_w=None)
    # start with the smallest acceptable plate (k_min + clearance): skips strips that are too narrow anyway
    k, s, k_strip = k_min + p.lever_strip_clear / 5.6, None, None
    for _ in range(8):
        s = panels.find_lever_site(tm, 5.6 * k, 22.0 * k, edge=edge, hm=hm)
        if s is None or s["max_plate_w"] > 25:              # nothing, or a wide field: no strip to fill
            break
        k_new = (s["max_plate_w"] - p.lever_strip_clear) / 5.6
        if abs(k_new - k) < 0.01:
            k_strip = k = k_new
            break
        k = k_new
    else:
        k_strip = k
    strip_w = None if s is None or s["max_plate_w"] > 25 else s["max_plate_w"]
    if k_strip is None or k_strip < k_min:
        how = dict(mode="feld (kein Streifen breit genug)", k_strip=None if k_strip is None else round(k_strip, 3),
                   strip_w=strip_w)
        k = k_field
    else:
        how = dict(mode="streifen gefuellt", k_strip=round(k_strip, 3), strip_w=strip_w)
    site = panels.find_lever_site(tm, 5.6 * k, 22.0 * k, edge=edge, hm=hm)
    assert site is not None, f"{door['name']}: no flat place for the escutcheon at k={k:.2f}"
    return k, site, how


def mount_lever_on_door(door, p, k, site, hand="links", field_inset=1.0):
    """Unite a conforming lever handle with the door. In a strip the escutcheon is centred in the strip; in a
    wide field (strip_len > 5 mm) it goes to the closest feasible position + field_inset towards the centre."""
    if site["strip_len"] > 5.0:
        x, y = site["closest"]
        x += -field_inset if site["edge"] == "right" else field_inset
        mode = "feld, randnah"
    else:
        x, y = site["x"], site["y"]
        mode = "streifen, zentriert"
    gp = G.Params(voxel=p.lever_voxel, bridge_max=p.bridge_max, lever_len=0.0, material=p.material)
    at = (x, y + G.BOSS_Y * k)
    L, info = G.mount_lever(gp, door["mesh"], at, hand, k=k, embed=0.1)
    ok = G.details_ok(info, gp.nozzle)
    assert all(ok.values()), (door["name"], ok, info)
    D = _clean_manifold(door["mesh"]) + L
    parts = D.decompose()
    assert len(parts) == 1, f"{door['name']}: door + lever is {len(parts)} bodies"
    door["mesh"] = mesh.manifold_to_trimesh(D)
    lever_tm = mesh.manifold_to_trimesh(L)
    info = {k_: v for k_, v in info.items() if k_ != "lever_len_search"} | dict(
        lever_len_search={str(a): b for a, b in info["lever_len_search"].items()})
    door["lever"] = dict(k=round(k, 3), mode=mode, plate_center=(round(x, 2), round(y, 2)),
                         dist_plate_center_from_edge=round(door["w"] - x if site["edge"] == "right" else x, 2),
                         plate_mm=(round(5.6 * k, 2), round(22 * k, 2)),
                         plate_h_pct_of_door=round(100 * 22 * k / door["h"], 1), site=site, info=info,
                         details_ok={a: bool(b) for a, b in ok.items()},
                         lever_report=check.report(lever_tm, p.material))
    door["lever_mesh"] = lever_tm
    return door


# --------------------------------------------------------------------------------------------- knobs + pins
def build_knob(variant, bulb_d, rosette_d, res):
    M, info = K.plug_knob(variant, bulb_d, rosette_d, res=res)
    return mesh.manifold_to_trimesh(M), info


def knob_items(doors, p, cache):
    """(name, trimesh, info) for every knob variant of every knob door + one pin per knob."""
    items = []
    for d in doors:
        kn = d.get("knob")
        if not kn:
            continue
        for v in kn["variants"]:
            key = (v, kn["bulb_d"], kn["rosette_d"])
            if key not in cache:
                cache[key] = build_knob(v, kn["bulb_d"], kn["rosette_d"], p.knob_res)
            tm, info = cache[key]
            items.append((f"knauf_{v}_{kn['bulb_d']:g}__{d['name']}", tm, dict(knob=info, door=d["name"])))
            P, pinfo = K.rivet_pin(kn["door_t"])
            items.append((f"stift_t{kn['door_t']:g}__{d['name']}_{v}", mesh.manifold_to_trimesh(P),
                          dict(pin=pinfo, door=d["name"])))
    return items


# --------------------------------------------------------------------------------------------- layout
def _rot_z90(tm):
    t = tm.copy()
    t.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 0, 1]))
    return t


def shelf_layout(items, bed=180.0, margin=3.0, gap=4.0, sort=True):
    """Place (name, trimesh, info) in rows (bbox based), centred on the bed. Returns [(name, tm, info)] moved to
    bed coordinates. Raises AssertionError if they do not fit."""
    use = bed - 2 * margin
    order = sorted(items, key=lambda it: -it[1].extents[1]) if sort else list(items)
    placed, x, y, row_h = [], 0.0, 0.0, 0.0
    for name, tm, info in order:
        w, h = tm.extents[0], tm.extents[1]
        assert w <= use + 1e-6 and h <= use + 1e-6, f"{name} ({w:.1f} x {h:.1f}) larger than the bed area"
        if x > 0 and x + w > use + 1e-6:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        placed.append((name, tm, info, x, y))
        x, row_h = x + w + gap, max(row_h, h)
    W = max(px + tm.extents[0] for _, tm, _, px, _ in placed)
    Hh = max(py + tm.extents[1] for _, tm, _, _, py in placed)
    assert W <= use + 1e-6 and Hh <= use + 1e-6, f"layout {W:.1f} x {Hh:.1f} exceeds {use:.1f} x {use:.1f}"
    ox, oy = (bed - W) / 2, (bed - Hh) / 2
    out = []
    for name, tm, info, px, py in placed:
        t = tm.copy()
        t.apply_translation([ox + px - t.bounds[0, 0], oy + py - t.bounds[0, 1], -t.bounds[0, 2]])
        out.append((name, t, info))
    return out


def bed_check(objs, bed=180.0, margin=3.0, gap=4.0):
    """Every object within [margin, bed - margin], z >= 0, pairwise bbox distance >= gap."""
    res = dict(bed_mm=bed, margin_mm=margin, gap_mm=gap, objects={})
    ok = True
    for name, tm, _ in objs:
        lo, hi = tm.bounds
        inside = bool(lo[0] >= margin - 1e-6 and lo[1] >= margin - 1e-6 and hi[0] <= bed - margin + 1e-6
                      and hi[1] <= bed - margin + 1e-6 and abs(lo[2]) < 1e-6 and hi[2] <= bed)
        res["objects"][name] = dict(lo=np.round(lo, 2).tolist(), hi=np.round(hi, 2).tolist(), inside=inside)
        ok &= inside
    dmin = math.inf
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i][1].bounds, objs[j][1].bounds
            dx = max(b[0, 0] - a[1, 0], a[0, 0] - b[1, 0], 0.0)
            dy = max(b[0, 1] - a[1, 1], a[0, 1] - b[1, 1], 0.0)
            dmin = min(dmin, math.hypot(dx, dy) if dx > 0 and dy > 0 else max(dx, dy))
    res["min_gap_mm"] = round(dmin, 2) if dmin < math.inf else None
    ok &= dmin >= gap - 1e-6
    res["ok"] = bool(ok)
    return res


# --------------------------------------------------------------------------------------------- render
def hillshade(H, h, light=(-0.45, 0.55, 0.7)):
    gx, gy = np.gradient(H, h)
    n = np.dstack([-gx, -gy, np.ones_like(H)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    L = np.asarray(light, float) / np.linalg.norm(light)
    return np.clip(n @ L, 0, 1)


def top_image(meshes_colors, lo, hi, h=0.25):
    """RGB top view: each (trimesh, rgb) rasterised, the highest surface wins, hill-shaded."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    Hs, cols = [], []
    for tm, c in meshes_colors:
        hm = mount.HeightMap(tm, lo, hi, h)
        H = hm.H.copy()
        H[H <= float(tm.bounds[0, 2]) + 1e-9] = -1.0
        Hs.append(H)
        cols.append(c)
    Hs = np.stack(Hs)
    top = Hs.max(0)
    idx = Hs.argmax(0)
    shade = hillshade(np.maximum(top, 0), h)
    rgb = np.ones(top.shape + (3,))
    C = np.asarray(cols, float)[idx]
    covered = top > -0.5
    rgb[covered] = C[covered] * (0.3 + 0.7 * shade[covered, None])
    return np.transpose(rgb, (1, 0, 2))           # rows = y


WOOD, GOLD, PIN = (0.86, 0.72, 0.52), (0.85, 0.68, 0.25), (0.6, 0.6, 0.65)


def plate_png(objs, png, title, bed=180.0, margin=3.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    mc = [(tm, GOLD if n.startswith("knauf") else PIN if n.startswith(("stift", "fit")) else WOOD)
          for n, tm, _ in objs]
    img = top_image(mc, (0, 0), (bed, bed), h=0.25)
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img, origin="lower", extent=(0, bed, 0, bed))
    ax.add_patch(Rectangle((0, 0), bed, bed, fill=False, color="k", lw=1.5))
    ax.add_patch(Rectangle((margin, margin), bed - 2 * margin, bed - 2 * margin, fill=False, color="0.5", ls="--"))
    for n, tm, _ in objs:
        if n.startswith(("stift",)):
            continue
        c = tm.bounds.mean(0)
        ax.text(c[0], tm.bounds[0, 1] + 1, n.split("__")[0], ha="center", va="bottom", fontsize=6,
                bbox=dict(fc="white", alpha=0.6, lw=0))
    ax.set_xlim(-2, bed + 2)
    ax.set_ylim(-2, bed + 2)
    ax.set_title(f"{title}  (A1 mini {bed:g} x {bed:g} mm, gestrichelt: {margin:g} mm Rand)")
    fig.savefig(png, dpi=110)
    plt.close(fig)


def seated_knob(door, knob_tm):
    """Knob mesh moved onto the door's hole (rosette bottom on the door front at the site)."""
    s = door["knob"]["site"]
    t = knob_tm.copy()
    t.apply_translation([s["x"], s["y"], s["z"]])
    return t


def montage_png(groups, knob_side, png):
    """groups: [(title, [(door, knob_tm or None, dx)])]; knob_side: [(title, knob_tm)] side views."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(groups)
    fig = plt.figure(figsize=(6 * n, 11))
    for gi, (title, members) in enumerate(groups):
        mcs = []
        for door, ktm, dx in members:
            d = door["mesh"].copy()
            d.apply_translation([dx, 0, 0])
            mcs.append((d, WOOD))
            if door.get("lever_mesh") is not None:
                lv = door["lever_mesh"].copy()
                lv.apply_translation([dx, 0, 0.02])
                mcs.append((lv, GOLD))
            if ktm is not None:
                k = seated_knob(door, ktm)
                k.apply_translation([dx, 0, 0])
                mcs.append((k, GOLD))
        lo = np.min([m.bounds[0, :2] for m, _ in mcs], 0) - 2
        hi = np.max([m.bounds[1, :2] for m, _ in mcs], 0) + 2
        img = top_image(mcs, lo, hi, h=0.2)
        ax = fig.add_subplot(2, n, gi + 1)
        ax.imshow(img, origin="lower", extent=(lo[0], hi[0], lo[1], hi[1]))
        ax.set_title(title, fontsize=10)
        ax.set_aspect("equal")
    m = len(knob_side)
    for i, (title, ktm) in enumerate(knob_side):
        t = ktm.copy()
        t.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))   # z(knob) -> y
        t.apply_translation(-t.bounds[0])
        t.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))       # view from -y side
        t.apply_translation(-t.bounds[0])
        img = top_image([(t, GOLD)], (-1, -1), t.bounds[1, :2] + 1, h=0.05)
        ax = fig.add_subplot(2, m, m + i + 1)
        ax.imshow(img, origin="lower", extent=(-1, t.bounds[1, 0] + 1, -1, t.bounds[1, 1] + 1))
        ax.set_title(title, fontsize=8)
        ax.set_aspect("equal")
    fig.subplots_adjust(left=0.03, right=0.99, bottom=0.04, top=0.92, wspace=0.25, hspace=0.25)
    fig.suptitle("Montageübersicht: Türen von vorn mit Knauf/Klinke (Holzton = Paneel, gold = Beschlag); "
                 "unten Knaufvarianten seitlich", fontsize=12)
    fig.savefig(png, dpi=100)
    plt.close(fig)


# --------------------------------------------------------------------------------------------- plates
def door_entry(door):
    e = {k: door[k] for k in ("name", "panel", "w", "h", "upright", "mirror_x", "scale_x", "scale_y", "distortion",
                              "thickness_max")}
    if "knob" in door:
        e["knob"] = door["knob"]
    if "lever" in door:
        e["lever"] = door["lever"]
    return e


def write_plate(name, objs, p, out_dir, extra=None, expected_bodies=None):
    """3MF (separate objects) + PNG + JSON with check.report of every object and the bed check."""
    expected_bodies = expected_bodies or {}
    reps = {}
    for n, tm, _ in objs:
        r = check.report(tm, p.material)
        check.assert_printable(r, bodies=expected_bodies.get(n, 1))
        reps[n] = r
    bc = bed_check(objs, p.bed, p.bed_margin, p.obj_gap)
    assert bc["ok"], json.dumps(bc, indent=1)
    sc = trimesh.Scene()
    for n, tm, _ in objs:
        sc.add_geometry(tm, node_name=n, geom_name=n)
    path = out_dir / f"{name}.3mf"
    sc.export(str(path))
    if p.previews:
        plate_png(objs, out_dir / f"{name}.png", name, p.bed, p.bed_margin)
    rep = dict(plate=name, file=path.name, file_mb=round(path.stat().st_size / 1e6, 2), bed_check=bc,
               objects={n: dict(report=reps[n], **{k: v for k, v in info.items() if k != "door_obj"})
                        for n, tm, info in objs})
    if extra:
        rep.update(extra)
    check.write(rep, str(out_dir / f"{name}_report.json"))
    return rep


def run(p: Params, out_dir: Path):
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    sel = None if p.plates == "all" else set(p.plates.split(","))
    want = (lambda k: sel is None or k in sel)  # noqa: E731
    P = panels.load_panels(p.panels_3mf, names={"kartusche", "rechteck", "achteck"})
    timing = dict(load_s=round(time.time() - t0, 1))
    big_var = [v.strip() for v in p.big_variants.split(",") if v.strip()]
    summary, knob_doors, montage = dict(params=asdict(p), plates={}), [], []

    def knob_door(panel_name, w, h, edge, variants, upright=False, mirror_x=False, name=None):
        d = make_door(P[panel_name], panel_name, w, h, upright, mirror_x, name)
        plan_knob(d, p, edge, variants)
        cut_knob_hole(d, p)
        knob_doors.append(d)
        return d

    def lever_door(panel_name, w, h):
        d = make_door(P[panel_name], panel_name, w, h, upright=True)
        kk, site, how = lever_k_for(d, p, "right")
        mount_lever_on_door(d, p, kk, site, hand="links")
        d["lever"]["k_choice"] = how
        return d

    def obj(d, rotate=False):
        tm = _rot_z90(d["mesh"]) if rotate else d["mesh"]
        return (f"tuer_{d['name']}", tm, dict(door=door_entry(d), rotated_on_bed_deg=90 if rotate else 0))

    k_p1 = None
    if want("P1"):
        t = time.time()
        a = knob_door("kartusche", p.big_w, p.big_h, "right", big_var)
        b = lever_door("rechteck", p.up_w, p.up_h)
        k_p1 = b["lever"]["k"]
        objs = shelf_layout([obj(a), obj(b, rotate=True)], p.bed, p.bed_margin, p.obj_gap, sort=False)
        summary["plates"]["P1"] = write_plate("plate1_145x89_kartusche_76x121_klinke", objs, p, out_dir)
        montage += [("P1: Kartusche 145 x 89,5", [(a, None, 0)]), ("P1: Rechteck 76 x 121 + Klinke", [(b, None, 0)])]
        timing["P1_s"] = round(time.time() - t, 1)
    if want("P1b"):
        t = time.time()
        a = knob_door("rechteck", p.big_w, p.big_h, "right", [big_var[0]])
        d = make_door(P["kartusche"], "kartusche", p.up_w, p.up_h, upright=True)
        k_auto, _, how = lever_k_for(d, p, "right")
        field = how["mode"].startswith("feld")
        k = k_p1 if (field and k_p1) else k_auto
        site = panels.find_lever_site(d["mesh"], 5.6 * k, 22 * k, edge="right")
        mount_lever_on_door(d, p, k, site, hand="links")
        d["lever"]["k_choice"] = how
        if field:
            d["lever"]["note"] = (f"kein flacher Randstreifen breit genug (Streifen {how['strip_w']} mm, k "
                                  f"{how['k_strip']} < 1,0 waere zu fein fuer 0,4-mm-Duese); Schild randnah ins glatte "
                                  f"Mittelfeld, k={k:.3f}" + (" wie P1" if k == k_p1 else ""))
        objs = shelf_layout([obj(a), obj(d, rotate=True)], p.bed, p.bed_margin, p.obj_gap, sort=False)
        summary["plates"]["P1b"] = write_plate("plate1b_145x89_rechteck_76x121_kartusche_klinke", objs, p, out_dir)
        montage += [("P1b: Rechteck 145 x 89,5", [(a, None, 0)]), ("P1b: Kartusche 76 x 121 + Klinke",
                                                                     [(d, None, 0)])]
        timing["P1b_s"] = round(time.time() - t, 1)
    if want("P2"):
        t = time.time()
        sv = [p.small_variant]
        ds = [knob_door("kartusche", p.small_w, p.small_h, "right", sv),
              knob_door("rechteck", p.small_w, p.small_h, "right", sv),
              knob_door("achteck", p.small_w, p.small_h, "right", sv),
              knob_door("kartusche", p.small_w, p.small_h, "left", sv, mirror_x=True,
                        name=f"kartusche_{p.small_w:g}x{p.small_h:g}_gespiegelt")]
        objs = shelf_layout([obj(d) for d in ds], p.bed, p.bed_margin, p.obj_gap, sort=False)
        summary["plates"]["P2"] = write_plate("plate2_81x52_vier", objs, p, out_dir)
        montage.append(("P2: 4 x 81 x 52", [(d, None, i * (p.small_w + 6)) for i, d in enumerate(ds[:2])]))
        montage.append(("P2: 4 x 81 x 52 (Forts.)", [(d, None, i * (p.small_w + 6)) for i, d in enumerate(ds[2:])]))
        timing["P2_s"] = round(time.time() - t, 1)
    if want("P3"):
        t = time.time()
        lw = (p.double_w - p.double_gap) / 2
        L = knob_door("achteck", lw, p.double_h, "right", [p.double_variant], upright=True,
                      name=f"achteck_{lw:g}x{p.double_h:g}_links")
        R = knob_door("achteck", lw, p.double_h, "left", [p.double_variant], upright=True, mirror_x=True,
                      name=f"achteck_{lw:g}x{p.double_h:g}_rechts")
        extra = dict(leaf_mm=[round(lw, 2), p.double_h], centre_gap_mm=p.double_gap,
                     note="zwei Flügel passen nicht mit 3 mm Rand + 4 mm Abstand auf ein 180er Bett (2 x "
                          f"{lw:.1f} + 4 = {2 * lw + 4:.1f} > {p.bed - 2 * p.bed_margin:g}): je Flügel eine Platte")
        for tag, d in (("a_links", L), ("b_rechts", R)):
            objs = shelf_layout([obj(d)], p.bed, p.bed_margin, p.obj_gap)
            summary["plates"][f"P3{tag[0]}"] = write_plate(f"plate3{tag}_doppeltuer_174x121", objs, p, out_dir,
                                                           extra=extra)
        montage.append(("P3: Doppeltür 174 x 121", [(L, None, 0), (R, None, lw + p.double_gap)]))
        timing["P3_s"] = round(time.time() - t, 1)
    if want("PH"):                                     # horizontal doors, knob fused on: one 3MF per door
        t = time.time()
        sv = [p.small_variant]
        specs = [("kartusche", p.big_w, p.big_h, big_var[0]), ("rechteck", p.big_w, p.big_h, big_var[1]),
                 ("kartusche", p.small_w, p.small_h, sv[0]), ("rechteck", p.small_w, p.small_h, sv[0]),
                 ("achteck", p.small_w, p.small_h, sv[0])]
        for pn, w, h, v in specs:
            d = make_door(P[pn], pn, w, h)
            plan_knob(d, p, "right", [v])
            kn = d["knob"]
            K_m, kinfo = K.plug_knob(v, kn["bulb_d"], kn["rosette_d"], res=p.knob_res, solid=True)
            s = kn["site"]
            fused = _clean_manifold(d["mesh"]) + K_m.translate([s["x"], s["y"], s["z"] - 0.15])
            fused = m3.Manifold.compose([q for q in fused.decompose() if q.volume() > 1e-3])
            tm = mesh.manifold_to_trimesh(fused)
            nm = f"plateH_{pn}_{w:g}x{h:g}_knauf_{v}"
            objs = shelf_layout([(f"tuer_{pn}_{w:g}x{h:g}_mit_knauf", tm, dict(door=door_entry(d), knob=kinfo))],
                                p.bed, p.bed_margin, p.obj_gap)
            summary["plates"][nm] = write_plate(nm, objs, p, out_dir)
        timing["PH_s"] = round(time.time() - t, 1)
    # ------------------------------------------------------------------ knobs, pins, coupon
    cache = {}
    if want("PK") and knob_doors:
        t = time.time()
        items = knob_items(knob_doors, p, cache)
        C, cinfo = K.fit_coupon(1.6)
        items.append(("fit_coupon_t1.6", mesh.manifold_to_trimesh(C), dict(coupon=cinfo)))
        plates_k, rest = [], items
        while rest:                                    # greedy split into as many plates as needed
            n = len(rest)
            while n > 0:
                try:
                    objs = shelf_layout(rest[:n], p.bed, p.bed_margin, p.obj_gap)
                    break
                except AssertionError:
                    n -= 1
            assert n > 0
            plates_k.append(objs)
            rest = rest[n:]
        for i, objs in enumerate(plates_k):
            nm = "plateK_knaeufe" if len(plates_k) == 1 else f"plateK{i + 1}_knaeufe"
            summary["plates"][nm] = write_plate(nm, objs, p, out_dir, expected_bodies={"fit_coupon_t1.6": 4})
        timing["PK_s"] = round(time.time() - t, 1)
    # ------------------------------------------------------------------ montage overview
    if p.previews and montage:
        t = time.time()

        def first_knob(d):
            kn = d.get("knob")
            if not kn:
                return None
            key = (kn["variants"][0], kn["bulb_d"], kn["rosette_d"])
            if key not in cache:
                cache[key] = build_knob(*key, res="coarse")
            return cache[key][0]

        groups = [(ti, [(d, first_knob(d), dx) for d, _, dx in mem]) for ti, mem in montage]
        side = [(f"{v} d{bd:g} (Rosette {rd:g})", tm) for (v, bd, rd), (tm, _) in sorted(cache.items())]
        montage_png(groups, side[:8], out_dir / "montage_overview.png")
        timing["montage_s"] = round(time.time() - t, 1)
    timing["total_s"] = round(time.time() - t0, 1)
    summary["timing"] = timing
    summary["doors"] = {d["name"]: door_entry(d) for d in knob_doors}
    check.write(summary, str(out_dir / "doors_report.json"))
    return summary


def main():
    a = cli.parser_for(Params, out=(str, str(panels.OUT_PRIVATE))).parse_args()
    s = run(cli.params_from(a, Params), Path(a.out))
    for name, r in s["plates"].items():
        print(name, r["file"], r["file_mb"], "MB, min gap", r["bed_check"]["min_gap_mm"], "objects",
              len(r["objects"]))
    print(s["timing"])


if __name__ == "__main__":
    main()
