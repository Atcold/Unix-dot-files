#!/usr/bin/env python3
"""Serve my radio stations as icecast mounts, with a web page to switch them on and off.

Stations come from ~/.settings/Mpv/radio.m3u, the same file the `radio` alias plays on
the Macs. Each station that is on runs one ffmpeg that decodes the upstream and
republishes it as a uniform 128k MP3 mount at http://<host>:8000/<slug>.mp3, so a
listener's player only ever sees plain MP3 at one bitrate whatever the station sends.
A supervisor restarts ffmpeg when a station's stream drops.

Built for Termux on AlfDROID: `pkg install ffmpeg icecast python`, then
`radio-server.py up` starts icecast, the relays and a control page on port 8080.
Open http://alfdroid:8080/ on the tailnet to switch stations and copy their mount
URLs into a player such as Evermusic. State, icecast config and logs live under
~/.local/share/radio/; station logos are fetched once into logos/ there, and dropping
your own logos/<slug>.png overrides the fetched one. Pieces land in log.tsv there,
in the same shape radio.lua writes on the Macs: date, time, station, piece, once a
piece has played 30 s with a listener connected.
"""

import base64
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
from pathlib import Path
from urllib.parse import urlparse

M3U = Path("~/.settings/Mpv/radio.m3u").expanduser()
STATE = Path("~/.local/share/radio").expanduser()
LOGDIR = STATE / "logs"
LOGOS = STATE / "logos"
PIDFILE = STATE / "radio.pid"
CONFIG = STATE / "icecast.xml"
ENABLED = STATE / "enabled.json"
LOGTSV = STATE / "log.tsv"

ICECAST_PORT = 8000
WEB_PORT = 8080
UA = "AlfDROID-radio/1.0 (Termux)"

# ColorBrewer Set3 in the order radio.lua uses, without the yellow and the grey.
COLOURS = ["8dd3c7", "bebada", "fb8072", "80b1d3", "fdb462", "b3de69", "fccde5", "bc80bd", "ccebc5"]

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
    """Write icecast.xml once, with random passwords kept on the phone for later runs."""
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


