"""
Live PvP (phase 4): tournament matchmaking and the lockstep duel relay. notes/findings.md 6.30, 6.45.

The phones simulate the duel themselves; the server pairs players, relays each round's placed cards and compares
the checksums both phones send (module/cardgame/flowhandling/flowhandler/LivePvPFlow.as:158-300,
project/livepvp/LivePvPManager.as). All of it travels on the PvP connection (Tournament, ReadyForCombat and LivePvP
DALs use ManagerA.PvpEngineCom). Server-to-client messages are queued per player and appended to the next response
on that player's PvP connection (EngineServerCom.OnReceivedData dispatches every object of a response array); the
search popup switches that connection to a 2 s ping (YGOMPvPLogin.EnterPvpMode, mmog.xml ping_pvp_frequency).

Flow:
  queue    PlayCombatTournament{cards} -> waiting, or matched with the oldest waiting player:
           both get NewCombatNotification{combat} and StartDuelNotification{player1Id (starts, random),
           player2Id, player1Deck, player2Deck (template ids), player1/2NbrFriend}.
           CancelTournamentMatch removes you from the queue.
  start    StartRound from both -> StartRoundNotification to both (once, after the coin flip).
  round    BamReady{slotCard, checksumBefore, roundNumber} from both -> equal checksums: each gets
           BamReadyNotification{slotCard of the opponent}; different: ChecksumErrorNotification to both.
           BamReady{forfeit} -> the opponent gets OpponentSurrenderedNotification; the duel ends.
  end      BamEnd{checksum, externalIdWinner} from both -> BamEndNotification{winnerExternalId, redeemCode 0};
           a winner != 0 ends the duel.
  timeout  an opponent who sends nothing on the PvP connection for DISCONNECT_SECONDS gets reported to the other
           player as OpponentDisconnectedNotification and the duel ends.
  challenge  friend live duels (as3_new/com/revival/friends/LiveChallenge.as): the challenger names a friend
           (set_challenge, POST /fb/graph/me/revival_challenge) and then queues like for the tournament; a player
           with a challenge only pairs with that friend when the friend queues with a challenge back (accepting from
           the friends page does that), never with strangers. incoming_challenges lists who is waiting for you.
           Challenge duels don't count for the tournament ladder.
  result   a ranked duel that ends with a winner (BamEnd, surrender, disconnect, or leaving it for a new search) moves both
           players on the tournament ladder (Teams.record_result) and both get PlayCombatEndNotification{tournamentLevel}
           with their new level. An out-of-sync duel counts for nobody.
"""

import random
import threading
import time

import amf3

P = "com.frimastudio.snowstorm.project."
DISCONNECT_SECONDS = 45
# online = any request in this window. While the game runs it pings every 30 s (10 s in APKs before 1.1, mmog.xml
# ping_frequency) and polls for challenges every 20 s from the main menu on (notes 6.50).
ONLINE_SECONDS = 70
QUEUE_SECONDS = 600


def _card_ids(cards):
    ids = []
    for c in cards or []:
        tid = c.get("itemTemplateId") if hasattr(c, "get") else None
        if isinstance(tid, (int, float)) and tid > 0:
            ids += [int(tid)] * max(1, int(c.get("quantity") or 1))
    return ids


class Duel:
    def __init__(self, combat_id, p1, p2, decks, ranked=True):
        self.id = combat_id
        self.players = (p1, p2)
        self.decks = decks
        self.ranked = ranked
        self.started = set()
        self.ready = {}  # uid -> (round, checksum, slotCard)
        self.ended = {}  # uid -> (checksum, winner)
        self.over = False

    def other(self, uid):
        return self.players[1] if uid == self.players[0] else self.players[0]


