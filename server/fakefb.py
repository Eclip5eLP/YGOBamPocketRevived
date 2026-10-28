"""
Stand-in for the few Facebook endpoints the client uses, served under /fb on the revival
server. The client is patched to call these instead of facebook.com (tools/patch_swf.py
string_patches). Nothing is ever sent to Facebook.

Flow (client code references in work/as3):
  1. Login button -> FacebookManagerMobile.Authorize opens  <fb>/dialog/oauth?client_id&
     redirect_uri=fb<appId>://authorize&...  in the external browser (FacebookManagerMobile.as:395-412).
  2. Our page: username + password, "Log in" or "Create account". After a login the browser keeps a
     remember cookie (REMEMBER_COOKIE, path /fb/), so the next login is one "Continue as <name>" tap.
  3. Success -> browser goes to  fb<appId>://authorize#access_token=..&expires_in=..  which Android
     routes to the app (manifest VIEW filter, scheme fb145583478967400); OnInvoke -> ProcessLogin
     reads access_token / expires_in (FacebookManagerMobile.as:101-121, 235-261).
  4. FacebookMobile.init -> GET <fb>/graph/me?access_token=.. ; id becomes the player's uid
     (FacebookMobile.as:211-232, FacebookManagerMobile.as:132-162).
  5. FQL friends: GET/POST <fb>/api/method/fql.query?query=..&format=json -> array of
     {uid, name, first_name, is_app_user} (FacebookManagerMobile.as:382-393, 190-219).
     Friends are is_app_user=true (Duel Ground, friend help: GetFriendList(true)); every other
     registered player is is_app_user=false, which the game lists under "Invite friends"
     (InviteFriendsPopup: GetFriendList(false)). Players with a pending request to you are marked.
  7. Invite: the game opens <fb>/dialog/apprequests?to=<uids>&access_token=..&redirect_uri=.. in an
     in-game StageWebView (FacebookManagerMobile.InviteFriends, DialogWindow.as). Each invite is a
     friend request; inviting someone who already invited you makes you friends. The page's Close
     link goes to redirect_uri (LOGIN_SUCCESS_URL), which closes the web view.
  6. Pictures: <fb>/graph/<id>/picture (AbstractFacebook.as:235-238).
"""

import html
import json
import re
import struct
import urllib.parse
import zlib

from accounts import AccountError, AccountStore
from arena import bot_name

APP_ID = "145583478967400"
ALLOWED_REDIRECT = f"fb{APP_ID}://authorize"


def _png(width=50, height=50, rgb=(40, 70, 140)):
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


DEFAULT_PICTURE = _png()

STYLE = """body{margin:0;font-family:sans-serif;background:#0b1730;color:#eef;display:flex;justify-content:center}
main{max-width:380px;width:100%;padding:24px 16px}
h1{font-size:20px;margin:8px 0 16px;text-align:center}
input{width:100%;box-sizing:border-box;padding:12px;margin-bottom:10px;font-size:16px;border-radius:6px;border:1px solid #456;background:#12244a;color:#fff}
.row{display:flex;gap:10px;margin-top:6px}
button,a.btn{flex:1;padding:14px;font-size:16px;border:0;border-radius:6px;color:#fff;text-align:center;text-decoration:none;display:block;background:#2d6cdf}
.alt{background:#3a8f3a} .link{background:none;color:#aac;font-size:14px;margin-top:14px}
.err{background:#5a1d1d;padding:10px;border-radius:6px;margin-bottom:12px;font-size:14px}"""

