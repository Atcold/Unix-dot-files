#!/usr/bin/env python3
"""Add the missing pinyin caron letters to Cascadia Code / Caskaydia Cove.

    uv run --with fonttools --quiet python \
        Projects/tech-projects/second-brain/scripts/patch_pinyin_font.py \
        ~/Library/Fonts/CaskaydiaCoveNerdFont-ExtraLight.ttf

Cascadia Code covers U+01CD/U+01CE (Ǎ ǎ) and then stops: U+01CF through U+01DC
are absent — no cmap entry and no glyph. That range is exactly the third tone of
i, o and u plus all four tones of ü, so seven of the 24 tone-marked pinyin
vowels are missing. The terminal then substitutes a proportional face (Helvetica
on macOS), which is why ǐ looks foreign next to i and why a column of ǒ drifts
out of alignment with a column of o.

Nothing needs drawing. Every caron letter already in the font is a composite of
a base plus the combining mark, and the pieces these need are all present:

    U+01CE ǎ -> a        + uni030C
    U+01F0 ǰ -> uni0237  + uni030C     (dotless j — the pattern ǐ needs)
    U+010C Č -> C        + uni030C.case

So this assembles the missing letters the same way. The i must use `dotlessi`
(U+0131), not `i`, or the tittle collides with the caron.

Marks are centred on the base's ink rather than copied from a neighbour, since
the offsets in the font vary per letter (a@-20, c@+50, n@-10). For the ü set the
mark is raised clear of the diaeresis, because no existing glyph stacks two
marks and there is nothing to copy.

The patched font is written beside the original with a new family name, so it
installs alongside rather than fighting the original in the font cache.
"""

import argparse
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent

ARGS_ARE_XY_VALUES = 0x0002
ROUND_XY_TO_GRID = 0x0004

# Breathing room between a diaeresis and the mark stacked above it, in font
# units (the em here is 2048). Small enough to stay within the line, large
# enough that the two marks do not read as one blob at terminal sizes.
GAP = 60

# codepoint -> (glyph name, base glyph, mark glyph, stacked?)
# `stacked` means the mark sits above an existing diaeresis and needs a lift;
# every other mark is drawn at its natural height and needs none.
PLAN = [
    (0x01CF, "uni01CF", "I", "uni030C.case", False),
    (0x01D0, "uni01D0", "dotlessi", "uni030C", False),
    (0x01D1, "uni01D1", "O", "uni030C.case", False),
    (0x01D2, "uni01D2", "o", "uni030C", False),
    (0x01D3, "uni01D3", "U", "uni030C.case", False),
    (0x01D4, "uni01D4", "u", "uni030C", False),
    (0x01D5, "uni01D5", "Udieresis", "uni0304", True),
    (0x01D6, "uni01D6", "udieresis", "uni0304", True),
    (0x01D7, "uni01D7", "Udieresis", "acute", True),
    (0x01D8, "uni01D8", "udieresis", "acute", True),
    (0x01D9, "uni01D9", "Udieresis", "uni030C.case", True),
    (0x01DA, "uni01DA", "udieresis", "uni030C", True),
    (0x01DB, "uni01DB", "Udieresis", "grave", True),
    (0x01DC, "uni01DC", "udieresis", "grave", True),
]


def ink_bounds(glyf, name):
    """(xMin, xMax, yMin, yMax) of a glyph's ink, resolving composites."""
    g = glyf[name]
    g.expand(glyf)
    if g.numberOfContours == 0:
        return None
    if g.isComposite():
        boxes = []
        for c in g.components:
            b = ink_bounds(glyf, c.glyphName)
            if b:
                boxes.append((b[0] + c.x, b[1] + c.x, b[2] + c.y, b[3] + c.y))
        if not boxes:
            return None
        return (min(b[0] for b in boxes), max(b[1] for b in boxes),
                min(b[2] for b in boxes), max(b[3] for b in boxes))
    coords = g.getCoordinates(glyf)[0]
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return (min(xs), max(xs), min(ys), max(ys))


def build(font, out_path, family_suffix):
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    cmap = font.getBestCmap()
    order = set(font.getGlyphOrder())

    added, skipped = [], []
    for cp, name, base, mark, stacked in PLAN:
        if cp in cmap:
            skipped.append((name, "already mapped"))
            continue
        if base not in order or mark not in order:
            missing = base if base not in order else mark
            skipped.append((name, f"no {missing}"))
            continue

        bb, mb = ink_bounds(glyf, base), ink_bounds(glyf, mark)
        if not bb or not mb:
            skipped.append((name, "empty base or mark"))
            continue

        # Centre the mark over the base's ink.
        dx = round(((bb[0] + bb[1]) - (mb[0] + mb[1])) / 2)
        # A mark is drawn at the height it expects to sit, so an unstacked one
        # needs no lift. Over a diaeresis it does: raise it so its underside
        # clears the base's ink, plus a small gap.
        dy = 0
        if stacked:
            base_top, mark_bottom = bb[3], mb[2]
            dy = round(base_top - mark_bottom) + GAP

        # ARGS_ARE_XY_VALUES is not optional: without it the two numbers are
        # read as point indices to be matched up, not as an offset, and the
        # component lands somewhere arbitrary. That is what silently ate the
        # diaeresis out of ǖ on the first attempt.
        flags = ARGS_ARE_XY_VALUES | ROUND_XY_TO_GRID

        comp_base = GlyphComponent()
        comp_base.glyphName, comp_base.x, comp_base.y = base, 0, 0
        comp_base.flags = flags

        comp_mark = GlyphComponent()
        comp_mark.glyphName, comp_mark.x, comp_mark.y = mark, dx, dy
        comp_mark.flags = flags

        g = Glyph()
        g.numberOfContours = -1
        g.components = [comp_base, comp_mark]
        glyf[name] = g
        hmtx[name] = hmtx[base]

        for table in font["cmap"].tables:
            if table.isUnicode():
                table.cmap[cp] = name
        added.append((name, chr(cp), base, mark, dx, dy))

    # A distinct family name so it installs alongside the original instead of
    # colliding with it in the font cache.
    name_tbl = font["name"]
    for rec in name_tbl.names:
        if rec.nameID in (1, 4, 16):
            val = rec.toUnicode()
            if family_suffix not in val:
                rec.string = f"{val} {family_suffix}"
        elif rec.nameID == 6:  # PostScript name: no spaces allowed
            rec.string = rec.toUnicode() + family_suffix.replace(" ", "")

    font.save(out_path)
    return added, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("font", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--suffix", default="Pinyin")
    args = ap.parse_args()

    if not args.font.exists():
        sys.exit(f"no such font: {args.font}")
    out = args.out or args.font.with_name(
        f"{args.font.stem}-{args.suffix.lower()}{args.font.suffix}")

    font = TTFont(args.font, fontNumber=0)
    added, skipped = build(font, out, args.suffix)

    for name, ch, base, mark, dx, dy in added:
        print(f"  + {ch}  {name:10s} = {base} + {mark}  @({dx},{dy})")
    for name, why in skipped:
        print(f"  - {name:10s} skipped: {why}")
    print(f"\n{len(added)} glyph(s) added -> {out}")


if __name__ == "__main__":
    main()
