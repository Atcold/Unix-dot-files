#!/usr/bin/env python3
"""Serve my radio stations as icecast mounts, with a web page to switch them on and off.

Stations come from radio.m3u in this folder, the file the `radio` alias plays on the Macs;
$RADIO_M3U names another. Each station that is recording runs one ffmpeg that decodes the
upstream and republishes it as a uniform 128k MP3 mount at http://<host>:8001/<slug>.mp3,
so a listener's player only ever sees plain MP3 at one bitrate whatever the station sends.
The same ffmpeg copies its encoded bytes into a Ring: a few minutes of recent audio in the
server's RAM, nothing on disk. The page's player listens out of a Ring, deliberately a set
number of seconds behind live, and when the phone's network drops the droid replays the
missed bytes from the Ring at line speed, so the buffer refills and the piece plays on
without a gap. Plain URL requests (Evermusic, copied mount links) still stream live
through icecast exactly as they always did.

Recording is by default off, so the droid does nothing when nobody listens: the page has a
recording switch, tapping a station also switches it on, and relays sleep themselves fifteen
minutes after the last listener. A supervisor restarts ffmpeg when a station's stream drops.

radio_core.py in this folder holds the rules both players share. It reads the icy
StreamTitle chunks, undoes the encoding the stations get wrong, and tells a station's own
announcement apart from a piece, so a banner is never logged as something I listened to and
a piece I hear several times stays one row.

Built for Termux on AlfDROID, where install.sh in this folder installs ffmpeg, icecast and
python and links this file onto the PATH. `radio-server.py up` starts icecast, the relays
and a control page on port 8080. Open http://alfdroid:8080/ on the tailnet to switch
stations and copy their mount URLs into a player such as Evermusic. State, icecast config
and logs live under ~/.local/share/radio/; station logos are fetched once into logos/
there, and dropping your own logos/<slug>.png overrides the fetched one. Pieces land in
log.tsv there, in the same shape radio.lua writes on the Macs: date, time, station, piece,
once a piece has played 30 s with a listener connected.
"""

import base64
import collections
import http.server
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse

try:
    import paho.mqtt.client as mqtt          # the Rai reader below; install.sh adds it on the droid
except ImportError:
    mqtt = None

try:
    import radio_core
except ImportError:  # a lone copy of this file: $RADIO_CORE names where the core lives
    sys.path.insert(0, str(Path(os.getenv("RADIO_CORE",
                                          "~/.settings/Radio/radio_core.py")).expanduser().parent))
    import radio_core


def m3u_path():
    """The playlist: $RADIO_M3U if set, else the copy install.sh links into mpv's
    config folder, else the file in this folder, which is where the Macs keep it."""
    for cand in (os.getenv("RADIO_M3U"), "~/.config/mpv/radio.m3u", "~/.settings/Radio/radio.m3u"):
        if cand and Path(cand).expanduser().is_file():
            return Path(cand).expanduser()
    return Path("~/.settings/Radio/radio.m3u").expanduser()


M3U = m3u_path()
STATE = Path("~/.local/share/radio").expanduser()
LOGDIR = STATE / "logs"
LOGOS = STATE / "logos"
PIDFILE = STATE / "radio.pid"
CONFIG = STATE / "icecast.xml"
MUTED = STATE / "muted.json"
LOGTSV = STATE / "log.tsv"
PAGE = Path(__file__).with_name("radio-page.html")

ICECAST_PORT = 8001
WEB_PORT = 8080
UA = radio_core.UA

AUDIO_BPS = 16000   # bytes per second of a 128 kbit/s MP3 (128000 / 8): how far a lag reaches into a Ring
RING_MAX = AUDIO_BPS * 300   # five minutes of tape beyond the page's 180 s buffer: a
                             # dropout up to eight minutes costs silence, not music
IDLE_OFF = int(os.getenv("RADIO_IDLE_OFF", "900"))   # a recording with no listener for this
                             # many seconds sleeps itself; 0 (or negative) keeps it awake

# ColorBrewer Set3 in the order radio.lua uses, without the yellow and the grey.
COLOURS = ["8dd3c7", "bebada", "fb8072", "80b1d3", "fdb462", "b3de69", "fccde5", "bc80bd", "ccebc5"]
WHITE_LOGOS = {"venice-classic-radio"}   # white-on-transparent art, sits on the dark default
DARK_INK_LOGOS = {"rai-radio-classica", "wqxr", "classic-fm"}   # dark ink: the page inverts it for the dark tile

# Where to fetch each station's logo from, tried in order: an official brand image
# (preferably SVG), then the station homepage's og:image, then DuckDuckGo's icon for
# the stream host; the page shows a coloured initials tile if all miss.
LOGO_URLS = {
    "classic-fm": ["https://upload.wikimedia.org/wikipedia/commons/a/ae/Classic_FM_logo.svg"],
    "radio-swiss-classic": ["https://www.radioswissclassic.ch/social-media/rsc-web.png"],
    "venice-classic-radio": ["https://www.veniceclassicradio.eu/logo/logo-vcr-white.svg"],
    "wqxr": ["https://upload.wikimedia.org/wikipedia/commons/1/11/WQXR-FM_logo.svg",
             "https://upload.wikimedia.org/wikipedia/commons/7/73/Wqxr-logo.png"],
    "rai-radio-classica": ["https://upload.wikimedia.org/wikipedia/commons/3/3a/Rai_Radio_Classica_logo.svg"],
}
HOMEPAGES = {
    "classic-fm": "https://www.classicfm.com/",
    "radio-swiss-classic": "https://www.radioswissclassic.ch/",
    "venice-classic-radio": "https://www.veniceclassicradio.eu/",
    "wqxr": "https://www.wqxr.org/",
    "rai-radio-classica": "https://www.raiplay.it/radio",
}

# Rai Radio Classica sends no StreamTitle, so its pieces come from the current-song
# service Rai's own web player uses: a one-hour token from the token service, then a
# retained MQTT message per piece on the channel's topic. The slug is the m3u name;
# clientId is Rai's own recipe, a UUIDv5 of the channel page's url.
RAI_SLUG = "rai-radio-classica"
RAI_TOKEN = "https://www.raiplaysound.it/atomatic/token-service/api/jwt-ws"
RAI_PAGE = "https://www.raiplaysound.it/radio3classica"
RAI_TOPIC = "ws/rai-radio-3-classica"
RAI_SCHEDULE = "https://www.raiplaysound.it/palinsesto/onAir.json"
RAI_CHANNEL = "Rai Radio 3 Classica"
IMG_MAGIC = [b"\x89PNG", b"GIF8", b"\xff\xd8", b"RIFF", b"BM", b"<svg", b"<?xml", b"\x00\x00\x01\x00"]


