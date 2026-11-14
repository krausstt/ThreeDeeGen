"""panels.py on synthetic panels only (the real boiserie panels are licensed and never part of the repo)."""
import math
import sys
from pathlib import Path

import manifold3d as m3
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "projects" / "tuerklinke-louis"))

import panels  # noqa: E402

from tdg import mesh  # noqa: E402


def synth_panel(flip=False, stand=False):
    """60 x 40 slab 1.6 with a 3.4 high frame 4..8 mm from the edge (flat strip 0..4, flat field inside)."""
    M = m3.Manifold.cube([60, 40, 1.6])
    frame = m3.Manifold.cube([52, 32, 1.8]) - m3.Manifold.cube([44, 24, 1.8]).translate([4, 4, 0])
    M = M + frame.translate([4, 4, 1.6])
    tm = mesh.manifold_to_trimesh(M)
    if flip:
        tm.apply_transform(panels._rot([1, 0, 0], 180))
    if stand:
        tm.apply_transform(panels._rot([1, 0, 0], 90))
    return tm


@pytest.mark.parametrize("flip,stand", [(False, False), (True, False), (True, True)])
def test_lay_flat_relief_up(flip, stand):
    p = panels.lay_flat(synth_panel(flip, stand))
    assert np.allclose(p.extents, [60, 40, 3.4], atol=1e-4)
    assert np.allclose(p.bounds[0], 0, atol=1e-6)
    assert p.metadata["back_flat_fraction"] > 0.98
    assert abs(panels.thickness_at(p, 30, 20) - 1.6) < 1e-3          # field, not the frame top
    assert abs(panels.thickness_at(p, 6, 20) - 3.4) < 1e-3


def test_fit_extents():
    p = panels.lay_flat(synth_panel())
    d = panels.fit(p, 145, 89.5)
    assert np.allclose(d.extents, [145, 89.5, 3.4], atol=1e-4) and d.is_watertight
    u = panels.fit(p, 76, 121, upright=True, mirror_x=True)
    assert np.allclose(u.extents, [76, 121, 3.4], atol=1e-4) and u.is_watertight and u.volume > 0


def test_knob_site_on_flat_field():
    p = panels.fit(panels.lay_flat(synth_panel()), 120, 80)          # x2: frame 8..16 mm from the edge
    s = panels.find_knob_site(p, 14, edge="right", margin=1.0)
    # closest flat disk of d 16 next to the frame inner edge at x = 104: centre at 104 - 8
    assert abs(s["x"] - 96.0) <= 0.25 and abs(s["y"] - 40.0) <= 0.1
    assert abs(s["z"] - 1.6) < 1e-3 and s["ptp"] <= 0.12 and s["level_name"] == "feld/grund"
    assert s["strips"][0]["dist_from_edge"][0] < 1.5                 # outer flat strip 0..8 is reported
    assert 5.0 <= s["strips"][0]["max_rosette_d"] <= 6.5             # 8 mm strip - 2 margin
    left = panels.find_knob_site(p, 14, edge="left")
    assert abs(left["x"] - 24.0) <= 0.25


def test_lever_site():
    p = panels.fit(panels.lay_flat(synth_panel()), 120, 80)
    s = panels.find_lever_site(p, 6.0, 30.0, edge="right")
    assert abs(s["x"] - 116.0) <= 0.3 and abs(s["z"] - 1.6) < 1e-3   # centre of the outer flat strip 112..120
    assert abs(s["max_plate_w"] - 8.0) <= 0.3


def test_cut_hole_volume_drop():
    p = panels.fit(panels.lay_flat(synth_panel()), 120, 80)
    out, info = panels.cut_hole(p, 96.0, 40.0, d=3.4)
    assert out.is_watertight and info["bodies"] == 1
    assert abs(info["volume_removed"] - math.pi * 1.7 ** 2 * 1.6) < 0.05 * math.pi * 1.7 ** 2 * 1.6
    assert abs((p.volume - out.volume) - info["volume_removed"]) < 1e-3
