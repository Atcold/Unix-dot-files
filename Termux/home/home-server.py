#!/usr/bin/env python3
"""AlfDROID's homepage on :8000, and on the internet at AlfFUNNEL's plain address, behind
the radio's key: a card per service, each with its tailnet link and, where Funnel
publishes it, its public link. The tailnet links use the name the page was opened with;
the public address comes from AlfFUNNEL's Tailscale, so it stays out of the repo."""
import html
import http.server
import json
import secrets
import subprocess
from pathlib import Path

PORT = 8000
PAGE = Path(__file__).with_name("index.html")
TS = Path("~/.local/share/tailscale/tailscaled.sock").expanduser()
TSBIN = Path("~/.local/bin/tailscale").expanduser()
KEY = Path("~/.local/share/radio/key").expanduser()


def public_name():
    """AlfFUNNEL's full name, such as alffunnel.<tailnet>.ts.net, or None while it is down."""
    try:
        out = subprocess.run([str(TSBIN), f"--socket={TS}", "status", "--json"],
                             capture_output=True, text=True, timeout=5).stdout
        return json.loads(out)["Self"]["DNSName"].rstrip(".") or None
    except Exception:
        return None


def key():
    """The radio's key, which also opens this page from the internet."""
    try:
        return KEY.read_text().strip()
    except OSError:
        return ""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path != "/":
            self.send_error(404)
            return
        # Tailnet requests pass. A request through Funnel needs the key: given once as ?k=,
        # it comes back as the rk cookie, which the radio on the same host accepts too.
        public = bool(self.headers.get("Tailscale-Funnel-Request") or self.headers.get("X-Forwarded-For"))
        if public:
            k = key()
            given = dict(q.split("=", 1) for q in query.split("&") if "=" in q).get("k", "")
            cookies = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
            if k and secrets.compare_digest(given.encode(), k.encode()):
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"rk={k}; Path=/; Max-Age=31536000; Secure; HttpOnly; SameSite=Lax")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not (k and secrets.compare_digest(cookies.get("rk", "").encode(), k.encode())):
                self.send_error(404)
                return
        # Through Funnel the page's own host is the public one; the tailnet links name the droid
        host = "alfdroid" if public else html.escape(self.headers.get("Host", "alfdroid").rsplit(":", 1)[0])
        name = public_name()
        radio = (f'<a href="https://{name}:8443/">public<small>{name}:8443</small></a>' if name else "")
        body = (PAGE.read_text().replace("%%HOST%%", host)
                .replace("%%RADIO_PUBLIC%%", radio).encode())
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("", PORT), Handler).serve_forever()