def slugify(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def load_stations():
    """Parse the m3u into {name, url, slug, colour}, in file order like radio.lua."""
    stations, pending = [], None
    for line in M3U.read_text().splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            pending = line.split(",", 1)[-1].strip()
        elif line and not line.startswith("#"):
            name = pending or line
            stations.append({"name": name, "url": line, "slug": slugify(name)})
            pending = None
    for i, st in enumerate(stations):
        st["colour"] = COLOURS[i % len(COLOURS)]
    return stations


def encoder():
    """Pick the MP3 encoder, falling back to the native AAC if lame is missing."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                         capture_output=True, text=True, timeout=30).stdout
    if "libmp3lame" in out:
        return ["-c:a", "libmp3lame", "-b:a", "128k"], "mp3", ".mp3"
    return ["-c:a", "aac", "-b:a", "128k"], "adts", ".aac"


def ensure_config():
    """Write icecast.xml once, with random passwords kept on the droid for later runs."""
    if CONFIG.exists():
        src = re.search(r"<source-password>([^<]+)", CONFIG.read_text())
        adm = re.search(r"<admin-password>([^<]+)", CONFIG.read_text())
        return src.group(1), adm.group(1)
    src, adm = secrets.token_hex(8), secrets.token_hex(8)
    CONFIG.write_text(f"""<icecast>
  <limits><sources>16</sources></limits>
  <authentication>
    <source-password>{src}</source-password>
    <relay-password>{src}</relay-password>
    <admin-user>admin</admin-user>
    <admin-password>{adm}</admin-password>
  </authentication>
  <hostname>alfdroid</hostname>
  <listen-socket><port>{ICECAST_PORT}</port></listen-socket>
  <paths><logdir>{LOGDIR}</logdir></paths>
  <logging>
    <accesslog>access.log</accesslog>
    <errorlog>error.log</errorlog>
    <loglevel>1</loglevel>
  </logging>
</icecast>
""")
    return src, adm


def fetch(url, timeout=15, data=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, data=data)
    return urllib.request.urlopen(req, timeout=timeout).read()


def og_images(home):
    """Image URLs the station's own homepage advertises for social cards."""
    try:
        html = fetch(home).decode("utf-8", "replace")
    except Exception:
        return []
    return re.findall(r"""(?i)<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""", html)


def fetch_logos(force=False):
    """Fill logos/<slug>.img, never overwriting a file the user dropped there."""
    for st in load_stations():
        dest = LOGOS / (st["slug"] + ".img")
        if dest.exists() and not force:
            continue
        host = urlparse(st["url"]).hostname or ""
        urls = list(LOGO_URLS.get(st["slug"], []))
        home = HOMEPAGES.get(st["slug"])
        if home:
            urls += og_images(home)
        urls.append(f"https://icons.duckduckgo.com/ip3/{host}.ico")
        for url in urls:
            try:
                blob = fetch(url)
            except Exception:
                continue
            if len(blob) > 200 and any(blob.startswith(m) for m in IMG_MAGIC):
                dest.write_bytes(blob)
                break


HLS_SEG = 6.0   # seconds per HLS segment: Safari's player fetches the tape in these pieces

# MPEG audio frame headers, enough to cut the tape on frame boundaries: bitrates in
# kbit/s by version (MPEG-1, else MPEG-2/2.5) for Layer III, and sample rates.
_BR = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
       2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
_SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_frame(b, i):
    """Length and sample count of the Layer III frame starting at b[i], or None."""
    if i + 4 > len(b) or b[i] != 0xFF or b[i + 1] & 0xE0 != 0xE0:
        return None
    ver, layer = (b[i + 1] >> 3) & 3, (b[i + 1] >> 1) & 3
    bri, sri, pad = b[i + 2] >> 4, (b[i + 2] >> 2) & 3, (b[i + 2] >> 1) & 1
    if ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
        return None
    sr = _SR[ver][sri]
    br = _BR[1 if ver == 3 else 2][bri] * 1000
    if ver == 3:
        return 144 * br // sr + pad, 1152, sr
    return 72 * br // sr + pad, 576, sr


def id3_timestamp(pts):
    """The ID3 PRIV tag HLS requires at the head of a packed-audio segment: Apple's
    transport-stream timestamp, a 33-bit count of 90 kHz ticks."""
    def safe(n):
        return bytes([(n >> 21) & 127, (n >> 14) & 127, (n >> 7) & 127, n & 127])
    body = b"com.apple.streaming.transportStreamTimestamp\x00" + (pts & 0x1FFFFFFFF).to_bytes(8, "big")
    frame = b"PRIV" + safe(len(body)) + b"\x00\x00" + body
    return b"ID3\x04\x00\x00" + safe(len(frame)) + frame


class Ring:
    """The last minutes of one relay's encoded audio, kept in RAM: a run of byte
    positions [start, end) behind a deque of blocks. A listener starts at lag seconds
    behind the end, so the phone hears a recording that is already a minute old while
    the relay keeps writing; when its network drops, it comes back asking for the byte
    it stopped at, and the Ring replays what arrived in the meantime at line speed.
    Pruning keeps RING_MAX bytes, so a listener whose connection died longer ago
    resumes from the oldest byte still held and skips the gap."""

    def __init__(self):
        self.cond = threading.Condition()
        self.blocks = collections.deque()   # (pos, bytes), oldest first
        self.size = 0
        self.start = 0
        self.end = 0
        self.clients = {}        # page client id -> {"anchor", "upto", "conns", "t"}
        self.segs = collections.deque()  # HLS segments: {"seq", "start", "end", "dur", "pts", "wall"}
        self.seq = 0
        self.hls = {}            # page client id -> {"bytes", "seq", "t"}: segments served
        self.cut = 0             # where the frame scanner stands, a Ring position
        self.seg_start = None    # the open segment: first byte, sample count, rate, wall time
        self.seg_samples = 0
        self.samples = 0         # samples cut so far, the segments' timestamp clock
        self.tail = b""          # bytes past self.cut not yet scanned

    def append(self, data):
        with self.cond:
            self.blocks.append((self.end, data))
            self.size += len(data)
            self.end += len(data)
            while self.size > RING_MAX and len(self.blocks) > 1:
                _, old = self.blocks.popleft()
                self.size -= len(old)
                self.start += len(old)
            self.segment(data)
            while self.segs and self.segs[0]["start"] < self.start:
                self.segs.popleft()          # its head has been pruned from the tape
            self.cond.notify_all()

    def segment(self, data):
        """Walk the new bytes frame by frame and close an HLS segment every HLS_SEG
        seconds of audio. A relay restart starts a fresh MP3 stream mid-tape, so
        anything that is not a frame (an ID3 tag, a torn frame) is skipped over."""
        b = self.tail + data
        i = 0
        while True:
            f = mp3_frame(b, i)
            if f is None:
                if i + 4 > len(b):
                    break
                if b[i:i + 3] == b"ID3" and i + 10 <= len(b):
                    z = i + 10 + ((b[i + 6] << 21) | (b[i + 7] << 14) | (b[i + 8] << 7) | b[i + 9])
                    if z > len(b):
                        break                # wait for the whole tag
                    i = z
                    self.seg_start = None    # a new stream: never splice across it
                    self.seg_samples = 0
                    continue
                i += 1
                continue
            n, spf, sr = f
            if i + n > len(b):
                break
            pos = self.cut + i
            if self.seg_start is None:
                self.seg_start, self.seg_sr, self.seg_wall = pos, sr, time.time()
                self.seg_pts = self.samples * 90000 // sr
            self.seg_samples += spf
            self.samples += spf
            i += n
            if self.seg_samples / self.seg_sr >= HLS_SEG - 0.013:
                self.segs.append({"seq": self.seq, "start": self.seg_start, "end": self.cut + i,
                                  "dur": self.seg_samples / self.seg_sr, "pts": self.seg_pts,
                                  "wall": self.seg_wall})
                self.seq += 1
                self.seg_start, self.seg_samples = None, 0
        self.tail = b[i:]
        self.cut += i

    def slice(self, a, z):
        """The bytes [a, z) while the tape still holds them, else None."""
        with self.cond:
            if a < self.start or z > self.end:
                return None
            out = bytearray()
            for bpos, blk in self.blocks:
                if bpos + len(blk) <= a or bpos >= z:
                    continue
                out += blk[max(0, a - bpos):z - bpos]
            return bytes(out)

    def playlist(self, base, behind, query):
        """A live HLS playlist over the whole tape that tells the player to start
        behind seconds from the live edge, so it can buffer forward up to live."""
        with self.cond:
            segs = list(self.segs)
        if not segs:
            return None
        target = max(round(x["dur"]) for x in segs)
        behind = min(behind, sum(x["dur"] for x in segs) - 8)   # beyond the playlist Safari starts at live
        lines = ["#EXTM3U", "#EXT-X-VERSION:6", f"#EXT-X-TARGETDURATION:{target}",
                 f"#EXT-X-MEDIA-SEQUENCE:{segs[0]['seq']}",
                 f"#EXT-X-START:TIME-OFFSET=-{behind:.1f},PRECISE=YES"]
        for x in segs:
            t = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(x["wall"]))
            lines.append(f"#EXT-X-PROGRAM-DATE-TIME:{t}.{int(x['wall'] % 1 * 1000):03d}Z")
            lines.append(f"#EXTINF:{x['dur']:.3f},")
            lines.append(f"{base}/{x['seq']}.mp3{query}")
        return "\n".join(lines) + "\n"

    def segment_bytes(self, seq):
        with self.cond:
            x = next((x for x in self.segs if x["seq"] == seq), None)
        if x is None:
            return None
        body = self.slice(x["start"], x["end"])
        return None if body is None else id3_timestamp(x["pts"]) + body

    def seconds(self):
        return (self.end - self.start) / AUDIO_BPS

    def attach(self, client, pos):
        """Register a connection of one page client and return where it starts. Safari
        opens two or three connections per play (a document request, a 2-byte Range
        probe, the real one) and reconnects on its own after a network blink; all of
        them carry the page's client id, so the first fixes the anchor the page counts
        its playhead from, the ones in the next few seconds start at that anchor too,
        and a later one resumes at the furthest byte already delivered."""
        with self.cond:
            now = time.time()
            for k in [k for k, c in self.clients.items() if not c["conns"] and now - c["t"] > 600]:
                del self.clients[k]
            c = self.clients.get(client) if client else None
            if c is None:
                c = {"anchor": pos, "upto": pos, "conns": 0, "t0": now, "t": now}
                if client:
                    self.clients[client] = c
            elif now - c["t0"] < 5:
                pos = c["anchor"]
            else:
                pos = max(self.start, min(c["upto"], self.end))
            c["conns"] += 1
            c["t"] = now
            return c, pos

    def client_view(self, client):
        """What the page needs to draw its buffer: the byte its playhead counts from,
        the furthest byte delivered to it, and the live edge, all in Ring positions."""
        with self.cond:
            c, h = self.clients.get(client), self.hls.get(client)
            if c is None and h is None:
                return None
            out = {"end": self.end, "start": self.start}
            if c:
                out.update(anchor=c["anchor"], upto=c["upto"], conns=c["conns"])
            if h:
                out.update(hls=h["bytes"], seg=h["seq"])
            return out

    def read_from(self, pos, stop, idle_max=45):
        """Yield chunks from byte position pos onward, waiting on the relay as it
        writes and giving up when stop() turns true or nothing has arrived for
        idle_max seconds; a stopped relay then releases the connection and the page
        retries on its own. pos itself moves with the yield."""
        last = time.time()
        while not stop():
            with self.cond:
                if pos < self.start:
                    pos = self.start          # what we wanted got pruned: skip the gap
                chunk = b""
                if self.end > pos:
                    out = bytearray()
                    for bpos, b in self.blocks:
                        if bpos + len(b) <= pos:
                            continue
                        out += b[max(0, pos - bpos):]
                    pos += len(out)
                    chunk = bytes(out)
                if not chunk:
                    if time.time() - last > idle_max:
                        return                # the relay has been silent: hang up
                    self.cond.wait(1.0)
                    continue
            last = time.time()
            yield chunk