class Radio:
    """The daemon's state: icecast, one wanted-flag and one relay thread per station."""

    def __init__(self):
        self.lock = threading.Lock()
        self.stations = load_stations()
        self.source_pw, self.admin_pw = ensure_config()
        self.auth = "Basic " + base64.b64encode(f"admin:{self.admin_pw}".encode()).decode()
        try:
            self.enc, self.fmt, self.ext = encoder()
        except Exception:
            self.enc, self.fmt, self.ext = [], "mp3", ".mp3"  # status reports ffmpeg's failure
        self.wanted = set()
        self.procs = {}      # slug -> ffmpeg Popen
        self.threads = {}    # slug -> relay thread
        self.titles = {}     # slug -> [title, since], from the icy side readers
        self.meta = {st["slug"]: {"restarts": 0, "started": 0.0} for st in self.stations}
        self.icecast = None
        if ENABLED.exists():
            for slug in json.loads(ENABLED.read_text()):
                self.wanted.add(slug)

    def mount(self, st):
        return "/" + st["slug"] + self.ext

    def save(self):
        ENABLED.write_text(json.dumps(sorted(self.wanted)))

    def respawn(self):
        """Relaunch relay and meta threads for stations enabled in a previous run;
        set() spawns threads, and the enabled set restored at startup bypasses it."""
        for slug in list(self.wanted):
            self.set(slug, True)

    def set(self, slug, on):
        with self.lock:
            if slug not in self.meta:
                return False
            if on:
                self.wanted.add(slug)
            else:
                self.wanted.discard(slug)
            self.save()
            if on and slug not in self.threads:
                t = threading.Thread(target=self.relay_loop, args=(slug,), daemon=True)
                self.threads[slug] = t
                t.start()
                threading.Thread(target=self.meta_loop, args=(slug,), daemon=True).start()
            if not on:
                proc = self.procs.pop(slug, None)
                if proc and proc.poll() is None:
                    proc.terminate()
        return True

    def set_all(self, on):
        for st in self.stations:
            self.set(st["slug"], on)

    def select(self, slug):
        """Single-listener mode: exactly this station on air, every other relay off."""
        for st in self.stations:
            if st["slug"] != slug:
                self.set(st["slug"], False)
        return self.set(slug, True)

    def relay_loop(self, slug):
        st = next(s for s in self.stations if s["slug"] == slug)
        log = open(LOGDIR / (slug + ".log"), "a", buffering=1)
        fails = 0
        while True:
            with self.lock:
                if slug not in self.wanted:
                    self.threads.pop(slug, None)
                    return
                cmd = (["ffmpeg", "-hide_banner", "-loglevel", "warning",
                        "-reconnect", "1", "-reconnect_streamed", "1",
                        "-reconnect_delay_max", "10", "-user_agent", UA,
                        "-i", st["url"], "-vn", "-map", "0:a:0", "-ac", "2"]
                       + self.enc
                       + ["-f", self.fmt,
                          f"icecast://source:{self.source_pw}@127.0.0.1:{ICECAST_PORT}{self.mount(st)}"])
                self.meta[slug]["started"] = time.time()
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL)
                self.procs[slug] = proc
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
        so this side reader is what feeds both the log and the page."""
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
                    title = (r.headers.get("icy-title") or "").strip()
                    r.close()
                    if title and title != last:
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
                    m = re.search(r"StreamTitle='([^']*)'", blob)
                    title = (m.group(1) if m else "").strip()
                    if title and title != last:
                        last = title
                        self.note_title(slug, title)
            except Exception:
                time.sleep(5)

    def note_title(self, slug, title):
        with self.lock:
            cur = self.titles.get(slug)
            if not cur or cur[0] != title:
                self.titles[slug] = [title, time.time()]

    def log_line(self, station, title):
        """Append one row, same columns as radio.lua: date, time, station, piece."""
        LOGTSV.parent.mkdir(parents=True, exist_ok=True)
        new = not LOGTSV.exists()
        with open(LOGTSV, "a") as f:
            if new:
                f.write("date\ttime\tstation\tpiece\n")
            f.write(time.strftime("%Y-%m-%d\t%H:%M") + "\t" + station + "\t" + title + "\n")

    def log_loop(self):
        """Mirror radio.lua's rule: a piece is logged once it held the mount for 30 s
        while a listener was connected, so skipping through stations logs nothing."""
        watching = {}  # slug -> [title, since, logged], the piece being watched
        while True:
            stats = self.stats()
            for st in self.stations:
                slug = st["slug"]
                try:
                    title = self.titles.get(slug, ["", 0])[0]
                    listening = stats.get(self.mount(st), {}).get("listeners", 0) > 0
                    cur = watching.get(slug)
                    if not title or not listening or not cur or cur[0] != title:
                        watching[slug] = [title, time.time(), False] if title and listening else None
                        continue
                    if not cur[2] and time.time() - cur[1] >= 30:
                        cur[2] = True
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
        """Listener counts and bitrates from icecast's /admin/stats legacy report."""
        try:
            xml = urllib.request.urlopen(
                urllib.request.Request(f"http://127.0.0.1:{ICECAST_PORT}/admin/stats",
                                       headers={"Authorization": self.auth}), timeout=2
            ).read().decode("utf-8", "replace")
        except Exception:
            return {}
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
        return out

    def status(self):
        stats = self.stats()
        rows = []
        for st in self.stations:
            slug = st["slug"]
            proc = self.procs.get(slug)
            live = proc is not None and proc.poll() is None and time.time() - self.meta[slug]["started"] > 3
            info = stats.get(self.mount(st), {})
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
                         "error": error})
        return {"pid": os.getpid(), "enc": self.ext.lstrip("."), "stations": rows}

    def shutdown(self):
        with self.lock:
            self.wanted.clear()
        for proc in list(self.procs.values()) + [self.icecast]:
            if proc and proc.poll() is None:
                proc.terminate()
        PIDFILE.unlink(missing_ok=True)
        threading.Timer(0.3, lambda: os._exit(0)).start()


