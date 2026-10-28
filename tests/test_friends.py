#!/usr/bin/env python3
"""
Phase 2 friends flow against a running (dev) server, two fresh accounts A and B:
A invites B via /fb/dialog/apprequests -> B's FQL list marks A as a pending request ->
B invites A -> both are friends (is_app_user true) -> GetRelationsProject lists the friend ->
B uploads a save -> A fetches B's deck with GetDeckByExternalId -> SetDuelArenaDeck overrides it.

Usage: python tests/test_friends.py [--base http://127.0.0.1:8087]
"""

import argparse
import http.cookiejar
import json
import re
import secrets
import sys
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))
import amf3  # noqa: E402
from test_login_flow import amf_request, rsa_encrypt, C, P  # noqa: E402

REDIRECT = "fb145583478967400://authorize"


class Player:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.name = "fr_" + secrets.token_hex(3)
        form = urllib.parse.urlencode({"username": self.name, "password": "secret123", "action": "register",
                                       "redirect_uri": REDIRECT}).encode()
        done = urllib.request.urlopen(base + "/fb/dialog/oauth", data=form).read().decode()
        self.token = urllib.parse.unquote(re.search(r"access_token=([^&\"]+)", done).group(1))
        self.uid = json.loads(urllib.request.urlopen(
            base + "/fb/graph/v2.0/me?access_token=" + urllib.parse.quote(self.token)).read())["id"]
        r = amf_request(self.opener, base, [(C + "player.amf.GetTokenRequest", {})])[0]
        login = amf_request(self.opener, base, [(C + "player.amf.LoginRequest",
                                                  {"token": r["token"], "name": rsa_encrypt(self.uid),
                                                   "password": rsa_encrypt(self.token)})])[0]
        assert login["exception"] is None
        self.player_id = login["playerId"]

    def fql(self):
        q = urllib.parse.urlencode({"query": "SELECT uid, name FROM user", "format": "json", "access_token": self.token})
        return json.loads(urllib.request.urlopen(self.base + "/fb/api/method/fql.query?" + q).read())

    def invite(self, *uids):
        q = urllib.parse.urlencode({"to": ",".join(uids), "access_token": self.token, "app_id": "145583478967400",
                                    "redirect_uri": "http://x/fb/connect/login_success.html"})
        return urllib.request.urlopen(self.base + "/fb/dialog/apprequests?" + q).read().decode()

    def amf(self, alias, props=None):
        return amf_request(self.opener, self.base, [(alias, props or {})])[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    a, b = Player(base), Player(base)
    print("A", a.name, a.uid, "| B", b.name, b.uid)

    page = a.invite(b.uid)
    assert "request sent" in page and "login_success.html?request=revival" in page, page
    row = next(r for r in b.fql() if r["uid"] == a.uid)
    assert row["is_app_user"] is False and row["name"].startswith("(!) "), row
    page = b.invite(a.uid)
    assert "you are now friends" in page, page
    for p, other in ((a, b), (b, a)):
        row = next(r for r in p.fql() if r["uid"] == other.uid)
        assert row["is_app_user"] is True and row["name"] == other.name, row
    print("friendship via invites OK")

    rels = a.amf(P + "relation.amf.GetRelationsProjectRequest")["relations"]
    assert [r["avatarName"] for r in rels] == [b.name], rels
    print("relations OK:", rels[0]["avatarName"], rels[0]["externalId"])

    items = [{"id": 1, "itemTemplateId": -1, "containerId": 0, "quantity": 1}] + \
            [{"id": 10 + i, "itemTemplateId": 1000 + i, "containerId": 1, "quantity": 3,
              "atkStat": 100 * i, "defStat": 0} for i in range(8)]
    save = zlib.compress(b"\x06" + amf3.encode_amf3_string(json.dumps({"items": items})))
    assert b.amf(P + "player.amf.SendPlayerSaveRequest", {"playerSave": save})["exception"] is None
    deck = a.amf(P + "arena.amf.GetDeckByExternalIdRequest", {"externalId": float(b.uid)})["deck"]
    ids = [int(x) for x in deck.split(",")]
    assert len(ids) == 15 and ids[:3] == [1007] * 3, ids
    print("deck from save OK:", deck)
    assert b.amf(P + "arena.amf.SetDuelArenaDeckRequest", {"cardsTemplateId": [5, 6, 7]})["exception"] is None
    assert a.amf(P + "arena.amf.GetDeckByExternalIdRequest", {"externalId": float(b.uid)})["deck"] == "5,6,7"
    print("arena deck override OK")
    r = a.amf(P + "worldmap.amf.CompleteDuelFriendRequest",
              {"friendAvatarId": b.player_id, "duelResult": True, "hasForfeited": False})
    assert r["exception"] is None and r["relationId"] == b.player_id and r["lastDuelDate"], r
    rels = a.amf(P + "relation.amf.GetRelationsProjectRequest")["relations"]
    assert rels[0]["lastDuelDate"], rels
    print("CompleteDuelFriend + lastDuelDate OK")
    print("ALL OK")


if __name__ == "__main__":
    main()
