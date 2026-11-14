"""
Conforming mount: sample the real panel surface under a handle and solve the minimal support web.

HeightMap rasterises the panel mesh (top surface, z-buffer) on a 0.05 mm grid around the handle, so the handle
can sit on the true stile height and the lever can rest on the frame moulding instead of standing on a post.

solve_web works along the lever path (arc length s, wall follows the path):
  L(s) = top of the web (lever underside at its 45 deg points), H(s) = surface below (panel / escutcheon).
  Supports are points where the web reaches down to the surface: the neck (s = 0), every point where the lever
  already rests on the surface (L - H <= touch), plus points added until every web-free stretch under the lever
  is a bridge <= bridge_max and the free end (scroll / knob) cantilevers <= cant_max.
  The web bottom is b(s) = max(H, min_t (h_t + |s - t|)): pointed arches with 45 deg flanks between supports,
  i.e. every layer only grows 1:1 over the one below (support free).
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit


@njit(cache=True)
def _raster(tri, x0, y0, h, H):
    nx, ny = H.shape
    for t in range(tri.shape[0]):
        ax, ay, az = tri[t, 0, 0], tri[t, 0, 1], tri[t, 0, 2]
        bx, by, bz = tri[t, 1, 0], tri[t, 1, 1], tri[t, 1, 2]
        cx, cy, cz = tri[t, 2, 0], tri[t, 2, 1], tri[t, 2, 2]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        i0 = max(int(math.floor((min(ax, bx, cx) - x0) / h)), 0)
        i1 = min(int(math.ceil((max(ax, bx, cx) - x0) / h)), nx - 1)
        j0 = max(int(math.floor((min(ay, by, cy) - y0) / h)), 0)
        j1 = min(int(math.ceil((max(ay, by, cy) - y0) / h)), ny - 1)
        for i in range(i0, i1 + 1):
            px = x0 + i * h
            for j in range(j0, j1 + 1):
                py = y0 + j * h
                l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
                l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
                l3 = 1.0 - l1 - l2
                if l1 >= -1e-9 and l2 >= -1e-9 and l3 >= -1e-9:
                    z = l1 * az + l2 * bz + l3 * cz
                    if z > H[i, j]:
                        H[i, j] = z


class HeightMap:
    """Top surface of a mesh on a regular grid over the xy window [lo, hi] (outside the mesh: its min z)."""

    def __init__(self, tm, lo, hi, h=0.05):
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        tri = tm.triangles
        tmin, tmax = tri.min(1), tri.max(1)
        keep = np.all(tmax[:, :2] >= lo, 1) & np.all(tmin[:, :2] <= hi, 1)
        n = np.ceil((hi - lo) / h).astype(int) + 1
        self.H = np.full(n, float(tm.bounds[0, 2]))
        _raster(np.ascontiguousarray(tri[keep], dtype=np.float64), lo[0], lo[1], h, self.H)
        self.lo, self.h = lo, h

    def __call__(self, xy):
        xy = np.atleast_2d(xy)
        i = np.clip(np.round((xy[:, 0] - self.lo[0]) / self.h).astype(int), 0, self.H.shape[0] - 1)
        j = np.clip(np.round((xy[:, 1] - self.lo[1]) / self.h).astype(int), 0, self.H.shape[1] - 1)
        return self.H[i, j]


def placement(at, angle, k, axis_local):
    """local (reference units) xy -> panel xy: scale k, rotate about the lever axis, move the axis to `at`."""
    a = math.radians(angle)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    at, ax = np.asarray(at, float), np.asarray(axis_local, float)
    return lambda xy: at + (np.atleast_2d(xy) - ax) * k @ R.T


def _runs(mask):
    """[(i0, i1)] of consecutive True."""
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


def solve_web(s, L, H, bridge_max=3.0, cant_max=0.6, touch=0.45, eps=0.02):
    """Return (b, supports, metrics); b = web bottom per sample, web exists where b < L - eps."""
    sup = {0: float(L[0])}                                   # the neck carries the lever start
    for i in np.nonzero(L - H <= touch)[0]:
        sup[int(i)] = float(H[i])
    for _ in range(200):
        ts = np.array(list(sup.keys()))
        hs = np.array(list(sup.values()))
        b = np.maximum(H, np.min(hs[None, :] + np.abs(s[:, None] - s[ts][None, :]), axis=1))
        free = b >= L - eps
        added = False
        for i0, i1 in _runs(free):
            span = s[i1] - s[i0]
            if i1 == len(s) - 1 and span > cant_max:         # free end
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
    ds = np.gradient(s)
    hgt = np.maximum(L - b, 0)
    metrics = dict(web_area=float((hgt * ds).sum()), end_post=float(hgt[-1]), supports=len(sup),
                   max_bridge=max([s[i1] - s[i0] for i0, i1 in _runs(b >= L - eps) if i1 < len(s) - 1] + [0.0]),
                   max_web_h=float(hgt.max()))
    return b, sup, metrics


def demo_panel(slab=3.6):
    """Synthetic wall panel for tests / demo: 50 x 70 mm slab, a cove frame moulding along y at x 8..13."""
    import manifold3d as m3
    import trimesh
    prof = m3.CrossSection([[(8.0, 0.0), (13.0, 0.0), (13.0, slab), (12.4, slab + 1.4), (11.6, slab + 1.8),
                             (9.6, slab + 1.6), (8.6, slab + 1.0), (8.0, slab)]])
    mould = prof.extrude(60).rotate([90, 0, 0]).translate([0, 65, 0])        # extrude along y
    M = m3.Manifold.cube([50, 70, slab]) + mould
    mm = M.to_mesh()
    return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=False)
