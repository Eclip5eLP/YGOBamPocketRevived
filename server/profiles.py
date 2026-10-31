"""
Player profiles (notes/todo.md "Profile"): preset picture, stats from the online save, play deck; rename and
password change. Served on the fake Graph API the client already talks to (server/fakefb.py):

  GET  /fb/graph/revival_icons               [{"id": n, "card": name}, ...] preset pictures
  GET  /fb/graph/revival_icons/<n>           preset picture n (PNG, 128 px)
  GET  /fb/graph/revival_cards/<id>          card picture (JPEG, 128 px) of card template <id>
  GET  /fb/graph/<uid>/picture               the player's chosen card (or older preset), else the default picture
  GET  /fb/graph/<uid>/revival_profile       public profile (anyone may view)
  POST /fb/graph/me/revival_profile          access_token + action=card (card=<template id, owned>) | icon (icon=n)
                                             | rename (name=)
                                             | password (old=, new=); answers {"ok": true} or {"error": msg}

  GET/POST /fb/dialog/revival_profile         edit page shown in the game's web view (EDIT PROFILE button):
                                             current picture + Choose picture (view=picture: the cards in the
                                             player's online save, pictures load as they scroll in), online deck,
                                             rename and password forms, Close

Card pictures are built by tools/content_mods.card_icons into <content_dir>/server/cards/, the older preset
pictures by tools/content_mods.profile_icons into <content_dir>/server/icons/.
"""

import html
import json
import os
import time
import urllib.parse
import zlib

import amf3
from accounts import AccountError


class Profiles:
    def __init__(self, store, content_dir, game, logger):
        self.store = store
        self.icons_dir = os.path.join(content_dir or "", "server", "icons")
        self.cards_dir = os.path.join(content_dir or "", "server", "cards")
        self._card_names = None
        self.deck_source = game.deck_source if game else None  # uid -> (label, [template ids])
        self.is_online = game.livepvp.is_online if game else None  # profile LIVE DUEL button
        self.decks = game.save_decks if game else None
        self.save_items = game.save_items if game else None
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

    def card_names(self):
        """{template id (str): name} of the cards that have a picture."""
        if self._card_names is None:
            try:
                with open(os.path.join(self.cards_dir, "cards.json"), encoding="utf-8") as f:
                    self._card_names = json.load(f)
            except (OSError, ValueError):
                return {}
        return self._card_names

    def card_jpg(self, template_id):
        if not str(template_id).isdigit() or str(int(template_id)) not in self.card_names():
            return None
        try:
            with open(os.path.join(self.cards_dir, f"{int(template_id)}.jpg"), "rb") as f:
                return f.read()
        except OSError:
            return None

    def owned_cards(self, uid):
        """Template ids of the cards in the player's online save (collection and decks) that have a picture."""
        names = self.card_names()
        items = self.save_items(uid) if self.save_items else []
        return {int(it["itemTemplateId"]) for it in items
                if str(it.get("itemTemplateId", 0)) in names and int(it.get("quantity", 1) or 1) > 0}

    def picture(self, uid):
        """Image bytes (JPEG or PNG) of the player's card or preset picture, or None for the default."""
        card = self.store.get_player_data(uid, "icon_card")
        if card is not None:
            jpg = self.card_jpg(card)
            if jpg is not None:
                return jpg
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
        deck_name, deck_cards = self.deck_source(uid) if self.deck_source else ("No deck yet", [])
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
            "deck": deck_cards,
            "created": user.get("created", 0),
            "online": bool(self.is_online and self.is_online(uid)),
        }

    # --- changes by the player ------------------------------------------------------------------------
    def update(self, uid, form):
        action = (form.get("action") or [""])[0]
        value = lambda key: (form.get(key) or [""])[0]  # noqa: E731
        try:
            if action == "card":
                card = value("card")
                if not card.isdigit() or int(card) not in self.owned_cards(uid):
                    raise AccountError("You don't own that card (cards count once the game has saved online).")
                self.store.set_player_data(uid, "icon_card", int(card))
            elif action == "icon":
                n = value("icon")
                if self.icon_png(n) is None:
                    raise AccountError("Unknown picture")
                self.store.set_player_data(uid, "icon", int(n))
                self.store.set_player_data(uid, "icon_card", None)
            elif action == "rename":
                self.store.rename(uid, value("name").strip())
            elif action == "password":
                self.store.change_password(uid, value("old"), value("new"))
            elif action == "deck":
                if value("deck") == "auto":
                    self.store.set_player_data(uid, "defense_deck", None)
                else:
                    ids = [d["id"] for d in self.decks(self.save_items(uid)) if d["cards"]] if self.decks else []
                    if not value("deck").lstrip("-").isdigit() or int(value("deck")) not in ids:
                        raise AccountError("Unknown deck")
                    self.store.set_player_data(uid, "defense_deck", int(value("deck")))
            else:
                raise AccountError("Unknown action")
        except AccountError as e:
            return {"error": str(e)}
        self.log.info("profile %s: %s", uid, action)
        return {"ok": True}


