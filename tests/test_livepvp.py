#!/usr/bin/env python3
"""
Live PvP relay (server/livepvp.py) against a running (dev) server, two fresh accounts A and B on the PvP path:
A queues (waits) -> B queues (matched: combat in the response) -> both receive StartDuelNotification with both
decks -> StartRound from both -> StartRoundNotification -> two rounds of BamReady (each gets the other's cards) and
BamEnd -> a checksum mismatch is reported -> new duel: surrender -> OpponentSurrenderedNotification ->
cancel queue. Ranking: both register for the tournament (level 81 = rank 15, 0 tokens); the win at the end of
round 2 moves A to level 2 and keeps B at 81 (floor), both get PlayCombatEndNotification with their new level; the
surrender moves A on to level 3; an out-of-sync duel changes nothing.
Friend challenge: C challenges friend D (POST /fb/graph/me/revival_challenge) and waits; a tournament player is not
paired with C; a stranger can't challenge; D sees the challenge (badge count, friends page) and accepts by
challenging back: C and D are paired; the duel is unranked (D's level stays 81 after winning). Notifications arrive on later requests (pings),
as on the phones.

Usage: python tests/test_livepvp.py [--base http://127.0.0.1:8087]
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_friends import Player  # noqa: E402
from test_login_flow import amf_request, C, P  # noqa: E402
import amf3  # noqa: E402

PVP = "/facebook/pvp/proxy.html"
L = P + "livepvp.amf."
T = P + "tournament.amf."


def card(tid):
    return amf3.AMF3Object(P + "inventory.amf.Card", itemTemplateId=tid, quantity=1, id=tid * 10)


def slot(n, tid):
    return amf3.AMF3Object("", slot=n, card=tid)


def pvp(player, alias, props=None):
    """Sends one request on the PvP path; returns (response, [notifications])."""
    out = amf_request(player.opener, player.base, [(alias, props or {})], path=PVP)
    return out[0], out[1:]


def poll(player):
    return pvp(player, C + "player.amf.PingRequest", {"gameframe": 0.0})[1]


def names(notes):
    return [n.class_alias.rsplit(".", 1)[1] for n in notes]


def queue(player, deck):
    return pvp(player, T + "PlayCombatTournamentRequest", {"cards": [card(c) for c in deck], "deckName": "d",
                                                          "deckDescription": "", "defaultDeck": True, "friendsNbr": 2})


def ready(player, round_number, checksum, cards):
    return pvp(player, L + "BamReadyRequest", {"slotCard": cards, "checksumBefore": checksum,
                                               "roundNumber": round_number, "forfeit": False})


def level_of(notes):
    end = [n for n in notes if n.class_alias.endswith("PlayCombatEndNotification")]
    assert len(end) == 1, names(notes)
    return int(end[0]["tournamentLevel"]["levelTemplateId"])


def start_duel(a, b, deck_a, deck_b):
    queue(a, deck_a)
    queue(b, deck_b)
    poll(a), poll(b)


def challenge(player, to):
    data = urllib.parse.urlencode({"access_token": player.token, "to": to}).encode()
    return json.loads(urllib.request.urlopen(player.base + "/fb/graph/me/revival_challenge", data=data).read())


def friends_page(player):
    q = urllib.parse.urlencode({"access_token": player.token, "redirect_uri": "http://x/fb/connect/login_success.html"})
    return urllib.request.urlopen(player.base + "/fb/dialog/revival_friends?" + q).read().decode()


def badge(player):
    q = urllib.parse.urlencode({"access_token": player.token})
    return json.loads(urllib.request.urlopen(player.base + "/fb/graph/me/revival_requests?" + q).read())


def test_challenge(base, a, deck_a, deck_b):
    c, d, e = Player(base), Player(base), Player(base)
    c.invite(d.uid)
    d.invite(c.uid)
    resp, _ = pvp(d, T + "RegisterTournamentRequest")
    assert "error" in challenge(e, d.uid), "strangers can't challenge"
    assert challenge(c, d.uid) == {"ok": True}
    resp, _ = queue(c, deck_a)
    assert resp["combat"] is None
    resp, _ = queue(a, deck_a)
    assert resp["combat"] is None, "a tournament player must not be paired with a challenger"
    pvp(a, T + "CancelTournamentMatchRequest")
    assert badge(d)["challenges"] == 1, badge(d)
    page = friends_page(d)
    assert "Waiting for a live duel" in page and "challenge=" + c.uid in page, page
    assert challenge(d, c.uid) == {"ok": True}
    resp, notes_d = queue(d, deck_b)
    assert resp["combat"] is not None, resp
    notes_c = poll(c)
    assert names(notes_c) == ["NewCombatNotification", "StartDuelNotification"], names(notes_c)
    assert {str(int(notes_d[0]["player1Id"])), str(int(notes_d[0]["player2Id"]))} == {c.uid, d.uid}
    assert badge(d)["challenges"] == 0
    pvp(c, L + "BamEndRequest", {"checksum": 9, "externalIdWinner": float(d.uid)})
    _, notes_d = pvp(d, L + "BamEndRequest", {"checksum": 9, "externalIdWinner": float(d.uid)})
    assert level_of(notes_d) == 81, "challenge duels don't count for the ladder"
    print("friend challenge OK (private pairing, unranked)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    a, b = Player(base), Player(base)
    deck_a, deck_b = [1460] * 3 + [1459] * 12, [91] * 3 + [93] * 12
    for p in (a, b):
        resp, _ = pvp(p, T + "RegisterTournamentRequest")
        assert int(resp["tournementLevel"]["levelTemplateId"]) == 81, resp

    resp, notes = queue(a, deck_a)
    assert resp["combat"] is None and notes == [], (resp, notes)
    resp, notes_b = queue(b, deck_b)
    assert resp["combat"] is not None, resp
    notes_a = poll(a)
    assert names(notes_a) == ["NewCombatNotification", "StartDuelNotification"], names(notes_a)
    assert names(notes_b) == ["StartDuelNotification"], names(notes_b)
    start = notes_a[1]
    assert dict(start) == dict(notes_b[0])
    players = {str(int(start["player1Id"])), str(int(start["player2Id"]))}
    assert players == {a.uid, b.uid}, players
    decks = {str(int(start["player1Id"])): list(start["player1Deck"]), str(int(start["player2Id"])): list(start["player2Deck"])}
    assert decks[a.uid] == deck_a and decks[b.uid] == deck_b
    print("matchmaking OK, starts:", int(start["player1Id"]))

    assert pvp(a, L + "StartRoundRequest")[1] == []
    _, notes_b = pvp(b, L + "StartRoundRequest")
    assert names(notes_b) == ["StartRoundNotification"] and names(poll(a)) == ["StartRoundNotification"]
    print("start round OK")

    for rnd, checksum in ((1, 0), (2, 1234)):
        assert ready(a, rnd, checksum, [slot(0, 1460)])[1] == []
        _, notes_b = ready(b, rnd, checksum, [slot(1, 91)])
        notes_a = poll(a)
        assert names(notes_b) == ["BamReadyNotification"] and names(notes_a) == ["BamReadyNotification"]
        assert notes_a[0]["slotCard"][0]["card"] == 91 and notes_b[0]["slotCard"][0]["card"] == 1460
        winner = float(a.uid) if rnd == 2 else 0
        pvp(a, L + "BamEndRequest", {"checksum": checksum + 5, "externalIdWinner": winner})
        _, notes_b = pvp(b, L + "BamEndRequest", {"checksum": checksum + 5, "externalIdWinner": winner})
        notes_a = poll(a)
        assert names(notes_b)[0] == "BamEndNotification" and names(notes_a)[0] == "BamEndNotification"
    assert level_of(notes_a) == 2 and level_of(notes_b) == 81, (level_of(notes_a), level_of(notes_b))
    print("2 rounds OK, A won: level 81 -> 2, B stays 81")

    start_duel(a, b, deck_a, deck_b)
    ready(a, 3, 777, [])
    _, notes_b = ready(b, 3, 778, [])
    assert names(notes_b) == ["ChecksumErrorNotification"] and names(poll(a)) == ["ChecksumErrorNotification"]
    print("checksum mismatch OK (no ranking)")

    start_duel(a, b, deck_a, deck_b)
    _, notes_b = pvp(b, L + "BamReadyRequest", {"slotCard": [], "checksumBefore": 0, "roundNumber": 1, "forfeit": True})
    notes_a = poll(a)
    assert names(notes_a) == ["OpponentSurrenderedNotification", "PlayCombatEndNotification"], names(notes_a)
    assert str(int(notes_a[0]["winnerExternalId"])) == a.uid
    assert level_of(notes_a) == 3 and level_of(notes_b) == 81, (level_of(notes_a), level_of(notes_b))
    resp, _ = pvp(a, T + "GetTournamentInfoRequest")
    assert int(resp["tournamentLevel"]["levelTemplateId"]) == 3, resp
    print("surrender OK, A level 3")

    resp, _ = queue(a, deck_a)
    assert resp["combat"] is None
    pvp(a, T + "CancelTournamentMatchRequest")
    resp, _ = queue(b, deck_b)
    assert resp["combat"] is None, "a cancelled player must not be matched"
    pvp(b, T + "CancelTournamentMatchRequest")
    print("cancel OK")
    test_challenge(base, a, deck_a, deck_b)
    print("ALL LIVE PVP TESTS PASSED")


if __name__ == "__main__":
    main()
