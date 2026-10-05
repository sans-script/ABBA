#!/usr/bin/env python3
"""
Build SVG outlines for every lyric word used by the site.

Reads site/data/scenes.json, lays each word out with the font's advance
widths and kerning, and writes site/data/words.json. The page draws these
outlines, so the font file itself is never served.

Requirements:
    pip install fonttools skia-pathops

Usage:
    python tools/build_words.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from pathops import Path as UnionPath
from pathops import PathOp, op


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "fonts" / "Futura Script EF Regular.ttf"
SCENES = ROOT / "site" / "data" / "scenes.json"
OUTPUT = ROOT / "site" / "data" / "words.json"

# Letter spacing in font units (1000 per em), added between letters on top
# of kerning. The reference sets the script tight enough that letters touch.
TRACKING = -45

# Script joins: letters whose outlines come within CONNECT_GAP of each
# other are pulled together until they overlap by JOIN_OVERLAP, so the
# union makes one solid stroke (a bare touch would bevel into a groove).
# Wider pairs stay apart, as W-a and V-i do in the reference.
CONNECT_GAP = 20
JOIN_OVERLAP = 30


def _glyph_path(glyphs, name: str, x: float) -> UnionPath:
    path = UnionPath()
    glyphs[name].draw(TransformPen(path.getPen(), (1, 0, 0, 1, x, 0)))
    return path


def contact(glyphs, left: str, left_x: float, right: str, right_x: float) -> int:
    """
    Signed outline distance between two placed glyphs: > 0 is the gap to
    close until they touch, <= 0 is minus how deep they already overlap.
    """

    fixed = _glyph_path(glyphs, left, left_x)

    def touching(shift: int) -> bool:
        moved = _glyph_path(glyphs, right, right_x - shift)
        return op(fixed, moved, PathOp.INTERSECTION).area > 1

    lo, hi = -300, 300  # smallest shift (leftward) at which they touch
    if not touching(hi):
        return hi
    while lo < hi:
        mid = (lo + hi) // 2
        if touching(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def kerning(font: TTFont) -> dict[tuple[str, str], int]:
    pairs: dict[tuple[str, str], int] = {}

    if "kern" in font:
        for table in font["kern"].kernTables:
            pairs.update(table.kernTable)

    return pairs


def word_outline(font: TTFont, word: str, kern: dict) -> dict:
    """
    One SVG path for the word: baseline at y=0, y pointing down, font units.
    Letters are unioned into a single outline, so where script letters
    overlap they join seamlessly instead of stacking as separate shapes.
    """

    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    hmtx = font["hmtx"]

    union = UnionPath()
    pen = union.getPen()
    x = 0
    previous = None
    previous_x = 0

    for char in word:
        name = cmap.get(ord(char))

        if name is None:
            raise ValueError(f"Font has no glyph for {char!r} in {word!r}")

        if previous is not None:
            x += kern.get((previous, name), 0) + TRACKING
            distance = contact(glyphs, previous, previous_x, name, x)
            if -JOIN_OVERLAP < distance <= CONNECT_GAP:
                x -= distance + JOIN_OVERLAP

        glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        previous, previous_x = name, x
        x += hmtx[name][0]

    union.simplify()
    svg = SVGPathPen(glyphs)
    union.draw(svg)
    return {"d": svg.getCommands(), "advance": x}


def main() -> None:
    font = TTFont(FONT)
    kern = kerning(font)
    scenes = json.loads(SCENES.read_text(encoding="utf-8"))["scenes"]

    words = sorted({
        word
        for scene in scenes
        for line in scene["lines"]
        for word in line
    })

    space = font["hmtx"][font.getBestCmap()[ord(" ")]][0]

    data = {
        "unitsPerEm": font["head"].unitsPerEm,
        "ascent": font["hhea"].ascent,
        "descent": font["hhea"].descent,
        "space": space,
        "words": {word: word_outline(font, word, kern) for word in words},
    }

    OUTPUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{len(words)} words -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
