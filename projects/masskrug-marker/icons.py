"""
Icon library for the Maßkrug clip badge.

Every icon is a 2D manifold3d.CrossSection in badge coordinates (mm):
u = horizontal (badge width), v = vertical (along the handle), origin = badge
centre. Usable box: |u| <= 5.0, |v| <= 3.5. The region returned is RECESSED
into the badge; holes inside it stay raised (islands), which is how faces,
eyes etc. get contrast.

Printability rules (0.4 mm nozzle, recess 0.8 mm deep):
recessed features >= 0.7 mm wide, raised islands / walls >= 0.6 mm.
`check_icon` verifies both with morphological opening.
"""
from __future__ import annotations

import math

import numpy as np
import manifold3d as m3

C = m3.CrossSection
BOX_U, BOX_V = 5.0, 3.5


# ------------------------------------------------------------------ primitives
def circ(r, u=0.0, v=0.0, seg=48):
    return C.circle(r, seg).translate([u, v])


def ell(ru, rv, u=0.0, v=0.0, rot=0.0, seg=48):
    return C.circle(1.0, seg).scale([ru, rv]).rotate(rot).translate([u, v])


def box(u0, u1, v0, v1):
    return C.square([u1 - u0, v1 - v0]).translate([u0, v0])


def poly(pts):
    pts = [tuple(map(float, p)) for p in pts]
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return C([pts if a > 0 else pts[::-1]])       # CCW, otherwise manifold drops it


def stroke(pts, w):
    """Round-capped polyline of width w."""
    r = w / 2
    parts = [(circ(r, *a, seg=24) + circ(r, *b, seg=24)).hull() for a, b in zip(pts[:-1], pts[1:])]
    return C.batch_boolean(parts, m3.OpType.Add)


def union(*cs):
    return C.batch_boolean(list(cs), m3.OpType.Add)


def fit(cs, w=2 * BOX_U, h=2 * BOX_V):
    """Uniformly scale + centre a shape into the usable box."""
    (u0, v0), (u1, v1) = cs.bounds()[:2], cs.bounds()[2:]
    s = min(w / (u1 - u0), h / (v1 - v0))
    return cs.translate([-(u0 + u1) / 2, -(v0 + v1) / 2]).scale([s, s])


def norm(cs):
    """Scale down (never up) so the icon stays inside the usable box."""
    b = cs.bounds()
    if b[0] >= -BOX_U and b[2] <= BOX_U and b[1] >= -BOX_V and b[3] <= BOX_V:
        return cs
    return fit(cs)


# ------------------------------------------------------------------ stroke font (3 x 5 grid)
GLYPHS = {
    "0": [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)], [(0, 0.6), (2, 3.4)]],
    "1": [[(0.2, 3), (1, 4), (1, 0)], [(0, 0), (2, 0)]],
    "5": [[(2, 4), (0, 4), (0, 2), (2, 2), (2, 0), (0, 0)]],
    "6": [[(2, 4), (0, 4), (0, 0), (2, 0), (2, 2), (0, 2)]],
    "7": [[(0, 4), (2, 4), (0.8, 0)]],
    "8": [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)], [(0, 2), (2, 2)]],
    "9": [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 2), (2, 2)]],
    "A": [[(0, 0), (0, 3), (1, 4), (2, 3), (2, 0)], [(0, 1.8), (2, 1.8)]],
    "C": [[(2, 4), (0, 4), (0, 0), (2, 0)]],
    "M": [[(0, 0), (0, 4), (1, 2), (2, 4), (2, 0)]],
    "P": [[(0, 0), (0, 4), (2, 4), (2, 2), (0, 2)]],
    "R": [[(0, 0), (0, 4), (2, 4), (2, 2), (0, 2), (2, 0)]],
    "U": [[(0, 4), (0, 0), (2, 0), (2, 4)]],
}


def text(s, w=0.75, gap=0.65, s_max=1.0, s_min=0.66):
    """Stroke text fitted into the usable box; thinner strokes for long strings,
    raises if the counters would close (2*scale - stroke < 0.6 mm)."""
    n = len(s)
    for w in (w, 0.65):
        sc = min(s_max, (2 * BOX_U - (n - 1) * gap - n * w) / (2 * n), (2 * BOX_V - w) / 4)
        if 2 * sc - w >= 0.6:
            break
    if 2 * sc - w < 0.6:
        raise ValueError(f"text '{s}' too long for the badge (scale {sc:.2f} < {s_min})")
    adv = 2 * sc + w + gap
    parts = []
    for i, ch in enumerate(s):
        for line in GLYPHS[ch]:
            parts.append(stroke([(i * adv + x * sc, y * sc) for x, y in line], w))
    t = union(*parts)
    b = t.bounds()
    return t.translate([-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2])


