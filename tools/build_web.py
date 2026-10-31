#!/usr/bin/env python3
"""
Browser build (notes/browser_version.md): the same game as the APK plus the web-only patches, for Ruffle.

  1. patched SWF  (tools/patch_swf.py, build_newclasses.py, patch_as3.py with YGO_WEB=1: the APK's patches plus
                   tools/as3_patches.py WEB_EDITS)
  2. game files   (<out>/game: MobileGame.swf + config/ + asset/ staged exactly like the APK, game data included)
  3. storage      (<out>/storage: our content packages extracted, i.e. what a phone unzips into app storage;
                   files the packages don't change come from the original content, Local Store, at serve time)

No APK, no ADT. Served under /bam/ by server/webgame.py (the game server, or tools/web_spike.py for dev).
--host is the site's host[:port] (live: ygo.eclip5e.com; dev: 127.0.0.1:8090).

Usage: python tools/build_web.py [--host 127.0.0.1:8090] [--out work/web]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_game_adt  # noqa: E402
from build_release import ORIG_SWF  # noqa: E402

# package -> directory in app storage (EExternalAsset.as; server/server.py PACKAGE_PATHS plus our packages)
PACKAGE_PATHS = {
    "series1": "asset/cards/", "series2": "asset/cards/", "series3": "asset/cards/",
    "anim": "asset/anim/", "common": "asset/common/", "cardgamebg": "asset/misc/cardgamebg/",
    "mapbackground": "asset/misc/mapbackground/", "mapcharacter": "asset/misc/mapcharacter/",
    "maplibrary": "asset/misc/maplibrary/", "mappreview": "asset/misc/mappreview/", "arena": "asset/module/arena/",
    "cardgamecommon": "asset/module/cardgamecommon/", "crafting": "asset/module/crafting/",
    "deckbuilder": "asset/module/deckbuilder/", "duelground": "asset/module/duelground/",
    "filters": "asset/module/filters/", "hud": "asset/module/hud/", "login": "asset/module/login/",
    "livepvpgame": "asset/module/livepvpgame/", "mainmenu": "asset/module/mainmenu/", "shop": "asset/module/shop/",
    "tournament": "asset/module/tournament/", "transition": "asset/transition/", "world": "asset/world/",
    "guild": "asset/module/guild/", "menubackground": "asset/misc/menubackground/", "font": "asset/font/",
}


def run(cmd, env=None):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    if subprocess.run([str(c) for c in cmd], env=env).returncode != 0:
        sys.exit(f"step failed: {cmd[1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1:8090", help="the page's origin host[:port]; the game talks to it")
    ap.add_argument("--out", default=str(ROOT / "work" / "web"))
    args = ap.parse_args()
    out = Path(args.out)
    py = sys.executable

    if not ORIG_SWF.exists():
        ORIG_SWF.parent.mkdir(parents=True, exist_ok=True)
        ORIG_SWF.write_bytes(zipfile.ZipFile(ROOT / "input" / "ygo.apk").read("assets/MobileGame.swf"))
    content = ROOT / "work" / "content"
    if not os.environ.get("YGO_KEEP_CONTENT") or not (content / "manifest.json").exists():
        run([py, ROOT / "tools" / "build_content.py"])
    gamedata_version = (content / "gamedata" / "gamedata_version").read_text(encoding="utf-8").strip()

    # http:// URLs on purpose: on an https page Ruffle upgrades them (upgradeToHttps), on a dev page they stay
    swf = ROOT / "work" / "game_adt" / f"MobileGame_web_{args.host.replace(':', '_')}.swf"
    bytepatched = swf.with_suffix(".bytes.swf")
    run([py, ROOT / "tools" / "patch_swf.py", ORIG_SWF, bytepatched, "--fb-base", f"http://{args.host}/fb"])
    withnew = swf.with_suffix(".new.swf")
    run([py, ROOT / "tools" / "build_newclasses.py", bytepatched, withnew])
    run([py, ROOT / "tools" / "patch_as3.py", withnew, swf],
        env={**os.environ, "YGO_WEB": "1", "YGO_WEB_GAMEDATA": gamedata_version})

    if out.exists():
        shutil.rmtree(out)
    build_game_adt.stage_files(args.host, str(swf), str(content))
    shutil.copytree(build_game_adt.STAGE, out / "game")

    manifest = json.loads((content / "manifest.json").read_text(encoding="utf-8"))
    n = 0
    for name, info in manifest["packages"].items():
        if name == "gamedata":  # already in the game files (config/)
            continue
        base = out / "storage" / PACKAGE_PATHS[name]
        with zipfile.ZipFile(content / info["zip"]) as z:
            for member in z.infolist():
                if member.is_dir() or ".." in member.filename:
                    continue
                target = base / member.filename.lower()  # a phone stores package files lower-cased
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(member))
                n += 1
    print(f"\nWeb build in {out}: game files + {n} content file(s) from {len(manifest['packages']) - 1} package(s)"
          f" for origin {args.host}")


if __name__ == "__main__":
    main()
