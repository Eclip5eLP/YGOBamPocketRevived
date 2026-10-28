"""
Account, access-token and save storage for the revival server (stdlib only, JSON files).

Accounts replace Facebook: each account gets a numeric "Facebook uid" that the client uses
as its external id (FacebookManagerMobile.OnLoadOwnUserComplete: mOwnUser.uid = /me id,
YGOMLoginImpl.LoginGame: EngineServerCom.Login(OwnUser.uid, AccessToken)).

Layout under <data_dir>:
  accounts.json   {"next_id": int, "users": {lower_username: {id, uid, username, salt, hash, created}}}
  tokens.json     {access_token: {"uid": str, "expires": epoch}}
  saves/<uid>.bin the client's playerSave blob as sent (zlib(AMF3(JSON string))), plus <uid>.json meta
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Optional

UID_BASE = 1_000_000_000  # account id 1 -> uid 1000000001 (Number on the client, fits a double)
TOKEN_LIFETIME = 60 * 24 * 3600
PBKDF2_ROUNDS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,20}$")


class AccountError(ValueError):
    pass


class AccountStore:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        (self.dir / "saves").mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.accounts = self._load("accounts.json", {"next_id": 1, "users": {}})
        self.tokens = self._load("tokens.json", {})

    def _load(self, name, default):
        p = self.dir / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return default

    def _store(self, name, obj):
        p = self.dir / name
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
        os.replace(tmp, p)

    @staticmethod
    def _hash(password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS).hex()

    def register(self, username: str, password: str) -> dict:
        if not USERNAME_RE.match(username or ""):
            raise AccountError("Username must be 3-20 characters: letters, digits, _ . -")
        if len(password or "") < 6 or len(password) > 128:
            raise AccountError("Password must be 6-128 characters")
        key = username.lower()
        with self.lock:
            if key in self.accounts["users"]:
                raise AccountError("This username is already taken")
            acc_id = self.accounts["next_id"]
            self.accounts["next_id"] = acc_id + 1
            salt = secrets.token_bytes(16)
            user = {"id": acc_id, "uid": str(UID_BASE + acc_id), "username": username,
                    "salt": salt.hex(), "hash": self._hash(password, salt), "created": int(time.time())}
            self.accounts["users"][key] = user
            self._store("accounts.json", self.accounts)
            return user

    def authenticate(self, username: str, password: str) -> dict:
        user = self.accounts["users"].get((username or "").lower())
        if user is None:
            self._hash(password or "", b"\0" * 16)  # same cost for unknown users
            raise AccountError("Wrong username or password")
        if not hmac.compare_digest(user["hash"], self._hash(password or "", bytes.fromhex(user["salt"]))):
            raise AccountError("Wrong username or password")
        return user

    def user_by_uid(self, uid: str) -> Optional[dict]:
        for user in self.accounts["users"].values():
            if user["uid"] == str(uid):
                return user
        return None

    def issue_token(self, uid: str) -> str:
        token = secrets.token_urlsafe(24)
        with self.lock:
            now = time.time()
            self.tokens = {t: v for t, v in self.tokens.items() if v["expires"] > now}
            self.tokens[token] = {"uid": str(uid), "expires": int(now + TOKEN_LIFETIME)}
            self._store("tokens.json", self.tokens)
        return token

    def uid_for_token(self, token: str) -> Optional[str]:
        entry = self.tokens.get(token or "")
        if entry and entry["expires"] > time.time():
            return entry["uid"]
        return None

    # --- saves -----------------------------------------------------------------------------
    def _save_path(self, uid: str) -> Path:
        if not str(uid).isdigit():
            raise AccountError("bad uid")
        return self.dir / "saves" / f"{uid}.bin"

    def get_save(self, uid: str) -> Optional[bytes]:
        p = self._save_path(uid)
        return p.read_bytes() if p.exists() else None

    def put_save(self, uid: str, blob: bytes) -> float:
        p = self._save_path(uid)
        with self.lock:
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(blob)
            os.replace(tmp, p)
            saved = time.time()
            p.with_suffix(".json").write_text(json.dumps({"saved": saved, "size": len(blob)}))
        return saved

    def last_saved(self, uid: str) -> Optional[float]:
        meta = self._save_path(uid).with_suffix(".json")
        if meta.exists():
            return json.loads(meta.read_text())["saved"]
        return None
