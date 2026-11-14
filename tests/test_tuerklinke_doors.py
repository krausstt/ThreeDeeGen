"""doors.py (cabinet doors from boiserie panels) on synthetic panels only: the real panels are licensed and never
part of the repo. Covers knob site + plug hole, lever mount with explicit scale, plate layout and bed check."""
import sys
from pathlib import Path

import manifold3d as m3
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "projects" / "tuerklinke-louis"))

import doors  # noqa: E402
import knob  # noqa: E402

from tdg import mesh  # noqa: E402


def synth_panel():
    """121 x 76 slab 2.6, bolection frame 0..4 mm (+1.5), flat strip 4..11, inner moulding 11..13 (+1.0), field."""
    M = m3.Manifold.cube([121, 76, 2.6])
    outer = m3.Manifold.cube([121, 76, 1.5]) - m3.Manifold.cube([113, 68, 1.5]).translate([4, 4, 0])
    inner = m3.Manifold.cube([99, 54, 1.0]) - m3.Manifold.cube([95, 50, 1.0]).translate([2, 2, 0])
    M = M + outer.translate([0, 0, 2.6]) + inner.translate([11, 11, 2.6])
    return mesh.manifold_to_trimesh(M)


def test_bulb_rule():
    p = doors.Params()
    assert doors.bulb_for(p, 89.5) == 12.5 and doors.bulb_for(p, 52) == 9.0 and doors.bulb_for(p, 121) == 17.0


def test_knob_door_hole_and_pin():
    p = doors.Params()
    d = doors.make_door(synth_panel(), "synth", 81, 52)
    assert d["scale_x"] == pytest.approx(81 / 121, abs=1e-4) and d["scale_y"] == pytest.approx(52 / 76, abs=1e-4)
    doors.plan_knob(d, p, "right", ["olive"])
    kn = d["knob"]
    s = kn["site"]
    assert kn["bulb_d"] == 9.0 and kn["rosette_d"] == 11.25
    assert abs(s["z"] - 2.6) < 1e-3 and abs(kn["door_t"] - 2.6) < 1e-3 and s["ptp"] <= 0.12
    assert abs(s["y"] - 26.0) < 0.15
    # inner moulding ends 81 * 13 / 121 = 8.7 mm from the right edge -> rosette disk (r 5.625 + 1 margin) beyond it
    assert 81 - s["x"] >= 8.7 + 6.625 - 0.15
    doors.cut_knob_hole(d, p)
    h = d["knob"]["hole"]
    assert h["watertight"] and h["bodies"] == 1 and abs(h["thickness"] - 2.6) < 1e-3
    pin, pinfo = knob.rivet_pin(kn["door_t"])
    assert pinfo["shaft_len_mm"] == pytest.approx(2.6 + 7.0 - 0.3, abs=1e-6)


def test_lever_door_explicit_scale():
    p = doors.Params(lever_voxel=0.08)
    d = doors.make_door(synth_panel(), "synth", 76, 121, upright=True)
    k, site, how = doors.lever_k_for(d, p, "right")
    assert how["mode"] == "streifen gefuellt"
    assert abs(5.6 * k - (7.0 - p.lever_strip_clear)) < 0.25        # strip 4..11 mm minus 1 mm
    assert abs(site["z"] - 2.6) < 1e-3 and abs(site["dist_from_edge"] - 7.5) < 0.3
    doors.mount_lever_on_door(d, p, k, site, hand="links")
    lv = d["lever"]
    assert all(lv["details_ok"].values())
    assert lv["info"]["max_bridge_mm"] <= 3.0 + 1e-6
    assert d["mesh"].is_watertight and len(d["mesh"].split(only_watertight=False)) == 1
    assert d["lever_mesh"].bounds[0, 0] < site["x"] - 5.6 * k     # lever points left (towards the hinge)


def test_layout_and_bed_check(tmp_path):
    p = doors.Params(previews=False)
    big = trimesh.creation.box([145, 89.5, 3.6])
    up = trimesh.creation.box([121, 76, 6.2])                     # 76 x 121 door rotated on the bed
    objs = doors.shelf_layout([("a", big, {}), ("b", up, {})], 180, 3, 4, sort=False)
    bc = doors.bed_check(objs, 180, 3, 4)
    assert bc["ok"] and bc["min_gap_mm"] >= 4.0
    with pytest.raises(AssertionError):                            # two 86.6 wide leaves do not fit
        leaf = trimesh.creation.box([86.6, 121, 3.5])
        doors.shelf_layout([("l", leaf, {}), ("r", leaf, {})], 180, 3, 4)
    rep = doors.write_plate("test_plate", objs, p, tmp_path)
    sc = trimesh.load(str(tmp_path / "test_plate.3mf"))
    assert len(sc.geometry) == 2 and rep["bed_check"]["ok"]
    bad = [(n, tm.copy(), i) for n, tm, i in objs]
    bad[0][1].apply_translation([-16, 0, 0])
    assert not doors.bed_check(bad, 180, 3, 4)["ok"]
