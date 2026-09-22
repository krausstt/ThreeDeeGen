"""Narrow-band SDF accumulation for organic, lattice-like models.

Rods (polylines with per-vertex radius) are hard-min'ed within themselves and
merged with each other by an order-independent exponential smooth union
  d = -k * ln(sum_i exp(-d_i / k)).
Analytic solids (anything with .bbox() and .sdf(X, Y, Z)) are added the same way.
"""
from __future__ import annotations

import time

import numpy as np


class Rod:
    """Polyline with per-vertex radius (union of round cones)."""

    def __init__(self, pts, rad, name=""):
        self.p = np.asarray(pts, float)
        self.r = np.broadcast_to(np.asarray(rad, float), (len(self.p),)).copy()
        self.name = name


def _rod_kernel():
    from numba import njit

    @njit(cache=True, fastmath=True)
    def splat(S, buf, lo, h, A, Bv, ra, rb, band, k):
        nx, ny, nz = S.shape
        m = A.shape[0]
        # pass 1: hard min of this rod into buf (inf = untouched)
        for q in range(m):
            rmax = max(ra[q], rb[q]) + band
            i0 = max(int((min(A[q, 0], Bv[q, 0]) - rmax - lo[0]) / h), 0)
            i1 = min(int((max(A[q, 0], Bv[q, 0]) + rmax - lo[0]) / h) + 1, nx - 1)
            j0 = max(int((min(A[q, 1], Bv[q, 1]) - rmax - lo[1]) / h), 0)
            j1 = min(int((max(A[q, 1], Bv[q, 1]) + rmax - lo[1]) / h) + 1, ny - 1)
            l0 = max(int((min(A[q, 2], Bv[q, 2]) - rmax - lo[2]) / h), 0)
            l1 = min(int((max(A[q, 2], Bv[q, 2]) + rmax - lo[2]) / h) + 1, nz - 1)
            abx = Bv[q, 0] - A[q, 0]
            aby = Bv[q, 1] - A[q, 1]
            abz = Bv[q, 2] - A[q, 2]
            L2 = abx * abx + aby * aby + abz * abz + 1e-12
            for i in range(i0, i1 + 1):
                px = lo[0] + i * h - A[q, 0]
                for j in range(j0, j1 + 1):
                    py = lo[1] + j * h - A[q, 1]
                    for l in range(l0, l1 + 1):
                        pz = lo[2] + l * h - A[q, 2]
                        t = (px * abx + py * aby + pz * abz) / L2
                        t = min(max(t, 0.0), 1.0)
                        dx = px - t * abx
                        dy = py - t * aby
                        dz = pz - t * abz
                        d = np.sqrt(dx * dx + dy * dy + dz * dz) - (ra[q] + t * (rb[q] - ra[q]))
                        if d < band and d < buf[i, j, l]:
                            buf[i, j, l] = d
        # pass 2: exponential smooth-union into S, reset buf
        for q in range(m):
            rmax = max(ra[q], rb[q]) + band
            i0 = max(int((min(A[q, 0], Bv[q, 0]) - rmax - lo[0]) / h), 0)
            i1 = min(int((max(A[q, 0], Bv[q, 0]) + rmax - lo[0]) / h) + 1, nx - 1)
            j0 = max(int((min(A[q, 1], Bv[q, 1]) - rmax - lo[1]) / h), 0)
            j1 = min(int((max(A[q, 1], Bv[q, 1]) + rmax - lo[1]) / h) + 1, ny - 1)
            l0 = max(int((min(A[q, 2], Bv[q, 2]) - rmax - lo[2]) / h), 0)
            l1 = min(int((max(A[q, 2], Bv[q, 2]) + rmax - lo[2]) / h) + 1, nz - 1)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    for l in range(l0, l1 + 1):
                        d = buf[i, j, l]
                        if d < 1e20:
                            S[i, j, l] += np.exp(-max(d, -20.0 * k) / k)
                            buf[i, j, l] = np.inf

    return splat


def evaluate(rods, solids, lo, hi, voxel, blend, bed_cut=True):
    """Return (D, lo) where D is the blended SDF on a regular grid starting at lo.

    Pick lo[2] so that no sample lies exactly on z=0 (e.g. -1 - 0.3*voxel),
    otherwise the bed cut produces zero-thickness slivers.
    """
    k = blend
    band = 7 * k + 0.5
    lo = np.asarray(lo, float)
    hi = np.asarray(hi, float)
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    S = np.zeros(n, np.float32)
    buf = np.full(n, np.inf, np.float32)
    ax = [lo[i] + voxel * np.arange(n[i]) for i in range(3)]
    splat = _rod_kernel()
    t0 = time.time()
    for rd in rods:
        splat(S, buf, lo, voxel, rd.p[:-1].copy(), rd.p[1:].copy(),
              rd.r[:-1].copy(), rd.r[1:].copy(), band, k)
    del buf
    for so in solids:
        bmin, bmax = so.bbox()
        a = np.clip(np.floor((bmin - band - lo) / voxel).astype(int), 0, n - 1)
        b = np.clip(np.ceil((bmax + band - lo) / voxel).astype(int) + 1, 0, n)
        X, Y, Z = np.meshgrid(ax[0][a[0]:b[0]], ax[1][a[1]:b[1]], ax[2][a[2]:b[2]], indexing="ij")
        d = so.sdf(X, Y, Z)
        sub = S[a[0]:b[0], a[1]:b[1], a[2]:b[2]]
        sub += np.where(d < band, np.exp(-np.maximum(d, -20 * k) / k), 0).astype(np.float32)
    print(f"  SDF accumulated in {time.time() - t0:.1f}s, grid {tuple(int(x) for x in n)}")
    with np.errstate(divide="ignore"):
        D = (-k * np.log(np.maximum(S, 1e-30))).astype(np.float32)
    del S
    if bed_cut:
        Z = ax[2][None, None, :]
        np.maximum(D, (-Z).astype(np.float32), out=D)   # flat cut at the bed, z >= 0
    return D, lo


def to_mesh(D, lo, voxel, sit_on_bed=True):
    """Marching cubes -> trimesh.Trimesh (outward normals)."""
    from skimage.measure import marching_cubes
    import trimesh
    v, f, _, _ = marching_cubes(D, 0.0, spacing=(voxel,) * 3, allow_degenerate=False)
    v += lo
    m = trimesh.Trimesh(v, f[:, ::-1], process=True)
    if m.volume < 0:
        m.invert()
    if sit_on_bed:
        m.apply_translation([0, 0, -m.bounds[0, 2]])
    return m