# shown in the game's in-app web view (like the invite dialog): Close first, compact
EDIT_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;font-family:sans-serif;background:#0b1730;color:#eef;padding:8px;font-size:14px}}
h2{{font-size:15px;margin:14px 0 6px}} a.close,button{{display:block;width:100%;box-sizing:border-box;padding:9px;
background:#2d6cdf;color:#fff;text-align:center;border:0;border-radius:6px;text-decoration:none;font-size:15px}}
input{{width:100%;box-sizing:border-box;padding:9px;margin-bottom:6px;font-size:15px;border-radius:6px;
border:1px solid #456;background:#12244a;color:#fff}} .msg{{padding:8px;border-radius:6px;margin:8px 0;background:#1d4a2a}}
.err{{background:#5a1d1d}} .icons{{display:flex;flex-wrap:wrap;gap:6px}} .icons button{{width:64px;height:64px;padding:0;
background:#12244a;border:3px solid transparent}} .icons button.sel{{border-color:#f2c200}} .icons img{{width:58px;height:58px;
border-radius:4px}} .pic{{display:flex;align-items:center;gap:10px}} .pic img{{width:72px;height:72px;border-radius:6px;
border:2px solid #456}} .pic a{{flex:1;display:block;padding:9px;background:#2d6cdf;color:#fff;text-align:center;
border-radius:6px;text-decoration:none;font-size:15px}} .hint{{color:#99a;margin:2px 0 6px;font-size:12px}} .deck{{display:flex;align-items:center;gap:8px;
padding:4px 0}} .deck span{{flex:1}} .deck form{{margin:0}} .deck button{{width:auto;padding:7px 12px}} .deck b{{color:#f2c200}}</style></head><body><a class="close" href="{close}">Close</a>{message}
<h2>Picture</h2><div class="pic"><img src="{picture}" alt=""><a href="{choose}">Choose picture</a></div>
<h2>Online deck</h2><p class="hint">The deck friends duel against. Decks appear here after the game has saved
online.</p>{decks}
<h2>Username</h2><form method="post">{hidden}<input type="hidden" name="action" value="rename">
<input name="name" value="{name}" maxlength="20" autocomplete="off"><button>Change username</button></form>
<h2>Password</h2><form method="post">{hidden}<input type="hidden" name="action" value="password">
<input name="old" type="password" placeholder="Current password" autocomplete="current-password">
<input name="new" type="password" placeholder="New password (6+ characters)" autocomplete="new-password">
<button>Change password</button></form></body></html>"""


PICTURE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{style}</style></head><body><a class="close" href="{back}">Back</a>
<h2>Choose picture</h2><p class="hint">Any card you own, in your collection or a deck ({count} cards). New cards count
once the game has saved online.</p><input id="find" placeholder="Search by card name" autocomplete="off">
<form method="post" action="{main}" class="icons">{hidden}<input type="hidden" name="action" value="card">{cards}</form>
<script>
var imgs = [].slice.call(document.querySelectorAll("img[data-src]"));
function show(img) {{ if (img.dataset.src) {{ img.src = img.dataset.src; img.removeAttribute("data-src"); }} }}
var io = window.IntersectionObserver ? new IntersectionObserver(function (es) {{
  es.forEach(function (e) {{ if (e.isIntersecting) {{ show(e.target); io.unobserve(e.target); }} }});
}}, {{rootMargin: "200px"}}) : null;
imgs.forEach(function (img) {{ io ? io.observe(img) : show(img); }});
document.getElementById("find").oninput = function () {{
  var q = this.value.toLowerCase();
  [].forEach.call(document.querySelectorAll(".icons button"), function (b) {{
    b.style.display = b.title.toLowerCase().indexOf(q) < 0 ? "none" : "";
  }});
}};
</script></body></html>"""


def edit_dialog(profiles, store, query, form):
    """The edit page for the player owning access_token; POSTs apply one change and show the page again."""
    value = lambda key: (form.get(key) or query.get(key) or [""])[0]  # noqa: E731
    token, redirect = value("access_token"), value("redirect_uri") or "/fb/connect/login_success.html"
    close = redirect + ("&" if "?" in redirect else "?") + "request=revival_profile"
    uid = store.uid_for_token(token)
    if uid is None:
        body = EDIT_PAGE.split("<h2>")[0].format(close=html.escape(close),
                                                 message='<p class="msg err">Your login has expired. '
                                                         'Log in again from the game.</p>')
        return 200, "text/html; charset=utf-8", (body + "</body></html>").encode("utf-8")
    message = ""
    if form.get("action"):
        result = profiles.update(uid, form)
        done = {"card": "Picture changed.", "icon": "Picture changed.", "rename": "Username changed.", "password": "Password changed.",
                "deck": "Online deck changed."}
        message = (f'<p class="msg err">{html.escape(result["error"])}</p>' if "error" in result else
                   f'<p class="msg">{done.get(value("action"), "Saved.")}</p>')
    user = store.user_by_uid(uid)
    main = "/fb/dialog/revival_profile?" + urllib.parse.urlencode({"access_token": token, "redirect_uri": redirect})
    hidden = "".join(f'<input type="hidden" name="{k}" value="{html.escape(v)}">'
                     for k, v in (("access_token", token), ("redirect_uri", redirect)))
    if value("view") == "picture" and not form.get("action"):
        names, current = profiles.card_names(), store.get_player_data(uid, "icon_card")
        owned = {}  # name -> template id: a few cards exist as two templates with the same name and picture
        for c in sorted(profiles.owned_cards(uid)):
            owned.setdefault(names[str(c)], c)
        chosen = names.get(str(current))
        cards = "".join(f'<button name="card" value="{c}" title="{html.escape(name)}"'
                        f'{" class=sel" if name == chosen else ""}><img data-src="/fb/graph/revival_cards/{c}" alt="">'
                        f'</button>' for name, c in sorted(owned.items(), key=lambda nc: nc[0].lower()))
        style = EDIT_PAGE.split("<style>", 1)[1].split("</style>", 1)[0].replace("{{", "{").replace("}}", "}")
        body = PICTURE_PAGE.format(style=style, back=html.escape(main), main=html.escape(main), hidden=hidden,
                                   count=len(owned), cards=cards or '<p class="hint">No cards yet.</p>')
        return 200, "text/html; charset=utf-8", body.encode("utf-8")
    decks = profiles.decks(profiles.save_items(uid)) if profiles.decks else []
    chosen = store.get_player_data(uid, "defense_deck")
    rows = []
    for d in [{"id": "auto", "name": "Automatic (arena deck, else default deck)", "cards": None}] +             [d for d in decks if d["cards"]]:
        on = (d["id"] == "auto" and chosen is None) or d["id"] == chosen
        count = "" if d["cards"] is None else f' ({len(d["cards"])} cards)'
        button = "<b>In use</b>" if on else (f'<form method="post">{hidden}<input type="hidden" name="action" value="deck">'
                                            f'<button name="deck" value="{d["id"]}">Use</button></form>')
        rows.append(f'<div class="deck"><span>{html.escape(d["name"])}{count}</span>{button}</div>')
    picture = f"/fb/graph/{uid}/picture?t={int(time.time())}"
    body = EDIT_PAGE.format(close=html.escape(close), message=message, hidden=hidden, picture=picture,
                            choose=html.escape(main + "&view=picture"), decks="".join(rows),
                            name=html.escape(user["username"]))
    return 200, "text/html; charset=utf-8", body.encode("utf-8")
