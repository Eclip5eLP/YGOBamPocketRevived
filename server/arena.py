"""
Arena (phase 3): asynchronous duels against other players' decks, played by the client's AI, plus the
arena leaderboards. The original server logic is unknown; the rules below are our own, shaped to what
the client reads.

Client references (work/as3):
  ArenaModule.InitQueue: LoseUnfinishedDuels -> SetDuelArenaDeck -> CompleteDuelArena (pending) ->
    GetDuelArena -> GetHighScores (module/arena/ArenaModule.as:224-238).
  ArenaManagerYGO (project/arena/ArenaManagerYGO.as):
    GetDuelArena{cardTemplatesId} -> {matches, playerRegistry}; both must be set (115-128).
    LoadOpponentName waits for one Graph name per duel and never finishes with 0 duels (351-372), so
      there are always NBR_DUELS duels.
    PayDuelArena: client checks INGAME currency >= nextResetCost and deducts it itself after the reply
      (130-154).
    StartDuelArena{opponentExternalId}: client marks the duel STARTED locally (171-192).
    CompleteDuelArena{opponentExternalId, matchResultId} -> {playerRegistry, matches}; points = new
      registry score - old (194-232). exception.code -1 = OPPONENT_INEXISTANT (EArenaError.as:6).
  ArenaModuleUI: 5 duel slots (NBR_DUELS, ui/ArenaModuleUI.as:44-46).
  DuelDisplay: matchScore / 50 must be a bonus multiplier 1,2,4,8,16 (ui/DuelDisplay.as:170-195).
  CompletedDuelBlocker: new duels at lastDateGenerated + 1 day; reset price = nextResetCost
    (ui/CompletedDuelBlocker.as:94-99, 180-200).
  MatchResultTypes PENDING 1, STARTED 2, VICTORY 3, DEFEAT 4; BonusTypes ids 0..5, multipliers
    1,2,4,8,16,16 (project/arena/enumeration/).
  StatisticsPopup: registry score / victories / defeat / aiVictories / aiDefeat (module/arena/popup).
  LeaderboardManagerYGO.GetHighScores{friendExternalIds} -> GetHighScoresResponse
    (project/leaderboardygo/LeaderboardManagerYGO.as:63-133); ScoreTypes.ARENA 1, LeaderboardTypes
    ALLTIME 1, WEEKLY 2, ALLTIME_FRIEND 3, WEEKLY_FRIEND 4.

Our rules:
  * 5 opponents per set: other registered players with a deck, friends first (random order); the rest are
    practice bots (BOTS, uid BOT_BASE+n, names served by fakefb Graph) playing a real player's deck
    or, with nobody else around, your own.
  * A new set when the old one is a day old (lastDateGenerated) or when paid for (RESET_COST coins).
  * Victory: matchScore = 50 x bonus multiplier, then the bonus stage goes up (max STAGE6); defeat
    resets it to STAGE1. Score counts for all-time and the current week (weeks as in the guild reset).
  * A real opponent's aiVictories/aiDefeat count how their deck did when others fought it.
"""

import random
import threading
import time

import amf3

P = "com.frimastudio.snowstorm.project."
NBR_DUELS = 5
BASE_SCORE = 50
MULTIPLIERS = [1, 2, 4, 8, 16, 16]
PENDING, STARTED, VICTORY, DEFEAT = 1, 2, 3, 4
RESET_COST = 100  # INGAME coins (CurrencyTypes.INGAME id 0); our choice
DAY = 24 * 3600
WEEK = 7 * DAY
BOT_BASE = 900_000_000
BOTS = ["Rookie Duelist", "Card Shark", "Deck Master", "Shadow Gambler", "Duel Academy Student",
        "Street Duelist", "Tournament Veteran", "Mystic Collector", "Trap Specialist", "Dragon Tamer",
        "Spellcaster Adept", "Graveyard Keeper"]
LEADERBOARD_SIZE = 50


def bot_name(uid):
    """Display name for a practice bot uid, or None if uid is not a bot."""
    try:
        n = int(uid) - BOT_BASE
    except (TypeError, ValueError):
        return None
    return BOTS[n] if 0 <= n < len(BOTS) else None


