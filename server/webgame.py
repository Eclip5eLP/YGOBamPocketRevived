"""
Browser version of the game (notes/browser_version.md, findings 6.56-6.58), served under one path prefix
(default /bam/) next to the game API on the same origin:

  /bam/                 the page: our loading bar, Ruffle, the login frame
  /bam/ruffle/...       Ruffle's self-hosted web build (<ruffle_dir>)
  /bam/storage/...      content as a phone has it in app storage: our packages extracted (<web_dir>/storage),
                        then the original content (Local Store); paths lower-cased like on a phone
  /bam/<anything else>  the web build's game files (<web_dir>/game: MobileGame.swf, config/, asset/)

Built by tools/build_web.py. The game's own requests (/facebook/proxy.html, /fb/..., /closepopupconfig.xml) go to
the server root as usual. On an https page Ruffle upgrades the game's http:// URLs to https:// (upgradeToHttps).

Login: the game calls the page's revivalLogin(url) (as3_new/com/revival/web/WebLogin.as); the page shows the login
page (server/fakefb.py) in a frame over the game; its done page / Cancel link post {revivalLogin: link | null} to
the page, which hands it back to the game (revivalLoginDone).
"""

import mimetypes
import os
from pathlib import Path
from typing import Optional, Tuple

TYPES = {".swf": "application/x-shockwave-flash", ".wasm": "application/wasm", ".js": "text/javascript",
         ".xml": "text/xml", ".fnt": "text/xml", ".json": "application/json", ".png": "image/png",
         ".jpg": "image/jpeg", ".ace": "application/octet-stream", ".map": "application/json"}

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yugioh BAM Pocket Revived</title>
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}
body{display:flex;align-items:center;justify-content:center}
/* the game lays itself out once for a widescreen phone screen: a fixed 16:9 area (set by the script below, at most
   1280x720 rendered pixels), scaled to the window with CSS; the game never sees a resize */
#game{flex:none;transform-origin:center center}
#loading{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:14px;background:#000;color:#cfd8e6;font:600 15px/1 system-ui,sans-serif;letter-spacing:.15em;z-index:1;
  transition:opacity .4s}
#loading .bar{width:min(320px,70vw);height:6px;background:#1b2330;border-radius:3px;overflow:hidden}
#loading .fill{width:0;height:100%;background:#3d8bfd;transition:width .2s}
#loading.done{opacity:0;pointer-events:none}
#login{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.6);z-index:2}
#login.open{display:flex}
#login .box{position:relative;width:min(440px,94vw);height:min(600px,94vh);border-radius:10px;overflow:hidden;
  box-shadow:0 8px 40px rgba(0,0,0,.6);background:#0b1730}
#login.wide .box{width:min(1000px,94vw);height:min(85vh,94vh)}
#login iframe{width:100%;height:100%;border:0}
#login .close{position:absolute;top:6px;right:8px;border:0;background:none;color:#cfd8e6;font:28px/1 system-ui;
  cursor:pointer}</style></head>
