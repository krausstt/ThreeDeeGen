"""Plug-in knobs (Steckknauf) of tuerklinke-louis: printability, socket wall, pin interference, coupon, plate."""
import sys
from pathlib import Path

import manifold3d as m3
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "projects" / "tuerklinke-louis"))

import knob  # noqa: E402

from tdg import check, mesh  # noqa: E402


def rep(M):
    return check.report(mesh.manifold_to_trimesh(M))


@pytest.mark.parametrize("variant", knob.VARIANTS)
def test_plug_knob_variant(variant):
    M, info = knob.plug_knob(variant, 13, res="coarse")
    r = rep(M)
    assert r["watertight"] and r["bodies"] == 1
    assert r["overhang_area_gt45deg_mm2"] < 1.0
    assert info["socket_wall_min_mm"] >= knob.WALL_MIN
    assert info["body_underside_min_deg"] >= 45
    assert info["finger_gap_mm"] >= 4.0
    assert 1.15 * 13 <= info["projection_mm"] <= 1.6 * 13
    ft = info["function_test"]
    assert ft["ok"] and ft["interference_mm3"] > 0 and ft["wall_contact_mm3"] == 0
    assert ft["insert_depth_mm"] >= knob.PIN_ENGAGE - 0.31


@pytest.mark.parametrize("d", [9, 18])
def test_plug_knob_size_range(d):
    for v in ("olive", "krone"):          # thinnest neck / largest head
        M, info = knob.plug_knob(v, d, res="coarse")
        r = rep(M)
        assert r["watertight"] and r["bodies"] == 1 and r["overhang_area_gt45deg_mm2"] < 1.0
        assert info["socket_wall_min_mm"] >= knob.WALL_MIN


def test_function_test_detects_missing_interference():
    M, _ = knob.plug_knob("perle", 12, res="coarse")
    cav, _ = knob._socket(rib_d=3.2)                  # ribs too short -> no grip
    plain = M + knob._socket()[0] - cav               # refill the socket, cut the loose one
    assert not knob.pin_function_test(plain)["ok"]


def test_rosette_too_small_rejected():
    with pytest.raises(AssertionError):
        knob.plug_knob("olive", 13, rosette_d=8, res="coarse")


def test_rivet_pin_and_coupon():
    P, info = knob.rivet_pin(2.6)
    r = rep(P)
    assert r["watertight"] and r["bodies"] == 1 and r["overhang_area_gt45deg_mm2"] == 0
    assert abs(info["shaft_len_mm"] - (2.6 + 6.7)) < 1e-9
    C, ci = knob.fit_coupon()
    r = rep(C)
    assert r["watertight"] and r["bodies"] == ci["bodies"] == 4
    assert r["overhang_area_gt45deg_mm2"] < 1.0


def test_knob_set_plate_fits():
    items = knob.knob_set_plate(["olive", "zapfen", "krone"], [12, 14, 16], door_t=2.6, res="coarse")
    assert len(items) == 6
    A = m3.Manifold.batch_boolean([m for _, m in items], m3.OpType.Add)
    bb = A.bounding_box()
    assert bb[0] >= 0 and bb[1] >= 0 and bb[3] <= 170 and bb[4] <= 170
    assert len(A.decompose()) == 6                    # no two parts touch
