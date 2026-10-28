#!/usr/bin/env python3
"""
Same-length bytecode patches for MobileGame.swf (AS3 / ABC), no re-serialisation.

Each patch names one method body (by its ABC debug name suffix), an instruction
byte sequence built from the constant pool, a replacement of identical length and
the exact number of occurrences expected in that body. Anything unexpected aborts.
Because lengths never change, branch offsets, exception tables and tag sizes stay
valid. Verify the result with FFDec (P-code export + diff), see notes/findings.md.

Patches (game logic references are to work/as3 decompiled sources):
  login-free purchases
    BamProPopup.PurchaseBamPro            (BamProPopup.as:177-197)
    CurrencyPopup.OnPurchaseProduct       (CurrencyPopup.as:212-235)
    BamProHandlerImpl.GateBamPro          (BamProHandlerImpl.as:62-78)
      callproperty IYGOMLogin::IsLogguedIn,0  ->  pop; pushtrue; nop...
      (stack effect identical: YGOMLogin object in, Boolean out)
  no server save-date check before a currency purchase
    AppPurchaseHandlerImpl.PurchaseProduct (AppPurchaseHandlerImpl.as:~205-230)
      getproperty BAM_PRO (the one followed by ifne)  ->  pop; dup; nop...
      so `aProduct == BAM_PRO` is always true and every product takes the direct
      mStoreHandler.BuyProduct(aProduct.PurchaseId) path. Offline the save-date
      check never answers (PlayerManagerGT.as:71-124: no Facebook user -> no request,
      5 s timeout dispatches nothing), so currency purchases would hang otherwise.
  load store product details at startup (prices show "Free", first shop tap buys)
    MobileProjectEngine.LoadAppPurchaseData (MobileProjectEngine.as:769-781)
      callproperty IYGOMLogin::IsConnected,0  ->  pop; pushtrue; nop...

Then FFDec P-code method replacements (length may change; FFDec reassembles and adds
constant-pool entries; an unchanged round trip was verified byte-identical):
  AppPurchaseHandlerImpl.OnPurchaseComplete: after the success branch dispatches
  PURCHASE_COMPLETED, PopupManagerUtil.ShowInfo("Success", "Purchase complete.")
  (generated at build time from the SWF, see PCODE_INSERTIONS).

Usage: python tools/patch_swf.py <in.swf> <out.swf> [--fb-base http://ygo.eclip5e.com/fb]
"""

import struct
import subprocess
import sys
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FFDEC_JAR = PROJECT_ROOT / "tools" / "ffdec" / "ffdec-cli.jar"
# (class, pcode file, method body index inside that class's DoABC2 tag; computed with parse_abc,
#  bodies ordered by position)
# Each entry: class, method debug name, method body index in the class's DoABC2 tag, the anchor lines
# (consecutive, whitespace-stripped) after which to insert, and the instructions to insert.
# The method's P-code is exported from the SWF at build time with FFDec, so no game code is stored here.
PCODE_INSERTIONS = [
    ("com.frimastudio.mobile.apppurchase.AppPurchaseHandlerImpl",
     "com.frimastudio.mobile.apppurchase:AppPurchaseHandlerImpl/private:OnPurchaseComplete", 10,
     ['getproperty QName(PackageNamespace(""),"PURCHASE_COMPLETED")',
      'callproperty QName(PrivateNamespace("com.frimastudio.mobile.apppurchase:AppPurchaseHandlerImpl"),'
      '"DispatchAppPurchaseHandlerEvent"), 1',
      'pop'],
     ['findpropstrict QName(PackageNamespace("com.frimastudio.snowstorm.project.popup"),"PopupManagerUtil")',
      'getproperty QName(PackageNamespace("com.frimastudio.snowstorm.project.popup"),"PopupManagerUtil")',
      'pushstring "Success"',
      'pushstring "Purchase complete."',
      'callproperty QName(PackageNamespace(""),"ShowInfo"), 2',
      'pop']),
]


