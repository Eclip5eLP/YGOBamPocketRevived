"""
Teams (guilds) and tournament registration / leaderboards (phase 3). Tournament matches themselves are
real-time PvP (PlayCombatTournament -> PlayCombatNotification -> live duel -> PlayCombatEndNotification,
project/tournament/TournamentManager.as:443-516) and come with phase 4.

Teams, client references (work/as3/.../project/guild/GuildManager.as):
  IsInAGuild = teamTemplateId > 0 (151-154). JoinTeam -> {teamTemplateId}; the server picks the team
  (179-191, 314-333). CancelJoinTeam -> client sets 0 (193-202, 358-370).
  GetPlayerInfo -> PlayerGuildInfo{externalId, rank, score} (216-226, 386-398).
  GetTeamInfo{teamTemplateId} -> {teamRank, teamScore, top50[PlayerGuildInfo]} (228-242, 400-412).
  StartTeamContribution -> GetNewScoreToken -> {token}; after an arena/tournament duel
  SendTeamContributionPoints -> NewScore{score, token} -> {score}, shown as the contribution (256-303, 428-482).
  GetGlobalInfo{nextResetDate (ms), hasReward} (414-426); teams 1..20
  (config/ace/guild/guild_team_template.ace).
Our rules: join = the team with the fewest members this week (random among ties); scores count per week
(same week boundary as GetGlobalInfo); a team's score is the sum of its members' weekly scores.
Weekly team rewards (guild_team_*_reward_template) are not handed out yet.

Tournaments: registered = a TournamentLevel exists (module/tournament/util/TournamentUtil.as:53). The client
pays the entry fee locally, then RegisterTournament -> {tournament, tournementLevel}
(logic/BuyTournamentEntryFeeFlow.as:44-74, TournamentManager.as:487-503). Start level 81 = rank 15, 0 tokens
(config/ace/tournament/tournament_level_template.ace). Get(Previous)TopTournamentLeaderboard{numberPlayers}
-> {tournamentLevel[]} (395-434, 528-542).

Ranking (live tournament duels, server/livepvp.py): each result moves the player along the game's own level chain
(LEVELS, from tournament_level_template.ace: a win goes to levelTemplateAfter, a loss to levelTemplateBefore; -1 =
stay, so the 0-token level of a rank is its floor). The client compares the old and new level from
PlayCombatEndNotification{tournamentLevel} to animate a token or a new rank (module/tournament/view/TournamentView.as
CheckNewLevelReceived, TournamentManager.ConsumeTournamentLevelNotification). Level 80 is Elite (rank 0): the token
shown is eliteToken (module/tournament/util/TournamentUtil.as GetRank); ours counts +1 per win, -1 per loss, min 0
(INFERRED). eliteRank = position among Elite players by eliteToken (then who got there first), 1..100, else 0; the
elite rewards (tournament_reward_template.ace, level 80) are by eliteRank ranges 1..100, rank 0 = outside them, and
TournamentCacheLogic.GetTournamentRewardByLevel matches non-Elite levels on eliteRank 0 too. The top leaderboard is
the Elite list (TournamentScreenLeaderPopup), so it holds Elite players only.
"""

import os
import random
import secrets
import threading
import time

import amf3

