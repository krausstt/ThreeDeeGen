"""Smoke tests: every generator must yield single watertight bodies (fast settings)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(slug):
    spec = importlib.util.spec_from_file_location(slug.replace("-", "_"), ROOT / "projects" / slug / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses need the module registered
    spec.loader.exec_module(mod)
    return mod


def test_bike_bell_bayonet(tmp_path):
    g = load("bike-bell-bayonet")
    for strap in ("integrated", "separate"):
        s = g.generate(g.Params(strap=strap), tmp_path, previews=False)
        assert s["functional_test"]["ok"]
        for name, rep in s["parts"].items():
            assert rep["watertight"]
            assert rep["bodies"] == (3 if name == "fit_coupons" else 1)
        ft = s["functional_test"]
        assert ft["bar_min_vs_mount_mm3"] < 1.0 and ft["bar_max_vs_mount_mm3"] < 1.0


def test_mae_west_eiffel_coarse(tmp_path):
    g = load("mae-west-eiffel")
    _, rep = g.generate(g.Params(voxel=0.8), tmp_path / "m", simplify_eps=0, previews=False)
    assert rep["watertight"] and rep["bodies"] == 1
    assert rep["min_strut_angle_deg"] >= 50.0


def test_masskrug_marker(tmp_path):
    g = load("masskrug-marker")
    s = g.generate(g.Params(symbol="star"), tmp_path, previews=False)
    ft = s["functional_test"]
    assert ft["ok"] and ft["wrap_deg"] > 200 and ft["retention_per_side_mm"] >= 1.2
    assert s["parts"]["fit_set"]["bodies"] == 3
    assert s["parts"]["clip_star"]["watertight"] and s["parts"]["clip_star"]["bodies"] == 1
