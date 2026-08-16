#!/usr/bin/env python3
"""Copy a TTF under a new family name.

  ./rename-font.py ~/Library/Fonts/CaskaydiaCoveNerdFont-ExtraLight.ttf \
      ~/Library/Fonts/CascadiaExtraLight-Regular.ttf "Cascadia ExtraLight" CascadiaExtraLight-Regular


Qt asks CoreText for a *family*, and a family covers every weight, so "the Light face of
CaskaydiaCove NF" is not something TeXstudio can name -- it has no weight setting. Giving
the Light face a family of its own makes it nameable. Only the name table changes; the
glyphs, metrics and hinting are the file's own.
"""
import struct, sys

SRC, DST, FAMILY, PSNAME = sys.argv[1:5]
data = bytearray(open(SRC, 'rb').read())

version, num_tables = struct.unpack('>IH', data[:6])
tables = {}
for i in range(num_tables):
    off = 12 + 16 * i
    tag, checksum, offset, length = struct.unpack('>4sIII', data[off:off + 16])
    tables[tag.decode('latin-1')] = (offset, length)

offset, length = tables['name']
fmt, count, string_offset = struct.unpack('>HHH', data[offset:offset + 6])
records = []
for i in range(count):
    rec = offset + 6 + 12 * i
    plat, enc, lang, name_id, rec_len, rec_off = struct.unpack('>6H', data[rec:rec + 12])
    value = bytes(data[offset + string_offset + rec_off:][:rec_len])
    records.append([plat, enc, lang, name_id, value])

# 1 family, 4 full name, 6 PostScript name, 16 typographic family, 17 typographic style.
# 2 and 17 become Regular: this file is now the whole family, not a weight within one.
def encode(text, plat, enc):
    return text.encode('utf-16-be') if (plat == 0 or (plat == 3 and enc in (1, 10))) else text.encode('latin-1')

out = []
for plat, enc, lang, name_id, value in records:
    if name_id in (1, 16):
        value = encode(FAMILY, plat, enc)
    elif name_id in (2, 17):
        value = encode('Regular', plat, enc)
    elif name_id == 4:
        value = encode(FAMILY, plat, enc)
    elif name_id == 6:
        value = encode(PSNAME, plat, enc)
    out.append([plat, enc, lang, name_id, value])

storage = bytearray()
offsets = []
for rec in out:
    value = rec[4]
    at = storage.find(value)
    if at == -1:
        at = len(storage)
        storage += value
    offsets.append((at, len(value)))

header_len = 6 + 12 * len(out)
name_table = bytearray(struct.pack('>HHH', 0, len(out), header_len))
for rec, (at, ln) in zip(out, offsets):
    name_table += struct.pack('>6H', rec[0], rec[1], rec[2], rec[3], ln, at)
name_table += storage
while len(name_table) % 4:
    name_table += b'\0'

# Reassemble: a rewritten name table is a different length, so every table after it would
# move. Rebuilding the whole file from the tables is simpler than patching offsets, and
# DSIG is dropped because a signature over changed contents is worthless.
def checksum(block):
    total = 0
    padded = block + b'\0' * (-len(block) % 4)
    for i in range(0, len(padded), 4):
        total = (total + struct.unpack('>I', padded[i:i + 4])[0]) & 0xFFFFFFFF
    return total

contents = {}
for tag, (off, ln) in tables.items():
    if tag == 'DSIG':
        continue
    contents[tag] = name_table if tag == 'name' else bytes(data[off:off + ln])

tags = sorted(contents)
n = len(tags)
search_range = 16 * (2 ** (n.bit_length() - 1))
new = bytearray(struct.pack('>IHHHH', version, n, search_range, n.bit_length() - 1, 16 * n - search_range))
body_offset = 12 + 16 * n
records_at = len(new)
new += b'\0' * (16 * n)
for tag in tags:
    block = contents[tag]
    while len(new) % 4:
        new += b'\0'
    contents[tag] = (len(new), len(block))
    new += block
for i, tag in enumerate(tags):
    at, ln = contents[tag]
    struct.pack_into('>4sIII', new, records_at + 16 * i, tag.encode('latin-1'), checksum(bytes(new[at:at + ln])), at, ln)

# head.checkSumAdjustment is 0xB1B0AFBA minus the checksum of the whole file with that
# field zeroed, and every checksum above just changed.
head_at, head_len = contents['head']
struct.pack_into('>I', new, head_at + 8, 0)
struct.pack_into('>I', new, head_at + 8, (0xB1B0AFBA - checksum(bytes(new))) & 0xFFFFFFFF)

open(DST, 'wb').write(new)
print(f'{DST}: {len(new)} bytes, {n} tables, family {FAMILY!r}')
