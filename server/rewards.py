"""
Card rewards the server hands out (notes 6.52): Arena weekly rewards and the God card tournament milestones.

Data: <content>/server/rewards.json from tools/content_mods.py revival_rewards: the original ARENA_REWARD bundle
sets (bundle_template.ace type 6) as tiers of cards, and the God card template ids. Without the file there are no
rewards (old content, tests without content).

Delivery: each player has an inbox of pending rewards (player data "rewards"). The game asks
GET /fb/graph/me/revival_rewards from the main menu (as3_new/com/revival/rewards/RewardInbox.as), shows each
reward, adds the cards to the inventory, saves, then confirms with POST {consume: id}; only then is it removed.

Our rules (the original server's are unknown):
  Arena: the week before the current one (arena.week_index) is paid once, on the first inbox check after it ended.
    Week W pays set W mod len(sets). Ranking by weekly Arena score (> 0): rank 1, 2, 3 get tiers 1-3, ranks 4-10
    tier 4, ranks 11-25 tier 5 (the original sets have 5 tiers of 3/3/3/2/1 cards). A set with a single tier: ranks
    1-10. Empty tiers (cards without art) give nothing.
  God cards: Obelisk the Tormentor the first time a player reaches tournament rank 10, The Winged Dragon of Ra the
    first time they reach rank 5 (teams.LEVELS ranks; Elite counts as rank 0).
"""

import json
import threading
import time
from pathlib import Path

from arena import week_index

STATE_FILE = "rewards_state.json"
GOD_MILESTONES = (("obelisk", 10, "You reached rank 10 in the tournament for the first time."),
                  ("ra", 5, "You reached rank 5 in the tournament for the first time."))


def arena_tier(sets_tiers, rank):
    """Index of the tier for an arena rank, or None."""
    if len(sets_tiers) == 1:
        return 0 if rank <= 10 else None
    if rank <= 3:
        return min(rank - 1, len(sets_tiers) - 1)
    if rank <= 10:
        return min(3, len(sets_tiers) - 1)
    if rank <= 25:
        return min(4, len(sets_tiers) - 1)
    return None


class Rewards:
    def __init__(self, store, content_dir, logger):
        self.store = store
        self.log = logger
        self.lock = threading.Lock()
        self.data = {"arena_sets": [], "god_cards": {}}
        path = Path(content_dir or "") / "server" / "rewards.json"
        if content_dir and path.is_file():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                self.log.warning("rewards.json unreadable, no rewards: %s", e)

    # ---- inbox ---------------------------------------------------------------------------------
    def _inbox(self, uid):
        return self.store.get_player_data(uid, "rewards") or {"pending": [], "next": 1, "milestones": []}

    def grant(self, uid, cards, title, text):
        cards = [int(c) for c in cards if c]
        if not cards:
            return
        with self.lock:
            box = self._inbox(uid)
            box["pending"].append({"id": box["next"], "cards": cards, "title": title, "text": text,
                                   "time": int(time.time())})
            box["next"] += 1
            self.store.set_player_data(uid, "rewards", box)
        self.log.info("reward for %s: %s (%s)", uid, cards, title)

    def pending(self, uid):
        self.settle_arena()
        return list(self._inbox(uid)["pending"])

    def consume(self, uid, reward_id):
        with self.lock:
            box = self._inbox(uid)
            before = len(box["pending"])
            box["pending"] = [r for r in box["pending"] if r["id"] != int(reward_id)]
            if len(box["pending"]) != before:
                self.store.set_player_data(uid, "rewards", box)
                return True
        return False

    # ---- arena weekly -------------------------------------------------------------------------
    def settle_arena(self, now=None):
        sets = self.data.get("arena_sets") or []
        if not sets:
            return
        week = week_index(now) - 1
        with self.lock:
            state = self.store._load(STATE_FILE, {})
            if state.get("arena_week", -1) >= week:
                return
            state["arena_week"] = week
            self.store._store(STATE_FILE, state)
        rows = []
        for user in self.store.all_users():
            st = self.store.get_player_data(user["uid"], "arena") or {}
            for rec in (st.get("weekly"), st.get("last_weekly")):
                if rec and rec.get("week") == week and rec.get("score", 0) > 0:
                    rows.append((-rec["score"], user["uid"]))
                    break
        rows.sort()
        tiers = sets[week % len(sets)]["tiers"]
        for rank, (_, uid) in enumerate(rows, 1):
            t = arena_tier(tiers, rank)
            if t is not None and tiers[t]:
                self.grant(uid, tiers[t], "ARENA REWARD",
                           f"Last week you finished the Arena at rank {rank}. Your reward:")
        self.log.info("arena week %d settled: %d ranked players, set %d", week, len(rows), week % len(sets))

    # ---- tournament milestones ----------------------------------------------------------------------
    def on_tournament_rank(self, uid, rank):
        gods = self.data.get("god_cards") or {}
        for key, needed, text in GOD_MILESTONES:
            if key not in gods or rank > needed:
                continue
            with self.lock:
                box = self._inbox(uid)
                if key in box["milestones"]:
                    continue
                box["milestones"].append(key)
                self.store.set_player_data(uid, "rewards", box)
            self.grant(uid, [gods[key]], "TOURNAMENT MILESTONE", text)