# ------------------------------------------------------------------ poker
def heart_curve(scale=0.21, n=120):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    return poly(np.c_[x, y + 2.5] * scale)


def heart():
    return heart_curve(0.215)


def spade():
    top = heart_curve(0.17).mirror([0, 1]).translate([0, 0.9])
    stem = poly([(-1.6, -3.4), (1.6, -3.4), (0.35, -0.6), (-0.35, -0.6)])
    return fit(union(top, stem))


def club():
    leaves = union(circ(1.45, 0, 1.55), circ(1.45, -1.6, -0.35), circ(1.45, 1.6, -0.35), circ(0.9, 0, 0.3))
    stem = poly([(-1.5, -3.4), (1.5, -3.4), (0.3, -0.4), (-0.3, -0.4)])
    return fit(union(leaves, stem))


def card_diamond():
    t = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    n = 0.9                                     # < 1: slightly concave sides like a card pip
    return poly(np.c_[2.6 * np.sign(c) * np.abs(c) ** (2 / n), 3.5 * np.sign(s) * np.abs(s) ** (2 / n)])


def chip():
    ring = circ(3.5, seg=72) - circ(2.7, seg=72)
    for k in range(6):
        ring -= box(-0.45, 0.45, 2.6, 3.6).rotate(60 * k)
    return ring + circ(1.85, seg=48) - circ(1.0, seg=48)


def ace():
    a = text("A", s_max=0.95).translate([-1.9, 0])
    return union(a, heart_curve(0.1).translate([2.5, -0.2]))


# ------------------------------------------------------------------ emoji
def smiley():
    ring = circ(3.5, seg=72) - circ(2.75, seg=72)
    eyes = circ(0.5, -1.1, 0.8) + circ(0.5, 1.1, 0.8)
    t = np.linspace(math.radians(200), math.radians(340), 12)
    mouth = stroke([(1.7 * math.cos(a), 1.7 * math.sin(a) + 0.2) for a in t], 0.75)
    return union(ring, eyes, mouth)


def cool():
    ring = circ(3.5, seg=72) - circ(2.75, seg=72)
    glasses = union(ell(1.05, 0.75, -1.15, 0.6), ell(1.05, 0.75, 1.15, 0.6), box(-1.2, 1.2, 0.95, 1.35))
    t = np.linspace(math.radians(215), math.radians(330), 10)
    mouth = stroke([(1.5 * math.cos(a) + 0.2, 1.5 * math.sin(a) + 0.1) for a in t], 0.7)
    return union(ring, glasses, mouth)


def skull():
    head = union(circ(3.0, 0, 0.6, seg=64), box(-1.8, 1.8, -3.4, -1.2))
    head -= circ(0.85, -1.1, 0.5) + circ(0.85, 1.1, 0.5)          # eye sockets (raised)
    head -= poly([(0, -0.3), (-0.45, -1.1), (0.45, -1.1)])
    for u in (-0.6, 0.6):
        head -= box(u - 0.35, u + 0.35, -3.5, -2.3)                 # teeth gaps
    return head


def fire():
    outer = poly([(0, 3.5), (1.1, 1.8), (2.0, 0.6), (2.5, -1.0), (2.2, -2.5), (1.2, -3.4), (-1.2, -3.4),
                  (-2.3, -2.4), (-2.5, -0.9), (-1.9, 0.9), (-1.3, 0.1), (-0.9, 1.8)])
    inner = poly([(0.2, 0.8), (1.0, -0.6), (1.1, -1.9), (0.4, -2.7), (-0.6, -2.7), (-1.1, -1.9), (-0.8, -1.0),
                  (-0.3, -1.4)])
    return outer - inner


def poop():
    return union(ell(3.2, 0.95, 0, -2.5), ell(2.5, 0.85, 0, -1.0), ell(1.7, 0.75, 0, 0.4),
                 poly([(-1.0, 0.8), (1.0, 0.8), (0.2, 2.6), (-0.1, 3.3)]))