P = "com.frimastudio.snowstorm.project."
TEAM_IDS = list(range(1, 21))
WEEK = 7 * 24 * 3600
TOP = 50
START_LEVEL = {"level": 81, "rank": 15, "token": 0}
TOURNAMENT_TEMPLATES = list(range(2, 22))
TOURNAMENT_SECONDS = 1209600
TOURNAMENT_EPOCH = 1_767_225_600  # 2026-01-01 00:00 UTC
ELITE_LEVEL = 80
ELITE_RANKED = 100
# level id: (rank, token, level after a loss, level after a win), config/ace/tournament/tournament_level_template.ace
LEVELS = {
    2: (15, 1, 81, 3), 3: (15, 2, 2, 5), 5: (15, 3, 3, 7), 7: (14, 1, 62, 8), 8: (14, 2, 7, 9), 9: (14, 3, 8, 10),
    10: (13, 1, 63, 11), 11: (13, 2, 10, 12), 12: (13, 3, 11, 13), 13: (12, 1, 64, 14), 14: (12, 2, 13, 15),
    15: (12, 3, 14, 16), 16: (11, 1, 65, 17), 17: (11, 2, 16, 18), 18: (11, 3, 17, 19), 19: (10, 1, 66, 20),
    20: (10, 2, 19, 21), 21: (10, 3, 20, 22), 22: (10, 4, 21, 23), 23: (9, 1, 67, 25), 25: (9, 2, 23, 26),
    26: (9, 3, 25, 27), 27: (9, 4, 26, 28), 28: (8, 1, 68, 29), 29: (8, 2, 28, 30), 30: (8, 3, 29, 31),
    31: (8, 4, 30, 32), 32: (7, 1, 69, 33), 33: (7, 2, 32, 34), 34: (7, 3, 33, 35), 35: (7, 4, 34, 36),
    36: (6, 1, 70, 37), 37: (6, 2, 36, 38), 38: (6, 3, 37, 39), 39: (6, 4, 38, 40), 40: (5, 1, 71, 41),
    41: (5, 2, 40, 42), 42: (5, 3, 41, 43), 43: (5, 4, 42, 44), 44: (5, 5, 43, 46), 46: (4, 1, 72, 47),
    47: (4, 2, 46, 48), 48: (4, 3, 47, 49), 49: (4, 4, 48, 50), 50: (4, 5, 49, 51), 51: (3, 1, 73, 52),
    52: (3, 2, 51, 53), 53: (3, 3, 52, 54), 54: (3, 4, 53, 55), 55: (3, 5, 54, 56), 56: (2, 1, 74, 57),
    57: (2, 2, 56, 58), 58: (2, 3, 57, 59), 59: (2, 4, 58, 60), 60: (2, 5, 59, 61), 61: (1, 1, 75, 76),
    62: (14, 0, -1, 7), 63: (13, 0, -1, 10), 64: (12, 0, -1, 13), 65: (11, 0, -1, 16), 66: (10, 0, -1, 19),
    67: (9, 0, -1, 23), 68: (8, 0, -1, 28), 69: (7, 0, -1, 32), 70: (6, 0, -1, 36), 71: (5, 0, -1, 40),
    72: (4, 0, -1, 46), 73: (3, 0, -1, 51), 74: (2, 0, -1, 56), 75: (1, 0, -1, 61), 76: (1, 2, 61, 77),
    77: (1, 3, 76, 78), 78: (1, 4, 77, 79), 79: (1, 5, 78, 80), 80: (0, -1, -1, -1), 81: (15, 0, -1, 2)
}


def week_index(now=None):
    return int(now or time.time()) // WEEK