class Radio:
    """The daemon's state: icecast, the recording switch, one relay thread per station."""

    def __init__(self):
        self.lock = threading.Lock()
        self.stations = load_stations()
        self.source_pw, self.admin_pw = ensure_config()
        self.auth = "Basic " + base64.b64encode(f"admin:{self.admin_pw}".encode()).decode()
        try:
            self.enc, self.fmt, self.ext = encoder()
        except Exception:
            self.enc, self.fmt, self.ext = [], "mp3", ".mp3"  # status reports ffmpeg's failure
        self.powered = False     # the recording switch; relays run only while it is on
        self.muted = set()       # stations left out of the recording even while powered
        self.wanted = set()      # slugs that should be recording right now, from the two above
        self.procs = {}          # slug -> ffmpeg Popen
        self.threads = {}        # slug -> relay thread
        self.rings = {}          # slug -> Ring, alive while its relay is
        self.titles = {}         # slug -> [title, since, loggable], from the icy readers and Rai
        self.meta = {st["slug"]: {"restarts": 0, "started": 0.0} for st in self.stations}
        self.icecast = None
        self.proxy_listeners = {}    # mount -> listeners on the page's buffered stream
        self.last_listen = time.time()   # last time anyone streamed or switched on, for idle-off;
                                         # a fresh start counts as one, so the watchdog gives it 15 min
        self.recent = []    # newest first: {time, station, piece}, the page's played list
        try:
            for row in reversed(LOGTSV.read_text().splitlines()[1:]):
                cols = row.split("\t")
                if len(cols) >= 4:
                    self.recent.append({"time": cols[1], "station": cols[2], "piece": cols[3]})
                if len(self.recent) == 12:
                    break
        except FileNotFoundError:
            pass
        if MUTED.exists():
            try:
                data = json.loads(MUTED.read_text())
                self.muted = set(data["muted"]) if isinstance(data, dict) else set(data)
                if isinstance(data, dict):
                    self.powered = bool(data.get("powered"))   # a debug deploy keeps the recording on
            except Exception:
                self.muted = set()
        self.sync()

    def mount(self, st):
        return "/" + st["slug"] + self.ext

    def station_by_mount(self, mount):
        return next((st for st in self.stations if self.mount(st) == mount), None)

    def save(self):
        """The muted set and the recording switch are the persistent wishes, so a
        restart for a code update resumes exactly what the page had switched on."""
        MUTED.write_text(json.dumps({"muted": sorted(self.muted), "powered": self.powered}))

    def sync(self):
        """Make threads and Rings match the switch and the muted set. The caller holds
        the lock; a dying relay thread notices it is no longer wanted and retires."""
        self.wanted = set() if not self.powered else \
            {st["slug"] for st in self.stations} - set(self.muted)
        for slug in list(self.threads):
            if slug not in self.wanted:
                proc = self.procs.pop(slug, None)
                self.rings.pop(slug, None)
                if proc and proc.poll() is None:
                    proc.terminate()
        for slug in self.wanted:
            if slug not in self.threads:
                t = threading.Thread(target=self.relay_loop, args=(slug,), daemon=True)
                self.threads[slug] = t
                t.start()
                if slug != RAI_SLUG:   # Rai's titles come from rai_loop, not its stream
                    threading.Thread(target=self.meta_loop, args=(slug,), daemon=True).start()

    def power(self, on):
        with self.lock:
            self.powered = bool(on)
            if on:
                self.last_listen = time.time()
            self.save()
            self.sync()
        return self.powered

    def set(self, slug, on):
        """The page's per-station switch: off mutes a station out of the recording,
        on unmutes it and switches the whole recording on, because asking for a
        station is asking to listen."""
        with self.lock:
            if slug not in self.meta:
                return False
            if on:
                self.powered = True
                self.muted.discard(slug)
            else:
                self.muted.add(slug)
            self.save()
            self.sync()
        return True

    def set_all(self, on):
        with self.lock:
            if on:
                self.muted.clear()
            self.powered = bool(on)
            if on:
                self.last_listen = time.time()
            self.save()
            self.sync()

    def select(self, slug):
        """Listen to this station: it joins the recording and stays there, and every
        other station keeps recording too, so the next switch has a buffer ready."""
        with self.lock:
            if slug not in self.meta:
                return False
            self.powered = True
            self.muted.discard(slug)
            self.last_listen = time.time()
            self.save()
            self.sync()
        return True

    def note_listener(self, mount, on):
        with self.lock:
            if on:
                self.last_listen = time.time()
            n = self.proxy_listeners.get(mount, 0) + (1 if on else -1)
            if n > 0:
                self.proxy_listeners[mount] = n
            else:
                self.proxy_listeners.pop(mount, None)

    def auto_off(self):
        """The recording sleeps itself when nobody has listened for a while, so
        arriving at the office and forgetting the switch costs the droid nothing.
        $RADIO_IDLE_OFF=0 switches this watchdog off while debugging."""
        if IDLE_OFF <= 0:
            return
        while True:
            time.sleep(30)
            with self.lock:
                idle = self.powered and time.time() - self.last_listen > IDLE_OFF
                busy = any(self.proxy_listeners.values())
            if idle and not busy and not any(
                    v.get("listeners", 0) for v in self.stats().values()):
                self.power(False)

    def relay_loop(self, slug):
        st = next(s for s in self.stations if s["slug"] == slug)
        log = open(LOGDIR / (slug + ".log"), "a", buffering=1)
        fails = 0
        while True:
            with self.lock:
                if slug not in self.wanted:
                    self.threads.pop(slug, None)
                    return
                ring = self.rings.setdefault(slug, Ring())
                tee = (f"[f={self.fmt}]icecast://source:{self.source_pw}@127.0.0.1:"
                       f"{ICECAST_PORT}{self.mount(st)}|[f={self.fmt}]pipe:1")
                cmd = (["ffmpeg", "-hide_banner", "-loglevel", "warning",
                        "-reconnect", "1", "-reconnect_streamed", "1",
                        "-reconnect_delay_max", "10", "-user_agent", UA,
                        "-i", st["url"], "-vn", "-map", "0:a:0", "-ac", "2"]
                       + self.enc + ["-f", "tee", tee])
                self.meta[slug]["started"] = time.time()
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log,
                                        stdin=subprocess.DEVNULL)
                self.procs[slug] = proc
            while True:                     # stdout carries the relay's own bytes
                try:                        # a raw read: bytes flow at once, not in 64 kB lots
                    data = os.read(proc.stdout.fileno(), 65536)
                except OSError:
                    break
                if not data:
                    break
                ring.append(data)
            rc = proc.wait()
            with self.lock:
                self.procs.pop(slug, None)
                if slug not in self.wanted:
                    self.threads.pop(slug, None)
                    return
                fails += 1
                self.meta[slug]["restarts"] += 1
            time.sleep(min(30, 2 ** min(fails, 5)))

    def meta_loop(self, slug):
        """Follow the station's own stream to read its icy titles: fetch with
        Icy-MetaData and discard the audio, keeping only the StreamTitle updates.
        ffmpeg's icecast output here is a plain source and cannot carry metadata,
        so this side reader is what feeds both the log and the page. radio_core reads
        each chunk and decides what it means, so a station's own announcement between
        pieces never becomes a row here either."""
        st = next(s for s in self.stations if s["slug"] == slug)
        last = ""
        while True:
            with self.lock:
                if slug not in self.wanted:
                    return
            try:
                r = urllib.request.urlopen(urllib.request.Request(
                    st["url"], headers={"User-Agent": UA, "Icy-MetaData": "1"}), timeout=20)
                interval = int(r.headers.get("icy-metaint", "0") or 0)
                if not interval:  # no inline chunks; some stations only set icy-title in the header
                    title, banner = radio_core.clean_title(st["name"], r.headers.get("icy-title") or "")
                    r.close()
                    if title and title != last and not banner:
                        last = title
                        self.note_title(slug, title)
                    time.sleep(30)
                    continue
                while True:
                    with self.lock:
                        if slug not in self.wanted:
                            r.close()
                            return
                    r.read(interval)
                    first = r.read(1)
                    if not first:
                        break
                    blob = r.read(first[0] * 16).rstrip(b"\0").decode("utf-8", "replace")
                    title, banner = radio_core.clean_title(st["name"], radio_core.parse_stream_title(blob))
                    if title and title != last and not banner:
                        last = title
                        self.note_title(slug, title)
            except Exception:
                time.sleep(5)

    def rai_loop(self):
        """Keep Rai's piece captions current, in the one thread that talks to Rai.
        The caption arrives over Rai's own current-song channel, exactly as its web
        player reads it: a short-lived token opens an MQTT subscription whose
        retained message names the piece, then one message per change. The token
        lives about an hour, so this loop renews it before its expiry and
        reconnects, backing off when anything fails. While no caption is current,
        before the first message or after an expiry, the running programme from
        Rai's schedule json stands in, shown to the page but never logged, since a
        programme is not something I listened to."""
        st = next((s for s in self.stations if s["slug"] == RAI_SLUG), None)
        if st is None:
            return
        client_id = str(uuid.uuid5(uuid.NAMESPACE_URL, RAI_PAGE))
        seen = [0.0]  # wall-clock seconds until which the last caption still holds

        def programme():
            try:
                feed = json.loads(radio_core._open(RAI_SCHEDULE).read().decode("utf-8", "replace"))
                item = next((o["currentItem"] for o in feed.get("on_air", [])
                             if o.get("channel") == RAI_CHANNEL), None)
                name = (item or {}).get("name") or ""
                if name:
                    self.note_title(RAI_SLUG, name, loggable=False)
            except Exception:
                pass

        fails = 0
        while True:
            if mqtt is None:   # paho-mqtt missing: the programme is all this box can show
                programme()
                time.sleep(60)
                continue
            client = None
            try:
                tok = json.loads(radio_core._open(
                    f"{RAI_TOKEN}?clientId={client_id}&namespace=sound",
                    headers={"X-Caller-Version": "1.0"}).read().decode("utf-8", "replace"))
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=tok["clientId"],
                                     transport="websockets", protocol=mqtt.MQTTv311)
                client.username_pw_set(tok["clientId"])
                client.ws_set_options(path=f"/mqtt?jwt={tok['token']}&client-id={tok['clientId']}")
                client.tls_set()
                client.on_connect = lambda c, u, f, rc, p=None: c.subscribe(RAI_TOPIC, qos=1)

                def on_message(c, u, m):
                    try:
                        now = json.loads(m.payload.decode("utf-8", "replace")).get("now") or {}
                    except ValueError:
                        return
                    title, banner = radio_core.clean_title(st["name"], now.get("caption") or "")
                    if title and not banner:
                        self.note_title(RAI_SLUG, title)
                        seen[0] = max((now.get("expireAt") or 0) / 1000, time.time() + 90)

                client.on_message = on_message
                client.connect(tok["basePath"], 443, keepalive=30)
                client.loop_start()
                while True:  # hold the subscription until the token nears its hour
                    time.sleep(10)
                    if time.time() * 1000 > tok["exp"] - 300:
                        break
                    if not client.is_connected():
                        raise ConnectionError("the current-song subscription dropped")
                    if time.time() > seen[0]:
                        programme()
                fails = 0      # a token's hour passed cleanly: reset the backoff
            except Exception:
                time.sleep(min(60, 2 ** min(fails, 6)))
                fails += 1
            finally:
                try:
                    if client:
                        client.loop_stop()
                        client.disconnect()
                except Exception:
                    pass

    def note_title(self, slug, title, loggable=True):
        """Keep a station's current title. loggable False shows the title on the page
        and status without ever logging it: Rai's programme name stands in while no
        piece caption is current, and a programme is not something I listened to."""
        with self.lock:
            cur = self.titles.get(slug)
            if not cur or cur[0] != title:
                self.titles[slug] = [title, time.time(), loggable]

    def log_line(self, station, title):
        """Append one row, same columns as radio.lua: date, time, station, piece.
        The in-memory copy feeds the page's played list."""
        LOGTSV.parent.mkdir(parents=True, exist_ok=True)
        new = not LOGTSV.exists()
        hm = time.strftime("%H:%M")
        with open(LOGTSV, "a") as f:
            if new:
                f.write("date\ttime\tstation\tpiece\n")
            f.write(time.strftime("%Y-%m-%d\t%H:%M") + "\t" + station + "\t" + title + "\n")
        self.recent.insert(0, {"time": hm, "station": station, "piece": title})
        del self.recent[12:]

    def log_loop(self):
        """Mirror radio.lua's rule: a piece is logged once it held the mount for 30 s
        while a listener was connected, so skipping through stations logs nothing. A
        listener counts whether it came through icecast directly or through this page's
        buffered proxy. A station announces the same piece several times, so the last
        row per station is kept and a piece that comes back is not written twice."""
        watching = {}  # slug -> [title, since, logged], the piece being watched
        logged = {}    # slug -> the last title written, so one piece is one row
        while True:
            stats = self.stats()
            for st in self.stations:
                slug = st["slug"]
                try:
                    entry = self.titles.get(slug, ["", 0, True])
                    title, loggable = entry[0], entry[2]
                    listening = stats.get(self.mount(st), {}).get("listeners", 0) > 0
                    cur = watching.get(slug)
                    if not title or not loggable or not listening or not cur or cur[0] != title:
                        watching[slug] = ([title, time.time(), False]
                                          if title and loggable and listening else None)
                        continue
                    if not cur[2] and time.time() - cur[1] >= 30:
                        cur[2] = True
                        if logged.get(slug) != title:
                            logged[slug] = title
                            self.log_line(st["name"], title)
                except Exception:
                    continue
            time.sleep(5)

    def supervisor(self):
        while True:
            if self.icecast is None or self.icecast.poll() is not None:
                log = open(LOGDIR / "icecast.log", "a", buffering=1)
                self.icecast = subprocess.Popen(["icecast", "-c", str(CONFIG)],
                                                stdout=log, stderr=subprocess.STDOUT,
                                                stdin=subprocess.DEVNULL)
            time.sleep(3)

    def stats(self):
        """Listener counts and bitrates from icecast's /admin/stats legacy report,
        with this server's own buffered listeners merged into their mounts."""
        try:
            xml = urllib.request.urlopen(
                urllib.request.Request(f"http://127.0.0.1:{ICECAST_PORT}/admin/stats",
                                       headers={"Authorization": self.auth}), timeout=2
            ).read().decode("utf-8", "replace")
        except Exception:
            out = {}
        else:
            out = {}
            for chunk in xml.split("<source ")[1:]:
                m = re.search(r'mount="([^"]*)"', chunk)
                if not m:
                    continue
                def child(tag):
                    mm = re.search(r"<" + tag + r">([^<]*)</" + tag + ">", chunk)
                    return mm.group(1) if mm else ""
                try:
                    listeners = int(child("listeners") or 0)
                except ValueError:
                    listeners = 0
                out[m.group(1)] = {"listeners": listeners, "bitrate": child("bitrate")}
        for mount, n in list(self.proxy_listeners.items()):
            out.setdefault(mount, {"listeners": 0, "bitrate": ""})["listeners"] += n
        return out

    def status(self, client=None):
        stats = self.stats()
        rows = []
        for st in self.stations:
            slug = st["slug"]
            proc = self.procs.get(slug)
            live = proc is not None and proc.poll() is None and time.time() - self.meta[slug]["started"] > 3
            info = stats.get(self.mount(st), {})
            ring = self.rings.get(slug)
            error = ""
            if slug in self.wanted and not live:
                try:
                    error = (LOGDIR / (slug + ".log")).read_text().splitlines()[-1][:200]
                except Exception:
                    pass
            rows.append({**{k: st[k] for k in ("name", "slug", "url", "colour")},
                         "mount": self.mount(st), "enabled": slug in self.wanted,
                         "live": live, "restarts": self.meta[slug]["restarts"],
                         "title": self.titles.get(slug, [""])[0],
                         "bitrate": info.get("bitrate", ""), "listeners": info.get("listeners", 0),
                         "ring": round(ring.seconds()) if ring else 0,
                         "me": ring.client_view(client) if ring and client else None,
                         "error": error})
        return {"pid": os.getpid(), "enc": self.ext.lstrip("."), "powered": self.powered,
                "recent": self.recent, "stations": rows}

    def shutdown(self):
        with self.lock:
            self.wanted.clear()
        for proc in list(self.procs.values()) + [self.icecast]:
            if proc and proc.poll() is None:
                proc.terminate()
        PIDFILE.unlink(missing_ok=True)
        threading.Timer(0.3, lambda: os._exit(0)).start()