def svg_icon():
    return """<svg width=40 height=40 viewBox="0 0 48 48" fill=none stroke=#8dd3c7
stroke-width=2 stroke-linecap=round stroke-linejoin=round aria-hidden=true>
<rect x=5 y=19 width=38 height=24 rx=3/>
<line x1=11 y1=26 x2=25 y2=26/><line x1=11 y1=31 x2=25 y2=31/><line x1=11 y1=36 x2=25 y2=36/>
<circle cx=35 cy=31 r=4.5/><line x1=35 y1=31 x2=37.5 y2=27.5/>
<line x1=31 y1=19 x2=41 y2=7/><path d="M37 12a8 8 0 0 1 3 4"/><path d="M40 8a12 12 0 0 1 4 6"/>
</svg>"""


CSS = """
body{background:#000;color:#eaeaea;font-family:"Cascadia Code",ui-monospace,Menlo,monospace;
margin:24px auto;max-width:640px;padding:0 16px 96px}
header{display:flex;align-items:center;gap:12px;margin-bottom:4px}
h1{font-size:20px;font-weight:600;margin:0;flex:1}
.bar{display:flex;align-items:center;gap:14px;font-size:13px;color:#9a9a9a;margin-bottom:16px;flex-wrap:wrap}
.row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #1c1c1c}
.row.playing{background:#0d0d0d;border-left:3px solid;padding-left:9px}
img.logo{width:44px;height:44px;border-radius:8px;object-fit:contain;background:#e8e8e8;flex:none;padding:3px;box-sizing:border-box}
img.raster{background:none;padding:0}
.tile{width:44px;height:44px;border-radius:8px;background:#0d0d0d;flex:none;display:flex;align-items:center;justify-content:center;font-weight:700;border:1px solid}
.text{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.name{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.st{font-size:12px;white-space:nowrap;color:#9a9a9a;overflow:hidden;text-overflow:ellipsis}
.st.live{color:#b3de69}.st.warn{color:#fdb462}
button{background:none;border:1px solid #3a3a3a;color:#9a9a9a;border-radius:6px;padding:2px 8px;
font:inherit;font-size:11px;flex:none}
footer{margin-top:18px;font-size:11px;color:#6f6f6f;overflow-wrap:anywhere}
#player{position:fixed;bottom:0;left:0;right:0;background:#0a0a0a;border-top:1px solid #1c1c1c;
padding:10px 14px calc(10px + env(safe-area-inset-bottom));display:flex;align-items:center;gap:12px;
max-width:640px;margin:0 auto;box-sizing:border-box}
#player button{font-size:17px;padding:6px 12px;border-radius:20px}
#bar-tgl{border-color:#8dd3c7;color:#8dd3c7}
#bar-dot{width:12px;height:12px;border-radius:50%;flex:none;background:transparent}
#bar-text{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
#bar-name{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#bar-piece{font-size:11px;color:#9a9a9a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#vol{width:88px;flex:none;accent-color:#8dd3c7}
"""

