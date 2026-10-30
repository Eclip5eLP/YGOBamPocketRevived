#!/usr/bin/env python3
"""
Version gate against a running server with work/content (tools/build_content.py):
- every client gets GetVersionResponse with the minimum APK version (old APKs show their update popup);
- a client without ?v=&d= (the first public APK), an older APK and outdated game data are refused for
  everything else (login, save, ...); Ping stays answered;
- an up-to-date client logs in;
- the startup popup carries the update notice only for clients below the minimum version (by the version
  the client IP sent with its latest GetVersionRequest).

Usage: python tests/test_version_gate.py [--base http://127.0.0.1:8087]
"""

import argparse
import http.cookiejar
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_friends import Player  # noqa: E402
from test_login_flow import C, P, amf_request, client_query  # noqa: E402

VERSION = P + "player.amf.GetVersionRequest"
PING = C + "player.amf.PingRequest"
TOKEN = C + "player.amf.GetTokenRequest"
SAVE = P + "player.amf.GetLastSavedDateRequest"


def call(base, query, alias, props=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    return amf_request(opener, base, [(alias, props or {})], query=query)[0]


def refused(resp):
    exc = resp.get("exception")
    return exc is not None and "Update required" in str(exc.get("message", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    m = json.loads((ROOT / "work" / "content" / "manifest.json").read_text(encoding="utf-8"))
    apk, data = m["game_version"], m["packages"]["gamedata"]["version"]
    current = client_query()
    assert current == "?" + urllib.parse.urlencode({"v": apk, "d": data}), current

    for name, query in (("first public APK (no params)", ""), ("older APK", "?v=1.11.2&d=" + data),
                        ("outdated game data", "?v=" + apk + "&d=0.0.1")):
        v = call(base, query, VERSION)
        assert v["version"] == f"android={apk}~ios={apk}", v
        assert call(base, query, PING).get("exception") is None
        assert refused(call(base, query, TOKEN)), name
        assert refused(call(base, query, SAVE)), name
        print(f"{name}: version {v['version']}, ping answered, login/save refused")

    token = call(base, current, TOKEN)
    assert token.get("exception") is None and token["token"], token
    player = Player(base)  # full login + online request with the current client query
    assert player.amf(SAVE).get("exception") is None
    print("up-to-date client: token + login + save request OK (uid %s)" % player.uid)

    popup = lambda: urllib.request.urlopen(base + "/closepopupconfig.xml?time=1").read().decode("utf-8")  # noqa: E731
    call(base, "", VERSION)  # an old APK checks its version first, from this IP
    old_popup = popup()
    call(base, current, VERSION)  # then an up-to-date APK from the same IP
    new_popup = popup()
    assert "UPDATE AVAILABLE" in old_popup and "MISE" in old_popup, old_popup[:300]
    assert "UPDATE AVAILABLE" not in new_popup and "fan-run revival" in new_popup
    print("startup popup: update notice for old APKs only")
    print("ALL OK")


if __name__ == "__main__":
    main()
