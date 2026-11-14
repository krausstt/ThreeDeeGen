"""
Boiserie panels as real cabinet doors: load the user's panel 3MF, lay each panel flat (relief up), scale it to a
door size, find flat sites for a knob rosette / lever escutcheon and cut the plug hole for the knob pin.

The panels themselves are third-party (MakerWorld Exclusive License): nothing derived from them is committed.
Everything written from real panels goes to out_private/ (git-ignored). Tests use synthetic panels only.

Coordinates: mm, z = 0 is the flat back of the door (print bed), relief up, min x / y = 0.

Flat-site search (vectorised on the 0.1 mm height map of the top surface):
  knob  : local peak-to-peak over a disk = disk max filter - disk min filter. The disk filter is the union of a
          few centred rectangles whose corners lie on a slightly enlarged circle (a superset of the disk, so the
          test is conservative); each rectangle is a separable O(N) scipy max filter.
  lever : rectangle plate_w x plate_h, directly separable.
  max size at a site: the "level" mask |H - z_site| <= flat_tol / 2, Euclidean distance transform (knob) or the
          run length of columns that are level over plate_h (lever).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import mount  # noqa: E402

from tdg import mesh as tmesh  # noqa: E402

# 3MF geometry id -> name (MakerWorld "Four Boisserie Panels" by cynsight)
NAMES = {"1": "tuer_oberlicht", "3": "kartusche", "5": "achteck", "7": "rechteck"}
OUT_PRIVATE = HERE / "out_private"


# --------------------------------------------------------------------------------------------- loading
def _rot(axis, deg):
    return trimesh.transformations.rotation_matrix(math.radians(deg), axis)


def _to_origin(m):
    m.apply_translation(-m.bounds[0])
    return m


def back_flatness(m, h=0.5):
    """Fraction of the footprint where the bottom surface lies at z_min (+-0.05 mm)."""
    lo, hi = m.bounds[0, :2], m.bounds[1, :2]
    z0 = float(m.bounds[0, 2])
    top = mount.HeightMap(m, lo, hi, h).H
    refl = m.copy()
    refl.vertices[:, 2] *= -1
    bot = -mount.HeightMap(refl, lo, hi, h).H
    fp = top > z0 + 0.3                       # cells covered by the panel (thickness > 0.3)
    return float(np.mean(bot[fp] < z0 + 0.05)), float(fp.mean())


def lay_flat(m, min_back=0.9):
    """Thinnest axis -> z, relief up (flat back at z = 0), long side along x, min corner at the origin."""
    m = m.copy()
    thin = int(np.argmin(m.extents))
    if thin == 0:
        m.apply_transform(_rot([0, 1, 0], 90))
    elif thin == 1:
        m.apply_transform(_rot([1, 0, 0], 90))
    _to_origin(m)
    up, _ = back_flatness(m)
    flipped = _to_origin(m.copy().apply_transform(_rot([1, 0, 0], 180)))
    down, _ = back_flatness(flipped)
    if down > up:                              # the other side is the flat back
        m, up = flipped, down
    assert up > min_back, f"no flat back found (flat fraction {up:.2f} / {down:.2f})"
    if m.extents[1] > m.extents[0]:
        m.apply_transform(_rot([0, 0, 1], 90))
        _to_origin(m)
    m.metadata["back_flat_fraction"] = round(up, 4)
    return m


def load_panels(path_3mf, names=None):
    """dict name -> trimesh, laid flat relief up (see lay_flat). names: subset of NAMES values."""
    scene = trimesh.load(str(path_3mf))
    geoms = scene.geometry if hasattr(scene, "geometry") else {"1": scene}
    out = {}
    for key, g in geoms.items():
        name = NAMES.get(str(key), str(key))
        if names is not None and name not in names:
            continue
        out[name] = lay_flat(g)
    return out


# --------------------------------------------------------------------------------------------- scaling
def fit(panel, w, h, upright=False, mirror_x=False):
    """Non-uniform x/y scale to a w (x) by h (y) bounding box, z unchanged. upright: long side along y."""
    m = panel.copy()
    if upright != (m.extents[1] > m.extents[0]):
        m.apply_transform(_rot([0, 0, 1], 90))
    _to_origin(m)
    S = np.diag([w / m.extents[0], h / m.extents[1], 1.0, 1.0])
    if mirror_x:
        S[0, 0] *= -1
    m.apply_transform(S)                       # trimesh flips the winding for det < 0
    _to_origin(m)
    if panel.is_watertight:
        assert m.is_watertight and m.volume > 0, "fit broke the mesh"
    return m


# --------------------------------------------------------------------------------------------- height map
def heightmap(panel, h=0.1):
    """mount.HeightMap of the top surface over the whole panel (cell (i, j) at x = i h, y = j h from bounds min)."""
    return mount.HeightMap(panel, panel.bounds[0, :2], panel.bounds[1, :2], h)


def thickness_at(panel, x, y, h=0.05):
    """Top surface height at (x, y) = door thickness there (back at z = 0)."""
    p = np.array([x, y], float)
    hm = mount.HeightMap(panel, p - h, p + h, h)
    return float(hm.H.max()) - float(panel.bounds[0, 2])


def _disk_max(H, r_cells, n=8):
    """max over a disk of radius r_cells (superset: union of n centred rectangles on an enlarged circle)."""
    if r_cells < 1:
        return H.copy()
    R = r_cells / math.cos(math.pi / (4 * n))
    out = None
    for k in range(n):
        t = (k + 0.5) * (math.pi / 2) / n
        a, b = int(math.ceil(R * math.cos(t))), int(math.ceil(R * math.sin(t)))
        f = ndimage.maximum_filter(H, size=(2 * a + 1, 2 * b + 1), mode="nearest")
        out = f if out is None else np.maximum(out, f)
    return out


def _disk_ptp(H, r_cells):
    return _disk_max(H, r_cells) - (-_disk_max(-H, r_cells))


def _row(edge, along, nx, ny):
    """Grid indices of the search line, ordered from the edge inwards: (ii, jj)."""
    if edge in ("right", "left"):
        j = int(round(along * (ny - 1)))
        ii = np.arange(nx)[::-1] if edge == "right" else np.arange(nx)
        return ii, np.full_like(ii, j)
    if edge in ("top", "bottom"):
        i = int(round(along * (nx - 1)))
        jj = np.arange(ny)[::-1] if edge == "top" else np.arange(ny)
        return np.full_like(jj, i), jj
    raise ValueError(edge)


def _edge_dist(edge, x, y, W, Hy):
    return {"right": W - x, "left": x, "top": Hy - y, "bottom": y}[edge]


def _level_name(z, H, inside):
    zs = H[inside]
    lo, hi = float(np.percentile(zs, 2)), float(zs.max())
    if z <= lo + 0.15:
        return "feld/grund"
    if z >= hi - 0.15:
        return "rahmen-oberkante"
    return "zwischenstufe"


def _runs(mask):
    """start/stop (inclusive) of True runs of a 1-D bool array."""
    d = np.diff(np.r_[0, mask.astype(np.int8), 0])
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1))


def find_knob_site(panel, rosette_d, edge="right", along=0.5, flat_tol=0.12, margin=1.0, h=0.1, hm=None):
    """Closest point to `edge` on the line at fraction `along` of that edge where a disk of diameter
    rosette_d + 2 margin is flat (ptp <= flat_tol); plus the largest rosette that fits flat there."""
    hm = hm or heightmap(panel, h)
    H, h = hm.H, hm.h
    nx, ny = H.shape
    W, Hy = panel.extents[0], panel.extents[1]
    R = 0.5 * rosette_d + margin
    rc = R / h
    ptp = _disk_ptp(H, rc)
    i_ok = (np.arange(nx) * h >= R) & (np.arange(nx) * h <= W - R)
    j_ok = (np.arange(ny) * h >= R) & (np.arange(ny) * h <= Hy - R)
    ok = (ptp <= flat_tol) & i_ok[:, None] & j_ok[None, :]
    ii, jj = _row(edge, along, nx, ny)
    hit = np.nonzero(ok[ii, jj])[0]
    if len(hit) == 0:
        return None
    k = int(hit[0])
    i, j = int(ii[k]), int(jj[k])
    x, y, z = i * h + hm.lo[0], j * h + hm.lo[1], float(H[i, j])
    # largest rosette: level band around z, distance transform, best over the flat run starting at the site
    level = np.pad(np.abs(H - z) <= 0.5 * flat_tol, 1)
    edt = ndimage.distance_transform_edt(level)[1:-1, 1:-1] * h
    run = hit[: np.argmax(np.diff(np.r_[hit, 10 ** 9]) > 1) + 1]       # contiguous run from the closest hit
    rmax = edt[ii[run], jj[run]]
    q = int(run[int(np.argmax(rmax))])
    inside = H > float(panel.bounds[0, 2]) + 0.3
    strips = flat_strips(H, h, ii, jj, edge, W, Hy, flat_tol, margin, lo=hm.lo)
    return dict(x=round(x, 2), y=round(y, 2), z=round(z, 3), dist_from_edge=round(_edge_dist(edge, x, y, W, Hy), 2),
                gap_rosette_to_edge=round(_edge_dist(edge, x, y, W, Hy) - 0.5 * rosette_d, 2),
                ptp=round(float(ptp[i, j]), 3), level_name=_level_name(z, H, inside),
                max_rosette_d_here=round(2 * float(edt[i, j]) - 2 * margin, 2),
                max_rosette_d_strip=round(2 * float(rmax.max()) - 2 * margin, 2),
                max_rosette_at=(round(ii[q] * h + hm.lo[0], 2), round(jj[q] * h + hm.lo[1], 2)),
                strips=strips, edge=edge, along=along, rosette_d=rosette_d, margin=margin, flat_tol=flat_tol)


def flat_strips(H, h, ii, jj, edge, W, Hy, flat_tol=0.12, margin=1.0, r_min=1.0, min_width=2.0, lo=(0.0, 0.0)):
    """Flat strips crossed by the search line, from the edge inwards: where a disk of radius r_min is flat.
    Each: dist_from_edge (start, end) along the line, z, largest rosette (diameter - 2 margin) fitting flat in it
    and where."""
    rc = r_min / h
    flat = _disk_ptp(H, rc)[ii, jj] <= flat_tol
    out = []
    for s0, s1 in _runs(flat):
        if (s1 - s0) * h < min_width:
            continue
        z = float(np.median(H[ii[s0:s1 + 1], jj[s0:s1 + 1]]))
        edt = ndimage.distance_transform_edt(np.pad(np.abs(H - z) <= 0.5 * flat_tol, 1))[1:-1, 1:-1] * h
        e = edt[ii[s0:s1 + 1], jj[s0:s1 + 1]]
        q = s0 + int(np.argmax(e))
        x, y = ii[q] * h + lo[0], jj[q] * h + lo[1]
        d0 = _edge_dist(edge, ii[s0] * h + lo[0], jj[s0] * h + lo[1], W, Hy)
        d1 = _edge_dist(edge, ii[s1] * h + lo[0], jj[s1] * h + lo[1], W, Hy)
        out.append(dict(dist_from_edge=(round(d0, 2), round(d1, 2)), z=round(z, 3),
                        max_rosette_d=round(2 * float(e.max()) - 2 * margin, 2), at=(round(x, 2), round(y, 2))))
    return out


def find_lever_site(panel, plate_w, plate_h, edge="right", along=0.5, flat_tol=0.12, h=0.1, hm=None):
    """Centre of the closest strip (from `edge`) on the line at fraction `along` where a plate_w x plate_h
    rectangle (long side along y) is flat; plus the widest plate that fits flat in that strip."""
    hm = hm or heightmap(panel, h)
    H, h = hm.H, hm.h
    nx, ny = H.shape
    W, Hy = panel.extents[0], panel.extents[1]
    a, b = int(math.ceil(0.5 * plate_w / h)), int(math.ceil(0.5 * plate_h / h))
    size = (2 * a + 1, 2 * b + 1)
    ptp = ndimage.maximum_filter(H, size=size, mode="nearest") - ndimage.minimum_filter(H, size=size, mode="nearest")
    i_ok = (np.arange(nx) >= a) & (np.arange(nx) <= nx - 1 - a)
    j_ok = (np.arange(ny) >= b) & (np.arange(ny) <= ny - 1 - b)
    ok = (ptp <= flat_tol) & i_ok[:, None] & j_ok[None, :]
    ii, jj = _row(edge, along, nx, ny)
    hit = np.nonzero(ok[ii, jj])[0]
    if len(hit) == 0:
        return None
    run = hit[: np.argmax(np.diff(np.r_[hit, 10 ** 9]) > 1) + 1]
    k0, kc = int(run[0]), int(run[len(run) // 2])
    i, j = int(ii[kc]), int(jj[kc])
    x, y, z = i * h + hm.lo[0], j * h + hm.lo[1], float(H[i, j])
    # widest plate (width along x for every edge): columns level over plate_h around row j, run containing i
    level = np.abs(H - z) <= 0.5 * flat_tol
    col = ndimage.minimum_filter1d(level.astype(np.uint8), size=2 * b + 1, axis=1, mode="constant")[:, j] > 0
    c = i
    wmax = 0.0
    for s0, s1 in _runs(col):
        if s0 <= c <= s1:
            wmax = (s1 - s0) * h
    xc, yc = ii[k0] * h + hm.lo[0], jj[k0] * h + hm.lo[1]
    return dict(x=round(x, 2), y=round(y, 2), z=round(z, 3), dist_from_edge=round(_edge_dist(edge, x, y, W, Hy), 2),
                closest=(round(xc, 2), round(yc, 2)), strip_len=round((len(run) - 1) * h, 2),
                ptp=round(float(ptp[i, j]), 3), max_plate_w=round(wmax, 2),
                level_name=_level_name(z, H, H > float(panel.bounds[0, 2]) + 0.3),
                edge=edge, along=along, plate_w=plate_w, plate_h=plate_h, flat_tol=flat_tol)


# --------------------------------------------------------------------------------------------- plug hole
def cut_hole(panel, x, y, d=3.4, seg=48, check_volume=True):
    """Vertical through-hole d at (x, y) (manifold3d CSG). Returns (trimesh, info)."""
    import manifold3d as m3
    t = thickness_at(panel, x, y)
    z0, z1 = float(panel.bounds[0, 2]), float(panel.bounds[1, 2])
    M = tmesh.trimesh_to_manifold(panel)
    assert M.status() == m3.Error.NoError, f"panel is not a manifold: {M.status()}"
    cyl = m3.Manifold.cylinder(z1 - z0 + 2.0, d / 2, d / 2, seg).translate([x, y, z0 - 1.0])
    R = M - cyl
    parts = R.decompose()
    keep = [q for q in parts if q.volume() > 1e-3]            # drop zero-volume slivers some meshes carry
    if len(keep) < len(parts):
        R = m3.Manifold.compose(keep)
    out = tmesh.manifold_to_trimesh(R)
    dv = float(M.volume() - R.volume())
    ideal = 0.5 * seg * (d / 2) ** 2 * math.sin(2 * math.pi / seg) * t           # polygon area x thickness
    info = dict(x=x, y=y, d=d, thickness=round(t, 3), volume_removed=round(dv, 3), volume_expected=round(ideal, 3),
                bodies=len(keep), dropped_slivers=len(parts) - len(keep),
                watertight=bool(out.is_watertight))
    assert info["watertight"] and info["bodies"] == 1, info
    if check_volume:
        assert abs(dv - ideal) <= 0.05 * ideal + 0.02, f"hole volume off (site not flat?): {info}"
    return out, info


# --------------------------------------------------------------------------------------------- review
def review(path_3mf, png):
    """Verification on the real panels: sites for the requested doors, top-view PNG with the sites marked."""
    import time

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    t0 = time.time()
    P = load_panels(path_3mf, names={"kartusche", "rechteck", "achteck"})
    res = {"load_s": round(time.time() - t0, 1),
           "back_flat": {k: v.metadata["back_flat_fraction"] for k, v in P.items()},
           "extents": {k: np.round(v.extents, 2).tolist() for k, v in P.items()}}
    cases = [
        ("kartusche 145x89.5", P["kartusche"], (145, 89.5, False), [("knob", 14, "right")]),
        ("rechteck hoch 76x121", P["rechteck"], (76, 121, True), [("lever", (9.2, 36.3), "right")]),
        ("rechteck 145x89.5", P["rechteck"], (145, 89.5, False), [("knob", 14, "right")]),
        ("rechteck 81x52", P["rechteck"], (81, 52, False), [("knob", 14, "right")]),
        ("achteck hoch 86.6x121", P["achteck"], (86.6, 121, True), [("knob", 14, "left"), ("knob", 14, "right")]),
    ]
    fig, axs = plt.subplots(1, len(cases), figsize=(5 * len(cases), 6))
    for ax, (title, pan, (w, hh, up), sites) in zip(axs, cases):
        t1 = time.time()
        d = fit(pan, w, hh, upright=up)
        hm = heightmap(d)
        rr = {"extents": np.round(d.extents, 3).tolist(), "watertight": bool(d.is_watertight),
              "heightmap_s": round(time.time() - t1, 1)}
        ax.imshow(hm.H.T, origin="lower", extent=(0, d.extents[0], 0, d.extents[1]), cmap="viridis")
        for kind, size, edge in sites:
            t2 = time.time()
            if kind == "knob":
                s = find_knob_site(d, size, edge=edge, hm=hm)
                if s:
                    ax.add_patch(Circle((s["x"], s["y"]), size / 2, fill=False, color="r", lw=1.5))
                    ax.add_patch(Circle(s["max_rosette_at"], s["max_rosette_d_strip"] / 2, fill=False,
                                        color="w", ls="--", lw=1))
            else:
                s = find_lever_site(d, *size, edge=edge, hm=hm)
                if s:
                    ax.add_patch(Rectangle((s["x"] - size[0] / 2, s["y"] - size[1] / 2), *size, fill=False,
                                           color="r", lw=1.5))
            if s:
                s["search_s"] = round(time.time() - t2, 1)
                ax.plot(s["x"], s["y"], "r+")
                if kind == "knob":
                    t3 = time.time()
                    _, hi = cut_hole(d, s["x"], s["y"])
                    hi["cut_s"] = round(time.time() - t3, 1)
                    s["hole"] = hi
            rr[f"{kind}_{edge}"] = s
        ax.set_title(title)
        ax.set_aspect("equal")
        res[title] = rr
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(review(sys.argv[1], sys.argv[2]), indent=1, default=str))
