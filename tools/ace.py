#!/usr/bin/env python3
"""
Lossless codec for the game's .ace data files: zlib(AMF3 value), as written by Flash's ByteArray.writeObject.

Decoding keeps everything needed to write the file back identically: class aliases, sealed/dynamic traits,
Dates (AceDate), ByteArrays (bytes), Vectors (AceVector), and shared object references (the same Python object
is written as a reference again). Encoding uses AMF3 string, trait and object reference tables like Flash.

  python tools/ace.py dump FILE.ace [OUT.json]    readable JSON (dates/vectors/bytes tagged)
  python tools/ace.py check DIR                   round-trip every .ace under DIR, report byte equality

Also: Localization sections (config/ace/resource/<lang>/<section>.ace) via read_strings / write_strings.
"""

import json
import struct
import sys
import zlib
from pathlib import Path


class AceObject(dict):
    """Typed or anonymous AMF3 object; sealed property order and dynamic flag kept for re-encoding."""

    def __init__(self, alias="", sealed=(), dynamic=False, externalizable=False):
        super().__init__()
        self.alias, self.sealed, self.dynamic, self.externalizable = alias, list(sealed), dynamic, externalizable


class AceDate(float):
    pass


class AceVector(list):
    """AMF3 Vector: kind 0x0D int, 0x0E uint, 0x0F double, 0x10 object (with element type name)."""

    def __init__(self, items=(), kind=0x10, fixed=False, type_name=""):
        super().__init__(items)
        self.kind, self.fixed, self.type_name = kind, fixed, type_name


class AceArray(list):
    """AMF3 Array with optional associative part."""

    def __init__(self, items=(), assoc=None):
        super().__init__(items)
        self.assoc = assoc or {}


# ----------------------------------------------------------------------------------------------- decoding
class Decoder:
    def __init__(self, data):
        self.d, self.p = data, 0
        self.strings, self.objects, self.traits = [], [], []

    def u8(self):
        self.p += 1
        return self.d[self.p - 1]

    def u29(self):
        v = 0
        for i in range(4):
            b = self.u8()
            if i == 3:
                return (v << 8) | b
            v = (v << 7) | (b & 0x7F)
            if not b & 0x80:
                return v
        return v

    def string(self):
        h = self.u29()
        if not h & 1:
            return self.strings[h >> 1]
        n = h >> 1
        s = self.d[self.p:self.p + n].decode("utf-8")
        self.p += n
        if s:
            self.strings.append(s)
        return s

    def value(self):
        m = self.u8()
        if m in (0, 1):
            return None
        if m == 2:
            return False
        if m == 3:
            return True
        if m == 4:
            v = self.u29()
            return v - (1 << 29) if v & 0x10000000 else v
        if m == 5:
            self.p += 8
            return struct.unpack(">d", self.d[self.p - 8:self.p])[0]
        if m == 6:
            return self.string()
        if m in (7, 0x0B, 0x0C):
            h = self.u29()
            if not h & 1:
                return self.objects[h >> 1]
            n = h >> 1
            raw = self.d[self.p:self.p + n]
            self.p += n
            v = bytes(raw) if m == 0x0C else ("xmldoc" if m == 7 else "xml", raw.decode("utf-8"))
            self.objects.append(v)
            return v
        if m == 8:
            h = self.u29()
            if not h & 1:
                return self.objects[h >> 1]
            self.p += 8
            v = AceDate(struct.unpack(">d", self.d[self.p - 8:self.p])[0])
            self.objects.append(v)
            return v
        if m == 9:
            h = self.u29()
            if not h & 1:
                return self.objects[h >> 1]
            arr = AceArray()
            self.objects.append(arr)
            while True:
                k = self.string()
                if not k:
                    break
                arr.assoc[k] = self.value()
            arr.extend(self.value() for _ in range(h >> 1))
            return arr
        if m == 0x0A:
            h = self.u29()
            if not h & 1:
                return self.objects[h >> 1]
            if not h & 2:
                alias, sealed, dyn, ext = self.traits[h >> 2]
            else:
                ext, dyn = bool(h & 4), bool(h & 8)
                alias = self.string()
                sealed = [self.string() for _ in range(h >> 4)]
                self.traits.append((alias, sealed, dyn, ext))
            if ext:
                raise ValueError(f"externalizable {alias} not supported")
            obj = AceObject(alias, sealed, dyn)
            self.objects.append(obj)
            for name in sealed:
                obj[name] = self.value()
            if dyn:
                while True:
                    k = self.string()
                    if not k:
                        break
                    obj[k] = self.value()
            return obj
        if m in (0x0D, 0x0E, 0x0F, 0x10):
            h = self.u29()
            if not h & 1:
                return self.objects[h >> 1]
            n, fixed = h >> 1, bool(self.u8())
            vec = AceVector(kind=m, fixed=fixed)
            self.objects.append(vec)
            if m == 0x10:
                vec.type_name = self.string()
                vec.extend(self.value() for _ in range(n))
            else:
                fmt = {0x0D: ">i", 0x0E: ">I", 0x0F: ">d"}[m]
                size = 8 if m == 0x0F else 4
                for _ in range(n):
                    vec.append(struct.unpack(fmt, self.d[self.p:self.p + size])[0])
                    self.p += size
            return vec
        raise ValueError(f"unsupported AMF3 marker 0x{m:02X} at {self.p - 1}")