class LivePvP:
    def __init__(self, store, teams, logger):
        self.store = store
        self.teams = teams
        self.log = logger
        self.lock = threading.Lock()
        self.queue = []  # [(uid, deck ids, friends, time, challenged uid or None)]
        self.challenges = {}  # uid -> (challenged uid, time)
        self.duels = {}  # uid -> Duel
        self.outbox = {}  # uid -> [encoded notification]
        self.last_seen = {}  # uid -> time of the last PvP request
        self.presence = {}  # uid -> time of the last request on any connection (online status)
        self.next_combat = 1
        self.rewards = None  # server/rewards.py (tournament milestones), set by server.py

    # --- delivery -------------------------------------------------------------------------------
    def _notify(self, uid, alias, props):
        self.outbox.setdefault(uid, []).append(amf3.encode_typed_object(alias, props))

    def drain(self, uid):
        """Notifications for uid, appended to the response of any request on its PvP connection."""
        with self.lock:
            self.last_seen[uid] = time.time()
            self._check_timeouts()
            return self.outbox.pop(uid, [])

    def _check_timeouts(self):
        now = time.time()
        self.queue = [q for q in self.queue if now - q[3] < QUEUE_SECONDS and now - self.last_seen.get(q[0], now) < DISCONNECT_SECONDS]
        for uid, duel in list(self.duels.items()):
            other = duel.other(uid)
            if not duel.over and now - self.last_seen.get(other, now) > DISCONNECT_SECONDS:
                self.log.info("live pvp %s: %s timed out", duel.id, other)
                self._notify(uid, P + "readyforcombat.amf.OpponentDisconnectedNotification", {"opponentExternalId": float(other)})
                self._finish(duel, winner=uid)

    def _finish(self, duel, winner=None):
        duel.over = True
        for uid in duel.players:
            if self.duels.get(uid) is duel:
                del self.duels[uid]
        if winner in duel.players:
            for uid in duel.players:
                try:
                    level = self.teams.record_result(uid, uid == winner) if duel.ranked else self.teams.level(uid)
                    if level is not None and duel.ranked and self.rewards is not None:
                        self.rewards.on_tournament_rank(uid, self.teams.rank_of(level))
                except Exception:
                    self.log.exception("live pvp %s: ranking %s failed", duel.id, uid)
                    level = None
                self._notify(uid, P + "tournament.amf.PlayCombatEndNotification", {"tournamentLevel": level})

    # --- online status ----------------------------------------------------------------------------
    def touch(self, uid):
        self.presence[str(uid)] = time.time()

    def is_online(self, uid):
        return time.time() - self.presence.get(str(uid), 0) < ONLINE_SECONDS

    # --- queue ----------------------------------------------------------------------------------------
    def enter_queue(self, uid, req):
        deck = _card_ids(req.get("cards"))
        friends = int(req.get("friendsNbr") or 0)
        with self.lock:
            self.last_seen[uid] = time.time()
            old = self.duels.get(uid)
            if old is not None:  # a new search abandons an unfinished duel
                self._notify(old.other(uid), P + "livepvp.amf.OpponentSurrenderedNotification",
                             {"winnerExternalId": float(old.other(uid)), "loserExternalId": float(uid)})
                self._finish(old, winner=old.other(uid))
            self.queue = [q for q in self.queue if q[0] != uid]
            self._check_timeouts()
            target, since = self.challenges.get(uid, (None, 0))
            if target is not None and time.time() - since > QUEUE_SECONDS:
                target = None
            match = next((q for q in self.queue if q[4] == (str(uid) if target else None) and (target is None or str(q[0]) == target)), None)
            if match is None:
                self.queue.append((uid, deck, friends, time.time(), target))
                self.log.info("live pvp: %s waiting (%d cards)%s", uid, len(deck), f", challenging {target}" if target else "")
                return None
            self.queue.remove(match)
            other, other_deck, other_friends = match[0], match[1], match[2]
            for p in (uid, other):
                self.challenges.pop(p, None)
            combat_id = self.next_combat
            self.next_combat += 1
            first, second = (uid, other) if random.random() < 0.5 else (other, uid)
            decks = {uid: deck, other: other_deck}
            friend_counts = {uid: friends, other: other_friends}
            duel = Duel(combat_id, first, second, decks, ranked=target is None)
            self.duels[uid] = self.duels[other] = duel
            combat = amf3.AMF3Object(P + "readyforcombat.amf.Combat", id=float(combat_id), senderExternalId=float(other),
                                     receiverExternalId=float(uid), dateSent=amf3.AMF3Date(time.time() * 1000),
                                     combatStatusTypeId=1, combatRequestId=float(combat_id), combatTemplateId=1)
            start = {"player1Id": float(first), "player2Id": float(second),
                     "player1Deck": decks[first], "player2Deck": decks[second],
                     "player1NbrFriend": float(friend_counts[first]), "player2NbrFriend": float(friend_counts[second])}
            self._notify(other, P + "readyforcombat.amf.NewCombatNotification", {"combat": combat})
            for p in (uid, other):
                self._notify(p, P + "livepvp.amf.StartDuelNotification", start)
            self.log.info("live pvp %s: %s vs %s (%s starts%s)", combat_id, first, second, first, "" if duel.ranked else ", challenge")
            return combat

    def cancel_queue(self, uid):
        with self.lock:
            self.queue = [q for q in self.queue if q[0] != uid]
            self.challenges.pop(uid, None)

    def set_challenge(self, uid, target):
        """The next search of uid only pairs with target (None: back to the tournament queue)."""
        with self.lock:
            if target:
                self.challenges[uid] = (str(target), time.time())
            else:
                self.challenges.pop(uid, None)

    def incoming_challenges(self, uid):
        """Players waiting in the queue for a live duel with uid."""
        with self.lock:
            self._check_timeouts()
            return [str(q[0]) for q in self.queue if q[4] == str(uid)]

    # --- duel -----------------------------------------------------------------------------------------
    def start_round(self, uid):
        with self.lock:
            duel = self.duels.get(uid)
            if duel is None:
                return
            duel.started.add(uid)
            if duel.started == set(duel.players):
                for p in duel.players:
                    self._notify(p, P + "livepvp.amf.StartRoundNotification", {})

    def bam_ready(self, uid, req):
        """Returns an error message for the response (checksum mismatch), else None."""
        with self.lock:
            duel = self.duels.get(uid)
            if duel is None:
                return None
            if req.get("forfeit"):
                other = duel.other(uid)
                self._notify(other, P + "livepvp.amf.OpponentSurrenderedNotification",
                             {"winnerExternalId": float(other), "loserExternalId": float(uid)})
                self.log.info("live pvp %s: %s surrendered", duel.id, uid)
                self._finish(duel, winner=other)
                return None
            duel.ready[uid] = (int(req.get("roundNumber") or 0), req.get("checksumBefore"), list(req.get("slotCard") or []))
            if set(duel.ready) != set(duel.players):
                return None
            (r1, c1, s1), (r2, c2, s2) = (duel.ready[p] for p in duel.players)
            duel.ready = {}
            if r1 != r2 or c1 != c2:
                self.log.warning("live pvp %s: out of sync (rounds %s/%s, checksums %s/%s)", duel.id, r1, r2, c1, c2)
                for p in duel.players:
                    self._notify(p, P + "livepvp.amf.ChecksumErrorNotification", {})
                self._finish(duel)
                return None
            p1, p2 = duel.players
            self._notify(p1, P + "livepvp.amf.BamReadyNotification", {"slotCard": s2})
            self._notify(p2, P + "livepvp.amf.BamReadyNotification", {"slotCard": s1})
            return None

    def bam_end(self, uid, req):
        with self.lock:
            duel = self.duels.get(uid)
            if duel is None:
                return None
            duel.ended[uid] = (req.get("checksum"), int(req.get("externalIdWinner") or 0))
            if set(duel.ended) != set(duel.players):
                return None
            (c1, w1), (c2, w2) = (duel.ended[p] for p in duel.players)
            duel.ended = {}
            if c1 != c2 or w1 != w2:
                self.log.warning("live pvp %s: end out of sync (%s/%s, winners %s/%s)", duel.id, c1, c2, w1, w2)
                for p in duel.players:
                    self._notify(p, P + "livepvp.amf.ChecksumErrorNotification", {})
                self._finish(duel)
                return None
            for p in duel.players:
                self._notify(p, P + "livepvp.amf.BamEndNotification", {"winnerExternalId": float(w1), "redeemCode": 0.0})
            if w1:
                self.log.info("live pvp %s: winner %s", duel.id, w1)
                self._finish(duel, winner=next((p for p in duel.players if str(p) == str(w1)), None))
            return None
