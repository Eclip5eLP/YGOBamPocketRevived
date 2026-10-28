"""
Stand-in for the few Facebook endpoints the client uses, served under /fb on the revival
server. The client is patched to call these instead of facebook.com (tools/patch_swf.py
string_patches). Nothing is ever sent to Facebook.

Flow (client code references in work/as3):
  1. Login button -> FacebookManagerMobile.Authorize opens  <fb>/dialog/oauth?client_id&
     redirect_uri=fb<appId>://authorize&...  in the external browser (FacebookManagerMobile.as:395-412).
  2. Our page: username + password, "Log in" or "Create account".
  3. Success -> browser goes to  fb<appId>://authorize#access_token=..&expires_in=..  which Android
     routes to the app (manifest VIEW filter, scheme fb145583478967400); OnInvoke -> ProcessLogin
     reads access_token / expires_in (FacebookManagerMobile.as:101-121, 235-261).
  4. FacebookMobile.init -> GET <fb>/graph/me?access_token=.. ; id becomes the player's uid
     (FacebookMobile.as:211-232, FacebookManagerMobile.as:132-162).
  5. FQL friends: GET/POST <fb>/api/method/fql.query?query=..&format=json -> array of
     {uid, name, first_name, is_app_user} (FacebookManagerMobile.as:382-393, 190-219).
     Phase 1: empty list.
  6. Pictures: <fb>/graph/<id>/picture (AbstractFacebook.as:235-238).
"""

import html
import json
import re
import struct
import urllib.parse
import zlib

from accounts import AccountError, AccountStore

APP_ID = "145583478967400"
ALLOWED_REDIRECT = f"fb{APP_ID}://authorize"


def _png(width=50, height=50, rgb=(40, 70, 140)):
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


DEFAULT_PICTURE = _png()

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yu-Gi-Oh! BAM Pocket - Login</title>
<style>
body{{margin:0;font-family:sans-serif;background:#0b1730;color:#eef;display:flex;justify-content:center}}
main{{max-width:420px;width:100%;padding:24px 16px}}
h1{{font-size:22px;margin:8px 0 4px}} p{{color:#aac;font-size:14px}}
label{{display:block;margin:14px 0 4px;font-size:14px}}
input{{width:100%;box-sizing:border-box;padding:12px;font-size:16px;border-radius:6px;border:1px solid #456;background:#12244a;color:#fff}}
.row{{display:flex;gap:10px;margin-top:20px}}
button,a.btn{{flex:1;padding:14px;font-size:16px;border:0;border-radius:6px;color:#fff;text-align:center;text-decoration:none;display:block}}
.login{{background:#2d6cdf}} .register{{background:#3a8f3a}}
.err{{background:#5a1d1d;padding:10px;border-radius:6px;margin-top:12px}}
</style></head><body><main>
<h1>Yu-Gi-Oh! BAM Pocket</h1>
<p>Private preservation server account. This is not Facebook.</p>
{error}
<form method="post" action="{action}">
<input type="hidden" name="redirect_uri" value="{redirect}">
<label for="u">Username</label><input id="u" name="username" autocomplete="username" value="{username}" required>
<label for="p">Password</label><input id="p" name="password" type="password" autocomplete="current-password" required>
<div class="row"><button class="login" name="action" value="login">Log in</button>
<button class="register" name="action" value="register">Create account</button></div>
</form></main></body></html>"""

DONE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Logged in</title>
<style>body{{margin:0;font-family:sans-serif;background:#0b1730;color:#eef;display:flex;justify-content:center}}
main{{max-width:420px;width:100%;padding:24px 16px}} a{{display:block;padding:16px;background:#2d6cdf;color:#fff;
text-align:center;border-radius:6px;text-decoration:none;font-size:18px;margin-top:20px}}</style></head>
<body><main><h1>Logged in as {name}</h1><p>Returning to the game...</p>
<a id="go" href="{url}">Return to the game</a></main>
<script>window.location.href = {url_js};</script></body></html>"""


class FakeFacebook:
    def __init__(self, store: AccountStore, logger):
        self.store = store
        self.log = logger

    # returns (status, content_type, body_bytes) or None if the path is not ours
    def handle(self, method: str, path: str, query: dict, form: dict, ip: str):
        if path == "/fb/dialog/oauth":
            if method == "POST":
                return self._oauth_post(form, ip)
            redirect = query.get("redirect_uri", [ALLOWED_REDIRECT])[0]
            return self._page(redirect)
        if path.startswith("/fb/graph/"):
            rest = path[len("/fb/graph/"):]
            # the client asks for versioned Graph paths, e.g. /fb/graph/v2.0/me (seen on device)
            if re.match(r"^v\d+\.\d+/", rest):
                rest = rest.split("/", 1)[1]
            if rest == "me":
                return self._me(query)
            return self._graph_object(rest, query)
        if path.startswith("/fb/api/method/fql."):
            return 200, "application/json", b"[]"
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

    def _oauth_post(self, form, ip):
        username = form.get("username", [""])[0].strip()
        password = form.get("password", [""])[0]
        action = form.get("action", ["login"])[0]
        try:
            if action == "register":
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
        body = DONE.format(name=html.escape(user["username"]), url=html.escape(url), url_js=json.dumps(url))
        return 200, "text/html; charset=utf-8", body.encode("utf-8")

    @staticmethod
    def _user_json(user):
        return {"id": user["uid"], "name": user["username"], "first_name": user["username"],
                "last_name": "", "locale": "en_US", "gender": "", "verified": True, "timezone": 0}

    def _me(self, query):
        uid = self.store.uid_for_token(query.get("access_token", [""])[0])
        user = self.store.user_by_uid(uid) if uid else None
        if user is None:
            err = {"error": {"message": "Invalid OAuth access token.", "type": "OAuthException", "code": 190}}
            return 400, "application/json", json.dumps(err).encode()
        return 200, "application/json", json.dumps(self._user_json(user)).encode()

    def _graph_object(self, rest, query):
        parts = [p for p in rest.split("/") if p]
        if not parts:
            return 404, "application/json", b'{"error":{"message":"not found"}}'
        if len(parts) >= 2 and parts[1] == "picture":
            return 200, "image/png", DEFAULT_PICTURE
        user = self.store.user_by_uid(parts[0])
        if user is None:
            return 404, "application/json", b'{"error":{"message":"Unknown user"}}'
        return 200, "application/json", json.dumps(self._user_json(user)).encode()