# ----------------------------------------------------------------------------------------------- encoding
def u29(v):
    v &= 0x1FFFFFFF
    if v < 0x80:
        return bytes([v])
    if v < 0x4000:
        return bytes([(v >> 7) | 0x80, v & 0x7F])
    if v < 0x200000:
        return bytes([(v >> 14) | 0x80, ((v >> 7) & 0x7F) | 0x80, v & 0x7F])
    return bytes([(v >> 22) | 0x80, ((v >> 15) & 0x7F) | 0x80, ((v >> 8) & 0x7F) | 0x80, v & 0xFF])


class Encoder:
    def __init__(self):
        self.out = bytearray()
        self.strings, self.objects, self.traits = {}, {}, {}

    def string(self, s):
        if s == "":
            self.out += b"\x01"
            return
        if s in self.strings:
            self.out += u29(self.strings[s] << 1)
            return
        self.strings[s] = len(self.strings)
        b = s.encode("utf-8")
        self.out += u29((len(b) << 1) | 1) + b

    def ref(self, v):
        """Write a reference if v was written before (by identity); otherwise register it."""
        if id(v) in self.objects:
            self.out += u29(self.objects[id(v)][0] << 1)
            return True
        self.objects[id(v)] = (len(self.objects), v)  # keep v alive so ids stay unique
        return False

    def value(self, v):
        o = self.out
        if v is None:
            o.append(1)
        elif v is False:
            o.append(2)
        elif v is True:
            o.append(3)
        elif isinstance(v, AceDate):
            o.append(8)
            if not self.ref(v):
                o += b"\x01" + struct.pack(">d", v)
        elif isinstance(v, int):
            if -(1 << 28) <= v < (1 << 28):
                o.append(4)
                o += u29(v)
            else:
                o.append(5)
                o += struct.pack(">d", v)
        elif isinstance(v, float):
            o.append(5)
            o += struct.pack(">d", v)
        elif isinstance(v, str):
            o.append(6)
            self.string(v)
        elif isinstance(v, tuple):  # xml
            o.append(7 if v[0] == "xmldoc" else 0x0B)
            if not self.ref(v):
                b = v[1].encode("utf-8")
                o += u29((len(b) << 1) | 1) + b
        elif isinstance(v, (bytes, bytearray)):
            o.append(0x0C)
            if not self.ref(v):
                o += u29((len(v) << 1) | 1) + bytes(v)
        elif isinstance(v, AceVector):
            o.append(v.kind)
            if not self.ref(v):
                o += u29((len(v) << 1) | 1) + bytes([1 if v.fixed else 0])
                if v.kind == 0x10:
                    self.string(v.type_name)
                    for x in v:
                        self.value(x)
                else:
                    fmt = {0x0D: ">i", 0x0E: ">I", 0x0F: ">d"}[v.kind]
                    for x in v:
                        o += struct.pack(fmt, x)
        elif isinstance(v, list):
            o.append(9)
            if not self.ref(v):
                o += u29((len(v) << 1) | 1)
                for k, x in getattr(v, "assoc", {}).items():
                    self.string(k)
                    self.value(x)
                o += b"\x01"
                for x in v:
                    self.value(x)
        elif isinstance(v, dict):
            o.append(0x0A)
            if self.ref(v):
                return
            alias = getattr(v, "alias", "")
            sealed = getattr(v, "sealed", None)
            dyn = getattr(v, "dynamic", True) if isinstance(v, AceObject) else True
            if sealed is None:
                sealed = []
            key = (alias, tuple(sealed), dyn)
            if key in self.traits:
                o += u29((self.traits[key] << 2) | 1)
            else:
                self.traits[key] = len(self.traits)
                o += u29((len(sealed) << 4) | (8 if dyn else 0) | 3)
                self.string(alias)
                for n in sealed:
                    self.string(n)
            for n in sealed:
                self.value(v[n])
            if dyn:
                for k, x in v.items():
                    if k not in sealed:
                        self.string(k)
                        self.value(x)
                o += b"\x01"
        else:
            raise TypeError(f"cannot encode {type(v)}")


