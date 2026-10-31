"""
Player profiles (notes/todo.md "Profile"): preset picture, stats from the online save, play deck; rename and
password change. Served on the fake Graph API the client already talks to (server/fakefb.py):

  GET  /fb/graph/revival_icons               [{"id": n, "card": name}, ...] preset pictures
  GET  /fb/graph/revival_icons/<n>           preset picture n (PNG, 128 px)
  GET  /fb/graph/<uid>/picture               the player's chosen preset, else the default picture
  GET  /fb/graph/<uid>/revival_profile       public profile (anyone may view)
  POST /fb/graph/me/revival_profile          access_token + action=icon (icon=n) | rename (name=)
                                             | password (old=, new=); answers {"ok": true} or {"error": msg}

Preset pictures are built by tools/content_mods.profile_icons into <content_dir>/server/icons/.
"""

import json
import os
import zlib

import amf3
from accounts import AccountError


class Profiles:
    def __init__(self, store, content_dir, deck_for, logger):
        self.store = store
        self.icons_dir = os.path.join(content_dir or "", "server", "icons")
        self.deck_for = deck_for  # Game.deck_for: uid -> "id,id,..." (arena deck, default deck or best cards)
        self.log = logger

    # --- preset pictures ------------------------------------------------------------------------
    def icon_list(self):
        try:
            with open(os.path.join(self.icons_dir, "icons.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def icon_png(self, n):
        if not str(n).isdigit():
            return None
        try:
            with open(os.path.join(self.icons_dir, f"{int(n)}.png"), "rb") as f:
                return f.read()
        except OSError:
            return None

    def picture(self, uid):
        """PNG of the player's preset picture, or None for the default."""
        icon = self.store.get_player_data(uid, "icon")
        return self.icon_png(icon) if icon is not None else None

    # --- public profile -----------------------------------------------------------------------------
    def _save(self, uid):
        blob = self.store.get_save(uid)
        if not blob:
            return {}
        try:
            raw = amf3.AMF3Decoder(zlib.decompress(blob)).decode_value()
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:  # noqa: BLE001
            self.log.warning("profile %s: unreadable save: %s", uid, e)
            return {}

    def public(self, uid):
        user = self.store.user_by_uid(uid)
        if user is None:
            return None
        save = self._save(uid)
        items = save.get("items") or []
        inventory = {it.get("id") for it in items if it.get("itemTemplateId") == -1}
        cards = [it for it in items if it.get("containerId") in inventory and it.get("itemTemplateId", 0) > 0]
        league = save.get("league") or {}
        deck_name = next((it.get("deckName") for it in items if it.get("isDefaultDeck") and it.get("deckName")), "")
        deck = self.deck_for(uid) if self.deck_for else ""
        return {
            "uid": user["uid"],
            "name": user["username"],
            "icon": self.store.get_player_data(uid, "icon"),
            "league": int(league.get("leagueTemplateId") or 1),
            "experience": int(league.get("totalExperience") or 0),
            "stars": sum(int(w.get("totalStarCompleted") or 0) for w in save.get("worldMapArray") or []),
            "cards_unique": len({c["itemTemplateId"] for c in cards}),
            "cards_total": sum(int(c.get("quantity") or 1) for c in cards),
            "deck_name": deck_name,
            "deck": [int(c) for c in deck.split(",") if c.strip().isdigit()] if deck else [],
            "created": user.get("created", 0),
        }

    # --- changes by the player ------------------------------------------------------------------------
    def update(self, uid, form):
        action = (form.get("action") or [""])[0]
        value = lambda key: (form.get(key) or [""])[0]  # noqa: E731
        try:
            if action == "icon":
                n = value("icon")
                if self.icon_png(n) is None:
                    raise AccountError("Unknown picture")
                self.store.set_player_data(uid, "icon", int(n))
            elif action == "rename":
                self.store.rename(uid, value("name").strip())
            elif action == "password":
                self.store.change_password(uid, value("old"), value("new"))
            else:
                raise AccountError("Unknown action")
        except AccountError as e:
            return {"error": str(e)}
        self.log.info("profile %s: %s", uid, action)
        return {"ok": True}