HEAD = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yu-Gi-Oh! BAM Pocket</title><style>""" + STYLE.replace("{", "{{").replace("}", "}}") + """</style></head><body><main>
<h1>Yu-Gi-Oh! BAM Pocket</h1>"""

PAGE = HEAD + """{error}
<form method="post" action="{action}">
<input type="hidden" name="redirect_uri" value="{redirect}">
<input name="username" placeholder="Username" autocomplete="username" value="{username}" required>
<input name="password" type="password" placeholder="Password" autocomplete="current-password" required>
<div class="row"><button name="action" value="login">Log in</button>
<button class="alt" name="action" value="register">Create account</button></div>
</form></main></body></html>"""

# shown when the browser still remembers an account (REMEMBER_COOKIE): one tap back into the game
CONTINUE_PAGE = HEAD + """
<form method="post" action="{action}">
<input type="hidden" name="redirect_uri" value="{redirect}">
<button name="action" value="continue" style="width:100%">Continue as {name}</button>
<button class="link" name="action" value="switch" style="width:100%">Use another account</button>
</form></main></body></html>"""

DONE = HEAD + """
<a class="btn" href="{url}">Return to the game</a></main>
<script>window.location.href = {url_js};</script></body></html>"""


# shown in the game's 800x400 invite web view: Close first, short lines
INVITE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;font-family:sans-serif;background:#0b1730;color:#eef;padding:8px;font-size:13px}}
p{{margin:4px 0}} a{{display:block;margin-bottom:8px;padding:8px;background:#2d6cdf;color:#fff;
text-align:center;border-radius:6px;text-decoration:none;font-size:15px}}</style></head>
<body><a href="{close}">Close</a>{lines}</body></html>"""

REMEMBER_COOKIE = "ygo_remember"
REMEMBER_SECONDS = 60 * 24 * 3600