def ghost():
    body = union(circ(2.6, 0, 0.8, seg=64), box(-2.6, 2.6, -2.6, 0.8))
    for u in (-1.75, 0, 1.75):
        body -= circ(0.62, u, -3.05)
    return body - circ(0.55, -0.9, 1.0) - circ(0.55, 0.9, 1.0) - ell(0.5, 0.7, 0, -0.6)


def eggplant():
    body = ell(1.55, 3.1, 0, -0.3, seg=64).rotate(-38)
    cap = union(ell(1.25, 0.8, -1.55, 1.7, rot=-38), stroke([(-1.8, 2.1), (-2.6, 3.2)], 0.75))
    return fit(union(body, cap) - stroke([(-0.95, 1.05), (-0.35, 1.75)], 0.6))

def peach():
    fruit = union(circ(2.35, -1.05, -0.6), circ(2.35, 1.05, -0.6))
    cleft = stroke([(0.0, 1.6), (0.35, 0.2), (0.1, -1.4)], 0.65)
    leaf = ell(1.5, 0.6, 1.4, 2.4, rot=25)
    return fit(union(fruit - cleft, leaf))


def lightning():
    return poly([(1.4, 3.5), (-1.9, -0.2), (-0.1, -0.2), (-1.3, -3.5), (2.0, 0.6), (0.2, 0.6)]).offset(
        0.2, m3.JoinType.Round)

def beer():
    mug = box(-2.6, 1.2, -3.4, 1.4)
    handle = union(box(1.0, 3.2, -1.8, 1.0)) - box(1.2, 2.4, -1.1, 0.3)
    foam = union(circ(0.9, -2.0, 1.8), circ(1.0, -0.7, 2.2), circ(0.95, 0.6, 1.9))
    return mug + handle + foam


def mass():
    """Maßkrug with raised 'dimples' like the real Masskrug."""
    m = beer()
    for u in (-1.8, -0.7):
        for v in (-2.3, -0.9):
            m -= ell(0.35, 0.5, u + 0.1, v + 0.1)
    return m


# ------------------------------------------------------------------ Bavaria / Munich
def brezn():
    w = 1.05
    belly = stroke([(-3.6, 0.6), (-3.1, -1.9), (-1.6, -3.1), (0, -3.3), (1.6, -3.1), (3.1, -1.9), (3.6, 0.6)], 1.4)
    left = stroke([(-3.6, 0.6), (-3.5, 2.4), (-2.3, 3.3), (-0.9, 2.9), (0.2, 1.2), (1.2, -1.1), (1.6, -2.7)], w)
    right = stroke([(3.6, 0.6), (3.5, 2.4), (2.3, 3.3), (0.9, 2.9), (-0.2, 1.2), (-1.2, -1.1), (-1.6, -2.7)], w)
    return fit(union(belly, left, right))


def raute():
    s = 1.55                                        # lozenge half diagonal
    rec = []
    for i in range(-4, 5):
        for j in range(-3, 4):
            if (i + j) % 2 == 0:
                rec.append(poly([(0, s), (s * 1.3, 0), (0, -s), (-s * 1.3, 0)]).offset(-0.25, m3.JoinType.Miter)
                           .translate([i * s * 1.3, j * s]))
    return union(*rec) ^ box(-BOX_U, BOX_U, -BOX_V, BOX_V)


def lebkuchenherz():
    h = heart_curve(0.215)
    ring = h - h.offset(-0.8, m3.JoinType.Round)
    dots = union(*[circ(0.42, u, v) for u, v in ((-1.3, 0.9), (0, 0.2), (1.3, 0.9), (0, -1.5))])
    return ring + dots


def weisswurst():
    a = stroke([(-3.8, -2.0), (-1.6, -0.9), (1.6, -0.9), (3.8, -2.0)], 1.9)
    b = stroke([(-3.8, 1.0), (-1.6, 2.1), (1.6, 2.1), (3.8, 1.0)], 1.9)
    ends = union(*[circ(0.45, u, v) for u, v in ((-4.6, -2.4), (4.6, -2.4), (-4.6, 0.6), (4.6, 0.6))])
    return fit(union(a, b, ends))

def edelweiss():
    petals = union(*[ell(0.85, 2.3, 0, 2.0, seg=32).rotate(360 / 7 * k) for k in range(7)])
    return fit(petals - circ(1.25, seg=48) + union(*[circ(0.3, 0.55 * math.cos(a), 0.55 * math.sin(a))
                                                      for a in np.radians([90, 210, 330])]))


