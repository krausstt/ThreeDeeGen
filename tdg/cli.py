"""Tiny helper: expose a Params dataclass as --kebab-case CLI flags."""
from __future__ import annotations

import argparse
from dataclasses import asdict, fields


def parser_for(params_cls, **extra):
    ap = argparse.ArgumentParser()
    defaults = asdict(params_cls())
    for f in fields(params_cls):
        v = defaults[f.name]
        if isinstance(v, bool):
            ap.add_argument("--" + f.name.replace("_", "-"), type=lambda s: s.lower() in ("1", "true", "yes"),
                            default=v)
        else:
            ap.add_argument("--" + f.name.replace("_", "-"), type=type(v), default=v)
    for k, (typ, default) in extra.items():
        ap.add_argument("--" + k.replace("_", "-"), type=typ, default=default)
    return ap


def params_from(args, params_cls):
    return params_cls(**{f.name: getattr(args, f.name) for f in fields(params_cls)})