<body><div id="loading"><div>LOADING</div><div class="bar"><div class="fill"></div></div></div>
<div id="login"><div class="box"><button class="close" title="Cancel">&times;</button><iframe title="Log in"></iframe></div></div>
<div id="game"></div>
<script>
window.RufflePlayer = window.RufflePlayer || {};
window.RufflePlayer.config = {
  playerRuntime: "air",       // the game is an AIR app: enables Ruffle's AIR-only classes where it has them
  autoplay: "on", unmuteOverlay: "hidden", letterbox: "on",
  splashScreen: false,        // no Ruffle loading animation: our bar, then the game's own loading screen
  backgroundColor: "#000000", contextMenu: "off",
  logLevel: "warn", allowNetworking: "all", allowScriptAccess: true,
  base: new URL(".", location.href).pathname,   // the game's relative URLs (config/, asset/, storage/) live here
};
// ?renderer=webgpu | wgpu-webgl | webgl | canvas (Stage3D needs a wgpu renderer)
const renderer = new URLSearchParams(location.search).get("renderer");
if (renderer) window.RufflePlayer.config.preferredRenderer = renderer;
</script>
<script src="ruffle/ruffle.js"></script>
<script>
let player = null;
// game area: 16:9, at most 1280x720 (rendering cost grows with the pixel count; the game's art is phone-sized)
const gameBox = document.getElementById("game");
// (a tab opened in the background reports a 0x0 window: then 1280x720)
const GAME_W = innerWidth > 0 && innerHeight > 0 ? Math.round(Math.min(1280, innerWidth, innerHeight * 16 / 9)) : 1280;
const GAME_H = Math.round(GAME_W * 9 / 16);
gameBox.style.width = GAME_W + "px";
gameBox.style.height = GAME_H + "px";
function fitGame() {
  if (innerWidth > 0 && innerHeight > 0)
    gameBox.style.transform = "scale(" + Math.min(innerWidth / GAME_W, innerHeight / GAME_H) + ")";
}
fitGame();
addEventListener("resize", fitGame);
const fill = document.querySelector("#loading .fill");
const setProgress = (f) => { fill.style.width = Math.round(Math.min(1, f) * 100) + "%"; };
async function fetchGame() {
  const resp = await fetch("MobileGame.swf");
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

// login: the game asks for its login page (com.revival.web.WebLogin); it opens in a frame over the game
const login = document.getElementById("login");
const loginFrame = login.querySelector("iframe");
function finishLogin(link) {
  if (!login.classList.contains("open")) return;
  login.classList.remove("open");
  loginFrame.src = "about:blank";
  try { player.revivalLoginDone(link || null); } catch (e) { console.error("login callback", e); }
}
window.revivalLogin = function (url) {
  if (location.protocol === "https:") url = url.replace(/^http:/, "https:");
  loginFrame.src = url;
  login.classList.toggle("wide", url.indexOf("/dialog/revival_") !== -1);  // friends, profile editor
  login.classList.add("open");
};
login.querySelector(".close").addEventListener("click", () => finishLogin(null));
// the server's in-game pages (friends, profile editor) end on their redirect_uri, .../fb/connect/login_success.html
loginFrame.addEventListener("load", () => {
  let href = "";
  try { href = loginFrame.contentWindow.location.href; } catch (e) { return; }
  if (href.indexOf("/fb/connect/login_success.html") !== -1) finishLogin(href);
});
window.addEventListener("message", (e) => {
  if (e.origin === location.origin && e.data && "revivalLogin" in e.data) finishLogin(e.data.revivalLogin);
});

window.addEventListener("load", async () => {
  player = window.RufflePlayer.newest().createPlayer();
  player.style.width = "100%"; player.style.height = "100%";
  document.getElementById("game").appendChild(player);
  player.addEventListener("loadeddata", () => {
    setProgress(1);
    // the game draws its own loading screen about a second after it starts
    setTimeout(() => document.getElementById("loading").classList.add("done"), 1200);
  });
  // parameters the game reads (com.revival.web.Web.Param): origin = the host content and the startup text come
  // from; boosterpacks = config/boosterpacks.json, which the APK reads from its files at start-up
  const packs = await fetch("config/boosterpacks.json").then((r) => r.ok ? r.text() : "[]").catch(() => "[]");
  player.ruffle().load({ data: await fetchGame(), swfFileName: "MobileGame.swf",
                         parameters: { origin: location.host, boosterpacks: packs } });
});
</script></body></html>
"""


class WebGame:
    def __init__(self, web_dir: str, local_store_dir: str, ruffle_dir: str, prefix: str = "/bam/"):
        self.game = Path(web_dir) / "game"
        self.storage = [Path(web_dir) / "storage", Path(local_store_dir)]
        self.ruffle = Path(ruffle_dir)
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"

    def available(self) -> bool:
        return (self.game / "MobileGame.swf").is_file() and (self.ruffle / "ruffle.js").is_file()

    def resolve(self, path: str) -> Optional[Tuple[str, object]]:
        """For a GET path: ("page", bytes), ("redirect", location), ("file", Path) or ("missing", None);
        None when the path is not the web game's."""
        path = path.split("?")[0].split("#")[0]
        if path == self.prefix.rstrip("/"):
            return "redirect", self.prefix
        if not path.startswith(self.prefix):
            return None
        rel = path[len(self.prefix):]
        if rel in ("", "index.html"):
            return "page", PAGE.encode("utf-8")
        parts = [p for p in rel.split("/") if p]
        if any(p in ("..", ".") or "\\" in p or ":" in p for p in parts):
            return "missing", None
        if parts[0] == "ruffle":
            f = self.ruffle.joinpath(*parts[1:])
        elif parts[0] == "storage":
            rel_store = [p.lower() for p in parts[1:]]
            f = next((b.joinpath(*rel_store) for b in self.storage if b.joinpath(*rel_store).is_file()), None)
        else:
            f = self.game.joinpath(*parts)
        return ("file", f) if f is not None and f.is_file() else ("missing", None)

    @staticmethod
    def content_type(f: Path) -> str:
        return TYPES.get(f.suffix.lower()) or mimetypes.guess_type(str(f))[0] or "application/octet-stream"

    @staticmethod
    def cache_control(kind: str, f: Optional[Path] = None) -> str:
        # the page and the game file change with each build; content and Ruffle rarely
        if kind == "page" or (f is not None and f.name in ("MobileGame.swf", "mmog.xml")):
            return "no-cache"
        return "public, max-age=3600"


def default(root: str) -> "WebGame":
    """The usual layout of a checkout: work/web (tools/build_web.py), work/ruffle, input/.../Local Store."""
    return WebGame(os.path.join(root, "work", "web"),
                   os.path.join(root, "input", "data", "data", "air.com.konami.ygo", "com.konami.ygo", "Local Store"),
                   os.path.join(root, "work", "ruffle"))
