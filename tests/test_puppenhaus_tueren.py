"""Tests für projects/puppenhaus-tueren (Türen 1:12 und Barock-Drücker)."""


# ---------------------------------------------------------------- doors.py (Türen ohne Griff)
def _doors():
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    p = root / "projects" / "puppenhaus-tueren" / "doors.py"
    spec = importlib.util.spec_from_file_location("puppenhaus_tueren_doors", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_puppenhaus_tuer_alle_tueren(tmp_path):
    D = _doors()
    for kind in D.DOORS:
        s = D.spec(kind, orn_dx_p=0.4)
        door, rep = D.write_door(s, tmp_path)
        r = rep["parts"][f"{kind}_ohne_griff"]
        assert r["watertight"] and r["bodies"] == 1, kind
        assert r["overhang_area_gt45deg_mm2"] < 0.5, (kind, r["overhang_area_gt45deg_mm2"])
        b = door.bounding_box()
        assert abs(b[2]) < 1e-9
        assert abs((b[3] - b[0]) - s.leaf_w / 12) < 1e-6 and abs((b[4] - b[1]) - s.leaf_h / 12) < 1e-6
        assert rep["door"]["bed_fit"]["fits"] and rep["door"]["bed_fit"]["margin_long_side"] >= 2.0
        h = rep["door"]["handle"]
        assert h["keepout_free"] and 0 < h["x"] < b[3] / 2 and abs(h["z"] - s.slab_t_p) < 1e-9
        assert (tmp_path / f"{kind}_ohne_griff.3mf").stat().st_size > 0


def test_puppenhaus_tuer_rueckseite_flach():
    D = _doors()
    for kind in D.DOORS:
        s = D.spec(kind, orn_dx_p=0.4)
        door, _ = D.build_door(s)
        W, H = s.leaf_w / 12, s.leaf_h / 12
        bottom = door ^ D.box(-1, -1, -1, W + 1, H + 1, 0.05)   # full slab cross-section at the bed
        assert abs(bottom.volume() - W * H * 0.05) < 1e-3 * W * H, kind


def test_puppenhaus_tuer_glas_varianten(tmp_path):
    D = _doors()
    for g in D.GLASS_MODES:
        s = D.spec("zimmertuer_glas", glass=g, orn_dx_p=0.4)
        _, rep = D.write_door(s, tmp_path, name=f"glas_{g}")
        for name, r in rep["parts"].items():
            assert r["watertight"] and r["bodies"] == 1, (g, name)
        f = next(x for x in rep["door"]["features"] if x["name"] == "glas")
        if g == "ornament":
            assert f["ornament_pp"] <= 0.3
        if g == "offen":
            assert rep["assembly_check"]["ok"]
            assert rep["door"]["plate_layout"]["fits"]
            assert set(rep["parts"]) == {"glas_offen", "glasleiste_rahmen"}
            assert f["frame"]["width"] >= 1.2


# ---------------------------------------------------------------- handle.py (Barock-Drücker 1:12)
def _griff():
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    p = root / "projects" / "puppenhaus-tueren" / "handle.py"
    spec = importlib.util.spec_from_file_location("puppenhaus_tueren_handle", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_puppenhaus_griff_rechts_links():
    G = _griff()
    from tdg import check, mesh
    for hand, sign in (("rechts", 1), ("links", -1)):
        M, info = G.build_handle(hand=hand)
        rep = check.report(mesh.manifold_to_trimesh(M))
        check.assert_printable(rep)
        ok = G.details_ok(info)
        assert all(ok.values()), (hand, ok)
        b = M.bounding_box()
        assert abs(b[2]) < 1e-9                                  # sits on the door surface / bed
        assert sign * (b[3] + b[0]) > 5                          # lever points to the requested side
        f = info["min_features_mm"]
        assert f["lever_t"] >= 0.9 and f["lever_w"] >= 1.0 and f["keyhole_slot"] >= 0.45 and f["screw_d"] >= 0.5
        assert info["web"]["max_bridge_mm"] <= 3.0 and info["overhang"]["over45_non_bridge_mm2"] <= 0.05
        assert 3.0 <= info["projection_mm"] <= 5.0 and abs(info["key_dist_mm"] - 6.0) < 1e-6
        e = info["escutcheon_bbox_mm"]
        assert e[0] < 0 < e[2] and e[1] < -9 and e[3] > 6                 # axis inside the escutcheon


def test_puppenhaus_griff_unebene_tuer_und_massstab():
    import numpy as np
    G = _griff()

    def surf(xy):
        return 0.3 * np.sin(np.atleast_2d(xy)[:, 0] * 0.5) + 0.2

    M, info = G.build_handle(hand="links", surface=surf)
    assert len(M.decompose()) == 1 and info["overhang"]["over45_non_bridge_mm2"] <= 0.05
    M6, i6 = G.build_handle(scale=1 / 6)
    assert len(M6.decompose()) == 1 and i6["escutcheon_size_mm"][1] > 30 and all(G.details_ok(i6).values())
    try:
        G.build_handle(lever_h=2.0)
        raise AssertionError("lever_h below the neck height must be rejected")
    except ValueError:
        pass


def test_puppenhaus_griff_ausgabe(tmp_path):
    G = _griff()
    s = G.generate(tmp_path, previews=False)
    for name in ("griff_rechts", "griff_links", "griff_probe"):
        r = s["parts"][name]
        assert r["watertight"] and r["bodies"] == 1, name
        assert (tmp_path / f"{name}.3mf").stat().st_size > 0
    assert s["parts"]["griff_probe"]["bbox_mm"][:2] == [30.0, 30.0]
    assert (tmp_path / "griff_rechts.stl").exists() and (tmp_path / "griff_report.json").exists()
