"""Font measurement and glyph outlining. Everything here works in millimetres."""
from __future__ import annotations
import functools, pathlib
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FONT_DIR = pathlib.Path(__file__).parent / "fonts"
SANS = "BarlowSemiCondensed-Bold"
MONO = "IBMPlexMono-SemiBold"


class Face:
    def __init__(self, name: str):
        self.name = name
        self.font = TTFont(FONT_DIR / f"{name}.ttf", lazy=False)
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"].metrics
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        os2 = self.font["OS/2"]
        self.cap = (getattr(os2, "sCapHeight", None) or int(self.upm * 0.70)) / self.upm

    def _g(self, ch: str) -> str:
        return self.cmap.get(ord(ch)) or self.cmap.get(ord("?")) or ".notdef"

    def width(self, text: str, size: float) -> float:
        u = sum(self.hmtx.get(self._g(c), (self.upm // 2, 0))[0] for c in text)
        return u * size / self.upm

    def cap_height(self, size: float) -> float:
        return self.cap * size

    def path(self, text: str, size: float, xscale: float = 1.0) -> str:
        """SVG path data for `text`, baseline at y=0, left edge at x=0, y growing downward."""
        s = size / self.upm
        pen = SVGPathPen(self.glyphs)
        x = 0.0
        for ch in text:
            g = self._g(ch)
            if ch != " ":
                self.glyphs[g].draw(TransformPen(pen, (s * xscale, 0, 0, -s, x, 0)))
            x += self.hmtx.get(g, (self.upm // 2, 0))[0] * s * xscale
        return pen.getCommands()


@functools.lru_cache(maxsize=None)
def face(name: str) -> Face:
    return Face(name)


def fit(text: str, name: str, box: float, max_size: float, min_size: float,
        squeeze: float = 0.86):
    """Fit `text` into `box` mm.

    Ladder: shrink the point size, then compress glyphs to `squeeze`, then
    middle-ellipsis (a part number is identified by its prefix and suffix).
    Returns (size, xscale, text, demotion) where demotion is None when the
    string set at full size with no tricks.
    """
    f = face(name)
    natural = f.width(text, max_size)
    if natural <= box:
        return max_size, 1.0, text, None
    size = max_size * box / natural
    if size >= min_size:
        return size, 1.0, text, None
    size = min_size
    w = f.width(text, size)
    if w <= box:
        return size, 1.0, text, None
    if box / w >= squeeze:
        return size, box / w, text, f"squeezed to {box / w:.0%}"
    t = text
    while len(t) > 5:
        cut = t[: len(t) // 2 - 1] + t[len(t) // 2 :]
        if f.width(cut[: len(cut) // 2] + "…" + cut[len(cut) // 2 :], size) <= box:
            t = cut
            break
        t = cut
    t = t[: len(t) // 2] + "…" + t[len(t) // 2 :]
    w = f.width(t, size)
    xs = min(1.0, box / w)
    return size, xs, t, f"truncated to {t!r}"
