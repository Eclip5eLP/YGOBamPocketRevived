#!/usr/bin/env python3
"""
Phase 3 arena flow against a running (dev) server, two fresh accounts A and B:
B sets an arena deck -> A's GetDuelArena returns 5 duels, B among them with B's deck, the rest bots with
Graph names -> Start/Complete: win scores 50 x stage multiplier and raises the bonus, a loss resets it ->
B's registry counts its deck's AI result -> unknown opponent gives exception code -1 -> PayDuelArena
gives a fresh set -> leaderboards list A.

Usage: python tests/test_arena.py [--base http://127.0.0.1:8087]
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_friends import Player  # noqa: E402
from test_login_flow import P  # noqa: E402

A = P + "arena.amf."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    base = ap.parse_args().base
    a, b = Player(base), Player(base)
    print("A", a.name, a.uid, "| B", b.name, b.uid)

    assert b.amf(A + "SetDuelArenaDeckRequest", {"cardsTemplateId": [11, 12, 13]})["exception"] is None
    r = a.amf(A + "GetDuelArenaRequest", {"cardTemplatesId": [1, 2, 3, 4]})
    assert r["exception"] is None, r
    m, reg = r["matches"], r["playerRegistry"]
    duels = m["duels"]
    assert len(duels) == 5 and m["bonusTypeId"] == 0 and m["nextResetCost"] > 0, m
    assert reg["score"] == 0 and reg["cardTemplatesId"] == [1, 2, 3, 4], reg
    by_id = {str(int(d["externalId"])): d for d in duels}
    assert b.uid in by_id and by_id[b.uid]["cardTemplatesId"] == [11, 12, 13], by_id.get(b.uid)
    assert all(d["matchResultId"] == 1 and d["cardTemplatesId"] for d in duels)
    print("GetDuelArena OK:", [(d["firstName"], len(d["cardTemplatesId"])) for d in duels])

    bot = next(i for i in by_id if i != b.uid)
    name = json.loads(urllib.request.urlopen(base + "/fb/graph/v2.0/" + bot + "?fields=first_name,last_name&").read())
    assert name["first_name"] == by_id[bot]["firstName"], name
    print("bot Graph name OK:", name["first_name"])

    order = [b.uid] + [i for i in by_id if i != b.uid]
    expected_scores = []
    for opp, result in zip(order, [3, 3, 4, 3]):
        assert a.amf(A + "StartDuelArenaRequest", {"opponentExternalId": float(opp)})["exception"] is None
        r = a.amf(A + "CompleteDuelArenaRequest", {"opponentExternalId": float(opp), "matchResultId": result})
        assert r["exception"] is None, r
        d = next(x for x in r["matches"]["duels"] if str(int(x["externalId"])) == opp)
        expected_scores.append(d["matchScore"])
        assert d["matchResultId"] == result
    assert expected_scores == [50, 100, 0, 50], expected_scores
    assert r["matches"]["bonusTypeId"] == 1 and r["playerRegistry"]["score"] == 200, r
    assert (r["playerRegistry"]["victories"], r["playerRegistry"]["defeat"]) == (3, 1)
    print("scores/bonus OK:", expected_scores)

    again = a.amf(A + "CompleteDuelArenaRequest", {"opponentExternalId": float(b.uid), "matchResultId": 3})
    assert again["playerRegistry"]["score"] == 200, "completing twice must not score twice"
    rb = b.amf(A + "GetDuelArenaRequest", {"cardTemplatesId": [11, 12, 13]})["playerRegistry"]
    assert rb["aiDefeat"] == 1 and rb["aiVictories"] == 0, rb
    print("idempotent completion + B's deck stats OK")

    bad = a.amf(A + "CompleteDuelArenaRequest", {"opponentExternalId": 12345.0, "matchResultId": 3})
    assert bad["exception"] is not None and bad["exception"]["code"] == -1, bad
    print("unknown opponent -> code", bad["exception"]["code"])

    hs = a.amf(P + "leaderboardygo.amf.GetHighScoresRequest", {"friendExternalIds": []})
    assert hs["exception"] is None and hs["playerHighScoreWeekly"]["score"] == 200, hs
    assert any(e["externalId"] == float(a.uid) for e in hs["highScoreWeekly"])
    assert [e["externalId"] for e in hs["highScoreFriendAllTime"]] == [float(a.uid)]
    print("leaderboards OK, weekly rank", 1 + [e["externalId"] for e in hs["highScoreWeekly"]].index(float(a.uid)))

    paid = a.amf(A + "PayDuelArenaRequest")
    assert paid["exception"] is None and all(d["matchResultId"] == 1 for d in paid["matches"]["duels"]), paid
    assert paid["matches"]["bonusTypeId"] == 1
    print("PayDuelArena OK (fresh set, bonus kept)")
    print("ALL OK")


if __name__ == "__main__":
    main()
