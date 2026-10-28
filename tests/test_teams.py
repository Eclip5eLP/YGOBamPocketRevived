#!/usr/bin/env python3
"""
Phase 3 teams + tournament registration against a running (dev) server, fresh account A:
GetTeam 0 -> JoinTeam picks a team -> GetTeam returns it -> NewScore needs the token from GetNewScoreToken
-> player/team info show the score -> CancelJoinTeam leaves. Tournament: level null before
RegisterTournament, level 81 after, A on the top leaderboard.

Usage: python tests/test_teams.py [--base http://127.0.0.1:8087]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_friends import Player  # noqa: E402
from test_login_flow import P  # noqa: E402

G = P + "guild.amf."
T = P + "tournament.amf."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8087")
    a = Player(ap.parse_args().base)
    print("A", a.name, a.uid)

    assert a.amf(G + "GetTeamRequest")["teamTemplateId"] == 0
    team = a.amf(G + "JoinTeamRequest")["teamTemplateId"]
    assert 1 <= team <= 20 and a.amf(G + "GetTeamRequest")["teamTemplateId"] == team
    print("joined team", team)

    assert a.amf(G + "NewScoreRequest", {"score": 50, "token": 12345})["score"] == 0, "score without token"
    tok = a.amf(G + "GetNewScoreTokenRequest")["token"]
    assert a.amf(G + "NewScoreRequest", {"score": 50, "token": tok})["score"] == 50
    assert a.amf(G + "NewScoreRequest", {"score": 50, "token": tok})["score"] == 0, "token reused"
    me = a.amf(G + "GetPlayerInfoRequest")["playerGuildInfo"]
    assert me["score"] == 50 and me["rank"] >= 1 and me["externalId"] == float(a.uid), me
    info = a.amf(G + "GetTeamInfoRequest", {"teamTemplateId": team})
    assert info["teamScore"] >= 50 and 1 <= info["teamRank"] <= 20, info
    assert any(p["externalId"] == float(a.uid) for p in info["top50"])
    print("team score OK: rank", info["teamRank"], "score", info["teamScore"])
    assert a.amf(G + "CancelJoinTeamRequest")["exception"] is None
    assert a.amf(G + "GetTeamRequest")["teamTemplateId"] == 0
    print("leave OK")

    ti = a.amf(T + "GetTournamentInfoRequest")
    assert ti["tournament"]["tournementTemplateId"] >= 2 and ti["tournamentLevel"] is None, ti
    reg = a.amf(T + "RegisterTournamentRequest")
    assert reg["tournementLevel"]["levelTemplateId"] == 81, reg
    assert a.amf(T + "GetTournamentInfoRequest")["tournamentLevel"]["levelTemplateId"] == 81
    top = a.amf(T + "GetTopTournamentLeaderboardRequest", {"numberPlayers": 50})["tournamentLevel"]
    assert any(t["externalId"] == float(a.uid) for t in top), top
    prev = a.amf(T + "GetPreviousTopTournamentLeaderboardRequest", {"numberPlayers": 3})
    assert prev["exception"] is None
    print("tournament registration + leaderboards OK")
    print("ALL OK")


if __name__ == "__main__":
    main()
