# Revival roadmap: QoL, features, content (2026-10-30)

Working rule (from the project owner): **availability over functionality.** Every new feature must fail
gracefully: on any error it disappears or falls back to the original behaviour, the core game keeps working,
offline play always works. Every change: emulator test of the feature + `tools/emu.py smoke` (fresh + upgrade),
its own commit.

Code references are to `work/as3/scripts` (decompiled 1.11.2). Effort: S = hours, M = a day or two, L = several
days, XL = weeks.

## New capability found during research: brand-new classes [VERIFIED, emulator]

Until now we could only edit existing classes (FFDec recompile). New classes now work too:
`mxmlc` from the HARMAN AIR SDK compiles new AS3 classes against a SWC of the game (`ffdec -swf2swc`, game
classes external), the resulting DoABC tag is appended to MobileGame.swf before the first ShowFrame, and patched
game code can use them. Tested: a world-select popup title came from a new class `com.revival.RevivalHello`
(scratch test, 2026-10-30). To do once: a build step (`tools/build_newclasses.py`: compile `as3_new/**.as`,
merge ABC, then run patch_as3). This makes the big UI items (profile, friends, collection) clean new screens
instead of hacks inside old classes.

## Priority 1: small server/APK fixes, high value, low risk (one batch, S each) — DONE (findings 6.36)