class FakeFacebook:
    def __init__(self, store: AccountStore, logger):
        self.store = store
        self.log = logger

    # returns (status, content_type, body[, set_cookie_headers]) or None if the path is not ours
    def handle(self, method: str, path: str, query: dict, form: dict, ip: str, cookies: dict = None):
        cookies = cookies or {}
        if path == "/fb/dialog/oauth":
            if method == "POST":
                return self._oauth_post(form, ip, cookies)
            user = self._remembered(cookies)
            if user is not None:
                body = CONTINUE_PAGE.format(action="/fb/dialog/oauth", redirect=html.escape(ALLOWED_REDIRECT),
                                            name=html.escape(user["username"]))
                return 200, "text/html; charset=utf-8", body.encode("utf-8")
            return self._page(ALLOWED_REDIRECT)
        if path.startswith("/fb/graph/"):
            rest = path[len("/fb/graph/"):]
            # the client asks for versioned Graph paths, e.g. /fb/graph/v2.0/me (seen on device)
            if re.match(r"^v\d+\.\d+/", rest):
                rest = rest.split("/", 1)[1]
            if rest == "me":
                return self._me(query)
            return self._graph_object(rest, query)
        if path.startswith("/fb/api/method/fql."):
            return self._fql_friends(query or form)
        if path.startswith("/fb/dialog/apprequests"):
            return self._apprequests(query, ip)
        if path in ("/fb/logout.php", "/fb/connect/login_success.html"):
            return 200, "text/html; charset=utf-8", b"<html><body>OK</body></html>"
        return None

    def _page(self, redirect, error="", username=""):
        if redirect != ALLOWED_REDIRECT:
            redirect = ALLOWED_REDIRECT
        body = PAGE.format(error=f'<div class="err">{html.escape(error)}</div>' if error else "",
                           action="/fb/dialog/oauth", redirect=html.escape(redirect),
                           username=html.escape(username))
        return 200, "text/html; charset=utf-8", body.encode("utf-8")

    def _remembered(self, cookies):
        uid = self.store.uid_for_token(cookies.get(REMEMBER_COOKIE, ""))
        return self.store.user_by_uid(uid) if uid else None

    def _oauth_post(self, form, ip, cookies):
        username = form.get("username", [""])[0].strip()
        password = form.get("password", [""])[0]
        action = form.get("action", ["login"])[0]
        if action == "switch":
            page = self._page(ALLOWED_REDIRECT)
            return page + ([f"{REMEMBER_COOKIE}=; Path=/fb/; Max-Age=0; HttpOnly; SameSite=Lax"],)
        try:
            if action == "continue":
                user = self._remembered(cookies)
                if user is None:
                    raise AccountError("Please log in again.")
                self.log.info("[%s] FB: remembered login '%s' uid %s", ip, user["username"], user["uid"])
            elif action == "register":
                user = self.store.register(username, password)
                self.log.info("[%s] FB: registered account '%s' uid %s", ip, user["username"], user["uid"])
            else:
                user = self.store.authenticate(username, password)
                self.log.info("[%s] FB: login '%s' uid %s", ip, user["username"], user["uid"])
        except AccountError as e:
            self.log.info("[%s] FB: %s failed for '%s': %s", ip, action, username, e)
            return self._page(ALLOWED_REDIRECT, str(e), username)
        token = self.store.issue_token(user["uid"])
        url = f"{ALLOWED_REDIRECT}#access_token={urllib.parse.quote(token)}&expires_in=5184000"
        body = DONE.format(url=html.escape(url), url_js=json.dumps(url))
        remember = self.store.issue_token(user["uid"])
        cookie = f"{REMEMBER_COOKIE}={remember}; Path=/fb/; Max-Age={REMEMBER_SECONDS}; HttpOnly; SameSite=Lax"
        return 200, "text/html; charset=utf-8", body.encode("utf-8"), [cookie]

    INCOMING_MARK = "(!) "

    def _fql_friends(self, params):
        uid = self.store.uid_for_token(params.get("access_token", [""])[0])
        if uid is None:
            err = {"error_code": 190, "error_msg": "Invalid OAuth access token."}
            return 400, "application/json", json.dumps(err).encode()
        friends = set(self.store.friends_of(uid))
        incoming = set(self.store.incoming_requests(uid))
        rows = []
        for user in self.store.all_users():
            if user["uid"] == uid:
                continue
            is_friend = user["uid"] in friends
            name = user["username"]
            if not is_friend and user["uid"] in incoming:
                name = self.INCOMING_MARK + name
            rows.append({"uid": user["uid"], "name": name, "first_name": name, "is_app_user": is_friend})
        return 200, "application/json", json.dumps(rows).encode()

    def _apprequests(self, query, ip):
        uid = self.store.uid_for_token(query.get("access_token", [""])[0])
        close_url = query.get("redirect_uri", [""])[0] or "/fb/connect/login_success.html"
        close_url += ("&" if "?" in close_url else "?") + "request=revival"
        lines = []
        if uid is None:
            lines.append("Your login has expired. Log in again from the game.")
        else:
            for other in [u for u in query.get("to", [""])[0].split(",") if u.strip().isdigit()][:50]:
                user = self.store.user_by_uid(other.strip())
                try:
                    result = self.store.request_friend(uid, other.strip())
                except AccountError:
                    continue
                name = html.escape(user["username"])
                lines.append({"friends": f"<b>{name}</b>: you are now friends.",
                              "requested": f"<b>{name}</b>: request sent.",
                              "already": f"<b>{name}</b>: already sent."}[result])
                self.log.info("[%s] FB: %s -> %s friend request: %s", ip, uid, other, result)
            if not lines:
                lines.append("No players selected.")
            lines.append("New friends appear after restarting the game.")
        body = INVITE_PAGE.format(lines="".join(f"<p>{ln}</p>" for ln in lines), close=html.escape(close_url))
        return 200, "text/html; charset=utf-8", body.encode("utf-8")

    @staticmethod
    def _user_json(user):
        return {"id": user["uid"], "name": user["username"], "first_name": user["username"],
                "last_name": "", "locale": "en_US", "gender": "", "verified": True, "timezone": 0}

    def _me(self, query):
        uid = self.store.uid_for_token(query.get("access_token", [""])[0])
        user = self.store.user_by_uid(uid) if uid else None
        if user is None:
            # HTTP 200 with error_code makes the client report a failure with this object
            # (AbstractFacebook.handleRequestLoad); the "error" field tells the patched
            # OnInitFacebookComplete to forget the saved token (tools/patch_swf.py PCODE_INSERTIONS)
            err = {"error": {"message": "Invalid OAuth access token.", "type": "OAuthException", "code": 190},
                   "error_code": 190, "error_msg": "Invalid OAuth access token."}
            return 200, "application/json", json.dumps(err).encode()
        return 200, "application/json", json.dumps(self._user_json(user)).encode()

    def _graph_object(self, rest, query):
        parts = [p for p in rest.split("/") if p]
        if not parts:
            return 404, "application/json", b'{"error":{"message":"not found"}}'
        if len(parts) >= 2 and parts[1] == "picture":
            return 200, "image/png", DEFAULT_PICTURE
        user = self.store.user_by_uid(parts[0])
        if user is None and bot_name(parts[0]):  # arena practice bots (server/arena.py)
            user = {"uid": parts[0], "username": bot_name(parts[0])}
        if user is None:
            return 404, "application/json", b'{"error":{"message":"Unknown user"}}'
        return 200, "application/json", json.dumps(self._user_json(user)).encode()