def svg_icon():
    return """<svg width="40" height="40" viewBox="0 0 48 48" fill="none" stroke="#8dd3c7"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
<rect x="5" y="19" width="38" height="24" rx="3"/>
<line x1="11" y1="26" x2="25" y2="26"/><line x1="11" y1="31" x2="25" y2="31"/><line x1="11" y1="36" x2="25" y2="36"/>
<circle cx="35" cy="31" r="4.5"/><line x1="35" y1="31" x2="37.5" y2="27.5"/>
<line x1="31" y1="19" x2="41" y2="7"/><path d="M37 12a8 8 0 0 1 3 4"/><path d="M40 8a12 12 0 0 1 4 6"/>
</svg>"""


def page(radio, host):
    menu_rows, station_list = [], []
    for st in radio.stations:
        slug, colour, mount = st["slug"], st["colour"], radio.mount(st)
        url = f"http://{host}:{WEB_PORT}{mount}"
        station_list.append({"slug": slug, "name": st["name"], "url": url, "colour": colour})
        logo = LOGOS / (slug + ".img")
        if logo.exists():
            # Rasters carry their own ground; the tile defaults to dark for white art,
            # and only dark-ink art gets the light one.
            magic = logo.read_bytes()[:4]
            raster = magic[:3] in (b"\x89PN", b"GIF", b"RIFF") or magic[:2] == b"\xff\xd8"
            if slug in DARK_INK_LOGOS:
                cls = "logo ink"
            elif slug in WHITE_LOGOS:
                cls = "logo"
            elif raster:
                cls = "logo raster"
            else:
                cls = "logo ink"
            art = f'<img class="{cls}" src="/logo/{slug}" alt="">'
        else:
            initials = "".join(w[0] for w in st["name"].split()[:2]).upper()
            art = f'<span class=tile style="border-color:#{colour};color:#{colour}">{initials}</span>'
        menu_rows.append(
            f'<div class=mrow id=row-{slug} onclick="playRow(\'{slug}\',event)">{art}'
            f'<div class=text><span class=name style="color:#{colour}">{st["name"]}</span>'
            f'<span class=st id=st-{slug}>off</span></div>'
            f'<span class=pdot id=dot-{slug} title="on"></span></div>')
    # The client is the template file next to the server, read fresh every request:
    # edit radio-page.html, scp it, done — no restart, so client tweaks never
    # disturb the recording or the RAM tapes. Four holes get filled per request.
    # The controls live in a fixed bar at the bottom of the main page; the station
    # menu holds nothing but stations. copy link builds its URL in the page itself.
    menu = "".join(menu_rows)
    foot = (f"{len(radio.stations)} stations from {M3U.name}, one ffmpeg each, restarted on a drop · "
            f"{round(RING_MAX / AUDIO_BPS / 60)} min of each kept in RAM, played 3 min behind live · "
            f"page and streams on :{WEB_PORT}, icecast on :{ICECAST_PORT}, over the tailnet")
    return (PAGE.read_text()
            .replace("%%ICON%%", svg_icon())
            .replace("%%VARS%%", "var ST=" + json.dumps(station_list)
                     + ",RSEC=" + str(round(RING_MAX / AUDIO_BPS)) + ";")
            .replace("%%MENU%%", menu)
            .replace("%%FOOT%%", foot))


