"""
Friends manager page for the game's in-app web view (Duel Ground > Friends button, notes/todo.md "Friends
rewrite"): GET/POST /fb/dialog/revival_friends with the player's access_token.

Tabs: Friends (remove, profile), Requests (people who added you: accept / decline; your pending requests:
cancel), Find players (every player, 40 per page, filtered by name: add). "Profile" closes the view with ...login_success.html?view=<uid>;
the game then opens that player's profile (as3_new/com/revival/friends).
Friendships use AccountStore (request_friend: a request to someone who requested you makes you friends;
remove_friend: removes the friendship and pending requests both ways).
"""

import html
import urllib.parse

from accounts import AccountError

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;font-family:sans-serif;background:#0b1730;color:#eef;padding:8px;font-size:14px}}
a.close{{display:block;padding:9px;background:#2d6cdf;color:#fff;text-align:center;border-radius:6px;
text-decoration:none;font-size:15px}} .tabs{{display:flex;gap:4px;margin:8px 0}} .tabs a{{flex:1;padding:8px 2px;
text-align:center;border-radius:6px;background:#12244a;color:#aac;text-decoration:none}} .tabs a.on{{background:#2d6cdf;
color:#fff}} .row{{display:flex;align-items:center;gap:8px;padding:6px;border-bottom:1px solid #1d3360}}
.row img{{width:40px;height:40px;border-radius:4px}} .row .n{{flex:1;overflow:hidden;text-overflow:ellipsis}}
.row form{{margin:0}} button,.row a.b{{padding:7px 10px;border:0;border-radius:6px;background:#2d6cdf;color:#fff;
font-size:13px;text-decoration:none;display:inline-block}} .alt{{background:#3a8f3a!important}} .red{{background:#8a2b2b!important}}
.msg{{padding:8px;border-radius:6px;margin:8px 0;background:#1d4a2a}} .err{{background:#5a1d1d}}
.search{{display:flex;gap:6px}} .search input{{flex:1;padding:8px;font-size:15px;border-radius:6px;border:1px solid #456;
background:#12244a;color:#fff}} p.e{{color:#99a;margin:10px 4px}} h3{{font-size:13px;color:#aac;margin:12px 4px 2px}}
.nav{{display:flex;justify-content:space-between;align-items:center;margin:10px 0}}</style>
</head><body><a class="close" href="{close}">Close</a>
<div class="tabs">{tabs}</div>{message}{body}</body></html>"""

TABS = (("friends", "Friends"), ("requests", "Requests"), ("find", "Find players"))
PAGE_SIZE = 40


class FriendsPage:
    def __init__(self, store, logger):
        self.store = store
        self.log = logger

    def handle(self, query, form):
        value = lambda key: (form.get(key) or query.get(key) or [""])[0]  # noqa: E731
        token, redirect = value("access_token"), value("redirect_uri") or "/fb/connect/login_success.html"
        tab = value("tab") if value("tab") in dict(TABS) else "friends"
        uid = self.store.uid_for_token(token)
        base = {"access_token": token, "redirect_uri": redirect}
        link = lambda **kw: "?" + urllib.parse.urlencode({**base, **kw})  # noqa: E731
        close = redirect + ("&" if "?" in redirect else "?") + "request=revival_friends"
        if uid is None:
            return self._page(close, "", '<p class="msg err">Your login has expired. Log in again from the game.</p>', "")

        message = ""
        action, other = value("action"), value("uid")
        if action and other.isdigit():
            message = self._apply(uid, action, other)

        tabs = "".join(f'<a class="{"on" if key == tab else ""}" href="{html.escape(link(tab=key))}">{label}'
                       f'{self._badge(uid) if key == "requests" else ""}</a>' for key, label in TABS)
        hidden = "".join(f'<input type="hidden" name="{k}" value="{html.escape(v)}">' for k, v in base.items())
        hidden += f'<input type="hidden" name="tab" value="{tab}">'
        search_hidden = hidden
        if tab == "find":
            hidden += (f'<input type="hidden" name="q" value="{html.escape(value("q"))}">'
                       f'<input type="hidden" name="page" value="{html.escape(value("page"))}">')

        def row(user, *buttons):
            pic = f'/fb/graph/{user["uid"]}/picture'
            view = html.escape(redirect + ("&" if "?" in redirect else "?") + "request=revival_friends&view=" + user["uid"])
            acts = "".join(f'<form method="post">{hidden}<input type="hidden" name="uid" value="{user["uid"]}">'
                           f'<button name="action" value="{a}" class="{cls}">{label}</button></form>'
                           for a, label, cls in buttons)
            return (f'<div class="row"><img src="{pic}" alt="" loading="lazy"><span class="n">{html.escape(user["username"])}</span>'
                    f'<a class="b" href="{view}">Profile</a>{acts}</div>')

        users = lambda uids: [u for u in (self.store.user_by_uid(x) for x in uids) if u]  # noqa: E731
        if tab == "friends":
            friends = sorted(users(self.store.friends_of(uid)), key=lambda u: u["username"].lower())
            body = "".join(row(u, ("remove", "Remove", "red")) for u in friends) or \
                '<p class="e">No friends yet. Find players in the third tab.</p>'
        elif tab == "requests":
            incoming = users(self.store.incoming_requests(uid))
            outgoing = users(self.store._entry(uid)["outgoing"])
            body = "<h3>Added you</h3>" + ("".join(row(u, ("add", "Accept", "alt"), ("remove", "Decline", "red"))
                                                   for u in incoming) or '<p class="e">No requests.</p>')
            body += "<h3>Sent by you</h3>" + ("".join(row(u, ("remove", "Cancel", "red")) for u in outgoing)
                                              or '<p class="e">None pending.</p>')
        else:
            # every player, newest first; the search box filters by name (prefix matches first). Pages of PAGE_SIZE
            # rows keep the page small with any number of players; pictures load lazily.
            q = value("q").strip()
            page = int(value("page")) if value("page").isdigit() else 0
            body = (f'<form method="get" class="search">{search_hidden}<input name="q" value="{html.escape(q)}" '
                    f'placeholder="Filter by name" autocomplete="off"><button>Filter</button></form>')
            friends, outgoing = set(self.store.friends_of(uid)), set(self.store._entry(uid)["outgoing"])
            incoming = set(self.store.incoming_requests(uid))
            players = [u for u in self.store.all_users() if u["uid"] != uid and q.lower() in u["username"].lower()]
            if q:
                players.sort(key=lambda u: (not u["username"].lower().startswith(q.lower()), u["username"].lower()))
            else:
                players.sort(key=lambda u: -u.get("created", 0))
            pages = max(1, (len(players) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = min(page, pages - 1)
            rows = []
            for u in players[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
                if u["uid"] in friends:
                    rows.append(row(u))
                elif u["uid"] in outgoing:
                    rows.append(row(u, ("remove", "Cancel", "red")))
                elif u["uid"] in incoming:
                    rows.append(row(u, ("add", "Accept", "alt")))
                else:
                    rows.append(row(u, ("add", "Add", "alt")))
            body += f'<p class="e">{len(players)} player{"s" if len(players) != 1 else ""}</p>'
            body += "".join(rows) or '<p class="e">No player found.</p>'
            if pages > 1:
                nav = []
                if page > 0:
                    nav.append(f'<a class="b" href="{html.escape(link(tab="find", q=q, page=page - 1))}">Previous</a>')
                nav.append(f'<span class="e">Page {page + 1} / {pages}</span>')
                if page < pages - 1:
                    nav.append(f'<a class="b" href="{html.escape(link(tab="find", q=q, page=page + 1))}">Next</a>')
                body += '<div class="nav">' + "".join(nav) + "</div>"
        return self._page(close, tabs, message, body)

    def _badge(self, uid):
        n = len(self.store.incoming_requests(uid))
        return f" ({n})" if n else ""

    def _apply(self, uid, action, other):
        user = self.store.user_by_uid(other)
        if user is None:
            return '<p class="msg err">Unknown player.</p>'
        name = html.escape(user["username"])
        try:
            if action == "add":
                result = self.store.request_friend(uid, other)
                text = {"friends": f"You are now friends with {name}.", "requested": f"Request sent to {name}.",
                        "already": f"Already sent to {name}."}[result]
            elif action == "remove":
                self.store.remove_friend(uid, other)
                text = f"{name} removed."
            else:
                return '<p class="msg err">Unknown action.</p>'
        except AccountError as e:
            return f'<p class="msg err">{html.escape(str(e))}</p>'
        self.log.info("friends page %s: %s %s", uid, action, other)
        return f'<p class="msg">{text}</p>'

    @staticmethod
    def _page(close, tabs, message, body):
        page = PAGE.format(close=html.escape(close), tabs=tabs, message=message, body=body)
        return 200, "text/html; charset=utf-8", page.encode("utf-8")