def loads(raw):
    return Decoder(zlib.decompress(raw)).value()


def dumps(value):
    e = Encoder()
    e.value(value)
    return zlib.compress(bytes(e.out), 9)


def read(path):
    return loads(Path(path).read_bytes())


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(dumps(value))


# ------------------------------------------------------------------------------------- localization sections
def _utf(blob, off):
    n = struct.unpack(">H", blob[off:off + 2])[0]
    return blob[off + 2:off + 2 + n].decode("utf-8")


def read_strings(section):
    """Localization section object -> (by_key {key: text}, by_id {resourceId: text}, key_ids {key: [resourceId]}).

    key_ids pairs a key with the resource ids that point at the same stored text (same offset)."""
    g, s = bytes(section["guid"]), bytes(section["string"])
    by_key = {_utf(g, int(a)): _utf(s, int(b)) for a, b in section["sortedByGuid"]}
    by_id = {int(r): _utf(s, int(b)) for r, b in section["sortedByResourceId"]}
    ids_at = {}
    for r, b in section["sortedByResourceId"]:
        ids_at.setdefault(int(b), []).append(int(r))
    key_ids = {_utf(g, int(a)): ids_at.get(int(b), []) for a, b in section["sortedByGuid"]}
    return by_key, by_id, key_ids


def _localecompare_key(s):
    # the key index (StringFinder.GetString binary search) is in plain code point order; verified on all sections
    return s


def write_strings(section, by_key, by_id):
    """Rebuild a localization section in place from key->text and resourceId->text maps.

    Entries keep their key/resource id; the original pairing between keys and resource ids is unknown, so each
    text is stored once per key and once per resource id."""
    guid, strings, str_off = bytearray(), bytearray(), {}

    def put_str(text):
        if text not in str_off:
            b = text.encode("utf-8")
            str_off[text] = len(strings)
            strings.extend(struct.pack(">H", len(b)) + b)
        return str_off[text]

    by_guid = []
    for key in sorted(by_key, key=_localecompare_key):
        off = len(guid)
        b = key.encode("utf-8")
        guid.extend(struct.pack(">H", len(b)) + b)
        by_guid.append(AceArray([off, put_str(by_key[key])]))
    by_res = [AceArray([float(r), float(put_str(by_id[r]))]) for r in sorted(by_id)]
    # the text index (StringFinder.GetResourceIdFromString) is sorted case-insensitively; verified on all sections
    by_utf = sorted(by_res, key=lambda e: _utf(bytes(strings), int(e[1])).lower())
    section["guid"], section["string"] = bytes(guid), bytes(strings)
    section["sortedByGuid"] = AceArray(by_guid)
    section["sortedByResourceId"] = AceArray(by_res)
    section["resourceIdSortedByUTF"] = AceArray([e[0] for e in by_utf])
    section["sortedByUTF"] = AceArray([int(e[1]) for e in by_utf])
    return section


# ----------------------------------------------------------------------------------------------- CLI
def to_json(v):
    if isinstance(v, AceDate):
        return {"$date": float(v)}
    if isinstance(v, (bytes, bytearray)):
        return {"$bytes": len(v)}
    if isinstance(v, AceVector):
        return {"$vector": v.type_name or v.kind, "items": [to_json(x) for x in v]}
    if isinstance(v, dict):
        d = {k: to_json(x) for k, x in v.items()}
        if getattr(v, "alias", ""):
            d = {"$class": v.alias, **d}
        return d
    if isinstance(v, list):
        return [to_json(x) for x in v]
    if isinstance(v, tuple):
        return {"$xml": v[1]}
    return v


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "dump":
        text = json.dumps(to_json(read(sys.argv[2])), ensure_ascii=False, indent=1)
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(text, encoding="utf-8")
        else:
            print(text)
    elif cmd == "check":
        bad = 0
        files = sorted(Path(sys.argv[2]).rglob("*.ace"))
        for f in files:
            raw = zlib.decompress(f.read_bytes())
            e = Encoder()
            e.value(Decoder(raw).value())
            if bytes(e.out) != raw:
                bad += 1
                print("DIFF", f, len(raw), len(e.out))
        print(f"{len(files) - bad}/{len(files)} files round-trip byte-identical")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