def lederhosn():
    shorts = poly([(-2.9, -3.4), (-0.5, -3.4), (0, -1.3), (0.5, -3.4), (2.9, -3.4), (2.4, 0.5), (-2.4, 0.5)])
    straps = union(stroke([(-1.5, 0.3), (-1.5, 3.3)], 0.8), stroke([(1.5, 0.3), (1.5, 3.3)], 0.8),
                   box(-1.5, 1.5, 1.8, 2.6))
    return shorts + straps


def frauenkirche():
    towers = box(-3.6, -1.2, -3.5, 1.3) + box(1.2, 3.6, -3.5, 1.3)
    caps = union(ell(1.2, 1.3, -2.4, 1.5), ell(1.2, 1.3, 2.4, 1.5), stroke([(-2.4, 2.4), (-2.4, 3.5)], 0.6),
                 stroke([(2.4, 2.4), (2.4, 3.5)], 0.6))
    nave = box(-1.3, 1.3, -3.5, -1.0)
    windows = union(box(-2.7, -2.1, -1.6, -0.2), box(2.1, 2.7, -1.6, -0.2))
    return union(towers, caps, nave) - windows


def olympiaturm():
    shaft = stroke([(0, -3.2), (0, 1.2)], 1.0)
    pod = ell(1.9, 0.75, 0, 1.4)
    top = stroke([(0, 2.0), (0, 3.05)], 0.85)
    base = box(-2.0, 2.0, -3.5, -2.8)
    return union(shaft, pod, top, base)


def kindl():
    """Stylised Münchner Kindl: hooded monk, raised oath hand, book."""
    hood = circ(1.35, 0, 2.05)
    robe = poly([(-2.6, -3.5), (2.6, -3.5), (1.4, 1.2), (-1.4, 1.2)])
    arm = stroke([(1.2, 0.4), (2.6, 1.6), (2.8, 2.9)], 0.8)
    book = box(-3.2, -1.6, -0.9, 0.6)
    face = ell(0.6, 0.7, 0, 1.85)
    return union(hood, robe, arm, book) - face


def arena():
    shell = ell(4.9, 2.3, 0, 0.6, seg=96) - box(-5, 5, 0.25, 0.95)
    return shell + box(-3.8, 3.8, -3.5, -2.4)


def label(s):
    return lambda: text(s)


# ------------------------------------------------------------------ pr0gramm (fan references, no logo)
def fliesentisch():
    top = box(-4.9, 4.9, 0.6, 3.5)
    for u in (-1.6, 1.6):
        top -= box(u - 0.35, u + 0.35, 0.6, 3.5)
    top -= box(-5, 5, 1.7, 2.4)
    legs = union(stroke([(-3.9, 0.6), (-3.9, -3.1)], 0.9), stroke([(3.9, 0.6), (3.9, -3.1)], 0.9),
                 box(-3.9, 3.9, -1.6, -0.9))
    return top + legs

def benis():
    frame = C.square([6.4, 6.4], True).offset(0.6, m3.JoinType.Round)
    frame = frame - C.square([5.0, 5.0], True).offset(0.4, m3.JoinType.Round)
    return frame + box(-2.0, 2.0, -0.45, 0.45) + box(-0.45, 0.45, -2.0, 2.0)


# ------------------------------------------------------------------ memes
def stonks():
    line = stroke([(-4.6, -3.0), (-2.2, -0.6), (-0.8, -1.8), (1.8, 1.6)], 0.95)
    head = poly([(3.8, 3.4), (0.5, 2.7), (2.9, 0.2)])
    return line + head


def penguin():
    body = union(ell(2.0, 2.9, 0, -0.5, seg=64), circ(1.45, 0.2, 2.1))
    belly = ell(1.1, 2.0, 0.55, -0.8)
    beak = poly([(1.4, 2.4), (2.8, 2.0), (1.4, 1.7)])
    feet = union(ell(0.9, 0.45, 0.6, -3.3), ell(0.9, 0.45, -0.9, -3.3))
    flipper = ell(0.5, 1.5, -1.9, -0.6, rot=-20)
    return union(body, beak, feet, flipper) - belly - circ(0.3, 0.7, 2.4)