Left open (the 25 DP Pro reward is dropped on purpose, owner's decision):
- DONE (6.38) Energy leftovers (S): hide the energy cost in `DuelInfoPopup` (`:98-104`, icon + number) and `DuelStarPopup`
  (`:170-175`); check other energy UI: the energy popup (`EnergyPopup`, reachable from `EnergyWidget` and the shop,
  both hidden now), any "+ energy" buttons, energy rewards in objectives/loot text.

| Item | Where | Plan | Risk / interactions |
|---|---|---|---|
| Server info popup when opening the currency shop | `PopupManagerUtil.ShowCurrencyPopup` calls `ShowApplicationClosePopup()` (`PopupManagerUtil.as:94-100`) | remove that call; startup still shows it (`LoginModule.as:444`) | none |
| Leaderboard "friends only" ticked by default | `LeaderboardPopupUI.as:231` `IsChecked = true` | `false` (check the list it initially fills, `LeaderboardPopup.UpdateScoreInfoDisplay`) | server fallback for friendless players (6.30) stays as a safety net |
| Settings: support button → GitHub, remove "restore purchases" | `OptionPopup.as:48` `FORUM_URL`, `:236-256` restore button | URL → `https://github.com/Eclip5eLP/YGOBamPocketRevived`; restore button hidden (not added) | none |
| BAM Pro always unlocked | `BamProHandlerImpl.IsBamPro` getter (`:105-108`) | return true; hide "Upgrade to BAM Pro" banners (`MainMenuView.UpdateBamDisplay`, login view); give the one-time Pro reward (25 DP, `receivedPremiumReward`) automatically once | removes all Pro gates (chapters ≥16, series 2 packs, arena); check save field `isPremium` server-side; the free "purchase" path stays harmless |
| Energy | consumption `CardBattleModule.ConsumeEnergy` → `EnergyManager.DoConsumeEneryRequest` (`CardBattleModule.as:420-568`), checks `GameEndHandler.as:374,806`, display `EnergyWidget` | recommended: keep the system but never consume (energy stays at max), hide the energy bar + its "+" button; node energy costs remain in data but are ignored | full removal touches 13 classes and the duel-end flow (try-again popup checks energy); "never consume" is 1-2 edits and fails safe |

## Priority 2: quality-of-life features (M each)

| Item | Feasibility | Plan | Interactions |
|---|---|---|---|
| DONE (findings 6.37) Map scrolling jumps to top when moving to a node (sub-maps) | needs reproduction; drag code moves `mScrollingEngine.x/y` directly (`AbstractMap.MoveDrag :209-238`) while the pointer/camera logic (`StoryMapPointer`, ScrollingEngine2D camera) likely re-centres on its own target; first reproduce in the emulator, then fix the camera target | M, mostly investigation | affects world maps too; test with world 2 |
| Deck delete | DONE (65245be) | | |
| World selection | DONE (2daebec) | | |
| Collection menu (main menu button) | L. Reuse `CardScroller` + `FullCardVisual` + card filters from the deck builder (`module/deckbuilder/screens/EditDeckScreen`, `utils/cardfiltering`) in a new read-only screen (new classes) | browse owned + unowned cards (greyed), filters (series, rarity, type, pack), card details popup with how to obtain (BuyCardPopup logic) | profile "collection info" reuses its counters; needs a 10th/11th main menu button → main menu relayout (see Profile) |
| Main menu relayout for new buttons | S-M. 9 buttons from `CreateMainMenuButton` (171x144 each, `MainMenuView.as:204-226`) in a 3x3 grid | 4 columns or 2 rows of 5–6; new icons from existing atlases or new hud/mainmenu atlas pages (pipeline exists) | needed by Profile and Collection |

## Priority 3: social (L–XL), server + client, do in this order

1. **Profile (L)**: new main-menu button and screen (new classes).
   - Own profile: icon picker (preset icons; the server serves the chosen icon at `/fb/graph/<uid>/picture`, which
     the game already loads everywhere a player picture appears, `AbstractFacebook.as:237`), username change,
     password change, stars, level, play deck, collection summary.
   - Other players: same view, read-only, plus "copy deck" if you own the cards (deck build reuses
     `InventoryManagerGame.BuildDeck`).
   - Server: new AMF calls or plain JSON endpoints for profile get/set (icon id, rename with uniqueness check,
     password change with old password, PBKDF2 like now), deck/collection snapshot from the online save
     (`accounts.py` saves).
   - Interactions: the profile-picture fix (currently a blue placeholder for logged-in players) comes for free; the
     friends menu opens profiles; rename must keep Graph names/leaderboards consistent (uid-based, so fine).
2. **Friends menu rewrite (L)**: a new screen replacing `InviteFriendsPopup` (472 lines, horizontal icon list).
   - Vertical list, search field, tabs Friends / Requests (people who added you, with accept) / Find players,
     remove friend, open profile, select the online defense deck (= the arena/friend-duel deck; today set via
     `arena.amf.SetDuelArenaDeckRequest`).
   - Server: `accounts.remove_friend` exists (`:150`); search and incoming-requests endpoints; FQL list stays for
     the old screens.
   - Interactions: profile (open), version gate (online only), live PvP (challenge a friend later).

## Priority 4: big features (XL)

| Item | Status / plan |
|---|---|
| Live PvP | protocol mapped (findings 6.30): lockstep relay over HTTP polling, matchmaking via `readyforcombat`; server relay + matchmaking first, then 2-emulator tests (two AVDs headless can run side by side). Interacts with friends (challenge) and teams/tournament (tournament matches are live duels). |
| Browser version | notes/browser_version.md; Ruffle spike after the APK features. |
| Performance | profile first: startup steps are sequential (`MobileProjectEngine.as:130-158`); candidates: content validation reads every package marker file, localization loads all 106 sections, the atlas loads, the 2 s PvP ping while idle. Measure per-step times with a temporary timing patch in the emulator, then fix the slowest. M, any time. |

## Content (independent of the above)

| Item | Plan |
|---|---|
| Cover art quality | the Poseidra cover is a test-quality composite (template pixels detected by comparing covers → fringe artifacts at the edges, card art upscaled from 200 px). Live quality needs the art layered properly: hand-made mask of the cover template (logo, rail, gems, emblem, frame) + higher-resolution illustration; either drawn by hand or with a proper alpha mask. Covers must look like originals before release. |
| Card split | `notes/pack_split_proposal.md`; 55 unassigned cards (mostly series 98/99 promo legends) still need a home (e.g. reward cards, a promo pack, arena rewards). |
| More world maps | engine ready (6.35 + world select); needs background art, chapter layouts, dialogue, opponents. Note: the "1" under a world-map node is the node's `displayname` in the world XML; set per node. |

## Open technical debts / safety items

- Runtime guard: a booster purchase charges before the pack is rolled (`ShopManagerDalMobile.DoQuickShopRequest`
  → `LootManagerYGO.CreateBooster`); a pack without loot table took DP and gave nothing. Now caught at build time
  (`write_boosterpacks` validation); add a client-side guard that skips listing packs without a loot table.
- `tools/build_newclasses.py` (see above) before the first feature that needs new classes.
- Release prep: deploy server + content, build signed 1.1.0 APK, update README (new features, emulator, content
  pipeline), GitHub release text.

## Suggested order

Done: Priority 1 batch (6.36), map scrolling fix (6.37).

## Next up (plan, 2026-10-30)

Owner decision (2026-10-30): no early 1.1.0. Updates are manual APK installs, so releases should be rare and
big; the next release bundles the new screens too.

Original recommendation (declined): ship a first update (1.1.0) soon with what already works, then build the big screens for 1.2.0.
Players get the fixes now, the version gate and hybrid data get tested by real users early, and every later
feature ships on a proven release path.

1. DONE (6.38) **Energy leftovers (S).** Hide the energy cost (icon + number) in `DuelInfoPopup` and `DuelStarPopup`; sweep for
   other energy texts/buttons (objectives, loot, popups). Emulator check on a duel node.
2. DONE (6.38, guard at purchase time in ShopManagerProject.BuyShopItem) **Pack safety guard (S).** Client: `EBoosterPackInfo.LoadExtraPacks` skips a pack whose shop item has no loot
   table (today only the build checks this). Fails safe: the pack just isn't listed.
3. **Release 1.1.0 (M).**
   - Contents: deck delete, world selection (hidden while there is one world), in-app login, no Facebook logo,
     quick fixes, map fix, Wings of Destiny and Blazing Wind (original covers).
   - Immemorial Cataclysm only if its cover reaches original quality in time; otherwise it waits for 1.2 (its
     cards stay unobtainable, as today). Decision for the owner.
   - Steps: deploy server (gate, content overlay) + content to ygo.eclip5e.com, signed armv8 APK with
     `work/release.p12`, README/changelog, GitHub release text. Old APKs see the update notice, keep offline play.
   - Check on the live server with the emulator (old-equivalent APK + new APK) before announcing.
4. DONE (6.39, not yet exercised by a real class) **`tools/build_newclasses.py` (S).** Make the verified mxmlc + DoABC merge a build step (`as3_new/**.as`),
   with a build-time check that the merged SWF still loads (smoke test).
5. DONE (6.39: top row holds 6 buttons, room for Profile in the bottom row) **Main menu relayout (S-M).** Room for Profile and Collection (two more buttons; 4+... grid or a second row).
6. DONE (6.39, collection mode of the shop card view, no new screen needed) **Collection menu (L).** Read-only browser (new classes), reuses deck builder scroller/filters; owned vs
   missing, how to obtain.
7. **Profile (L), then Friends rewrite (L).** Server endpoints first (tests), then the screens; profile icons fix the
   blue placeholder avatars.
8. **Release 1.2.0**, then Live PvP, then the browser spike. Performance profiling and cover art when convenient.

Interactions to keep in mind: the main menu relayout serves both Profile and Collection; Collection's counters feed
the Profile; Friends opens Profiles; Live PvP later hooks into Friends ("challenge"). Every new screen is a new class
behind a try/catch entry point, so a failure only hides the button.
