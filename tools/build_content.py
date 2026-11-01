#!/usr/bin/env python3
"""
Build the revival's game content (notes/findings.md 6.33): the "gamedata" package and changed art packages.

Inputs:  input/ygo.apk (original data files under assets/config/), the original downloaded content
         (input/.../Local Store, for art packages), content/content.json and the mods in tools/content_mods/.
Outputs (work/content/, git-ignored, derived from game data):
  gamedata/config/...          every data file that differs from the original APK, + gamedata_version
  zips/<package>-<version>.zip packages for the server's content overlay
  manifest.json                read by server/content.py
The APK build (tools/build_game_adt.py --content-dir) copies gamedata/config over the APK's config/, so the APK
and the downloadable package always hold the same data for the same gamedata_version.

Usage: python tools/build_content.py [--out work/content]
"""

import argparse
import json
import os
import shutil
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ace  # noqa: E402
import content_mods  # noqa: E402

INPUT_APK = ROOT / "input" / "ygo.apk"
LOCAL_STORE = ROOT / "input" / "data" / "data" / "air.com.konami.ygo" / "com.konami.ygo" / "Local Store"


class Context:
    """What a mod can touch. Data paths are APK-relative and lowercase, e.g. config/ace/shop/shop.ace."""

    def __init__(self, apk: zipfile.ZipFile):
        self.apk = apk
        self.names = {n[len("assets/"):].lower(): n for n in apk.namelist()
                      if n.startswith(("assets/config/", "assets/asset/list/"))}
        self.raw_cache = {}    # path -> decompressed bytes (raw edits)
        self.ace_cache = {}    # path -> decoded value (structured edits)
        self.string_edits = {}  # (lang, section) -> (section object, by_key, by_id, key_ids)
        self.new_files = {}    # path -> bytes, files that are not in the APK
        self.replaced = {}     # path -> bytes, plain (non-.ace) APK files replaced as a whole
        self.server_files = {}  # path -> bytes, files for the server only (<out>/server/<path>)
        self.boosterpacks = []  # config/boosterpacks.json entries (content_mods.add_booster_pack)
        self.packages = {}     # package -> {relative path: bytes} overlay files
        self.package_versions = {}

    def original(self, path):
        return self.apk.read(self.names[path.lower()])

    def ace(self, path):
        path = path.lower()
        if path not in self.ace_cache:
            if path in self.raw_cache:
                raise RuntimeError(f"{path}: mixing raw and structured edits")
            self.ace_cache[path] = ace.loads(self.original(path))
        return self.ace_cache[path]

    def raw_replace(self, path, old, new, count=1):
        path = path.lower()
        if path in self.ace_cache:
            raise RuntimeError(f"{path}: mixing raw and structured edits")
        data = self.raw_cache.get(path) or zlib.decompress(self.original(path))
        if data.count(old) != count:
            raise RuntimeError(f"{path}: expected {count} x {old!r}, found {data.count(old)}")
        self.raw_cache[path] = data.replace(old, new)

    def set_text(self, lang, section, key, text, resource_id=None):
        """Set a localized text by key (also updating the resource ids that shared the old text), or add it."""
        by_key, by_id, key_ids = self.strings(lang, section)
        for rid in key_ids.get(key, []):
            by_id[rid] = text
        if resource_id is not None:
            by_id[int(resource_id)] = text
            key_ids.setdefault(key, []).append(int(resource_id))
        by_key[key] = text

    def strings(self, lang, section):
        """(by_key, by_id, key_ids) of a localization section, editable in place; stored when the build finishes.

        The game loads every section from config/ace/resource/<lang>/localization_section.ace
        (Engine.ALL_LOCALIZATION_FILE, LocalizerManager.LoadAllSectionFile); the per-section files are unused."""
        key = (lang, section.lower())
        if key not in self.string_edits:
            all_sections = self.ace(f"config/ace/resource/{lang}/localization_section.ace")
            sec = next((x for x in all_sections if x["sectionName"] == section.lower()), None)
            if sec is None:
                raise RuntimeError(f"no localization section {section} for {lang}")
            self.string_edits[key] = (sec, *ace.read_strings(sec))
        return self.string_edits[key][1:]

    def new_file(self, path, data):
        """A data file the original APK does not have (e.g. config/boosterpacks.json)."""
        path = path.lower()
        if path in self.names:
            raise RuntimeError(f"{path} exists in the APK; edit it instead")
        self.new_files[path] = data

    def replace_file(self, path, data):
        """Replace a non-.ace data file from the APK (e.g. an asset list XML) with new bytes."""
        path = path.lower()
        if path not in self.names:
            raise RuntimeError(f"{path} is not in the APK")
        self.replaced[path] = data

    def package_file(self, package, rel_path, data, version):
        """Add or replace a file in a downloadable art package (rel_path inside the package's asset dir)."""
        self.packages.setdefault(package, {})[rel_path] = data
        self.package_versions[package] = version

    def changed_files(self):
        for sec, by_key, by_id, _ in self.string_edits.values():
            ace.write_strings(sec, by_key, by_id)
        out = {}
        for path, data in self.raw_cache.items():
            out[path] = zlib.compress(data, 9)
        for path, value in self.ace_cache.items():
            out[path] = ace.dumps(value)
        # keep only real changes (compare decompressed, compression levels may differ)
        out = {p: d for p, d in out.items() if zlib.decompress(d) != zlib.decompress(self.original(p))}
        out.update({p: d for p, d in self.replaced.items() if d != self.original(p)})
        out.update(self.new_files)
        return out


