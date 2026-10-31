#!/usr/bin/env python3
"""
Card rewards (server/rewards.py), offline against a scratch AccountStore (no server needed):
Arena week W is paid once, on the first inbox check after it ended, with set W mod len(sets): ranks 1-3 get
tiers 1-3, ranks 4-10 tier 4, 11-25 tier 5; a player with 0 points gets nothing; last week's score kept in
last_weekly counts. God cards: rank 10 -> Obelisk once, rank 5 -> Ra once. consume removes a reward once.
Also checks <content>/server/rewards.json from the content build when present.

Usage: python tests/test_rewards.py
"""

import json
import logging
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
import accounts  # noqa: E402
import arena  # noqa: E402
import rewards  # noqa: E402

SETS = {"arena_sets": [{"bundles": [1], "tiers": [[1, 2, 3], [1, 2, 3], [1, 2, 3], [1, 2], [2]]},
                       {"bundles": [9], "tiers": [[7]]}],
        "god_cards": {"obelisk": 1196, "ra": 1195}}


def main():
    log = logging.getLogger("t")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "content" / "server").mkdir(parents=True)
        (tmp / "content" / "server" / "rewards.json").write_text(json.dumps(SETS))
        store = accounts.AccountStore(tmp / "data")
        uids = [store.register(f"rw_{i}", "pw123456")["uid"] for i in range(13)]
        r = rewards.Rewards(store, tmp / "content", log)
        now = 1_800_000_000
        week = arena.week_index(now) - 1
        scores = [900, 800, 700, 600, 500, 400, 300, 200, 150, 120, 110, 100, 0]
        for i, (uid, sc) in enumerate(zip(uids, scores)):
            key = "weekly" if i % 2 else "last_weekly"  # both places count
            store.set_player_data(uid, "arena", {key: {"week": week, "score": sc},
                                                 **({"weekly": {"week": week + 1, "score": 5}} if key == "last_weekly" else {})})
        r.settle_arena(now)
        tiers = SETS["arena_sets"][week % 2]["tiers"]
        got = [[p["cards"] for p in r._inbox(uid)["pending"]] for uid in uids]
        if len(tiers) == 5:
            assert got[0] == [[1, 2, 3]] and got[2] == [[1, 2, 3]], got[:3]
            assert got[3] == [[1, 2]] and got[9] == [[1, 2]], got[3:10]
            assert got[10] == [[2]] and got[11] == [[2]], got[10:12]
        else:
            assert all(g == [[7]] for g in got[:10]) and got[10] == [], got
        assert got[12] == [], "0 points: no reward"
        r.settle_arena(now)
        assert [len(r._inbox(u)["pending"]) for u in uids] == [len(g) for g in got], "a week is paid once"
        print("arena week settled once, tiers by rank OK")

        u = uids[0]
        before = len(r._inbox(u)["pending"])
        r.on_tournament_rank(u, 12)
        assert len(r._inbox(u)["pending"]) == before
        r.on_tournament_rank(u, 10)
        r.on_tournament_rank(u, 9)
        r.on_tournament_rank(u, 5)
        r.on_tournament_rank(u, 0)
        cards = [p["cards"] for p in r._inbox(u)["pending"]][before:]
        assert cards == [[1196], [1195]], cards
        print("God card milestones once each OK")

        rid = r._inbox(u)["pending"][0]["id"]
        assert r.consume(u, rid) and not r.consume(u, rid)
        assert all(p["id"] != rid for p in r.pending(u))
        print("consume OK")

    built = ROOT / "work" / "content" / "server" / "rewards.json"
    if built.is_file():
        data = json.loads(built.read_text(encoding="utf-8"))
        assert data["arena_sets"] and data["god_cards"] == {"obelisk": 1196, "ra": 1195}
        assert all(t is not None for s in data["arena_sets"] for t in s["tiers"])
        print("built rewards.json OK:", len(data["arena_sets"]), "arena sets")
    print("ALL REWARDS TESTS PASSED")


if __name__ == "__main__":
    main()
