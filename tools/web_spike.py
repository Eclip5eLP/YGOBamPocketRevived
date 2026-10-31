"""
Browser version spike (notes/browser_version.md, option A): run the game SWF in Ruffle on a local page.

One origin for everything, as the game expects: this server serves the page, Ruffle, the game files
(work/web/game: MobileGame.swf, config/, asset/), the content under /storage/ (work/web/storage, then the original
content in Local Store; paths lower-cased like on a phone) and forwards every other request to the dev server.

    python tools/build_web.py --host 127.0.0.1:8090        # web build: work/web/game + work/web/storage
    python tools/web_spike.py [--ruffle work/ruffle] [--port 8090] [--backend http://127.0.0.1:8087]
    open http://127.0.0.1:8090/

work/ruffle/ holds Ruffle's self-hosted web build (ruffle.js + its .wasm files), downloaded separately.
"""

import argparse
import http.server
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "work" / "web" / "game"
STORAGE = [ROOT / "work" / "web" / "storage",
           ROOT / "input" / "data" / "data" / "air.com.konami.ygo" / "com.konami.ygo" / "Local Store"]

PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>BAM Pocket web spike</title>
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}#game{width:100vw;height:100vh}
#loading{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:14px;background:#000;color:#cfd8e6;font:600 15px/1 system-ui,sans-serif;letter-spacing:.15em;z-index:1;
  transition:opacity .4s}
#loading .bar{width:min(320px,70vw);height:6px;background:#1b2330;border-radius:3px;overflow:hidden}
#loading .fill{width:0;height:100%;background:#3d8bfd;transition:width .2s}
#loading.done{opacity:0;pointer-events:none}</style></head>
<body><div id="loading"><div>LOADING</div><div class="bar"><div class="fill"></div></div></div><div id="game"></div>
<script>
window.RufflePlayer = window.RufflePlayer || {};
window.RufflePlayer.config = {
  playerRuntime: "air",      // the game is an AIR app: enables Ruffle's AIR-only classes where it has them
  autoplay: "on", unmuteOverlay: "hidden", letterbox: "on",
  splashScreen: false,       // no Ruffle loading animation: the game's own loading screen follows right away
  backgroundColor: "#000000", contextMenu: "off",
  logLevel: "info", allowNetworking: "all", base: "/",
};
// ?renderer=webgpu | wgpu-webgl | webgl | canvas (Stage3D needs a wgpu renderer; Ruffle's default may not have it)
const renderer = new URLSearchParams(location.search).get("renderer");
if (renderer) window.RufflePlayer.config.preferredRenderer = renderer;
</script>
<script src="/ruffle/ruffle.js"></script>
<script>
// our own loading bar instead of Ruffle's: the page downloads the game file itself (real progress for the
// biggest wait), hands the bytes to Ruffle, and fades the bar out once the game has started
const fill = document.querySelector("#loading .fill");
const setProgress = (f) => { fill.style.width = Math.round(Math.min(1, f) * 100) + "%"; };
async function fetchGame() {
  const resp = await fetch("/MobileGame.swf");
  const total = Number(resp.headers.get("Content-Length")) || 0;
  const reader = resp.body.getReader();
  const chunks = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    if (total) setProgress(0.9 * got / total);
  }
  const data = new Uint8Array(got);
  let at = 0;
  for (const c of chunks) { data.set(c, at); at += c.length; }
  return data;
}
window.addEventListener("load", async () => {
  const player = window.RufflePlayer.newest().createPlayer();
  player.style.width = "100%"; player.style.height = "100%";
  document.getElementById("game").appendChild(player);
  player.addEventListener("loadeddata", () => {
    setProgress(1);
    // the game draws its own loading screen about a second after it starts
    setTimeout(() => document.getElementById("loading").classList.add("done"), 1200);
  });
  // origin: the web build loads content and the startup text from this host (com.revival.web.Web.Host)
  player.ruffle().load({ data: await fetchGame(), swfFileName: "MobileGame.swf",
                         parameters: { origin: location.host } });
});
</script></body></html>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    ruffle = None
    backend = None

    def translate_path(self, path):
        rel = path.split("?")[0].split("#")[0].lstrip("/")
        rel = urllib.parse.unquote(rel)
        if rel.startswith("ruffle/"):
            return str(self.ruffle / rel[len("ruffle/"):])
        if rel.startswith("storage/"):
            rel = rel[len("storage/"):].lower()
            for base in STORAGE:
                if (base / rel).is_file():
                    return str(base / rel)
            return str(STORAGE[0] / rel)
        return str(GAME / rel)

    def local(self):
        rel = self.path.split("?")[0].lstrip("/")
        return rel == "" or rel == "MobileGame.swf" or rel.startswith(("ruffle/", "config/", "asset/", "storage/"))

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
    if not (GAME / "MobileGame.swf").is_file():
        print(f"warning: no {GAME / 'MobileGame.swf'}; run tools/build_web.py first")
    print(f"http://127.0.0.1:{args.port}/  (game files from {GAME}, rest -> {Handler.backend})")
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