def week_index(now=None):
    return int(now or time.time()) // WEEK


class Arena:
    def __init__(self, store, deck_for, logger):
        self.store = store
        self.deck_for = deck_for  # uid -> "1,2,3" (Game.deck_for)
        self.log = logger
        self.lock = threading.Lock()

    # ---- state ---------------------------------------------------------------------------
    def _state(self, uid):
        st = self.store.get_player_data(uid, "arena") or {}
        st.setdefault("bonus", 0)
        st.setdefault("generated", 0)
        st.setdefault("duels", [])
        st.setdefault("reg", {"score": 0, "victories": 0, "defeat": 0, "aiVictories": 0, "aiDefeat": 0})
        st.setdefault("weekly", {"week": week_index(), "score": 0})
        if st["weekly"]["week"] != week_index():
            st["weekly"] = {"week": week_index(), "score": 0}
        return st

    def _save(self, uid, st):
        self.store.set_player_data(uid, "arena", st)

    @staticmethod
    def _deck_list(deck):
        return [int(c) for c in deck.split(",") if c.strip()] if deck else []

    def _generate(self, uid, own_deck, now):
        decks = {}
        for user in self.store.all_users():
            if user["uid"] != uid:
                deck = self._deck_list(self.deck_for(user["uid"]))
                if deck:
                    decks[user["uid"]] = deck
        friends = set(self.store.friends_of(uid))
        real = list(decks)
        random.shuffle(real)
        real.sort(key=lambda other: other not in friends)  # friends first, random order otherwise
        duels = []
        for other in real[:NBR_DUELS]:
            duels.append({"opp": other, "deck": decks[other], "result": PENDING, "score": 0,
                          "opp_score": self._state(other)["reg"]["score"]})
        bots = random.sample(range(len(BOTS)), NBR_DUELS - len(duels))
        for n in bots:
            deck = decks[random.choice(real)] if real else list(own_deck)
            duels.append({"opp": str(BOT_BASE + n), "deck": deck, "result": PENDING, "score": 0,
                          "opp_score": BASE_SCORE * random.randint(0, 40)})
        return duels

    def _ensure_matches(self, uid, st, own_deck, force=False):
        now = time.time()
        if force or not st["duels"] or now - st["generated"] >= DAY:
            st["duels"] = self._generate(uid, own_deck, now)
            st["generated"] = now
            return True
        return False

    # ---- AMF objects ---------------------------------------------------------------------
    def _matches(self, uid, st):
        duels = []
        for d in st["duels"]:
            user = self.store.user_by_uid(d["opp"])
            name = user["username"] if user else (bot_name(d["opp"]) or "Duelist")
            duels.append(amf3.AMF3Object(P + "arena.amf.DuelArena",
                                         externalId=float(d["opp"]), cardTemplatesId=list(d["deck"]),
                                         matchResultId=d["result"], opponentScore=int(d["opp_score"]),
                                         matchScore=int(d["score"]), firstName=name, lastName="", picUrl=None))
        return amf3.AMF3Object(P + "arena.amf.Matches",
                               externalId=float(uid), duels=duels,
                               lastDateGenerated=amf3.AMF3Date(st["generated"] * 1000),
                               bonusTypeId=st["bonus"], resetCurrencyTypeId=0, nextResetCost=RESET_COST)

    def _registry(self, uid, st):
        reg = st["reg"]
        deck = self._deck_list(self.deck_for(uid))
        return amf3.AMF3Object(P + "arena.amf.PlayerRegistry",
                               externalId=float(uid), cardTemplatesId=deck, score=int(reg["score"]),
                               victories=int(reg["victories"]), defeat=int(reg["defeat"]),
                               aiVictories=int(reg["aiVictories"]), aiDefeat=int(reg["aiDefeat"]))

    # ---- requests ------------------------------------------------------------------------
    def get_duel_arena(self, uid, own_deck):
        with self.lock:
            st = self._state(uid)
            if own_deck:
                self.store.set_player_data(uid, "arena_deck", own_deck)
            new = self._ensure_matches(uid, st, own_deck or self._deck_list(self.deck_for(uid)))
            self._save(uid, st)
            self.log.info("GetDuelArena uid %s: %s set, bonus %d, %s", uid, "new" if new else "current",
                          st["bonus"], [(d["opp"], d["result"]) for d in st["duels"]])
            return self._matches(uid, st), self._registry(uid, st)

    def pay_duel_arena(self, uid):
        with self.lock:
            st = self._state(uid)
            self._ensure_matches(uid, st, self._deck_list(self.deck_for(uid)), force=True)
            self._save(uid, st)
            self.log.info("PayDuelArena uid %s: new set", uid)
            return self._matches(uid, st)

    def start_duel(self, uid, opp):
        with self.lock:
            st = self._state(uid)
            for d in st["duels"]:
                if d["opp"] == opp and d["result"] == PENDING:
                    d["result"] = STARTED
                    self._save(uid, st)
                    return True
            return False

    def complete_duel(self, uid, opp, result):
        """Returns (matches, registry) or None if the opponent is not in the current set."""
        with self.lock:
            st = self._state(uid)
            duel = next((d for d in st["duels"] if d["opp"] == opp), None)
            if duel is None:
                return None
            if duel["result"] in (PENDING, STARTED) and result in (VICTORY, DEFEAT):
                reg = st["reg"]
                if result == VICTORY:
                    duel["score"] = BASE_SCORE * MULTIPLIERS[st["bonus"]]
                    st["bonus"] = min(st["bonus"] + 1, len(MULTIPLIERS) - 1)
                    reg["victories"] += 1
                    reg["score"] += duel["score"]
                    st["weekly"]["score"] += duel["score"]
                else:
                    st["bonus"] = 0
                    reg["defeat"] += 1
                duel["result"] = result
                if self.store.user_by_uid(opp):
                    other = self._state(opp)
                    other["reg"]["aiDefeat" if result == VICTORY else "aiVictories"] += 1
                    self._save(opp, other)
                self._save(uid, st)
                self.log.info("CompleteDuelArena uid %s vs %s: %s, +%d (bonus now %d)", uid, opp,
                              "win" if result == VICTORY else "loss", duel["score"], st["bonus"])
            return self._matches(uid, st), self._registry(uid, st)

    # ---- leaderboards --------------------------------------------------------------------
    def high_scores(self, uid, friend_ids):
        week = week_index()
        rows = []
        for user in self.store.all_users():
            st = self.store.get_player_data(user["uid"], "arena")
            if not st:
                continue
            weekly = st.get("weekly", {})
            rows.append((user, st["reg"]["score"], weekly.get("score", 0) if weekly.get("week") == week else 0))
        friends = set(str(f) for f in friend_ids or []) | {uid}
        now = amf3.AMF3Date(time.time() * 1000)

        def entry(kind, lb_type, user, score):
            return amf3.AMF3Object(P + "leaderboardygo.amf." + kind, id=int(user["id"]), avatarId=int(user["id"]),
                                   externalId=float(user["uid"]), scoreTypeId=1, leaderboardTypeId=lb_type,
                                   score=float(score), dateAdded=now, firstName=user["username"], lastName="")

        def board(kind, lb_type, col, only_friends):
            sel = [r for r in rows if r[col] > 0 and (not only_friends or r[0]["uid"] in friends)]
            sel.sort(key=lambda r: -r[col])
            return [entry(kind, lb_type, r[0], r[col]) for r in sel[:LEADERBOARD_SIZE]]

        me = next((r for r in rows if r[0]["uid"] == uid), None)
        me_user = self.store.user_by_uid(uid)
        return {
            "highScoreAllTime": board("HighScoreAllTime", 1, 1, False),
            "highScoreWeekly": board("HighScoreWeekly", 2, 2, False),
            "highScoreFriendAllTime": board("HighScoreFriendAllTime", 3, 1, True),
            "highScoreFriendWeekly": board("HighScoreFriendWeekly", 4, 2, True),
            "playerHighScoreAllTime": entry("HighScoreAllTime", 1, me_user, me[1] if me else 0),
            "playerHighScoreWeekly": entry("HighScoreWeekly", 2, me_user, me[2] if me else 0),
            "lastRefresh": now,
        }
