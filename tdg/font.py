"""Real outline fonts (TTF/OTF via fontTools) -> manifold3d CrossSection.

Bundled fonts (SIL Open Font License 1.1, see tdg/fonts/*-OFL.txt):
  outfit        Outfit Bold        geometric sans, default
  bigshoulders  Big Shoulders Bold condensed, for long texts
  nationalpark  National Park Bold rounded signage style
Any other .ttf/.otf path works too.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import manifold3d as m3

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONTS = {"outfit": "Outfit-Bold.ttf", "bigshoulders": "BigShoulders-Bold.ttf", "nationalpark": "NationalPark-Bold.ttf"}
_cache = {}


def font_path(name):
    return FONT_DIR / FONTS[name] if name in FONTS else Path(name)


def _load(name):
    from fontTools.ttLib import TTFont
    key = str(font_path(name))
    if key not in _cache:
        _cache[key] = TTFont(key)
    return _cache[key]


class _PolyPen:
    """fontTools pen that flattens quadratic / cubic segments into polylines."""

    def __init__(self, glyphset, steps=8):
        from fontTools.pens.basePen import BasePen

        outer = self

        class P(BasePen):
            def _moveTo(self, p):
                outer.cur = [p]

            def _lineTo(self, p):
                outer.cur.append(p)

            def _qCurveToOne(self, p1, p2):
                p0 = self._getCurrentPoint()
                for t in np.linspace(0, 1, steps + 1)[1:]:
                    outer.cur.append(tuple((1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1)
                                           + t ** 2 * np.array(p2)))

            def _curveToOne(self, p1, p2, p3):
                p0 = self._getCurrentPoint()
                for t in np.linspace(0, 1, steps + 1)[1:]:
                    a = np.array
                    outer.cur.append(tuple((1 - t) ** 3 * a(p0) + 3 * (1 - t) ** 2 * t * a(p1)
                                           + 3 * (1 - t) * t ** 2 * a(p2) + t ** 3 * a(p3)))

            def _closePath(self):
                if len(outer.cur) > 2:
                    outer.contours.append(outer.cur)
                outer.cur = []

            _endPath = _closePath

        self.contours, self.cur = [], []
        self.pen = P(glyphset)


def text_outline(text, font="outfit", cap_height=6.5, tracking=0.04, steps=8):
    """Text as CrossSection in mm, baseline at y=0, starts at x=0. cap_height = height of capital letters.
    tracking: extra letter spacing in em. Kerning is not applied."""
    f = _load(font)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm
    cap = getattr(f["OS/2"], "sCapHeight", 0) or 0.7 * upm
    s = cap_height / cap
    x = 0.0
    contours = []
    for ch in text:
        if ord(ch) not in cmap:
            raise ValueError(f"font {font!r} has no glyph for {ch!r}")
        gname = cmap[ord(ch)]
        pp = _PolyPen(gs, steps)
        gs[gname].draw(pp.pen)
        for c in pp.contours:
            contours.append([((px + x) * s, py * s) for px, py in c])
        x += gs[gname].width + tracking * upm
    if not contours:
        return m3.CrossSection(), 0.0
    cs = m3.CrossSection(contours, m3.FillRule.NonZero)
    return cs, (x - tracking * upm) * s


def license_note(font="outfit"):
    f = _load(font)
    return f"{f['name'].getDebugName(4)} ({f['name'].getDebugName(5)}), SIL Open Font License 1.1"
