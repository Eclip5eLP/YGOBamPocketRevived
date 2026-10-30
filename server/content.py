"""
Content overlay: new and changed asset packages produced by tools/build_content.py (notes/findings.md 6.33).

<content_dir>/manifest.json:
  {"game_version": "1.12.0",            client version (mmog.xml client/version) of APKs that use this content
   "base_version": "1.11.1",            versionning.xml block the new block is copied from
   "packages": {"gamedata": {"version": "1.0.0", "zip": "zips/gamedata-1.0.0.zip",
                             "uncompressedsize": 123, "compressedsize": 45}, ...}}

versionning.xml is served as the original plus one <version value=game_version> block (base block with the
manifest's packages added or replaced). Older clients keep using their own block, so they never see new
packages. Zips for game_version come from the manifest when listed, otherwise from the original content.

Version gate (notes/findings.md 6.34): with a manifest, online play needs APK version >= game_version and the
current gamedata version. Clients send both as ?v=&d= on every game request (tools/as3_patches.py
ServerComHTTP); the first public APK sends neither and is refused.
"""

import copy
import json
import os
import xml.etree.ElementTree as ET
from typing import Optional, Tuple


def version_tuple(v: str) -> Tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except (AttributeError, ValueError):
        return ()


class Content:
    def __init__(self, content_dir: str):
        self.dir = content_dir
        self._mtime = None
        self.manifest = None

    def load(self) -> Optional[dict]:
        path = os.path.join(self.dir, "manifest.json")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self.manifest, self._mtime = None, None
            return None
        if mtime != self._mtime:
            with open(path, encoding="utf-8") as f:
                self.manifest = json.load(f)
            self._mtime = mtime
        return self.manifest

    def versionning_xml(self, original: bytes) -> bytes:
        m = self.load()
        if not m:
            return original
        root = ET.fromstring(original)
        if root.find(f"version[@value='{m['game_version']}']") is not None:
            return original
        base = root.find(f"version[@value='{m['base_version']}']")
        if base is None:
            return original
        block = copy.deepcopy(base)
        block.set("value", m["game_version"])
        for name, info in m["packages"].items():
            pkg = block.find(f"package[@name='{name}']")
            if pkg is None:
                pkg = ET.SubElement(block, "package", {"name": name})
            pkg.set("version", info["version"])
            pkg.set("uncompressedsize", str(info["uncompressedsize"]))
            pkg.set("compressedsize", str(info["compressedsize"]))
        root.insert(list(root).index(base), block)
        ET.indent(root, "  ")
        return ET.tostring(root, encoding="utf-8")

    def package_zip(self, game_version: str, name: str) -> Optional[str]:
        """Path of the overlay zip for this client version and package, or None to use the original."""
        m = self.load()
        if not m or game_version != m["game_version"] or name not in m["packages"]:
            return None
        path = os.path.join(self.dir, m["packages"][name]["zip"])
        return path if os.path.isfile(path) else None

    def gate(self) -> Optional[Tuple[str, str]]:
        """(minimum APK version, required gamedata version), or None when there is no content (no gate)."""
        m = self.load()
        if not m or "gamedata" not in m["packages"]:
            return None
        return m["game_version"], m["packages"]["gamedata"]["version"]

    def check_client(self, apk_version: str, data_version: str) -> Optional[str]:
        """None if this client may play online, else the reason ("apk" or "data")."""
        g = self.gate()
        if g is None:
            return None
        if not version_tuple(apk_version) or version_tuple(apk_version) < version_tuple(g[0]):
            return "apk"
        if version_tuple(data_version) != version_tuple(g[1]):
            return "data"
        return None
