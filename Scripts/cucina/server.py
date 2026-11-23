"""The recipe index, previews, and tablet screen served by cucina."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import json
import hashlib
import mimetypes
import os
import re
import secrets
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import recipes

HERE = Path(__file__).resolve().parent
CACHE = Path(os.getenv('XDG_CACHE_HOME', str(Path.home()/'.cache')))/'cucina'
DATA = Path(os.getenv('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'cucina'
SITEMAP = 'https://ricette.giallozafferano.it/sitemap/ricette.xml'
BASE = 'https://ricette.giallozafferano.it/'
LOCK = threading.RLock()
INDEX = []
TABLETS = {}
STATE = {'slug': '', 'seq': 0}
RADIO_KEY = Path.home()/'.local/share/radio/key'


def keys():
    """Keys that open cucina through Funnel: the radio's key, and one per guest in DATA/keys
    as `name key` lines, re-read on every request so deleting a line shuts that guest out."""
    found = []
    try:
        found.append(RADIO_KEY.read_text().strip())
    except OSError:
        pass
    try:
        found += [line.split()[-1] for line in (DATA/'keys').read_text().splitlines() if line.strip() and not line.startswith('#')]
    except OSError:
        pass
    return [k for k in found if k]


def known(given, valid):
    return bool(given) and any(secrets.compare_digest(given.encode(), k.encode()) for k in valid)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def refresh():
    global INDEX
    req = urllib.request.Request(SITEMAP, headers={'User-Agent': recipes.BROWSER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        root = ET.fromstring(response.read())
    rows = {}
    for loc in root.findall('{*}url/{*}loc'):
        parsed = urlparse(loc.text or '')
        if parsed.hostname != 'ricette.giallozafferano.it' or not parsed.path.endswith('.html'):
            continue
        slug = unquote(parsed.path[1:-5])
        if '/' in slug or not re.fullmatch(r'[\w-]+', slug):
            continue
        title = slug.replace('-', ' ')
        rows[slug] = {'slug': slug, 'title': title[:1].upper()+title[1:]}
    if not rows:
        raise ValueError('Indice vuoto: conservo quello precedente.')
    with LOCK:
        INDEX = sorted(rows.values(), key=lambda row: row['title'].casefold())
        save(CACHE/'index.json', {'updated': time.time(), 'recipes': INDEX})
    return len(INDEX)


def catalogue_loop():
    while True:
        cached = load(CACHE/'index.json', {})
        if time.time()-cached.get('updated', 0) > 86400:
            try:
                refresh()
            except Exception as error:
                print('index:', error, flush=True)
        time.sleep(3600)


def get_recipe(slug):
    if not re.fullmatch(r'[\w-]+', slug) or slug not in {row['slug'] for row in INDEX}:
        raise ValueError('Ricetta non presente nell’indice.')
    path = CACHE/'recipes'/(slug+'.json')
    cached = load(path, {})
    if cached and 'image' in cached.get('recipe', {}) and time.time()-cached.get('updated', 0) < 7*86400:
        return dict(cached['recipe'], cached=False)
    try:
        found = recipes.fetch(BASE+slug+'.html')
        with LOCK:
            save(path, {'updated':time.time(), 'recipe':found})
        return dict(found, cached=False)
    except Exception:
        if cached:
            return dict(cached['recipe'], cached=True)
        raise


def get_image(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('www.giallozafferano.it', 'ricette.giallozafferano.it') or not parsed.path.startswith('/images/'):
        raise ValueError('Foto non disponibile.')
    path = CACHE/'images'/hashlib.sha256(url.encode()).hexdigest()
    if path.exists():
        return path.read_bytes(), mimetypes.guess_type(parsed.path)[0] or 'image/jpeg'
    request = urllib.request.Request(url, headers={'User-Agent': recipes.BROWSER_AGENT, 'Referer': 'https://www.giallozafferano.it/'})
    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read(10*1024*1024+1)
        if len(content) > 10*1024*1024 or not response.headers.get('Content-Type','').startswith('image/'):
            raise ValueError('Foto non disponibile.')
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(content)
        temporary.replace(path)
    return content, mimetypes.guess_type(parsed.path)[0] or 'image/jpeg'


class Handler(BaseHTTPRequestHandler):
    def reply(self, value, status=200, kind='application/json; charset=utf-8'):
        body = (json.dumps(value, ensure_ascii=False) if isinstance(value, (dict,list)) else value).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def locked(self, params):
        """Tailnet requests pass. A request through Funnel needs a key: given once as ?k=, it
        comes back as the ck cookie; the radio's rk cookie from the same host works too."""
        if not (self.headers.get('Tailscale-Funnel-Request') or self.headers.get('X-Forwarded-For')):
            return False
        valid = keys()
        given = params.get('k',[''])[0]
        if known(given, valid):
            self.send_response(302)
            self.send_header('Location', urlparse(self.path).path)
            self.send_header('Set-Cookie', f'ck={given}; Path=/; Max-Age=315360000; Secure; HttpOnly; SameSite=Lax')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return True
        cookies = dict(c.strip().split('=',1) for c in self.headers.get('Cookie','').split(';') if '=' in c)
        if known(cookies.get('ck',''), valid) or known(cookies.get('rk',''), valid):
            return False
        self.reply({'error':'Pagina non trovata.'},404)
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if self.locked(params):
            return
        try:
            if parsed.path in ('/', '/cook', '/screen'):
                name = {'/':'page.html','/cook':'cook.html','/screen':'screen.html'}[parsed.path]
                return self.reply((HERE/name).read_text(), kind='text/html; charset=utf-8')
            if parsed.path == '/image':
                content, kind = get_image(params.get('url',[''])[0])
                self.send_response(200)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'public, max-age=604800')
                self.end_headers()
                self.wfile.write(content)
                return
            if parsed.path == '/api/index':
                return self.reply({'recipes': INDEX, 'updated': load(CACHE/'index.json', {}).get('updated')})
            if parsed.path == '/api/recipe':
                return self.reply(get_recipe(params.get('slug',[''])[0]))
            if parsed.path == '/api/screen':
                with LOCK:
                    if params.get('watch'):
                        TABLETS[params.get('watch',[''])[0][:80]] = time.time()
                    online = any(time.time()-t < 8 for t in TABLETS.values())
                    return self.reply(dict(STATE, tablet_online=online))
            if parsed.path == '/api/status':
                return self.reply({'recipes':len(INDEX),'pid':os.getpid()})
            if parsed.path == '/api/notes':
                slug = params.get('slug',[''])[0]
                if not re.fullmatch(r'[\w-]+', slug):
                    raise ValueError('Ricetta non valida.')
                return self.reply(load(DATA/'notes'/(slug+'.json'), []))
            self.reply({'error':'Pagina non trovata.'},404)
        except (ValueError, OSError) as error:
            self.reply({'error':str(error)}, 502)

    def do_POST(self):
        if self.locked({}):
            return
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            return self.reply({'error':'Origine non valida.'},403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length > 16384:
                raise ValueError('Richiesta troppo lunga.')
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError('Richiesta non valida.')
            if self.path == '/api/index':
                return self.reply({'recipes': refresh()})
            if self.path == '/api/screen':
                slug = request.get('slug','')
                get_recipe(slug)
                with LOCK:
                    STATE.update(slug=slug, seq=time.time_ns())
                    save(DATA/'screen.json',STATE)
                    online = any(time.time()-t < 8 for t in TABLETS.values())
                return self.reply(dict(STATE, tablet_online=online))
            if self.path == '/api/notes':
                slug, text = request.get('slug',''), request.get('text','').strip()
                if not re.fullmatch(r'[\w-]+',slug) or not text:
                    raise ValueError('Nota vuota o ricetta non valida.')
                with LOCK:
                    path = DATA/'notes'/(slug+'.json')
                    notes = load(path,[])
                    notes.append(time.strftime('%Y-%m-%d')+' — '+text)
                    save(path,notes)
                return self.reply(notes)
            self.reply({'error':'Azione non trovata.'},404)
        except (ValueError,OSError) as error:
            self.reply({'error':str(error)},400)

    def log_message(self, fmt, *args):
        if self.path.startswith(('/api/screen','/api/status')):
            return
        super().log_message(fmt,*args)


def serve(host, port):
    global INDEX
    INDEX = load(CACHE/'index.json', {}).get('recipes',[])
    STATE.update(load(DATA/'screen.json', STATE))
    if not INDEX:
        refresh()
    threading.Thread(target=catalogue_loop,daemon=True).start()
    httpd = ThreadingHTTPServer((host,port),Handler)
    print(f'cucina · {host}:{port} · {len(INDEX)} ricette',flush=True)
    httpd.serve_forever()