def spinner():
    lobes = union(*[circ(1.55, 2.0 * math.cos(a), 2.0 * math.sin(a)) for a in np.radians([90, 210, 330])])
    core = poly([(2.0 * math.cos(a), 2.0 * math.sin(a)) for a in np.radians([90, 210, 330])]).offset(
        0.7, m3.JoinType.Round)
    holes = union(*[circ(0.7, 2.0 * math.cos(a), 2.0 * math.sin(a)) for a in np.radians([90, 210, 330])],
                  circ(0.8))
    return fit(union(lobes, core) - holes)


def labubu():
    head = union(circ(2.5, 0, -0.9, seg=64), ell(0.75, 1.9, -1.3, 1.9, rot=12), ell(0.75, 1.9, 1.3, 1.9, rot=-12))
    eyes = ell(0.55, 0.7, -0.95, -0.4) + ell(0.55, 0.7, 0.95, -0.4)
    pts = [(-1.5, -1.9)]
    for k in range(9):
        pts.append((-1.5 + 3.0 * (k + 0.5) / 9, -1.9 - (0.45 if k % 2 == 0 else 0.0)))
    pts.append((1.5, -1.9))
    grin = poly(pts + [(1.2, -2.6), (-1.2, -2.6)][::-1][::-1])
    return fit(head - eyes - grin.offset(0.05))


def tungtung():
    log = C.square([3.0, 6.6], True).offset(0.4, m3.JoinType.Round).translate([-1.2, 0])
    face = circ(0.45, -1.8, 1.4) + circ(0.45, -0.6, 1.4) + box(-1.9, -0.5, -0.2, 0.35)
    bat = union(stroke([(1.6, -3.2), (3.4, 2.2)], 0.9), stroke([(2.9, 0.7), (3.6, 2.9)], 1.5))
    return log - face + bat


# ------------------------------------------------------------------ the joke
def get(name):
    return norm(ICONS[name][1]())


# name -> (category, factory)
ICONS = {
    "heart": ("poker", heart), "spade": ("poker", spade), "club": ("poker", club),
    "card_diamond": ("poker", card_diamond), "chip": ("poker", chip), "ace": ("poker", ace),
    "smiley": ("emoji", smiley), "cool": ("emoji", cool), "skull": ("emoji", skull), "fire": ("emoji", fire),
    "poop": ("emoji", poop), "ghost": ("emoji", ghost), "eggplant": ("emoji", eggplant), "peach": ("emoji", peach),
    "lightning": ("emoji", lightning), "beer": ("emoji", beer),
    "mass": ("bavaria", mass), "brezn": ("bavaria", brezn), "raute": ("bavaria", raute),
    "lebkuchenherz": ("bavaria", lebkuchenherz), "weisswurst": ("bavaria", weisswurst),
    "edelweiss": ("bavaria", edelweiss), "lederhosn": ("bavaria", lederhosn),
    "frauenkirche": ("munich", frauenkirche), "olympiaturm": ("munich", olympiaturm), "kindl": ("munich", kindl),
    "arena": ("munich", arena), "089": ("munich", label("089")), "muc": ("munich", label("MUC")),
    "pr0": ("pr0gramm", label("PR0")), "fliesentisch": ("pr0gramm", fliesentisch), "benis": ("pr0gramm", benis),
    "67": ("memes", label("67")), "stonks": ("memes", stonks), "penguin": ("memes", penguin),
    "spinner": ("memes", spinner), "labubu": ("memes", labubu), "tungtung": ("memes", tungtung),
}


def check_icon(cs, recess_min=0.7, wall_min=0.6):
    """Morphological checks: fraction of the recess lost when features < recess_min are removed,
    and fraction of the raised area lost when walls < wall_min are removed (inside the box)."""
    a = cs.area()
    lost_rec = (cs - cs.offset(-recess_min / 2, m3.JoinType.Round).offset(recess_min / 2, m3.JoinType.Round)).area()
    boxc = box(-BOX_U - 1, BOX_U + 1, -BOX_V - 1, BOX_V + 1)
    raised = boxc - cs
    lost_wall = (raised - raised.offset(-wall_min / 2, m3.JoinType.Round).offset(wall_min / 2,
                                                                               m3.JoinType.Round)).area()
    b = cs.bounds()
    inside = b[0] >= -BOX_U - 0.05 and b[2] <= BOX_U + 0.05 and b[1] >= -BOX_V - 0.05 and b[3] <= BOX_V + 0.05
    return dict(area_mm2=round(a, 1), thin_recess_pct=round(100 * lost_rec / max(a, 1e-9), 1),
                thin_wall_mm2=round(lost_wall, 2), inside_box=bool(inside))
