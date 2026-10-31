"""
Local test server for the browser version (notes/browser_version.md): the web game at /bam/ (server/webgame.py, the
same code the game server uses) and every other request forwarded to the dev server, so everything is one origin
as the game expects.

    python tools/build_web.py --host 127.0.0.1:8090        # web build: work/web/game + work/web/storage
    python tools/web_spike.py [--port 8090] [--backend http://127.0.0.1:8087]
    open http://127.0.0.1:8090/bam/

work/ruffle/ holds Ruffle's self-hosted web build (ruffle.js + its .wasm files), downloaded separately.
"""

import argparse
import http.server
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
import webgame  # noqa: E402

GAME = webgame.default(str(ROOT))


class Handler(http.server.BaseHTTPRequestHandler):
    backend = None

    def do_GET(self):
        if self.path.split("?")[0] == "/":
            self.send_response(302)
            self.send_header("Location", GAME.prefix)
            self.end_headers()
            return
        res = GAME.resolve(self.path)
        if res is None:
            self.forward()
            return
        kind, value = res
        if kind == "redirect":
            self.send_response(302)
            self.send_header("Location", value)
            self.end_headers()
        elif kind == "missing":
            self.send_error(404)
        else:
            data = value if kind == "page" else value.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if kind == "page" else GAME.content_type(value))
            self.send_header("Cache-Control", GAME.cache_control(kind, None if kind == "page" else value))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

    do_HEAD = do_GET

    def do_POST(self):
        self.forward()

    def forward(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if self.command == "POST" else None
        req = urllib.request.Request(self.backend + self.path, data=body, method=self.command)
        for k in ("Content-Type", "Cookie"):
            if self.headers.get(k):
                req.add_header(k, self.headers[k])
        try:
            resp = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            resp = e
        except OSError as e:
            self.send_error(502, f"backend: {e}")
            return
        data = resp.read()
        self.send_response(resp.status if hasattr(resp, "status") else resp.code)
        for k in ("Content-Type", "Location"):
            if resp.headers.get(k):
                self.send_header(k, resp.headers[k])
        for cookie in resp.headers.get_all("Set-Cookie") or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--backend", default="http://127.0.0.1:8087")
    args = ap.parse_args()
    Handler.backend = args.backend.rstrip("/")
    if not GAME.available():
        print("warning: run tools/build_web.py first and put Ruffle's self-hosted web build in work/ruffle/")
    print(f"http://127.0.0.1:{args.port}{GAME.prefix}  (rest -> {Handler.backend})")
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
