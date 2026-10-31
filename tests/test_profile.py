#!/usr/bin/env python3
"""
Profile API (server/profiles.py) against a running (dev) server, two fresh accounts A and B:
preset icon list and PNGs -> A picks an icon -> A's /picture serves it -> B reads A's public profile ->
rename (taken name refused, then OK; login with the new name works) -> password change (wrong old password
refused, then OK; old password no longer works) -> bad token and unknown actions refused.

Usage: python tests/test_profile.py [--base http://127.0.0.1:8087]
"""

import argparse
import json
import secrets
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_friends import Player, REDIRECT  # noqa: E402


def get(base, path):
    return urllib.request.urlopen(base + path).read()


def post_profile(base, token, **fields):
    form = urllib.parse.urlencode({"access_token": token, **fields}).encode()
    return json.loads(urllib.request.urlopen(base + "/fb/graph/me/revival_profile", data=form).read())


def can_login(base, name, password):
    form = urllib.parse.urlencode({"username": name, "password": password, "action": "login",
                                   "redirect_uri": REDIRECT}).encode()
    page = urllib.request.urlopen(base + "/fb/dialog/oauth", data=form).read().decode()
    return "access_token=" in page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    a, b = Player(base), Player(base)

    icons = json.loads(get(base, "/fb/graph/revival_icons"))
    assert len(icons) >= 10 and icons[0]["id"] == 0, icons
    png = get(base, "/fb/graph/revival_icons/3")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    default = get(base, f"/fb/graph/{a.uid}/picture")
    print("icons OK:", len(icons))

    assert post_profile(base, a.token, action="icon", icon="3") == {"ok": True}
    assert get(base, f"/fb/graph/{a.uid}/picture") == png != default
    assert "error" in post_profile(base, a.token, action="icon", icon="9999")
    print("icon OK")

    prof = json.loads(get(base, f"/fb/graph/{a.uid}/revival_profile"))
    assert prof["uid"] == a.uid and prof["name"] == a.name and prof["icon"] == 3, prof
    for key in ("league", "stars", "cards_unique", "cards_total", "deck", "deck_name"):
        assert key in prof, key
    print("public profile OK:", {k: prof[k] for k in ("league", "stars", "cards_unique", "deck_name")})

    assert post_profile(base, a.token, action="rename", name=b.name)["error"] == "This username is already taken"
    assert "error" in post_profile(base, a.token, action="rename", name="x")
    new_name = "rn_" + secrets.token_hex(3)
    assert post_profile(base, a.token, action="rename", name=new_name) == {"ok": True}
    assert json.loads(get(base, f"/fb/graph/{a.uid}/revival_profile"))["name"] == new_name
    assert can_login(base, new_name, "secret123") and not can_login(base, a.name, "secret123")
    print("rename OK")

    assert "error" in post_profile(base, a.token, action="password", old="wrong-pass", new="newsecret1")
    assert "error" in post_profile(base, a.token, action="password", old="secret123", new="123")
    assert post_profile(base, a.token, action="password", old="secret123", new="newsecret1") == {"ok": True}
    assert can_login(base, new_name, "newsecret1") and not can_login(base, new_name, "secret123")
    print("password OK")

    assert "error" in post_profile(base, "not-a-token", action="icon", icon="1")
    assert "error" in post_profile(base, a.token, action="delete_everything")
    print("ALL PROFILE TESTS PASSED")


if __name__ == "__main__":
    main()
