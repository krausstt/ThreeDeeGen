"""Printability report shared by all projects."""
from __future__ import annotations

import json
import math

import numpy as np

DENSITY_G_CM3 = {"PLA": 1.24, "PETG": 1.27, "ASA": 1.07, "TPU": 1.21}  # typical datasheet values


def report(m, material="PLA", bed_eps=0.3, extra=None):
    n = m.face_normals
    zc = m.triangles_center[:, 2] - m.bounds[0, 2]
    area = m.area_faces
    over45 = (n[:, 2] < -math.cos(math.radians(45))) & (zc > bed_eps)
    over60 = (n[:, 2] < -math.cos(math.radians(30))) & (zc > bed_eps)
    vol = float(m.volume) / 1000
    r = dict(
        watertight=bool(m.is_watertight),
        winding_consistent=bool(m.is_winding_consistent),
        bodies=len(m.split(only_watertight=False)),
        faces=int(len(m.faces)),
        bbox_mm=[round(float(x), 2) for x in m.extents],
        volume_cm3=round(vol, 3),
        material=material,
        mass_g_at_100pct=round(vol * DENSITY_G_CM3.get(material, 1.2), 1),
        overhang_area_gt45deg_pct=round(100 * float(area[over45].sum() / area.sum()), 3),
        overhang_area_gt60deg_pct=round(100 * float(area[over60].sum() / area.sum()), 3),
        overhang_area_gt45deg_mm2=round(float(area[over45].sum()), 1),
    )
    if extra:
        r.update(extra)
    return r


def assert_printable(r, bodies=1):
    assert r["watertight"], "mesh is not watertight"
    assert r["bodies"] == bodies, f"expected {bodies} body/bodies, got {r['bodies']}"


def write(r, path):
    with open(path, "w") as fh:
        json.dump(r, fh, indent=2, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o))