class Handler(http.server.BaseHTTPRequestHandler):
    radio = None

    def reply(self, code, body, ctype):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def mount_routes(self, path):
        """Paths this server proxies to icecast: /<slug>.mp3 (or .aac)."""
        for st in self.radio.stations:
            if path == self.radio.mount(st) or path == "/" + st["slug"]:
                return self.radio.mount(st)
        return None

    def do_HEAD(self):
        mount = self.mount_routes(self.path.partition("?")[0])
        if mount:
            # icecast 2.5 answers HEAD with 405, which trips file-style probes in
            # players like Evermusic; answer here and stream through GET instead.
            self.reply(200, b"", "audio/mpeg")
        else:
            self.reply(404, "not found", "text/plain")

    def stream_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "none")
        self.send_header("Cache-Control", "no-cache")

    def stream(self, mount):
        # Hold the listener's request while a just-tapped relay comes up (icecast 404s
        # until the source registers), so Safari's gesture-initiated play survives.
        up = None
        for _ in range(15):
            try:
                up = urllib.request.urlopen(
                    urllib.request.Request(f"http://127.0.0.1:{ICECAST_PORT}{mount}",
                                           headers={"User-Agent": UA}), timeout=10)
                break
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    self.reply(e.code, b"station off air\n", "text/plain")
                    return
                time.sleep(1)
            except Exception:
                self.reply(502, b"icecast unreachable\n", "text/plain")
                return
        if up is None:
            self.reply(504, b"station did not come up\n", "text/plain")
            return
        self.stream_headers()
        for h in ("icy-name", "icy-br", "icy-genre"):
            v = up.headers.get(h)
            if v:
                self.send_header(h, v)
        self.end_headers()
        self.radio.note_listener(mount, True)
        try:
            while True:
                chunk = up.read(16384)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the listener hung up
        except Exception:
            pass  # icecast or the relay died mid-stream
        finally:
            self.radio.note_listener(mount, False)

    def ring_stream(self, st, lag, frm, client=None):
        """Serve a buffered listener from the Ring: at lag it starts that many seconds
        behind live, with from it resumes exactly where its last connection ended, so a
        phone whose network blinked replays what it missed at line speed. Plain URL
        listeners never come here; they keep the live icecast path above."""
        radio, slug = self.radio, st["slug"]
        ring = radio.rings.get(slug)
        if ring is None:
            self.reply(404, b"station not recording\n", "text/plain")
            return
        with ring.cond:
            if frm is not None:
                pos = max(ring.start, min(frm, ring.end))
            elif lag:
                pos = max(ring.start, ring.end - int(lag) * AUDIO_BPS)
            else:
                pos = ring.start
        mine, pos = ring.attach(client, pos)
        # Headers in icecast's shape: Safari's native <audio> plays endless streams it
        # recognises as internet radio (icy-*), and its MSE-less path is what iPhones use.
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("icy-name", st["name"])
        self.send_header("icy-br", "128")
        self.send_header("icy-public", "0")
        with ring.cond:
            self.send_header("X-Ring-End", str(ring.end))   # the live edge, for the page's delay line
        self.send_header("X-Ring-From", str(pos))
        self.end_headers()
        radio.note_listener(radio.mount(st), True)
        t0, why, sent = time.time(), "eof", 0
        h = self.headers
        self.log_message("ring open %s %s pos=%d range=%s ua=%s", slug, client, pos,
                         h.get("Range"), (h.get("User-Agent") or "")[:40])
        try:
            for chunk in ring.read_from(pos, lambda: radio.rings.get(slug) is not ring):
                self.wfile.write(chunk)
                sent += len(chunk)
                with ring.cond:
                    mine["upto"] = max(mine["upto"], pos + sent)
                    mine["t"] = time.time()
        except (BrokenPipeError, ConnectionResetError):
            why = "hangup"
        except Exception as e:
            why = "error " + type(e).__name__
        finally:
            with ring.cond:
                mine["conns"] -= 1
                mine["t"] = time.time()
            self.log_message("ring close %s %s %s bytes=%d secs=%.1f", slug, client, why, sent, time.time() - t0)
            radio.note_listener(radio.mount(st), False)

    def hls(self, path, params):
        """/<slug>.m3u8 is the station's playlist; /hls/<slug>/<seq>.mp3 one segment."""
        radio = self.radio
        if path.endswith(".m3u8"):
            slug = path[1:-5]
        else:
            parts = path.split("/")          # ["", "hls", slug, "<seq>.mp3"]
            slug = parts[2] if len(parts) == 4 else ""
        ring = radio.rings.get(slug)
        if ring is None:
            self.reply(404, "station not recording\n", "text/plain")
            return
        with radio.lock:
            radio.last_listen = time.time()  # an HLS listener keeps the relays awake too
        c = params.get("c", "")
        query = "?c=" + c if c else ""
        if path.endswith(".m3u8"):
            try:
                behind = float(params.get("start", "180"))
            except ValueError:
                behind = 180.0
            body = ring.playlist(f"/hls/{slug}", max(0.0, behind), query)
            if body is None:
                self.reply(503, "tape still empty\n", "text/plain")
                return
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        try:
            seq = int(path.rsplit("/", 1)[1].split(".")[0])
        except ValueError:
            seq = -1
        data = ring.segment_bytes(seq)
        if data is None:
            self.reply(404, "segment no longer on the tape\n", "text/plain")
            return
        if c:
            with ring.cond:
                if len(ring.hls) > 50:
                    for k in [k for k, v in ring.hls.items() if time.time() - v["t"] > 600]:
                        del ring.hls[k]
                h = ring.hls.setdefault(c, {"bytes": 0, "t": time.time()})
                h["bytes"] += len(data)
                h["seq"], h["t"] = seq, time.time()
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=600")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if path.endswith(".m3u8") or path.startswith("/hls/"):
            self.hls(path, params)
            return
        mount = self.mount_routes(path)
        if mount:
            if params.get("lag") or params.get("from"):
                st = self.radio.station_by_mount(mount)
                if st:
                    frm = params.get("from")
                    self.ring_stream(st, params.get("lag"),
                                     int(frm) if frm and frm.lstrip("-").isdigit() else None,
                                     params.get("c"))
                else:
                    self.reply(404, "not found", "text/plain")
            else:
                self.stream(mount)
        elif path.startswith("/api/"):
            self.handle_api(path, query)
        elif path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store")
            body = page(self.radio, self.headers.get("Host", "alfdroid").split(":")[0]).encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/logo/"):
            logo = LOGOS / (path[len("/logo/"):] + ".img")
            if logo.is_file() and "/" not in path[len("/logo/"):]:
                blob = logo.read_bytes()
                if blob.startswith(b"<?xm") or b"<svg" in blob[:300]:
                    ctype = "image/svg+xml"
                else:
                    ctype = {b"\x89PNG": "image/png", b"GIF8": "image/gif", b"\xff\xd8": "image/jpeg",
                             b"RIFF": "image/webp"}.get(blob[:4], "image/x-icon")
                self.reply(200, blob, ctype)
            else:
                self.reply(404, "not found", "text/plain")
        elif path == "/radio.m3u":
            # A fresh playlist for Evermusic's online-links feature: whatever is
            # switched on here is what the player gets, in the page's order.
            host = self.headers.get("Host", "alfdroid").split(":")[0]
            lines = ["#EXTM3U"]
            for st in self.radio.stations:
                if st["slug"] in self.radio.wanted:
                    lines.append(f'#EXTINF:-1,{st["name"]}')
                    lines.append(f'http://{host}:{WEB_PORT}{self.radio.mount(st)}')
            self.reply(200, "\n".join(lines) + "\n", "audio/x-mpegurl")
        elif path == "/favicon.ico":
            self.reply(200, svg_icon(), "image/svg+xml")
        else:
            self.reply(404, "not found", "text/plain")

    def handle_api(self, path, query):
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        slug = params.get("slug")
        if path == "/api/status":
            self.reply(200, json.dumps(self.radio.status(params.get("c"))), "application/json")
        elif path in ("/api/on", "/api/off") and slug:
            self.reply(200, json.dumps({"ok": self.radio.set(slug, path.endswith("on"))}),
                       "application/json")
        elif path == "/api/select" and slug:
            self.reply(200, json.dumps({"ok": self.radio.select(slug)}), "application/json")
        elif path == "/api/power":
            self.reply(200, json.dumps({"ok": True, "powered": self.radio.power(
                params.get("on", "1") == "1")}), "application/json")
        elif path == "/api/on-all":
            self.radio.set_all(True)
            self.reply(200, '{"ok":true}', "application/json")
        elif path == "/api/off-all":
            self.radio.set_all(False)
            self.reply(200, '{"ok":true}', "application/json")
        elif path == "/api/shutdown":
            self.reply(200, '{"ok":true}', "application/json")
            self.radio.shutdown()
        else:
            self.reply(404, "not found", "text/plain")

    def do_POST(self):
        path, _, query = self.path.partition("?")
        self.handle_api(path, query)

    def log_message(self, fmt, *args):
        # Keep a record of what players request: which path, which method, from whom.
        try:
            with open(LOGDIR / "requests.log", "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.address_string()} {fmt % args}\n")
        except Exception:
            pass


