"""Scaffold a new project: python3 scripts/new_project.py <slug> "<Title>"."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GEN = '''"""
{title}

Frame / print orientation: z = 0 is the bed. Document every assumption here.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import manifold3d as m3  # noqa: E402

from tdg import check, cli, mesh, render  # noqa: E402


@dataclass
class Params:
    # --- measured
    size: float = 20.0
    # --- assumed (to be measured)
    # --- fit / print
    fit: float = 0.2
    material: str = "PLA"


def build(p: Params):
    return m3.Manifold.cube([p.size] * 3)


def generate(p: Params, out_dir: Path, previews=True):
    tm = mesh.manifold_to_trimesh(build(p))
    base = out_dir / "{slug_u}"
    mesh.export(tm, str(base))
    rep = check.report(tm, p.material, extra=dict(params=asdict(p)))
    check.write(rep, str(base) + "_report.json")
    if previews:
        render.main(str(base) + ".stl", str(base))
    check.assert_printable(rep)
    return rep


def main():
    a = cli.parser_for(Params, out=(str, str(HERE / "out"))).parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print(generate(cli.params_from(a, Params), out))


if __name__ == "__main__":
    main()
'''

README = '''# {title}

Status: Entwurf

## Ziel

## Maße (gemessen / angenommen)

| Parameter | Wert | Quelle |
|---|---|---|

## Druck

## Offene Fragen
'''


def main():
    slug, title = sys.argv[1], sys.argv[2]
    d = ROOT / "projects" / slug
    if d.exists():
        sys.exit(f"{d} exists")
    (d / "reference").mkdir(parents=True)
    (d / "out").mkdir()
    (d / "generate.py").write_text(GEN.format(title=title, slug_u=slug.replace("-", "_")))
    (d / "README.md").write_text(README.format(title=title))
    print(f"created {d}  -> add it to README.md project index and tests/test_projects.py")


if __name__ == "__main__":
    main()
