"""Mesh conversion, manifold-safe simplification and export."""
from __future__ import annotations

import os

import numpy as np


def manifold_to_trimesh(M):
    import trimesh
    mm = M.to_mesh()
    return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=False)


def trimesh_to_manifold(m):
    import manifold3d as m3
    return m3.Manifold(m3.Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                               tri_verts=np.asarray(m.faces, np.uint32)))


def simplify(m, eps):
    """Decimate with max deviation eps [mm]; manifold3d keeps the mesh 2-manifold."""
    if eps <= 0:
        return m
    return manifold_to_trimesh(trimesh_to_manifold(m).simplify(eps))


def export(m, path_no_ext, formats=("stl", "3mf")):
    os.makedirs(os.path.dirname(path_no_ext) or ".", exist_ok=True)
    out = []
    for f in formats:
        p = f"{path_no_ext}.{f}"
        m.export(p)
        out.append(p)
    return out