def probe():
    try:
        return json.loads(fetch(f"http://127.0.0.1:{WEB_PORT}/api/status", timeout=2))
    except Exception:
        return None


def resolve(queries, stations):
    """Match CLI arguments to stations by slug, 1-based index, or name substring."""
    slugs = []
    for q in queries:
        found = [st for st in stations
                 if q == st["slug"] or (q.isdigit() and int(q) == stations.index(st) + 1)
                 or q.lower() in st["name"].lower()]
        if not found:
            sys.exit(f"no station matches {q!r}; one of: " + ", ".join(st["slug"] for st in stations))
        slugs += [st["slug"] for st in found]
    return slugs


def post(path):
    try:
        fetch("http://127.0.0.1:" + str(WEB_PORT) + path, timeout=3, data=b"")
        return True
    except Exception:
        return False


def serve():
    for d in (STATE, LOGDIR, LOGOS):
        d.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))
    radio = Radio()
    threading.Thread(target=radio.supervisor, daemon=True).start()
    threading.Thread(target=radio.log_loop, daemon=True).start()
    threading.Thread(target=radio.auto_off, daemon=True).start()
    threading.Thread(target=radio.rai_loop, daemon=True).start()
    threading.Thread(target=fetch_logos, daemon=True).start()
    Handler.radio = radio
    http.server.ThreadingHTTPServer(("0.0.0.0", WEB_PORT), Handler).serve_forever()


