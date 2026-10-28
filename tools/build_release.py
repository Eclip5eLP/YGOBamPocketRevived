#!/usr/bin/env python3
"""
One-command build of the Yugioh BAM Pocket Revived APK:
  1. stub ANEs           (tools/build_stub_anes.py, skipped if already built)
  2. patched SWF         (tools/patch_swf.py, fake-Facebook URLs point at <host>/fb)
  3. APK via HARMAN ADT  (tools/build_game_adt.py: server host, descriptor, assets, signing)

Prerequisites (see README "Building the APK"): input/ygo.apk (original v1.11.2 APK),
work/airsdk (HARMAN AIR SDK 51.5.1.1), tools/ffdec/ffdec-cli.jar (JPEXS FFDec), a JDK on PATH.

Signing: --keystore (PKCS#12) with its password in the env var YGO_KEYSTORE_PASS. Without
--keystore the build is signed with the throwaway dev key work/debug.keystore.

Usage:
  python tools/build_release.py --host ygo.eclip5e.com --keystore work/release.p12 --out work/release/x.apk
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "Yugioh BAM Pocket Revived"
VERSION_LABEL = "1.0.0"
STUB_DIR = ROOT / "work" / "stub_anes" / "out"
ORIG_SWF = ROOT / "work" / "game_adt" / "MobileGame_orig.swf"


def run(cmd):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    res = subprocess.run([str(c) for c in cmd])
    if res.returncode != 0:
        sys.exit(f"step failed ({res.returncode}): {cmd[1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="ygo.eclip5e.com", help="revival server host name (port 80)")
    ap.add_argument("--keystore", default="", help="PKCS#12 release key; password in env YGO_KEYSTORE_PASS")
    ap.add_argument("--version-label", default=VERSION_LABEL)
    ap.add_argument("--out", default=str(ROOT / "work" / "release" / "YugiohBAMPocketRevived.apk"))
    args = ap.parse_args()

    missing = [p for p in (ROOT / "input" / "ygo.apk", ROOT / "work" / "airsdk" / "bin",
                           ROOT / "tools" / "ffdec" / "ffdec-cli.jar") if not p.exists()]
    if missing:
        sys.exit("missing prerequisites: " + ", ".join(str(p) for p in missing))
    if args.keystore and "YGO_KEYSTORE_PASS" not in os.environ:
        sys.exit("set YGO_KEYSTORE_PASS to the keystore password")

    py = sys.executable
    if not any(STUB_DIR.glob("*.ane")):
        run([py, ROOT / "tools" / "build_stub_anes.py", "--ns", "20.0"])
    if not ORIG_SWF.exists():
        import zipfile
        ORIG_SWF.parent.mkdir(parents=True, exist_ok=True)
        ORIG_SWF.write_bytes(zipfile.ZipFile(ROOT / "input" / "ygo.apk").read("assets/MobileGame.swf"))
    swf = ROOT / "work" / "game_adt" / f"MobileGame_{args.host.replace(':', '_')}.swf"
    run([py, ROOT / "tools" / "patch_swf.py", ORIG_SWF, swf, "--fb-base", f"http://{args.host}/fb"])

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cmd = [py, ROOT / "tools" / "build_game_adt.py", "--ns", "51.1", "--target-sdk", "28",
           "--extdir", STUB_DIR, "--cutout", "shortEdges", "--swf", swf, "--host", args.host,
           "--name", APP_NAME, "--version-label", args.version_label, "--out", args.out]
    if args.keystore:
        cmd += ["--keystore", args.keystore, "--storepass-env", "YGO_KEYSTORE_PASS"]
    run(cmd)
    print(f"\nBuilt {args.out} ({Path(args.out).stat().st_size // 1024 // 1024} MB) for server {args.host}")


if __name__ == "__main__":
    main()