def build_pcode_replacement(swf_path, cls, method_name, anchor, insert, workdir):
    """Exports cls as P-code with FFDec, cuts out the method block and inserts the instructions
    after the (unique) anchor sequence. Returns the path of the edited method P-code."""
    import shutil
    import tempfile
    out = Path(tempfile.mkdtemp(prefix="pcode_", dir=workdir))
    res = subprocess.run(["java", "-jar", str(FFDEC_JAR), "-format", "script:pcode", "-selectclass", cls,
                          "-export", "script", str(out), str(swf_path)], capture_output=True, text=True)
    files = list(out.rglob("*.pcode"))
    if len(files) != 1:
        sys.exit(f"FFDec export of {cls} failed: {res.stdout[-300:]} {res.stderr[-300:]}")
    lines = [ln.strip() for ln in files[0].read_text(encoding="utf-8").splitlines()]
    shutil.rmtree(out, ignore_errors=True)
    start = lines.index(f'name "{method_name}"') - 1
    end = next(i for i in range(start, len(lines)) if lines[i] == "end ; method")
    block = lines[start:end + 1]
    hits = [i for i in range(len(block) - len(anchor) + 1) if block[i:i + len(anchor)] == anchor]
    if len(hits) != 1 or block[start - start] != "method":
        sys.exit(f"{method_name}: anchor found {len(hits)}x")
    at = hits[0] + len(anchor)
    edited = block[:at] + insert + block[at:]
    path = Path(workdir) / (method_name.rsplit(":", 1)[-1] + ".pcode")
    path.write_text("\n".join(edited) + "\n", encoding="utf-8")
    return path

# AVM2 opcodes used in replacements
OP_NOP, OP_PUSHTRUE, OP_POP, OP_DUP = 0x02, 0x26, 0x29, 0x2A
OP_GETPROPERTY, OP_CALLPROPERTY, OP_IFNE = 0x66, 0x46, 0x14


class Reader:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def u30(self):
        result, shift = 0, 0
        for _ in range(5):
            b = self.u8()
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
        return result

    def skip(self, n):
        self.p += n


