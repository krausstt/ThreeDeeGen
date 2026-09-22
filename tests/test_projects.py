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
        for rep in s["parts"].values():
            assert rep["watertight"] and rep["bodies"] == 1


def test_mae_west_eiffel_coarse(tmp_path):
    g = load("mae-west-eiffel")
    _, rep = g.generate(g.Params(voxel=0.8), tmp_path / "m", simplify_eps=0, previews=False)
    assert rep["watertight"] and rep["bodies"] == 1
    assert rep["min_strut_angle_deg"] >= 50.0
