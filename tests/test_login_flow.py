#!/usr/bin/env python3
"""
End-to-end test of the phase-1 custom login against a running server:
fake Facebook register/login -> /fb/graph/me -> AMF GetToken -> RSA LoginRequest (encrypted like
the client: PKCS#1 v1.5 type 2 with server/data/publickey.xml) -> GetServerTime ->
SendPlayerSave -> GetPlayerSave -> GetLastSavedDate, using the session cookie.

Usage: python tests/test_login_flow.py [--base http://127.0.0.1:8087]
"""

import argparse
import http.cookiejar
import json
import re
import secrets
import struct
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
import amf3  # noqa: E402

C = "com.frimastudio.snowstorm.core."
P = "com.frimastudio.snowstorm.project."


def rsa_encrypt(msg: str) -> bytes:
    key = ET.fromstring((ROOT / "server" / "data" / "publickey.xml").read_text())
    n, e = int(key.find("Modulus").text, 16), int(key.find("Exponent").text, 16)
    k = (n.bit_length() + 7) // 8
    m = msg.encode()
    ps = bytes(b % 255 + 1 for b in secrets.token_bytes(k - 3 - len(m)))
    block = b"\x00\x02" + ps + b"\x00" + m
    return pow(int.from_bytes(block, "big"), e, n).to_bytes(k, "big")


def amf_request(opener, base, objects, ext_id=""):
    arr = bytearray([0x09]) + amf3.encode_u29((len(objects) << 1) | 1) + b"\x01"
    for alias, props in objects:
        arr += amf3.encode_typed_object(alias, props)
    eid = ext_id.encode()
    body = zlib.compress(struct.pack(">H", len(eid)) + eid + bytes(arr))
    req = urllib.request.Request(base + "/facebook/proxy.html", data=body,
                                 headers={"Content-Type": "binary/octet-stream"})
    raw = opener.open(req).read()
    assert struct.unpack(">i", raw[:4])[0] == 0
    return amf3.AMF3Decoder(zlib.decompress(raw[4:])).decode_value()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    user, pw = "test_" + secrets.token_hex(3), "secret123"
    redirect = "fb145583478967400://authorize"
    page = urllib.request.urlopen(base + "/fb/dialog/oauth?" + urllib.parse.urlencode(
        {"client_id": "145583478967400", "redirect_uri": redirect})).read().decode()
    assert "Create account" in page
    form = urllib.parse.urlencode({"username": user, "password": pw, "action": "register",
                                   "redirect_uri": redirect}).encode()
    done = urllib.request.urlopen(base + "/fb/dialog/oauth", data=form).read().decode()
    token = urllib.parse.unquote(re.search(r"access_token=([^&\"]+)", done).group(1))
    print("registered", user, "token", token[:8] + "...")
    bad = urllib.request.urlopen(base + "/fb/dialog/oauth", data=urllib.parse.urlencode(
        {"username": user, "password": "wrongpass", "action": "login"}).encode()).read().decode()
    assert "Wrong username or password" in bad

    me = json.loads(urllib.request.urlopen(base + "/fb/graph/me?access_token=" + urllib.parse.quote(token)).read())
    print("/me", me)
    uid = me["id"]

    r = amf_request(opener, base, [(C + "player.amf.GetTokenRequest", {})])[0]
    print("GetToken", r.class_alias, r["token"][:8], r["seed"], "cookie:", [c.name for c in jar])
    login = amf_request(opener, base, [(C + "player.amf.LoginRequest",
                                        {"compressed": True, "encrypted": False, "token": r["token"],
                                         "name": rsa_encrypt(uid), "password": rsa_encrypt(token)})])[0]
    print("Login", login.class_alias, dict(login))
    assert login["exception"] is None and login["playerId"] >= 1

    rs = amf_request(opener, base, [(C + "player.amf.GetServerTimeRequest", {}),
                                    (P + "player.amf.GetPlayerSaveRequest", {})])
    print("ServerTime", rs[0]["serverTime"], "| first GetPlayerSave:", rs[1]["playerSave"])
    assert rs[1]["playerSave"] is None

    save = zlib.compress(b"\x06" + amf3.encode_amf3_string('{"hello":"world"}'))
    r = amf_request(opener, base, [(P + "player.amf.SendPlayerSaveRequest", {"playerSave": save})])[0]
    assert r["exception"] is None, r
    rs = amf_request(opener, base, [(P + "player.amf.GetPlayerSaveRequest", {}),
                                    (P + "player.amf.GetLastSavedDateRequest", {})])
    assert bytes(rs[0]["playerSave"]) == save, rs[0]
    print("GetPlayerSave round trip OK; lastSavedDate", rs[1]["lastSavedDate"])

    bad_login = amf_request(opener, base, [(C + "player.amf.LoginRequest",
                                            {"token": r and "x", "name": rsa_encrypt(uid),
                                             "password": rsa_encrypt("forged")})])[0]
    assert bad_login["exception"] is not None
    print("forged token rejected:", bad_login["exception"]["message"])
    print("ALL OK")


if __name__ == "__main__":
    main()
