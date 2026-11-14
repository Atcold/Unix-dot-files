#!/usr/bin/env python3
"""The rules my radio players share, so the Mac and the phone agree on what a piece is.

mpv on the Macs and the icecast relays on AlfDROID read the same icy StreamTitle chunks,
and each has to make the same three decisions about every title it gets. Stations double-
encode their UTF-8, so accents arrive as Ã© where they should read é. A station announces
itself between pieces and sends that announcement as the title, which is a banner and not
something I listened to. A player announces one piece several times, so it belongs in the
log once. Those decisions live here, and each player keeps its own terminal or web page.

The stations themselves come from radio.m3u in this folder, which install.sh also links
into mpv's config folder, so the Macs and the phone play the same list.

Run it directly to use the rules from a shell:

  radio_core.py clean <station>          the raw title on stdin, one JSON answer out
  radio_core.py sniff <station> <url>... what each stream is playing now, as JSON
  radio_core.py --selftest               the rules against titles the stations really send

radio.lua on the Macs calls clean once per announced title and sniff for the c menu and
its 20 s poll; radio-server.py on AlfDROID imports this module and calls the same two.
"""

import json
import re
import sys
import threading
import urllib.request

UA = "AlfDROID radio/1.0"
CHUNKS = 3        # metadata chunks to read before giving up on a stream's title
TIMEOUT = 4       # seconds per stream for a sniff


def _undo_double_encoding(s):
    """Venice Classic Radio sends StreamTitle as UTF-8 bytes encoded as UTF-8 again, so
    'Félicien' arrives as 'FÃ©licien'. Decode the string once more when the tell-tale Ã
    shows up and the second decode comes out clean."""
    if "Ã" in s:
        try:
            fixed = s.encode("latin-1", "strict").decode("utf-8", "strict")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
        if "Ã" not in fixed and "\ufffd" not in fixed:
            return fixed
    return s


def clean(raw):
    """The title as I want to read it: Venice's {+info: site} advertisement goes, and so
    does the double encoding. Stripping is part of it, since some stations pad the title."""
    s = re.sub(r"\s*\{\+info:[^}]*\}", "", raw or "")
    return _undo_double_encoding(s).strip()


def is_banner(station, title):
    """Whether this title is the station naming itself rather than a piece. Radio Swiss
    sends "Radio Swiss Classic - www.radioswissclassic.ch" between pieces, and a stream
    may send only its own address. Both are a station talking, so they get no line and no
    log row, and my 30 s rule never sees them."""
    t = (title or "").strip().lower()
    name = (station or "").strip().lower()
    if name and t.startswith(name):
        return True
    return "www." in t or "http://" in t or "https://" in t


def clean_title(station, raw):
    """Clean raw and decide whether it is a banner, in the one order that matters: the
    banner test wants the cleaned text, since an advertisement can hide the address."""
    title = clean(raw)
    return title, is_banner(station, title)


def same_piece(a, b):
    """Whether two {station, title} rows are the same listening, which is how a player
    writes one row per piece even though it hears the same title several times."""
    return bool(a and b) and a.get("station") == b.get("station") and a.get("title") == b.get("title")


def parse_stream_title(blob):
    """The StreamTitle out of one icy metadata chunk, or "" when the chunk carries none.
    Audiocdn, which serves Jazz24, fills most chunks with StreamTitle='' and names the
    piece in a single chunk, so callers keep reading until one arrives."""
    for pattern in (r"StreamTitle='(.*?)';", r"StreamTitle='([^']*)'"):
        m = re.search(pattern, blob)
        if m and m.group(1).strip():
            return m.group(1)
    return ""


def _open(url, headers=None, method=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, headers=h, method=method), timeout=TIMEOUT)


def sniff_one(url):
    """What a stream is playing right now, from its own metadata: read inline chunks when
    the server sets icy-metaint, and fall back to the icy-title response header, which is
    all some stations offer."""
    try:
        r = _open(url, {"Icy-MetaData": "1"})
        interval = int(r.headers.get("icy-metaint", "0") or 0)
        title = ""
        if interval:
            for _ in range(CHUNKS):
                r.read(interval)
                first = r.read(1)
                if not first:
                    break
                blob = r.read(first[0] * 16).rstrip(b"\0").decode("utf-8", "replace")
                title = parse_stream_title(blob)
                if title:
                    break
        r.close()
        if not title:
            title = (_open(url, method="HEAD").headers.get("icy-title") or "").strip()
        return title
    except Exception:
        return ""


