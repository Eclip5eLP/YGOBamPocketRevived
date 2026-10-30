#!/usr/bin/env python3
"""
Class-level AS3 source patches for MobileGame.swf, recompiled with FFDec.

For each class in tools/as3_patches.py the decompiled source is exported from the input SWF at build time,
each (old, new) edit is applied (old must occur exactly once), and all edited classes are recompiled into
the output SWF with one `ffdec-cli -air -replace` call. Only our edits live in the repository, never game
code. Run it after tools/patch_swf.py (it exports from that output, so byte patches are kept).

Usage: python tools/patch_as3.py <in.swf> <out.swf> [--keep-dir DIR]
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from as3_patches import PATCHES  # noqa: E402

FFDEC_JAR = ROOT / "tools" / "ffdec" / "ffdec-cli.jar"


def ffdec(*args):
    res = subprocess.run(["java", "-jar", str(FFDEC_JAR), *map(str, args)], capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"ffdec failed ({res.returncode}): {res.stdout[-2000:]} {res.stderr[-2000:]}")
    return res.stdout + res.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--keep-dir", help="keep the patched sources here (for debugging)")
    args = ap.parse_args()

    work = Path(args.keep_dir) if args.keep_dir else Path(tempfile.mkdtemp(prefix="as3patch_"))
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    classes = list(PATCHES)
    ffdec("-selectclass", ",".join(classes), "-export", "script", work / "export", args.src)

    replace_args = []
    for cls in classes:
        src = work / "export" / "scripts" / (cls.replace(".", "/") + ".as")
        if not src.exists():
            sys.exit(f"export missing for {cls}: {src}")
        text = src.read_text(encoding="utf-8").replace("\r\n", "\n")
        for n, (old, new) in enumerate(PATCHES[cls]):
            count = text.count(old)
            if count != 1:
                sys.exit(f"{cls} edit {n}: anchor found {count} times, expected 1:\n{old}")
            text = text.replace(old, new)
        out = work / "patched" / (cls.replace(".", "/") + ".as")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        replace_args += [cls, out]
        print(f"patched {cls}: {len(PATCHES[cls])} edit(s)")

    log = ffdec("-air", "-replace", args.src, args.dst, *replace_args)
    if "error" in log.lower():
        sys.exit("ffdec reported errors:\n" + log[-3000:])
    if not Path(args.dst).exists():
        sys.exit("ffdec produced no output SWF")
    print(f"wrote {args.dst} ({Path(args.dst).stat().st_size} bytes)")
    if not args.keep_dir:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