JS = """
var snd=null, now=null, want=false, titles={}, enabled=[];
function rep(id){return document.getElementById(id)}
function st_of(slug){for(var i=0;i<ST.length;i++)if(ST[i].slug===slug)return ST[i];return{}}
function copy(u,b,ev){if(ev)ev.stopPropagation();navigator.clipboard.writeText(u).then(function(){
  b.textContent='copied';setTimeout(function(){b.textContent='copy'},1200)})}
function setBar(){
  var st=st_of(now);
  rep('bar-dot').style.background=st.colour?'#'+st.colour:'transparent';
  rep('bar-name').textContent=st.name||'—';
  rep('bar-name').style.color=st.colour?'#'+st.colour:'#9a9a9a';
  rep('bar-piece').textContent=(now&&titles[now])||'';
  rep('bar-tgl').textContent=want?'■':'▶';
  ST.forEach(function(s){var r=rep('row-'+s.slug);
    if(r){r.classList.toggle('playing',s.slug===now);if(s.slug===now)r.style.borderLeftColor='#'+s.colour}});
  if(now&&titles[now]&&navigator.mediaSession)
    navigator.mediaSession.metadata=new MediaMetadata({title:titles[now],album:st.name,artist:'AlfDROID radio'});
}
function mk(){if(!now)return;var st=st_of(now);
  if(snd){snd.onerror=null;snd.ended=null;snd.pause()}
  snd=new Audio(st.url);snd.volume=rep('vol').value;
  snd.onended=snd.onerror=function(){if(want)setTimeout(mk,3000)};
  snd.play().catch(function(){});}
function playRow(slug,ev){if(ev)ev.stopPropagation();
  if(ev&&(ev.target.tagName==='BUTTON'||ev.target.tagName==='INPUT'))return;
  if(now===slug&&want){want=false;if(snd)snd.pause();fetch('/api/off-all');setBar();
    setTimeout(refresh,400);return}
  now=slug;want=true;
  fetch('/api/select?slug='+slug);setTimeout(refresh,400);
  mk();setBar();}
function tgl(){if(!now){if(ST.length)playRow(ST[0].slug);return}
  want=!want;if(want)mk();else snd.pause();setBar();}
function step(d){if(!ST.length)return;
  var i=-1;ST.forEach(function(s,idx){if(s.slug===now)i=idx});
  playRow(ST[(i+d+ST.length)%ST.length].slug);}
function refresh(){
  fetch('/api/status').then(function(r){return r.json()}).then(function(s){
    enabled=[];
    s.stations.forEach(function(st){
      if(st.enabled){enabled.push(st.slug)}
      if(st.title)titles[st.slug]=st.title;
      var e=rep('st-'+st.slug);if(!e)return;
      if(st.enabled&&st.live){var t='live \\u00b7 '+st.listeners+' listener'+(st.listeners==1?'':'s');
        if(st.title)t+=' \\u00b7 '+st.title;
        e.textContent=t;e.className='st live'}
      else if(st.enabled){e.textContent='restarting';e.className='st warn'}
      else{e.textContent='off';e.className='st'}
    });
    if(now&&enabled.indexOf(now)<0){want=false;if(snd)snd.pause()}
    var d=new Date(),p=rep('svc');
    p.textContent='service on \\u00b7 '+d.getHours()+':'+String(d.getMinutes()).padStart(2,'0');
    setBar();
  }).catch(function(){var p=rep('svc');if(p)p.textContent='service off'})}
function watch(){if(now&&want&&snd&&snd.paused)mk()}
setInterval(refresh,3000);setInterval(watch,8000);refresh();
if(navigator.mediaSession){
  navigator.mediaSession.setActionHandler('play',function(){if(!want)tgl()});
  navigator.mediaSession.setActionHandler('pause',function(){if(want)tgl()});
  navigator.mediaSession.setActionHandler('previoustrack',function(){step(-1)});
  navigator.mediaSession.setActionHandler('nexttrack',function(){step(1)});}
"""


