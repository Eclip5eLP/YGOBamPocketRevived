#!/usr/bin/env python3
"""
Friends manager page (server/friends_page.py) against a running (dev) server, fresh accounts A, B, C:
A finds B by search and adds B -> B sees A under Requests (badge) and accepts -> both are friends ->
C adds A, A declines -> A removes B -> expired token page.

Usage: python tests/test_friends_page.py [--base http://127.0.0.1:8087]
"""

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_friends import Player  # noqa: E402

URL = "/fb/dialog/revival_friends"


def page(base, p, method="GET", **fields):
    data = {"access_token": p.token, "redirect_uri": "http://x/fb/connect/login_success.html", **fields}
    enc = urllib.parse.urlencode(data)
    if method == "POST":
        return urllib.request.urlopen(base + URL, data=enc.encode()).read().decode()
    return urllib.request.urlopen(base + URL + "?" + enc).read().decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    a, b, c = Player(base), Player(base), Player(base)

    found = page(base, a, tab="find", q=b.name[-4:])
    assert b.name in found and 'value="add"' in found, found[-800:]
    assert f"view={b.uid}" in found  # Profile link closes the view with the uid
    out = page(base, a, "POST", tab="find", action="add", uid=b.uid)
    assert f"Request sent to {b.name}" in out
    print("search + add OK")

    req = page(base, b, tab="requests")
    assert "Requests (1)" in req and a.name in req, req[-800:]
    out = page(base, b, "POST", tab="requests", action="add", uid=a.uid)
    assert f"You are now friends with {a.name}" in out
    assert b.name in page(base, a, tab="friends") and a.name in page(base, b, tab="friends")
    print("accept OK")

    page(base, c, "POST", tab="find", action="add", uid=a.uid)
    assert c.name in page(base, a, tab="requests")
    out = page(base, a, "POST", tab="requests", action="remove", uid=c.uid)
    assert f"{c.name} removed." in out and c.name not in out.split("</p>", 1)[1]
    print("decline OK")

    out = page(base, a, "POST", tab="friends", action="remove", uid=b.uid)
    assert "No friends yet" in out and a.name not in page(base, b, tab="friends").split("</div>", 1)[1]
    print("remove OK")

    listing = page(base, c, tab="find")
    assert a.name in listing and b.name in listing and "players" in listing  # all players without a filter
    filtered = page(base, c, tab="find", q=a.name)
    assert a.name in filtered and b.name not in filtered
    import json
    count = json.loads(urllib.request.urlopen(f"{base}/fb/graph/me/revival_requests?access_token={a.token}").read())
    assert count == {"incoming": 0, "challenges": 0}, count
    page(base, c, "POST", tab="find", action="add", uid=a.uid)
    count = json.loads(urllib.request.urlopen(f"{base}/fb/graph/me/revival_requests?access_token={a.token}").read())
    assert count == {"incoming": 1, "challenges": 0}, count
    print("list all + filter + request count OK")

    expired = urllib.request.urlopen(base + URL + "?access_token=bad").read().decode()
    assert "expired" in expired
    print("ALL FRIENDS PAGE TESTS PASSED")


if __name__ == "__main__":
    main()