def daemon_up():
    if probe():
        return
    STATE.mkdir(parents=True, exist_ok=True)
    log = open(LOGDIR / "serve.log", "a", buffering=1) if LOGDIR.exists() else subprocess.DEVNULL
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "__serve"],
                     stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(120):
        if probe():
            return
        time.sleep(0.5)
    sys.exit("the service did not come up; see " + str(LOGDIR / "serve.log"))


def show_status(st):
    if not st:
        print("service off")
        return
    print(f"service on (pid {st['pid']}, relaying to {st['enc']} on :{ICECAST_PORT}, page on :{WEB_PORT})")
    print("  recording " + ("on" if st.get("powered") else "off"))
    for row in st["stations"]:
        state = "on " if row["enabled"] else "off"
        detail = "live" if row["live"] else ("restarting" if row["enabled"] else "-")
        print(f"  {state}  {detail:<10} {row['name']}  :{ICECAST_PORT}{row['mount']}"
              + (f"  {row['bitrate']}k x{row['listeners']}" if row["live"] and row["bitrate"] else "")
              + (f"  ring {row['ring']}s" if row.get("ring") else "")
              + (f"  restarts {row['restarts']}" if row["restarts"] else ""))
        if row["error"]:
            print(f"       last: {row['error']}")


def usage():
    print(__doc__.splitlines()[0])
    print("""
usage: radio-server.py <command> [station ...]

  up                  start the service (icecast, relays, page on :8080)
  down                stop the service and every relay
  restart             down, then up
  status              show each station's state (the default)
  start <station>...  record these stations (switches recording on)
  stop <station>...   mute them, leaving the rest of the recording alone
  web                 run in the foreground, for debugging
  logos [--force]     fetch station logos

Stations match by slug, 1-based number, or a word of the name.""")


def main(argv):
    cmd = argv[0] if argv else "status"
    if cmd == "__serve":
        serve()
    elif cmd == "up":
        daemon_up()
    elif cmd == "down":
        if not post("/api/shutdown"):
            print("service was not running")
    elif cmd == "restart":
        post("/api/shutdown")
        time.sleep(1)
        daemon_up()
    elif cmd == "web":
        serve()
    elif cmd == "logos":
        fetch_logos(force="--force" in argv[1:])
        print("logos in", LOGOS)
    elif cmd == "status":
        show_status(probe())
    elif cmd in ("start", "stop"):
        on = cmd == "start"
        if on:
            daemon_up()
        stations = load_stations()
        if not stations:
            sys.exit(f"no stations in {M3U}")
        for slug in resolve(argv[1:], stations):
            if not post(f"/api/{'on' if on else 'off'}?slug={slug}"):
                sys.exit("the service did not answer; try radio-server.py restart")
    elif cmd in ("help", "-h", "--help"):
        usage()
    else:
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