def sniff(pairs):
    """[(station, url), ...] -> [{"station":..., "title":..., "banner":...}, ...], all
    streams read at once so eight stations answer in about the time of one."""
    out = [None] * len(pairs)

    def work(i, station, url):
        title, banner = clean_title(station, sniff_one(url))
        out[i] = {"station": station, "title": title, "banner": banner}

    threads = [threading.Thread(target=work, args=(i, s, u), daemon=True)
               for i, (s, u) in enumerate(pairs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(TIMEOUT + 2)
    return [r if r else {"station": s, "title": "", "banner": False}
            for r, (s, _) in zip(out, pairs)]


def _selftest():
    """The rules against titles taken from the streams, so a station's own quirk that
    breaks the shared code shows up here on either machine before it reaches the log."""
    cases = [
        # (station, raw title, expected cleaned title, expected banner)
        ("Radio Swiss Classic", "Radio Swiss Classic - www.radioswissclassic.ch",
         "Radio Swiss Classic - www.radioswissclassic.ch", True),
        ("Radio Swiss Jazz", "Radio Swiss Jazz - www.radioswissjazz.ch",
         "Radio Swiss Jazz - www.radioswissjazz.ch", True),
        ("WQXR", "www.wqxr.org", "www.wqxr.org", True),
        ("Jazz24", "Tamir Hendelman - Soft Winds", "Tamir Hendelman - Soft Winds", False),
        ("Jazz24", "Jazz24 - Soft Winds", "Jazz24 - Soft Winds", True),
        ("Venice Classic Radio",
         "ThÃ©odore Dubois (1837-1924) - 'Promenade sentimentale' (Trio Arcadis)  "
         "{+info: veniceclassicradio.eu}",
         "Théodore Dubois (1837-1924) - 'Promenade sentimentale' (Trio Arcadis)", False),
        ("Classic FM", "Giuseppe Verduci - Sonata a Tre No. 3",
         "Giuseppe Verduci - Sonata a Tre No. 3", False),
        ("Rai Radio Classica", "  Friedrich Gulda - Piano Sonata No. 1  ",
         "Friedrich Gulda - Piano Sonata No. 1", False),
    ]
    bad = 0
    for station, raw, want_title, want_banner in cases:
        title, banner = clean_title(station, raw)
        if title != want_title or banner != want_banner:
            bad += 1
            print(f"FAIL {station}: {raw!r}\n  got  {title!r}, banner={banner}\n  want {want_title!r}, banner={want_banner}")
    chunks = [("StreamTitle='Dizzy Gillespie - Manteca';StreamUrl='x=y'", "Dizzy Gillespie - Manteca"),
              ("StreamTitle='Dizzy Gillespie - Manteca';", "Dizzy Gillespie - Manteca"),
              ("StreamTitle='';StreamUrl=''", ""),
              ("no metadata here", "")]
    for blob, want in chunks:
        got = parse_stream_title(blob)
        if got != want:
            bad += 1
            print(f"FAIL chunk {blob!r}: got {got!r}, want {want!r}")
    if same_piece({"station": "Jazz24", "title": "A"}, {"station": "Jazz24", "title": "A"}) is False:
        bad += 1
        print("FAIL same_piece: identical rows reported different")
    if same_piece({"station": "Jazz24", "title": "A"}, {"station": "WQXR", "title": "A"}):
        bad += 1
        print("FAIL same_piece: rows from two stations reported the same")
    print(f"{len(cases) + len(chunks) + 2} checks, {bad} failing")
    return 1 if bad else 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: radio_core.py clean <station> | sniff <station> <url>... | --selftest")
        return 0
    if argv[0] == "--selftest":
        return _selftest()
    if argv[0] == "clean" and len(argv) > 1:
        title, banner = clean_title(argv[1], sys.stdin.read())
        print(json.dumps({"title": title, "banner": banner}, ensure_ascii=False))
        return 0
    if argv[0] == "sniff" and len(argv) > 2 and (len(argv) - 1) % 2 == 0:
        pairs = list(zip(argv[1::2], argv[2::2]))
        print(json.dumps({"titles": sniff(pairs)}, ensure_ascii=False))
        return 0
    print("usage: radio_core.py clean <station> | sniff <station> <url>... | --selftest", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