def u30_bytes(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def parse_abc(abc):
    """Returns (strings, namespaces, multinames, method_names, bodies) where
    bodies maps method index -> (code_offset, code_length) inside `abc`."""
    r = Reader(abc)
    r.u16(); r.u16()  # minor, major
    n = r.u30()
    for _ in range(max(n - 1, 0)):
        r.u30()  # int
    n = r.u30()
    for _ in range(max(n - 1, 0)):
        r.u30()  # uint
    n = r.u30()
    r.skip(8 * max(n - 1, 0))  # double
    strings = [None]
    string_spans = [None]  # (start of u30 length, end of bytes) per string index
    for _ in range(max(r.u30() - 1, 0)):
        span_start = r.p
        ln = r.u30()
        strings.append(abc[r.p:r.p + ln].decode("utf-8", errors="replace"))
        r.skip(ln)
        string_spans.append((span_start, r.p))
    namespaces = [None]
    for _ in range(max(r.u30() - 1, 0)):
        kind = r.u8()
        namespaces.append((kind, r.u30()))
    for _ in range(max(r.u30() - 1, 0)):  # ns sets
        for _ in range(r.u30()):
            r.u30()
    multinames = [None]
    for _ in range(max(r.u30() - 1, 0)):
        kind = r.u8()
        if kind in (0x07, 0x0D):
            multinames.append(("QName", r.u30(), r.u30()))
        elif kind in (0x0F, 0x10):
            multinames.append(("RTQName", r.u30()))
        elif kind in (0x11, 0x12):
            multinames.append(("RTQNameL",))
        elif kind in (0x09, 0x0E):
            multinames.append(("Multiname", r.u30(), r.u30()))
        elif kind in (0x1B, 0x1C):
            multinames.append(("MultinameL", r.u30()))
        elif kind == 0x1D:
            qn = r.u30()
            params = [r.u30() for _ in range(r.u30())]
            multinames.append(("TypeName", qn, params))
        else:
            raise ValueError(f"unknown multiname kind 0x{kind:02x} at {r.p}")
    method_names = []
    for _ in range(r.u30()):
        pc = r.u30()
        r.u30()  # return type
        for _ in range(pc):
            r.u30()
        method_names.append(r.u30())
        flags = r.u8()
        if flags & 0x08:
            for _ in range(r.u30()):
                r.u30(); r.u8()
        if flags & 0x80:
            for _ in range(pc):
                r.u30()
    for _ in range(r.u30()):  # metadata
        r.u30()
        for _ in range(r.u30()):
            r.u30(); r.u30()

    def traits():
        for _ in range(r.u30()):
            r.u30()
            kind = r.u8()
            k = kind & 0x0F
            if k in (0, 6):
                r.u30(); r.u30()
                if r.u30():
                    r.u8()
            elif k in (1, 2, 3, 4, 5):
                r.u30(); r.u30()
            else:
                raise ValueError(f"unknown trait kind {k}")
            if kind & 0x40:
                for _ in range(r.u30()):
                    r.u30()

    class_count = r.u30()
    for _ in range(class_count):  # instance_info
        r.u30(); r.u30()
        flags = r.u8()
        if flags & 0x08:
            r.u30()
        for _ in range(r.u30()):
            r.u30()
        r.u30()
        traits()
    for _ in range(class_count):  # class_info
        r.u30()
        traits()
    for _ in range(r.u30()):  # script_info
        r.u30()
        traits()
    bodies = {}
    for _ in range(r.u30()):
        method = r.u30()
        r.u30(); r.u30(); r.u30(); r.u30()
        code_len = r.u30()
        bodies[method] = (r.p, code_len)
        r.skip(code_len)
        for _ in range(r.u30()):
            for _ in range(5):
                r.u30()
        traits()
    if r.p != len(abc):
        raise ValueError(f"ABC parse ended at {r.p}, size {len(abc)}")
    parse_abc.string_spans = string_spans
    return strings, namespaces, multinames, method_names, bodies


def find_qname(strings, namespaces, multinames, ns_name, name):
    hits = [i for i, m in enumerate(multinames)
            if m and m[0] == "QName" and strings[m[2]] == name
            and namespaces[m[1]] and strings[namespaces[m[1]][1]] == ns_name]
    if len(hits) != 1:
        raise ValueError(f"QName {ns_name}::{name}: {len(hits)} matches")
    return hits[0]


# (method debug-name suffix, pattern builder, expected count in that body)
PATCHES = [
    (":BamProPopup/private:PurchaseBamPro", "login_true", 2),
    (":CurrencyPopup/private:OnPurchaseProduct", "login_true", 2),
    (":BamProHandlerImpl/GateBamPro", "login_true", 1),
    (":AppPurchaseHandlerImpl/PurchaseProduct", "always_bam_pro_path", 1),
    (":MobileProjectEngine/private:LoadAppPurchaseData", "connected_true", 1),
]


def build_pattern(kind, strings, namespaces, multinames):
    if kind == "login_true":
        mn = find_qname(strings, namespaces, multinames,
                        "com.frimastudio.snowstorm.project.login:IYGOMLogin", "IsLogguedIn")
        old = bytes([OP_CALLPROPERTY]) + u30_bytes(mn) + u30_bytes(0)
        new = bytes([OP_POP, OP_PUSHTRUE]) + bytes([OP_NOP] * (len(old) - 2))
    elif kind == "connected_true":
        mn = find_qname(strings, namespaces, multinames,
                        "com.frimastudio.snowstorm.project.login:IYGOMLogin", "IsConnected")
        old = bytes([OP_CALLPROPERTY]) + u30_bytes(mn) + u30_bytes(0)
        new = bytes([OP_POP, OP_PUSHTRUE]) + bytes([OP_NOP] * (len(old) - 2))
    elif kind == "always_bam_pro_path":
        mn = find_qname(strings, namespaces, multinames, "", "BAM_PRO")
        old = bytes([OP_GETPROPERTY]) + u30_bytes(mn) + bytes([OP_IFNE])
        new = bytes([OP_POP, OP_DUP]) + bytes([OP_NOP] * (len(old) - 3)) + bytes([OP_IFNE])
    else:
        raise ValueError(kind)
    return old, new


def string_patches(fb_base):
    """Constant-pool string replacements per DoABC2 tag (lengths may change).
    Repoints the Facebook SDK / login to the revival server's fake Facebook under fb_base:
      FacebookURLDefaults statics (com/facebook/graph/core/FacebookURLDefaults.as): GRAPH_URL
        (AbstractFacebook.as:69 api, :237 picture), API_URL (:199 REST/FQL), OAuth URLs
      FacebookManagerMobile.Authorize (FacebookManagerMobile.as:395-412): the OAuth dialog that
        mobile login opens in the external browser, redirect_uri fb<appId>://authorize
      FacebookMobile.logout (FacebookMobile.as:320)"""
    return {
        "com/facebook/graph/core/FacebookURLDefaults": [
            ("https://graph.facebook.com", f"{fb_base}/graph"),
            ("https://api.facebook.com", f"{fb_base}/api"),
            ("https://graph.facebook.com/oauth/authorize", f"{fb_base}/oauth/authorize"),
            ("https://graph-video.facebook.com", f"{fb_base}/video"),
            ("http://www.facebook.com/connect/login_success.html", f"{fb_base}/connect/login_success.html"),
            ("https://www.facebook.com/connect/login_success.html", f"{fb_base}/connect/login_success.html"),
            ("http://www.facebook.com/connect/login_success.html?error_reason",
             f"{fb_base}/connect/login_success.html?error_reason"),
            ("https://www.facebook.com/connect/login_success.html?error_reason",
             f"{fb_base}/connect/login_success.html?error_reason"),
            ("https://login.facebook.com/login.php", f"{fb_base}/login.php"),
            ("https://graph.facebook.com/oauth/authorize_cancel", f"{fb_base}/oauth/authorize_cancel"),
        ],
        "com/frimastudio/snowstorm/project/facebook/FacebookManagerMobile": [
            ("https://m.facebook.com/v2.0/dialog/oauth", f"{fb_base}/dialog/oauth"),
        ],
        "com/frimastudio/snowstorm/project/facebook/FacebookMobile": [
            ("https://m.facebook.com/logout.php", f"{fb_base}/logout.php"),
        ],
    }


def replace_strings(abc, replacements):
    strings, *_ = parse_abc(bytes(abc))
    spans = parse_abc.string_spans
    edits = []
    for old, new in replacements:
        hits = [i for i, x in enumerate(strings) if x == old]
        if len(hits) != 1:
            raise ValueError(f"string {old!r}: {len(hits)} pool entries")
        a, b = spans[hits[0]]
        enc = new.encode("utf-8")
        edits.append((a, b, u30_bytes(len(enc)) + enc, f"{old} -> {new}"))
    for a, b, new_bytes, _ in sorted(edits, reverse=True):
        abc[a:b] = new_bytes
    return [e[3] for e in edits]


def patch_abc(abc, tag_name="", str_patches=None):
    """Applies every PATCHES entry whose method lives in this ABC tag (the game SWF has
    one DoABC2 tag per class, each with its own constant pool), then this tag's string patches."""
    abc = bytearray(abc)
    strings, namespaces, multinames, method_names, bodies = parse_abc(bytes(abc))
    applied = []
    for suffix, kind, expected in PATCHES:
        methods = [i for i, s in enumerate(method_names) if strings[s] and strings[s].endswith(suffix)]
        if not methods:
            continue
        if len(methods) != 1:
            raise ValueError(f"{suffix}: {len(methods)} methods match")
        old, new = build_pattern(kind, strings, namespaces, multinames)
        assert len(old) == len(new)
        off, length = bodies[methods[0]]
        code = bytes(abc[off:off + length])
        count = code.count(old)
        if count != expected:
            raise ValueError(f"{suffix}: pattern {old.hex()} found {count}x, expected {expected}")
        abc[off:off + length] = code.replace(old, new)
        applied.append(f"{strings[method_names[methods[0]]]}: {old.hex()} -> {new.hex()} x{count}")
    if str_patches and tag_name in str_patches:
        applied.append((tag_name, replace_strings(abc, str_patches[tag_name])))
    return bytes(abc), applied


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--fb-base", default="http://ygo.eclip5e.com/fb",
                    help="fake Facebook base URL on the revival server")
    args = ap.parse_args()
    src, dst = args.src, args.dst
    str_patches = string_patches(args.fb_base.rstrip("/"))
    data = open(src, "rb").read()
    sig = data[:3]
    if sig == b"CWS":
        body = zlib.decompress(data[8:])
    elif sig == b"FWS":
        body = data[8:]
    else:
        sys.exit(f"unsupported SWF signature {sig!r}")

    # skip RECT, frame rate, frame count; then copy tags, rebuilding headers of changed ABC tags
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4
    out_body = bytearray(body[:pos])
    abc_tags = 0
    all_applied = []
    while pos < len(body):
        code_len = struct.unpack_from("<H", body, pos)[0]
        code, ln = code_len >> 6, code_len & 0x3F
        hdr = 2
        if ln == 0x3F:
            ln = struct.unpack_from("<I", body, pos + 2)[0]
            hdr = 6
        start = pos + hdr
        content = body[start:start + ln]
        if code in (72, 82):
            abc_off = 0
            tag_name = ""
            if code == 82:
                name_end = content.index(0, 4)
                tag_name = content[4:name_end].decode("utf-8", errors="replace")
                abc_off = name_end + 1
            new_abc, applied = patch_abc(content[abc_off:], tag_name, str_patches)
            content = content[:abc_off] + new_abc
            abc_tags += 1
            all_applied += applied
        if hdr == 6 or len(content) >= 0x3F:
            out_body += struct.pack("<HI", (code << 6) | 0x3F, len(content))
        else:
            out_body += struct.pack("<H", (code << 6) | len(content))
        out_body += content
        if code == 0:
            break
        pos = start + ln
    body = out_body

    byte_patches = [a for a in all_applied if isinstance(a, str)]
    str_applied = [a for a in all_applied if not isinstance(a, str)]
    if len(byte_patches) != len(PATCHES):
        sys.exit(f"expected {len(PATCHES)} byte patches, applied {len(byte_patches)}: {byte_patches}")
    if {t for t, _ in str_applied} != set(str_patches):
        sys.exit(f"string patches missing: {set(str_patches) - {t for t, _ in str_applied}}")
    all_applied = byte_patches + [f"{t}: {x}" for t, xs in str_applied for x in xs]
    out = (b"CWS" + data[3:4] + struct.pack("<I", len(body) + 8) + zlib.compress(bytes(body), 9))         if sig == b"CWS" else (b"FWS" + data[3:4] + struct.pack("<I", len(body) + 8) + bytes(body))
    stage1 = dst + ".bytepatched.swf"
    open(stage1, "wb").write(out)
    print(f"ABC tags: {abc_tags}")
    for a in all_applied:
        print("patched", a)

    cmd = ["java", "-jar", str(FFDEC_JAR), "-replace", stage1, dst]
    workdir = Path(dst).parent
    for cls, method_name, body_index, anchor, insert in PCODE_INSERTIONS:
        pcode = build_pcode_replacement(stage1, cls, method_name, anchor, insert, workdir)
        print(f"pcode insertion: {method_name} (+{len(insert)} instructions)")
        cmd += [cls, str(pcode), str(body_index)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("ffdec:", res.stdout.strip()[-300:], res.stderr.strip()[-300:])
    if res.returncode != 0 or not Path(dst).exists():
        sys.exit("FFDec P-code replacement failed")
    print(f"wrote {dst} ({Path(dst).stat().st_size} bytes)")


if __name__ == "__main__":
    main()
