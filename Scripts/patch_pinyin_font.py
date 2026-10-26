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

It also turns off the ligatures for `<=` and `<<=`. In Verilog `<=` is an
assignment, and in C `<<=` is one too, but the font draws them as ≤ and ≪=. The
ligatures live in the GSUB table's chaining rules (`calt`): each rule, on
seeing its glyphs in context, calls a substitution that swaps in a ligature
glyph such as `less_equal.liga`. Removing `less` from the input of the rules
whose substitution would turn it into one of those glyphs leaves `<` and `=` as
they are, and every other ligature untouched.

Runs of hyphens are drawn as one line, so git's `-----` (lines removed) reads as
a rule. The `--` and `---` ligatures go the same way as `<=`. Longer runs are a
sequence: the first hyphen turns into `hyphen_start.seq` if the next glyph is a
hyphen, `<`, `>` or `|`, and the rest follow. Taking the hyphen out of that
look-ahead leaves plain runs alone, while `->`, `<--` and `|--` still join; the
cost is that `-->` shows as a dash and then a joined `->`.

The patched font is written beside the original with a new family name, so it
installs alongside rather than fighting the original in the font cache.
"""

import argparse
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
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

# Ligature glyphs the terminal should never show: `<=` alone, and as the start
# of a longer run (`<==`, `<=>`), and `<<=`.
NO_LIGATURE = {
    "less_equal.liga", "less_equal_start.seq", "less_equal_middle.seq",
    "less_equal_end.seq", "less_less_equal.liga", "less_less_equal_start.seq",
    "less_less_equal_middle.seq", "less_less_equal_end.seq",
    "hyphen_hyphen.liga", "hyphen_hyphen_hyphen.liga",
}


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


def drop_ligatures(font, glyphs):
    """Stop the chaining rules from producing `glyphs`; return how many changed."""
    lookups = font["GSUB"].table.LookupList.Lookup

    def real(lookup, sub):  # type 7 is an extension wrapper around the real subtable
        return sub.ExtSubTable if lookup.LookupType == 7 else sub

    def produces(index, glyph):
        lookup = lookups[index]
        for sub in lookup.SubTable:
            out = getattr(real(lookup, sub), "mapping", {}).get(glyph)
            if out is not None and set(out if isinstance(out, list) else [out]) & glyphs:
                return True
        return False

    changed = 0
    for lookup in lookups:
        keep = []
        for sub in lookup.SubTable:
            rule = real(lookup, sub)
            # Coverage-based chaining rules (format 3): one coverage per input position.
            if getattr(rule, "Format", None) == 3 and hasattr(rule, "InputCoverage"):
                for rec in rule.SubstLookupRecord:
                    cov = rule.InputCoverage[rec.SequenceIndex]
                    hit = [g for g in cov.glyphs if produces(rec.LookupListIndex, g)]
                    if hit:
                        # A new Coverage, since one may be shared between rules.
                        new = otTables.Coverage()
                        new.glyphs = [g for g in cov.glyphs if g not in hit]
                        rule.InputCoverage[rec.SequenceIndex] = new
                        changed += 1
                if not all(c.glyphs for c in rule.InputCoverage):
                    continue  # nothing left to match: drop the rule
            # Glyph-based chaining rules (format 1): one rule set per first glyph.
            elif getattr(rule, "Format", None) == 1 and hasattr(rule, "ChainSubRuleSet"):
                for first, rules in zip(rule.Coverage.glyphs, rule.ChainSubRuleSet):
                    def hits(r):
                        seq = [first] + list(r.Input)
                        return any(produces(rec.LookupListIndex, seq[rec.SequenceIndex])
                                   for rec in r.SubstLookupRecord)
                    kept = [r for r in rules.ChainSubRule if not hits(r)]
                    changed += len(rules.ChainSubRule) - len(kept)
                    rules.ChainSubRule, rules.ChainSubRuleCount = kept, len(kept)
            keep.append(sub)
        lookup.SubTable, lookup.SubTableCount = keep, len(keep)
    return changed


def no_plain_hyphen_runs(font):
    """A hyphen starts a joined run only before <, > or |; return rules changed."""
    lookups = font["GSUB"].table.LookupList.Lookup

    def real(lookup, sub):
        return sub.ExtSubTable if lookup.LookupType == 7 else sub

    starts = {i for i, lookup in enumerate(lookups) for sub in lookup.SubTable
              if getattr(real(lookup, sub), "mapping", {}).get("hyphen") == "hyphen_start.seq"}
    changed = 0
    for lookup in lookups:
        for sub in lookup.SubTable:
            rule = real(lookup, sub)
            # The rule that starts a run: hyphen, nothing before it, a look-ahead after.
            if (getattr(rule, "Format", None) == 3 and hasattr(rule, "InputCoverage")
                    and not rule.BacktrackCoverage and rule.LookAheadCoverage
                    and "hyphen" in rule.InputCoverage[0].glyphs
                    and "hyphen" in rule.LookAheadCoverage[0].glyphs
                    and any(rec.LookupListIndex in starts for rec in rule.SubstLookupRecord)):
                new = otTables.Coverage()
                new.glyphs = [g for g in rule.LookAheadCoverage[0].glyphs if g != "hyphen"]
                rule.LookAheadCoverage[0] = new
                changed += 1
    return changed


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

    unligated = drop_ligatures(font, NO_LIGATURE) + no_plain_hyphen_runs(font)

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
    return added, skipped, unligated


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
    added, skipped, unligated = build(font, out, args.suffix)

    for name, ch, base, mark, dx, dy in added:
        print(f"  + {ch}  {name:10s} = {base} + {mark}  @({dx},{dy})")
    for name, why in skipped:
        print(f"  - {name:10s} skipped: {why}")
    print(f"  {unligated} ligature rule(s) for <=, <<= and runs of hyphens turned off")
    print(f"\n{len(added)} glyph(s) added -> {out}")


if __name__ == "__main__":
    main()
