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
"""

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
        return amf3.AMF3Object(P + "tournament.amf.Tournament",
                               tournementTemplateId=TOURNAMENT_TEMPLATES[idx % len(TOURNAMENT_TEMPLATES)],
                               timeStarted=amf3.AMF3Date(start * 1000),
                               tournamentDurationInSeconds=float(TOURNAMENT_SECONDS))

    def _entry(self, uid, idx):
        t = self.store.get_player_data(uid, "tournament") or {}
        return t.get(str(idx))

    def level(self, uid, idx=None):
        idx = tournament_index() if idx is None else idx
        e = self._entry(uid, idx)
        if not e:
            return None
        return amf3.AMF3Object(P + "tournament.amf.TournamentLevel", externalId=float(uid),
                               levelTemplateId=e["level"], eliteRank=e.get("eliteRank", 0),
                               eliteToken=e.get("eliteToken", 0))

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
        rows = []
        for user in self.store.all_users():
            e = self._entry(user["uid"], idx)
            if e:
                rows.append((e.get("rank", 15), -e.get("token", 0), e.get("eliteRank", 0), user["uid"]))
        rows.sort()
        return [self.level(r[3], idx) for r in rows[:max(1, min(int(count or TOP), 200))]]
