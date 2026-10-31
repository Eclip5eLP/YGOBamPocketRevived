"""
Browser version spike (notes/browser_version.md, option A): run the game SWF in Ruffle on a local page.

One origin for everything, as the game expects: this server serves the page, Ruffle and the game files
(MobileGame.swf, config/, asset/ from the APK stage) and forwards every other request to the dev server.

    python tools/build_release.py --host 127.0.0.1:8090 --arch x64 --out work/emu/ygo_web.apk   # SWF + config for this origin
    python tools/web_spike.py [--ruffle work/ruffle] [--port 8090] [--backend http://127.0.0.1:8087]
    open http://127.0.0.1:8090/

work/ruffle/ holds Ruffle's self-hosted web build (ruffle.js + its .wasm files), downloaded separately.
"""

import argparse
import http.server
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "work" / "game_adt" / "stage"

PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>BAM Pocket web spike</title>
<style>html,body{margin:0;height:100%;background:#000}#game{width:100vw;height:100vh}</style></head>
<body><div id="game"></div>
<script>
window.RufflePlayer = window.RufflePlayer || {};
window.RufflePlayer.config = {
  playerRuntime: "air",      // the game is an AIR app: enables Ruffle's AIR-only classes where it has them
  autoplay: "on", unmuteOverlay: "hidden", letterbox: "on",
  logLevel: "info", allowNetworking: "all", base: "/",
};
</script>
<script src="/ruffle/ruffle.js"></script>
<script>
window.addEventListener("load", () => {
  const player = window.RufflePlayer.newest().createPlayer();
  player.style.width = "100%"; player.style.height = "100%";
  document.getElementById("game").appendChild(player);
  player.ruffle().load({ url: "/MobileGame.swf" });
});
</script></body></html>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    ruffle = None
    backend = None

    def translate_path(self, path):
        rel = path.split("?")[0].split("#")[0].lstrip("/")
        if rel.startswith("ruffle/"):
            return str(self.ruffle / rel[len("ruffle/"):])
        return str(STAGE / rel)

    def local(self):
        rel = self.path.split("?")[0].lstrip("/")
        return rel == "" or rel == "MobileGame.swf" or rel.startswith(("ruffle/", "config/", "asset/"))

    def do_GET(self):
        if self.path.split("?")[0] == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
        elif self.local():
            super().do_GET()
        else:
            self.forward()

    def do_HEAD(self):
        super().do_HEAD() if self.local() else self.forward()

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
        for k in ("Content-Type", "Set-Cookie", "Location"):
            if resp.headers.get(k):
                self.send_header(k, resp.headers[k])
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--ruffle", default=str(ROOT / "work" / "ruffle"))
    ap.add_argument("--backend", default="http://127.0.0.1:8087")
    args = ap.parse_args()
    Handler.ruffle = Path(args.ruffle)
    Handler.backend = args.backend.rstrip("/")
    if not (Handler.ruffle / "ruffle.js").is_file():
        print(f"warning: no ruffle.js in {Handler.ruffle} (download Ruffle's self-hosted web build)")
    if not (STAGE / "MobileGame.swf").is_file():
        print(f"warning: no {STAGE / 'MobileGame.swf'}; run tools/build_release.py first")
    print(f"http://127.0.0.1:{args.port}/  (game files from {STAGE}, rest -> {Handler.backend})")
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