def write_zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
            size += len(data)
    return size, path.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "work" / "content"))
    args = ap.parse_args()
    out = Path(args.out)
    cfg = json.loads((ROOT / "content" / "content.json").read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)

    with zipfile.ZipFile(INPUT_APK) as apk:
        ctx = Context(apk)
        mods = list(content_mods.MODS)
        if os.environ.get("YGO_TEST_CONTENT"):
            import content_test_mods
            at = mods.index(content_mods.write_summons)  # before write_summons and write_boosterpacks
            mods[at:at] = content_test_mods.MODS
            print("TEST CONTENT included (YGO_TEST_CONTENT)")
        for mod in mods:
            print("mod:", mod.__name__)
            mod(ctx)
        changed = ctx.changed_files()

    for path, data in ctx.server_files.items():
        (out / "server" / path).parent.mkdir(parents=True, exist_ok=True)
        (out / "server" / path).write_bytes(data)
    version = cfg["gamedata_version"]
    gd = out / "gamedata"
    files = {path: data for path, data in changed.items()}
    files["gamedata_version"] = version.encode("utf-8")
    for path, data in files.items():
        (gd / path).parent.mkdir(parents=True, exist_ok=True)
        (gd / path).write_bytes(data)
    packages = {}
    usize, csize = write_zip(out / "zips" / f"gamedata-{version}.zip", files)
    packages["gamedata"] = {"version": version, "zip": f"zips/gamedata-{version}.zip",
                            "uncompressedsize": usize, "compressedsize": csize}
    print(f"gamedata {version}: {len(changed)} changed data file(s)")

    for name, overlay in ctx.packages.items():
        pver = ctx.package_versions[name]
        pfiles = {}
        if content_mods.PACKAGE_DIRS[name] is not None:  # None: a new package, only our files
            src = LOCAL_STORE / content_mods.PACKAGE_DIRS[name]
            for f in src.rglob("*"):
                rel = f.relative_to(src).as_posix()
                if f.is_file() and "version" not in f.name:
                    pfiles[rel] = f.read_bytes()
        pfiles.update(overlay)
        pfiles[f"{name}_version"] = pver.encode("utf-8")
        zname = f"zips/{name}-{pver}.zip"
        usize, csize = write_zip(out / zname, pfiles)
        packages[name] = {"version": pver, "zip": zname, "uncompressedsize": usize, "compressedsize": csize}
        print(f"package {name} {pver}: {len(overlay)} overlay file(s)")

    manifest = {"game_version": cfg["game_version"], "base_version": cfg["base_version"], "packages": packages}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("wrote", out / "manifest.json")


if __name__ == "__main__":
    main()
