#!/usr/bin/env python3
"""
Live PvP relay (server/livepvp.py) against a running (dev) server, two fresh accounts A and B on the PvP path:
A queues (waits) -> B queues (matched: combat in the response) -> both receive StartDuelNotification with both
decks -> StartRound from both -> StartRoundNotification -> two rounds of BamReady (each gets the other's cards) and
BamEnd -> a checksum mismatch is reported -> new duel: surrender -> OpponentSurrenderedNotification ->
cancel queue. Notifications arrive on later requests (pings), as on the phones.

Usage: python tests/test_livepvp.py [--base http://127.0.0.1:8087]
"""

import argparse
import sys
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    a, b = Player(base), Player(base)
    deck_a, deck_b = [1460] * 3 + [1459] * 12, [91] * 3 + [93] * 12

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
        pvp(a, L + "BamEndRequest", {"checksum": checksum + 5, "externalIdWinner": 0})
        _, notes_b = pvp(b, L + "BamEndRequest", {"checksum": checksum + 5, "externalIdWinner": 0})
        assert names(notes_b) == ["BamEndNotification"] and names(poll(a)) == ["BamEndNotification"]
    print("2 rounds OK")

    ready(a, 3, 777, [])
    _, notes_b = ready(b, 3, 778, [])
    assert names(notes_b) == ["ChecksumErrorNotification"] and names(poll(a)) == ["ChecksumErrorNotification"]
    print("checksum mismatch OK")

    queue(a, deck_a)
    queue(b, deck_b)
    poll(a), poll(b)
    pvp(b, L + "BamReadyRequest", {"slotCard": [], "checksumBefore": 0, "roundNumber": 1, "forfeit": True})
    notes_a = poll(a)
    assert names(notes_a) == ["OpponentSurrenderedNotification"], names(notes_a)
    assert str(int(notes_a[0]["winnerExternalId"])) == a.uid
    print("surrender OK")

    resp, _ = queue(a, deck_a)
    assert resp["combat"] is None
    pvp(a, T + "CancelTournamentMatchRequest")
    resp, _ = queue(b, deck_b)
    assert resp["combat"] is None, "a cancelled player must not be matched"
    pvp(b, T + "CancelTournamentMatchRequest")
    print("cancel OK")
    print("ALL LIVE PVP TESTS PASSED")


if __name__ == "__main__":
    main()