def tournament_index(now=None):
    return int(((now or time.time()) - TOURNAMENT_EPOCH) // TOURNAMENT_SECONDS)


class Teams:
    def __init__(self, store, logger):
        self.store = store
        self.log = logger
        self.lock = threading.Lock()
        self.tokens = {}  # uid -> pending NewScore token

    # ---- teams ---------------------------------------------------------------------------
    def _team(self, uid):
        t = self.store.get_player_data(uid, "team") or {"id": 0, "week": week_index(), "score": 0}
        if t["week"] != week_index():
            t = {"id": t["id"], "week": week_index(), "score": 0}
        return t

    def _members(self):
        out = {}
        for user in self.store.all_users():
            t = self._team(user["uid"])
            if t["id"]:
                out.setdefault(t["id"], []).append((user["uid"], t["score"]))
        return out

    def team_of(self, uid):
        return self._team(uid)["id"]

    def join(self, uid):
        with self.lock:
            t = self._team(uid)
            if not t["id"]:
                members = self._members()
                fewest = min(len(members.get(i, [])) for i in TEAM_IDS)
                t["id"] = random.choice([i for i in TEAM_IDS if len(members.get(i, [])) == fewest])
                self.store.set_player_data(uid, "team", t)
                self.log.info("JoinTeam uid %s -> team %d", uid, t["id"])
            return t["id"]

    def leave(self, uid):
        with self.lock:
            self.store.set_player_data(uid, "team", {"id": 0, "week": week_index(), "score": 0})

    def new_token(self, uid):
        token = secrets.randbelow(0x7FFFFFFF) + 1
        self.tokens[uid] = token
        return token

    def add_score(self, uid, score, token):
        with self.lock:
            t = self._team(uid)
            if not t["id"] or self.tokens.pop(uid, None) != token or not 0 < score <= 100_000:
                return 0
            t["score"] += score
            self.store.set_player_data(uid, "team", t)
            self.log.info("NewScore uid %s team %d: +%d (week %d)", uid, t["id"], score, t["score"])
            return score

    @staticmethod
    def _info(uid, rank, score):
        return amf3.AMF3Object(P + "guild.amf.PlayerGuildInfo", externalId=float(uid), rank=rank, score=int(score))

    def player_info(self, uid):
        t = self._team(uid)
        ranked = sorted(self._members().get(t["id"], []), key=lambda m: -m[1])
        rank = next((i + 1 for i, m in enumerate(ranked) if m[0] == uid), 0)
        return self._info(uid, rank, t["score"])

    def team_info(self, team_id):
        members = self._members()
        totals = sorted(TEAM_IDS, key=lambda i: (-sum(s for _, s in members.get(i, [])), i))
        ranked = sorted(members.get(team_id, []), key=lambda m: -m[1])
        return {"teamRank": totals.index(team_id) + 1 if team_id in totals else 0,
                "teamScore": float(sum(s for _, s in ranked)),
                "top50": [self._info(u, i + 1, s) for i, (u, s) in enumerate(ranked[:TOP])]}

    # ---- tournaments ---------------------------------------------------------------------
    def tournament(self, idx=None):
        idx = tournament_index() if idx is None else idx
        start = TOURNAMENT_EPOCH + idx * TOURNAMENT_SECONDS
        # YGO_TOURNAMENT_TEMPLATE (dev/testing only): always this template, e.g. 5 = no deck restriction
        template = int(os.environ.get("YGO_TOURNAMENT_TEMPLATE") or TOURNAMENT_TEMPLATES[idx % len(TOURNAMENT_TEMPLATES)])
        return amf3.AMF3Object(P + "tournament.amf.Tournament",
                               tournementTemplateId=template,
                               timeStarted=amf3.AMF3Date(start * 1000),
                               tournamentDurationInSeconds=float(TOURNAMENT_SECONDS))

    def _entry(self, uid, idx):
        t = self.store.get_player_data(uid, "tournament") or {}
        return t.get(str(idx))

    def _elites(self, idx):
        """Elite uids, best first: most eliteToken, then who reached Elite first."""
        rows = []
        for user in self.store.all_users():
            e = self._entry(user["uid"], idx)
            if e and e["level"] == ELITE_LEVEL:
                rows.append((-e.get("eliteToken", 0), e.get("eliteSince", 0), user["uid"]))
        return [r[2] for r in sorted(rows)]

    def level(self, uid, idx=None, elites=None):
        idx = tournament_index() if idx is None else idx
        e = self._entry(uid, idx)
        if not e:
            return None
        elite_rank = 0
        if e["level"] == ELITE_LEVEL:
            elites = self._elites(idx) if elites is None else elites
            pos = elites.index(uid) + 1 if uid in elites else 0
            elite_rank = pos if pos <= ELITE_RANKED else 0
        return amf3.AMF3Object(P + "tournament.amf.TournamentLevel", externalId=float(uid),
                               levelTemplateId=e["level"], eliteRank=elite_rank,
                               eliteToken=e.get("eliteToken", 0))

    @staticmethod
    def rank_of(level):
        """Tournament rank (15..1, 0 = Elite) of a TournamentLevel."""
        return LEVELS.get(int(level["levelTemplateId"]), (15,))[0]

    def record_result(self, uid, won):
        """One live tournament duel result; returns the new TournamentLevel (None if not registered)."""
        with self.lock:
            idx = tournament_index()
            t = self.store.get_player_data(uid, "tournament") or {}
            e = t.get(str(idx))
            if not e:
                return None
            old = e["level"]
            if old == ELITE_LEVEL:
                e["eliteToken"] = max(0, e.get("eliteToken", 0) + (1 if won else -1))
            else:
                _, _, before, after = LEVELS.get(old, LEVELS[START_LEVEL["level"]])
                new = after if won else before
                if new > 0 and new in LEVELS:
                    e["level"] = new
                    e["rank"], e["token"] = LEVELS[new][0], LEVELS[new][1]
                    if new == ELITE_LEVEL:
                        e["eliteToken"], e["eliteSince"] = 0, time.time()
            e["wins" if won else "losses"] = e.get("wins" if won else "losses", 0) + 1
            self.store.set_player_data(uid, "tournament", t)
            self.log.info("tournament uid %s %s: level %s -> %s", uid, "won" if won else "lost", old, e["level"])
        return self.level(uid, idx)

    def register(self, uid):
        with self.lock:
            idx = tournament_index()
            t = self.store.get_player_data(uid, "tournament") or {}
            if str(idx) not in t:
                t[str(idx)] = dict(START_LEVEL)
                t = {k: v for k, v in t.items() if int(k) >= idx - 1}  # keep current + previous
                self.store.set_player_data(uid, "tournament", t)
                self.log.info("RegisterTournament uid %s, tournament %d", uid, idx)
            return self.level(uid, idx)

    def leaderboard(self, count, previous=False):
        idx = tournament_index() - (1 if previous else 0)
        elites = self._elites(idx)
        return [self.level(uid, idx, elites) for uid in elites[:max(1, min(int(count or TOP), 200))]]
