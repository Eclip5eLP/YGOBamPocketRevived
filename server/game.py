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
import threading
import time
from pathlib import Path

import amf3
from accounts import AccountStore

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
            self.sessions = {k: v for k, v in self.sessions.items() if now - v.created < 7 * 24 * 3600}
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

    def accidental_zero(self, req, ctx):
        return amf3.encode_typed_object(P + "player.amf.AccidentalZeroResponse", {"exception": None})


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
}
