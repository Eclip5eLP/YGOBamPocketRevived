"""
Game-server side of the custom login (phase 1): handshake, login, server time, online save.

Client references (work/as3):
  BaseAuthentication.MultiStepAuthentication (core/authentication/BaseAuthentication.as):
    GetTokenRequest -> {token, seed}; LoginRequest{token, name, password}; GetServerTimeRequest.
    name/password = RSA(PKCS#1 v1.5) of the account uid / access token (DoLogin, RSAKey.as:204-261),
    encrypted with config/publickey.xml, which we replace with our key (tools/gen_rsa_key.py).
  PvpAuthentication: same token/login on the PvP connection; it then sends the token as the HTTP
    ExternalId (PvpAuthentication.as:47-53).
  PlayerManager.OnLoginResponse: playerId -> EngineCom.DtbId (core/player/PlayerManager.as:487-498).
  YGOMDataImpl: GetPlayerSave (null -> GetPlayerInfo fallback), SendPlayerSave, AccidentalZero
    (project/engine/data/YGOMDataImpl.as:140-237, 470-528, 563-588).
  The main connection never sets an ExternalId (MobileAuthentication = BaseAuthentication), so the
  session is identified by a cookie set on GetTokenResponse (AIR on Android does send it back,
  verified on device), falling back to the ExternalId.
  PvP login: YGOMPvPLoginImpl.as:250 logs in with name "-1_" + uid and the fixed password "frima"
  (no access token). Its GetToken arrives with the main session's cookie, so the PvP session is
  linked to that logged-in main session and only accepted for the same uid. Both connections share
  one ServerComHTTP, so after PvP login every request carries the PvP token as ExternalId.
"""

import json
import secrets
import zlib
import threading
import time
from pathlib import Path

import amf3
from accounts import AccountStore
from arena import Arena

P = "com.frimastudio.snowstorm.project."
C = "com.frimastudio.snowstorm.core."
COOKIE = "YGOSID"


class RSAKey:
    def __init__(self, path: Path):
        k = json.loads(Path(path).read_text())
        self.n, self.e, self.d = int(k["n"], 16), int(k["e"], 16), int(k["d"], 16)
        self.size = (self.n.bit_length() + 7) // 8

    def decrypt(self, data: bytes) -> str:
        """PKCS#1 v1.5 type 2, one or more blocks (hurlant RSAKey._encrypt appends blocks)."""
        out = b""
        blocks = [data] if len(data) <= self.size else [data[i:i + self.size] for i in range(0, len(data), self.size)]
        for block in blocks:
            m = pow(int.from_bytes(block, "big"), self.d, self.n).to_bytes(self.size, "big")
            if m[0] != 0 or m[1] != 2:
                raise ValueError("bad RSA padding")
            out += m[m.index(0, 2) + 1:]
        return out.decode("utf-8")


class Session:
    def __init__(self, token, parent_uid=None):
        self.token = token
        self.uid = None
        self.parent_uid = parent_uid  # uid of the logged-in session whose cookie came with GetToken
        self.created = time.time()


