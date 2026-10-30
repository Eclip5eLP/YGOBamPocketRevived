#!/usr/bin/env python3
"""
Compile the brand-new AS3 classes in as3_new/ and merge them into the game SWF (notes/findings.md 6.35, todo.md).

  1. the game SWF as a SWC (FFDec -swf2swc), so the new classes compile against the game's classes without
     including them; cached in work/newclasses/ by the SWF's hash
  2. compc (HARMAN AIR SDK, airmobile config) compiles every as3_new/**.as into a library SWF
  3. its DoABC tags are inserted before the game SWF's first ShowFrame, so they load with the game code

Patched game classes (tools/as3_patches.py, applied afterwards by patch_as3.py) may then use the new classes.
Without any .as file in as3_new/ the SWF is copied unchanged.

Usage: build_newclasses.py in.swf out.swf
"""

import hashlib
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "as3_new"
WORK = ROOT / "work" / "newclasses"
FFDEC_JAR = ROOT / "tools" / "ffdec" / "ffdec-cli.jar"
COMPC = ROOT / "work" / "airsdk" / "bin" / "compc.bat"
DOABC_TAGS = (72, 82)  # DoABC, DoABC2
SHOW_FRAME = 1


def read_swf(data):
    body = zlib.decompress(data[8:]) if data[:3] == b"CWS" else data[8:]
    nbits = body[0] >> 3
    return data[:8], body, (5 + 4 * nbits + 7) // 8 + 4


def tags(body, pos):
    while pos < len(body):
        cl = struct.unpack_from("<H", body, pos)[0]
        code, length, header = cl >> 6, cl & 0x3F, 2
        if length == 0x3F:
            length, header = struct.unpack_from("<I", body, pos + 2)[0], 6
        yield code, pos, header + length
        pos += header + length


def merge_abc(game_data, library_data):
    header, game, game_pos = read_swf(game_data)
    _, lib, lib_pos = read_swf(library_data)
    abc = b"".join(lib[p:p + n] for code, p, n in tags(lib, lib_pos) if code in DOABC_TAGS)
    if not abc:
        sys.exit("compc output has no DoABC tag")
    first_frame = next(p for code, p, n in tags(game, game_pos) if code == SHOW_FRAME)
    body = game[:first_frame] + abc + game[first_frame:]
    return b"CWS" + header[3:4] + struct.pack("<I", len(body) + 8) + zlib.compress(body, 9)


def run(cmd):
    res = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"failed ({res.returncode}): {cmd[0]}\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
    return res.stdout


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src_swf, dst_swf = Path(sys.argv[1]), Path(sys.argv[2])
    sources = sorted(SRC.rglob("*.as")) if SRC.exists() else []
    if not sources:
        shutil.copyfile(src_swf, dst_swf)
        print("no new classes (as3_new/ empty)")
        return

    WORK.mkdir(parents=True, exist_ok=True)
    game_data = src_swf.read_bytes()
    game_swc, stamp = WORK / "game.swc", WORK / "game.swc.sha1"
    digest = hashlib.sha1(game_data).hexdigest()
    if not game_swc.exists() or not stamp.exists() or stamp.read_text() != digest:
        run(["java", "-jar", FFDEC_JAR, "-swf2swc", game_swc, src_swf])
        stamp.write_text(digest)

    library_swc = WORK / "new.swc"
    library_swc.unlink(missing_ok=True)
    run(["cmd", "/c", COMPC, "+configname=airmobile", f"-external-library-path+={game_swc}",
         f"-source-path={SRC}", f"-include-sources={SRC}", f"-output={library_swc}"])
    library_data = zipfile.ZipFile(library_swc).read("library.swf")
    dst_swf.write_bytes(merge_abc(game_data, library_data))
    print(f"merged {len(sources)} new class file(s) from as3_new/")


if __name__ == "__main__":
    main()