def page(radio, host):
    rows, station_list = [], []
    for st in radio.stations:
        slug, colour, mount = st["slug"], st["colour"], radio.mount(st)
        url = f"http://{host}:{WEB_PORT}{mount}"
        station_list.append({"slug": slug, "name": st["name"], "url": url, "colour": colour})
        logo = LOGOS / (slug + ".img")
        if logo.exists():
            # Rasters on these stations carry their own white ground; the light tile
            # stays only for SVGs, which are often white-on-transparent.
            head = logo.read_bytes()[:4]
            cls = "logo raster" if head in (b"\x89PNG", b"GIF8", b"\xff\xd8", b"RIFF") else "logo"
            art = f'<img class={cls} src="/logo/{slug}" alt="">'
        else:
            initials = "".join(w[0] for w in st["name"].split()[:2]).upper()
            art = f'<span class=tile style="border-color:#{colour};color:#{colour}">{initials}</span>'
        rows.append(
            f'<div class=row id=row-{slug} onclick="playRow(\'{slug}\',event)">{art}'
            f'<div class=text><span class=name style="color:#{colour}">{st["name"]}</span>'
            f'<span class=st id=st-{slug}>off</span></div>'
            f'<button onclick="copy(\'{url}\',this,event)">copy</button></div>')
    return ("<!doctype html><html><head><meta charset=utf-8>"
            '<meta name=viewport content="width=device-width, initial-scale=1">'
            "<title>AlfDROID radio</title><style>" + CSS + "</style></head><body>"
            "<header>" + svg_icon() + "<h1>AlfDROID radio</h1></header>"
            '<div class=bar><span id=svc></span>'
            f'<button onclick="copy(\'http://{host}:{WEB_PORT}/radio.m3u\',this,event)">copy playlist link</button></div>'
            + "".join(rows)
            + '<div id=player>'
              '<button onclick="step(-1)">⏮</button>'
              '<button id=bar-tgl onclick="tgl()">▶</button>'
              '<button onclick="step(1)">⏭</button>'
              '<span id=bar-dot></span>'
              '<span id=bar-text><span id=bar-name>—</span><span id=bar-piece></span></span>'
              '<input type=range id=vol min=0 max=1 step=0.05 value=1 oninput="if(snd)snd.volume=this.value">'
              '</div>'
            + f'<footer>stations from {M3U} · relays re-encode to {radio.ext.lstrip(".")}, '
              f"one ffmpeg per station, restarted on drop<br>streams served here on "
              f"{WEB_PORT} (icecast direct on {ICECAST_PORT}) · reach both over the tailnet</footer>"
              f'<script>var ST={json.dumps(station_list)};</script>'
              f'<script>{JS}</script></body></html>')


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
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "none")
        self.send_header("Cache-Control", "no-cache")
        for h in ("icy-name", "icy-br", "icy-genre"):
            v = up.headers.get(h)
            if v:
                self.send_header(h, v)
        self.end_headers()
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

    def do_GET(self):
        path, _, query = self.path.partition("?")
        mount = self.mount_routes(path)
        if mount:
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
        slug = dict(p.split("=", 1) for p in query.split("&") if "=" in p).get("slug")
        if path == "/api/status":
            self.reply(200, json.dumps(self.radio.status()), "application/json")
        elif path in ("/api/on", "/api/off") and slug:
            self.reply(200, json.dumps({"ok": self.radio.set(slug, path.endswith("on"))}),
                       "application/json")
        elif path == "/api/select" and slug:
            self.reply(200, json.dumps({"ok": self.radio.select(slug)}), "application/json")
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
    radio.respawn()
    threading.Thread(target=radio.supervisor, daemon=True).start()
    threading.Thread(target=radio.log_loop, daemon=True).start()
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
    for row in st["stations"]:
        state = "on " if row["enabled"] else "off"
        detail = "live" if row["live"] else ("restarting" if row["enabled"] else "-")
        print(f"  {state}  {detail:<10} {row['name']}  :{ICECAST_PORT}{row['mount']}"
              + (f"  {row['bitrate']}k x{row['listeners']}" if row["live"] and row["bitrate"] else "")
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
  start <station>...  relay these stations; brings the service up if needed
  stop <station>...   stop their relays
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