class Game:
    def __init__(self, store: AccountStore, rsa_key_path: Path, logger):
        self.store = store
        self.rsa = RSAKey(rsa_key_path)
        self.log = logger
        self.sessions = {}
        self.lock = threading.Lock()
        self.arena = Arena(store, self.deck_for, logger)
        self._load_sessions()

    # Logged-in sessions survive a server restart (deploy / auto-reload); otherwise every client
    # would get "no logged-in session" until it logs in again.
    SESSION_FILE = "sessions.json"
    SESSION_SECONDS = 7 * 24 * 3600

    def _load_sessions(self):
        now = time.time()
        for token, v in self.store._load(self.SESSION_FILE, {}).items():
            if now - v["created"] < self.SESSION_SECONDS:
                sess = Session(token, v.get("parent_uid"))
                sess.uid, sess.created = v["uid"], v["created"]
                self.sessions[token] = sess

    def _save_sessions(self):
        # caller holds self.lock
        data = {t: {"uid": v.uid, "parent_uid": v.parent_uid, "created": v.created}
                for t, v in self.sessions.items() if v.uid}
        self.store._store(self.SESSION_FILE, data)

    # ---- session lookup -----------------------------------------------------------------
    def find_session(self, ext_id, cookie_token):
        with self.lock:
            for key in (ext_id, cookie_token):
                if key and key in self.sessions:
                    return self.sessions[key]
        return None

    # ---- dispatch -------------------------------------------------------------------------
    def handle(self, alias, req, ctx):
        """Returns encoded response bytes, or None if this alias is not handled here.
        ctx: dict(ip, ext_id, cookie, set_cookie(list))"""
        fn = HANDLERS.get(alias)
        if fn is None:
            return None
        return fn(self, req, ctx)

    def _session(self, ctx):
        s = self.find_session(ctx["ext_id"], ctx["cookie"])
        if s is None or s.uid is None:
            self.log.warning("[%s] no logged-in session (ext_id=%r cookie=%r)", ctx["ip"], ctx["ext_id"], ctx["cookie"])
        return s if s and s.uid else None

    # ---- handlers -------------------------------------------------------------------------
    def get_token(self, req, ctx):
        token = secrets.token_hex(16)
        seed = secrets.randbelow(0x7FFFFFFF)
        with self.lock:
            now = time.time()
            self.sessions = {k: v for k, v in self.sessions.items() if now - v.created < self.SESSION_SECONDS}
            parent = self.sessions.get(ctx["cookie"] or "")
            parent_uid = parent.uid if parent else None
            self.sessions[token] = Session(token, parent_uid)
        if parent_uid is None:
            ctx["set_cookie"].append(f"{COOKIE}={token}; Path=/; HttpOnly")
        self.log.info("[%s] GetToken -> new session %s (cookie presented: %s, linked uid: %s)",
                      ctx["ip"], token[:8], bool(ctx["cookie"]), parent_uid)
        return amf3.encode_typed_object(C + "player.amf.GetTokenResponse",
                                        {"exception": None, "token": token, "seed": seed})

    def login(self, req, ctx):
        err_alias = C + "player.amf.LoginRequest"  # build_error_response derives the response alias
        try:
            uid = self.rsa.decrypt(bytes(req.get("name") or b""))
            access = self.rsa.decrypt(bytes(req.get("password") or b""))
        except Exception as e:  # noqa: BLE001
            self.log.warning("[%s] Login: RSA decrypt failed: %s", ctx["ip"], e)
            return amf3.build_error_response(err_alias, "Login failed", code=1)
        with self.lock:
            s = self.sessions.get(req.get("token")) or self.sessions.get(ctx["cookie"] or "")
        if s is None:
            self.log.warning("[%s] Login: unknown session token %r", ctx["ip"], req.get("token"))
            return amf3.build_error_response(err_alias, "Session expired", code=1)
        if "_" in uid:
            # PvP login: "-1_<uid>" / "frima", trusted only through the linked main session
            uid = uid.rsplit("_", 1)[1]
            ok = access == "frima" and s.parent_uid == uid
            token_uid = s.parent_uid
        else:
            token_uid = self.store.uid_for_token(access)
            ok = token_uid == uid
        user = self.store.user_by_uid(uid)
        if user is None or not ok:
            self.log.warning("[%s] Login rejected for uid %s (token/linked uid %s)", ctx["ip"], uid, token_uid)
            return amf3.build_error_response(err_alias, "Login failed", code=1)
        with self.lock:
            s.uid = uid
            self._save_sessions()
        self.log.info("[%s] Login OK: %s (uid %s, session %s, %s)", ctx["ip"], user["username"], uid, s.token[:8],
                      "pvp" if s.parent_uid else "main")
        return amf3.encode_typed_object(C + "player.amf.LoginResponse",
                                        {"exception": None, "playerId": int(user["id"])})

    def server_time(self, req, ctx):
        return amf3.encode_typed_object(C + "player.amf.GetServerTimeResponse",
                                        {"exception": None, "serverTime": amf3.AMF3Date(time.time() * 1000)})

    def get_player_save(self, req, ctx):
        s = self._session(ctx)
        blob = self.store.get_save(s.uid) if s else None
        self.log.info("[%s] GetPlayerSave uid %s -> %s", ctx["ip"], s.uid if s else None,
                      f"{len(blob)} bytes" if blob else "none")
        return amf3.encode_typed_object(P + "player.amf.GetPlayerSaveResponse",
                                        {"exception": None, "playerSave": blob})

    def send_player_save(self, req, ctx):
        s = self._session(ctx)
        blob = req.get("playerSave")
        if s is None or not blob:
            return amf3.build_error_response(P + "player.amf.SendPlayerSaveRequest", "Not logged in", code=1)
        self.store.put_save(s.uid, bytes(blob))
        self.log.info("[%s] SendPlayerSave uid %s: %d bytes stored", ctx["ip"], s.uid, len(blob))
        return amf3.encode_typed_object(P + "player.amf.SendPlayerSaveResponse", {"exception": None})

    def last_saved_date(self, req, ctx):
        s = self._session(ctx)
        saved = self.store.last_saved(s.uid) if s else None
        return amf3.encode_typed_object(P + "player.amf.GetLastSavedDateResponse",
                                        {"exception": None,
                                         "lastSavedDate": amf3.AMF3Date(saved * 1000) if saved else None})

    def get_player_info(self, req, ctx):
        # Legacy server-side model; only used when no JSON save exists. A null playerInfo makes
        # YGOMData dispatch LOAD_FAILED and keep the device save (YGOMDataImpl.as:176-191).
        return amf3.encode_typed_object(P + "player.amf.GetPlayerInfoResponse",
                                        {"exception": None, "playerInfo": None})

    def get_rewards(self, req, ctx):
        return amf3.encode_typed_object(P + "inventory.amf.GetRewardsResponse",
                                        {"exception": None, "inventoryRewards": []})

    def get_tournament_reward(self, req, ctx):
        return amf3.encode_typed_object(P + "inventory.amf.GetTournamentRewardResponse",
                                        {"exception": None, "tournamentReward": [], "items": []})

    # ---- PvP login startup steps (YGOMPvPLoginImpl.Login: tournament, team, guild info) ---------
    def tournament_info(self, req, ctx):
        # TournamentManager.OnGetTournamentInfoResponse returns WITHOUT dispatching when tournament is
        # null, which hangs the PvP login (TournamentManager.as:383-393), so there is always one.
        # Templates 2..21 (config/ace/tournament/tournament_template.ace), 14 days each; level template 2
        # = rank 15, token 1 (tournament_level_template.ace). Rotates every 14 days from TOURNAMENT_EPOCH.
        now = time.time()
        idx = int((now - TOURNAMENT_EPOCH) // TOURNAMENT_SECONDS)
        start = TOURNAMENT_EPOCH + idx * TOURNAMENT_SECONDS
        s = self._session(ctx)
        tournament = amf3.AMF3Object(P + "tournament.amf.Tournament",
                                     tournementTemplateId=TOURNAMENT_TEMPLATES[idx % len(TOURNAMENT_TEMPLATES)],
                                     timeStarted=amf3.AMF3Date(start * 1000),
                                     tournamentDurationInSeconds=float(TOURNAMENT_SECONDS))
        level = amf3.AMF3Object(P + "tournament.amf.TournamentLevel",
                                externalId=float(s.uid) if s else 0.0, levelTemplateId=2, eliteRank=0, eliteToken=0)
        return amf3.encode_typed_object(P + "tournament.amf.GetTournamentInfoResponse",
                                        {"exception": None, "tournament": tournament, "tournamentLevel": level,
                                         "beforeNext": 0.0})

    def get_team(self, req, ctx):
        # teamTemplateId 0 = not in a team (GuildManager.IsInAGuild: > 0, GuildManager.as:151-154)
        return amf3.encode_typed_object(P + "guild.amf.GetTeamResponse", {"exception": None, "teamTemplateId": 0})

    def guild_global_info(self, req, ctx):
        week = 7 * 24 * 3600
        next_reset = (int(time.time()) // week + 1) * week
        return amf3.encode_typed_object(P + "guild.amf.GetGlobalInfoResponse",
                                        {"exception": None, "nextResetDate": float(next_reset * 1000), "hasReward": False})

    def get_combats(self, req, ctx):
        # pending friend duel challenges (readyforcombat/CombatManager.as:208-224); none yet (phase 2)
        return amf3.encode_typed_object(P + "readyforcombat.amf.GetCombatsResponse", {"exception": None, "combat": []})

    # ---- phase 2: friends (Duel Ground friend duels, relations) -------------------------------
    def deck_for(self, uid):
        """Comma-separated card template ids the client parses in DuelGroundModule.OnFriendDeckReceived
        (DuelGroundModule.as:552-575; empty string = client default deck). Order of preference:
        deck uploaded by SetDuelArenaDeck (exact, ArenaModule.as:390) -> a save item flagged
        isDefaultDeck -> the 15 strongest collection cards (max 3 copies) -> ''."""
        arena = self.store.get_player_data(uid, "arena_deck")
        if arena:
            return ",".join(str(int(c)) for c in arena)
        blob = self.store.get_save(uid)
        if not blob:
            return ""
        try:
            raw = amf3.AMF3Decoder(zlib.decompress(blob)).decode_value()
            items = (json.loads(raw) if isinstance(raw, str) else raw).get("items", [])
        except Exception as e:  # noqa: BLE001
            self.log.warning("deck_for %s: unreadable save: %s", uid, e)
            return ""
        deck_ids = {it.get("id") for it in items if it.get("isDefaultDeck")}
        out = []
        if deck_ids:
            for c in items:
                if c.get("containerId") in deck_ids:
                    out += [int(c["itemTemplateId"])] * int(c.get("quantity", 1))
        else:
            collection = [it for it in items if it.get("itemTemplateId", 0) > 0 and "atkStat" in it]
            collection.sort(key=lambda c: -(c.get("atkStat", 0) + c.get("defStat", 0)))
            for c in collection:
                out += [int(c["itemTemplateId"])] * min(int(c.get("quantity", 1)), 3)
            out = out[:DECK_SIZE]
        return ",".join(map(str, out))

    def get_deck_by_external_id(self, req, ctx):
        other = str(int(float(req.get("externalId") or 0)))
        deck = self.deck_for(other) if self.store.user_by_uid(other) else ""
        self.log.info("[%s] GetDeckByExternalId %s -> %d cards", ctx["ip"], other, len(deck.split(",")) if deck else 0)
        return amf3.encode_typed_object(P + "arena.amf.GetDeckByExternalIdResponse", {"exception": None, "deck": deck})

    def set_duel_arena_deck(self, req, ctx):
        s = self._session(ctx)
        cards = [int(c) for c in (req.get("cardsTemplateId") or []) if isinstance(c, (int, float))]
        if s and cards:
            self.store.set_player_data(s.uid, "arena_deck", cards)
        return amf3.encode_typed_object(P + "arena.amf.SetDuelArenaDeckResponse", {"exception": None})

    def _relation(self, s, other_uid, rel):
        other = self.store.user_by_uid(other_uid)
        me = self.store.user_by_uid(s.uid)
        return amf3.AMF3Object(P + "relation.amf.Relation",
                               id=int(other["id"]), avatarIdFrom=int(me["id"]), avatarIdTo=int(other["id"]),
                               relationTypeId=1, relationStatusId=1, strength=0, mutual=True, avatarToOnline=False,
                               externalTypeId=1, externalId=float(other_uid), avatarName=other["username"], serverId=0,
                               lastDuelDate=amf3.AMF3Date(rel["duel"] * 1000) if rel.get("duel") else None,
                               lastHelpDate=amf3.AMF3Date(rel["help"] * 1000) if rel.get("help") else None)

    def get_relations(self, req, ctx):
        s = self._session(ctx)
        rels = []
        if s:
            stamps = self.store.get_player_data(s.uid, "relations", {})
            rels = [self._relation(s, f, stamps.get(f, {})) for f in self.store.friends_of(s.uid)
                    if self.store.user_by_uid(f)]
        return amf3.encode_typed_object(P + "relation.amf.GetRelationsProjectResponse",
                                        {"exception": None, "relations": rels})

    def _stamp(self, ctx, account_id, key, alias, date_field):
        s = self._session(ctx)
        other = next((u for u in self.store.all_users() if int(u["id"]) == int(account_id or 0)), None)
        now = time.time()
        if s and other:
            stamps = self.store.get_player_data(s.uid, "relations", {})
            stamps.setdefault(other["uid"], {})[key] = now
            self.store.set_player_data(s.uid, "relations", stamps)
        return amf3.encode_typed_object(alias, {"exception": None, "relationId": int(other["id"]) if other else 0,
                                                date_field: amf3.AMF3Date(now * 1000)})

    def complete_duel_friend(self, req, ctx):
        return self._stamp(ctx, req.get("friendAvatarId"), "duel",
                           P + "worldmap.amf.CompleteDuelFriendResponse", "lastDuelDate")

    def friend_help(self, req, ctx):
        return self._stamp(ctx, req.get("friendPlayerId"), "help",
                           P + "relation.amf.FriendHelpResponse", "lastHelpDate")

    # ---- phase 3: arena (server/arena.py) -------------------------------------------------------
    @staticmethod
    def _ext(value):
        return str(int(float(value or 0)))

    def get_duel_arena(self, req, ctx):
        s = self._session(ctx)
        if s is None:
            return amf3.build_error_response(P + "arena.amf.GetDuelArenaRequest", "Not logged in", code=1)
        deck = [int(c) for c in (req.get("cardTemplatesId") or []) if isinstance(c, (int, float))]
        matches, registry = self.arena.get_duel_arena(s.uid, deck)
        return amf3.encode_typed_object(P + "arena.amf.GetDuelArenaResponse",
                                        {"exception": None, "matches": matches, "playerRegistry": registry})

    def pay_duel_arena(self, req, ctx):
        s = self._session(ctx)
        if s is None:
            return amf3.build_error_response(P + "arena.amf.PayDuelArenaRequest", "Not logged in", code=1)
        return amf3.encode_typed_object(P + "arena.amf.PayDuelArenaResponse",
                                        {"exception": None, "matches": self.arena.pay_duel_arena(s.uid)})

    def start_duel_arena(self, req, ctx):
        s = self._session(ctx)
        if s:
            self.arena.start_duel(s.uid, self._ext(req.get("opponentExternalId")))
        return amf3.encode_typed_object(P + "arena.amf.StartDuelArenaResponse", {"exception": None})

    def complete_duel_arena(self, req, ctx):
        alias = P + "arena.amf.CompleteDuelArenaRequest"
        s = self._session(ctx)
        if s is None:
            return amf3.build_error_response(alias, "Not logged in", code=1)
        res = self.arena.complete_duel(s.uid, self._ext(req.get("opponentExternalId")), int(req.get("matchResultId") or 0))
        if res is None:  # EArenaError.OPPONENT_INEXISTANT: client clears its cached matches
            return amf3.build_error_response(alias, "Opponent not in current arena set", code=-1)
        return amf3.encode_typed_object(P + "arena.amf.CompleteDuelArenaResponse",
                                        {"exception": None, "playerRegistry": res[1], "matches": res[0]})

    def get_high_scores(self, req, ctx):
        s = self._session(ctx)
        if s is None:
            return amf3.build_error_response(P + "leaderboardygo.amf.GetHighScoresRequest", "Not logged in", code=1)
        props = self.arena.high_scores(s.uid, [self._ext(f) for f in (req.get("friendExternalIds") or [])])
        return amf3.encode_typed_object(P + "leaderboardygo.amf.GetHighScoresResponse", {"exception": None, **props})

    def accidental_zero(self, req, ctx):
        return amf3.encode_typed_object(P + "player.amf.AccidentalZeroResponse", {"exception": None})


DECK_SIZE = 15  # deck editor slots (EDIT DECK grid)
TOURNAMENT_TEMPLATES = list(range(2, 22))
TOURNAMENT_SECONDS = 1209600
TOURNAMENT_EPOCH = 1_767_225_600  # 2026-01-01 00:00 UTC

HANDLERS = {
    C + "player.amf.GetTokenRequest": Game.get_token,
    C + "player.amf.LoginRequest": Game.login,
    C + "player.amf.GetServerTimeRequest": Game.server_time,
    P + "player.amf.GetPlayerSaveRequest": Game.get_player_save,
    P + "player.amf.SendPlayerSaveRequest": Game.send_player_save,
    P + "player.amf.GetLastSavedDateRequest": Game.last_saved_date,
    P + "player.amf.GetPlayerInfoRequest": Game.get_player_info,
    P + "inventory.amf.GetRewardsRequest": Game.get_rewards,
    P + "inventory.amf.GetTournamentRewardRequest": Game.get_tournament_reward,
    P + "player.amf.AccidentalZeroRequest": Game.accidental_zero,
    P + "tournament.amf.GetTournamentInfoRequest": Game.tournament_info,
    P + "guild.amf.GetTeamRequest": Game.get_team,
    P + "guild.amf.GetGlobalInfoRequest": Game.guild_global_info,
    P + "readyforcombat.amf.GetCombatsRequest": Game.get_combats,
    P + "arena.amf.GetDeckByExternalIdRequest": Game.get_deck_by_external_id,
    P + "arena.amf.SetDuelArenaDeckRequest": Game.set_duel_arena_deck,
    P + "relation.amf.GetRelationsProjectRequest": Game.get_relations,
    P + "worldmap.amf.CompleteDuelFriendRequest": Game.complete_duel_friend,
    P + "relation.amf.FriendHelpRequest": Game.friend_help,
    P + "arena.amf.GetDuelArenaRequest": Game.get_duel_arena,
    P + "arena.amf.PayDuelArenaRequest": Game.pay_duel_arena,
    P + "arena.amf.StartDuelArenaRequest": Game.start_duel_arena,
    P + "arena.amf.CompleteDuelArenaRequest": Game.complete_duel_arena,
    P + "leaderboardygo.amf.GetHighScoresRequest": Game.get_high_scores,
}
