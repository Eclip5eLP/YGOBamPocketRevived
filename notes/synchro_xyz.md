# Synchro and Xyz: how they could work (research, 2026-11-01)

Nothing is changed yet. Source paths are under `work/as3/scripts/com/frimastudio/` (decompiled client 1.11.2).
Labels: VERIFIED = seen in code or data, INFERRED = my reading or a proposal.

## 1. What fusion already gives us

| Piece | Where | What it does |
|---|---|---|
| Rule data | `snowstorm/project/inventory/amf/FusionData.as` | Sits on the **base** card (`CardTemplate.fusionData`): one `resultCardTemplateId` plus conditions on the other card (level, card list, type, attribute, monster type), all-or-any. VERIFIED |
| Rule check | `snowstorm/module/cardgame/util/FusionUtil.as` `FindBaseMonster`, `MeetsFusionRequirementsInternal` | Either card of the pair can be the base. VERIFIED |
| Placing | `snowstorm/module/cardgame/player/hand/LocalPlayerHand.as` `SetAsPlaced` (~l.663), `CanSwapOrFuseCard` | Drop a card onto your monster (already on the field, or placed this round) in the same channel: `cardOnMat.CardToFuseWith = dragged card`. Always exactly **two** cards. VERIFIED |
| Resolving | `snowstorm/module/cardgame/round/RoundHandler.as` `DoFusionLaunch` → `GameMatBO.CreateFusionCard` | Both cards leave the field, the result takes the channel, gets the ON_FUSION trigger. VERIFIED |
| **Materials under the card** | `GameMatBO.CreateFusionCard` / `AddCardToIngredientList`; `CardBO` `IngredientCardList` (~l.590-640) | The two cards are kept in a list on the result and go to the graveyard only when the result dies (or come back with it). A fusion result can itself be fused again and its list is carried over. This is almost exactly an Xyz material stack already. VERIFIED |
| Live duels | `snowstorm/module/cardgame/player/hand/PlayerHandBO.as` (~l.160-190), `AwayPlayer.OnBamReadyNotification` (~l.98-125), `server/livepvp.py` l.218-231 | A placement is sent as `[slot, card id, second card id]`; the other phone works the result out from the rule data itself. The server passes `slotCard` on without reading it, so a 4th entry would also get through. VERIFIED |
| AI | `snowstorm/module/cardgame/ai/CardGameAI.as` `IsFusionPossible` (l.323) | Plans pairs with the same `FusionUtil` check. VERIFIED |
| Frame | `utils/rendering/card/CardVisual.as` `IsFusionCard` (l.107) | **One** check (`fusionData != null` or `fusionResult`) picks the purple look in every card view (table below). Base cards like Thousand-Eyes Idol get the purple frame too. VERIFIED |
| Owning results | `snowstorm/project/inventory/InventoryManagerGame.as` l.146 | Cards with `fusionResult` are left out of collection/decks: results only exist inside a duel. VERIFIED |

Game sizes: deck 15 cards (`DeckBuilderConstants.DECK_SIZE`), 3 cards in hand (`CGConst.NBR_CARD_IN_HAND`),
6 slots (`CGConst.NBR_CARD_SLOTS`). VERIFIED

Frame pictures in `asset/common/common/common_all_1` (atlas), each picked by the `IsFusionCard` check: VERIFIED

| Picture | Used by |
|---|---|
| `common_duel_fusion_card` (126x126) + mask colour 4865697 | `DuelCard.GetBackGroundName`, `AddMonsterMaskQuad` (duel field) |
| `common_cardtemplate_card_fusion` (460x640) + `common_card_template_bar_bottom` frame 1 + white text | `FullCardVisual` (big card) |
| `common_fusion_preview_card_background` (470x340) | `ZoomedCard` |
| `DetailedCardDisplayData.FusionBackgroundTextureName` | `DetailedCardVisual` (other views) |
| `common_cardtemplate_detail_fusion`, `common_fusion_ico` | fusion preview strip / icon |

A test recolour of these pictures to white (Synchro) and black (Xyz) works (scratch sheet, grey-scale + tint); the
beige text box needs a mask so it stays beige. New pictures can ship as a second atlas page like the main menu
icons (`content_mods.add_atlas_frames`, notes/findings.md l.1378). INFERRED (look) / VERIFIED (mechanism)

## 2. Extra deck or "the source card makes it"?

**Recommendation: no extra deck. Rules decide the result, like fusion.** INFERRED

Why:
- The game is built around a 15-card deck and a 3-card hand. An extra deck touches the deck builder (UI, save
  format, rules), the server's deck storage and checks, online deck copy / profile decks, arena and tournament
  decks, the AI, and the live-duel message (the chosen card must be sent: `slotCard` 4th entry). Effort XL.
- Fusion results already can't be owned (InventoryManagerGame l.146); Synchro/Xyz results would work the same way,
  and the existing "made in duels" path (art preload, zoom, preview in the card popup) is reused.
- With only pairs and 3 cards in hand, players can't really plan around a pile of extra cards anyway.

Optional middle way (later, if wanted): Synchro/Xyz cards become collectable and a summon only works if you **own**
the result card. No deck slot, but collecting matters. Cost: both phones in a live duel must know the other
player's owned results (sent at duel start); the AI ignores it. INFERRED

## 3. Synchro (proposal)

What the owner described: the Tuner is the "source", like the fusion base. Drop a non-Tuner monster onto your Tuner
(or the Tuner onto it) → Synchro monster in that channel, white frame.

- **Data**: the Tuner carries the rule. Simplest form that works **today with no code**: Tuner gets `fusionData` with
  `ingredientCardLevelId = N` → one fixed Synchro result. VERIFIED that the condition exists; only the frame
  would be purple and the Tuner itself would look like a fusion card.
- **Better (small code)**: a Tuner can make several Synchros, picked by the **level total**: Tuner level 3 + level
  4 monster → the level-7 Synchro from the Tuner's list. Deterministic from the two cards, so live duels need no
  message change and the AI only needs the new check. Two Tuners can't Synchro together (needs a "Tuner" flag).
- **Frame**: white frame on the result; the Tuner keeps its normal frame (maybe a small "Tuner" mark).

## 4. Xyz (proposal)

- **Summon**: two of your monsters with the **same level** in one channel → an Xyz monster of that rank. The rule
  can't sit on one "source" card (every level-4 monster would need it), so it becomes a rule table: per rank a
  list of Xyz monsters, picked by the materials (e.g. same type or attribute → the matching Xyz, else a default
  one). Deterministic, so again no message change. INFERRED
- **Materials**: the two cards go into the result's `IngredientCardList`, already kept under the card and sent to
  the graveyard with it (VERIFIED, fusion code). New: show the count on the card, and **attach** a third
  same-level monster by dropping it on the Xyz (a fusion result can already be fused again, so this is mostly
  a rule change).
- **Effects that use materials** ("detach 1: ..."): a new effect kind. Effects today are built from six
  primitives (findings 6.54), none removes a material. Needs a new EffectBO subclass, EffectCreater patch, AI
  scoring, the same code on both phones. This is the biggest piece. A first version can ship Xyz monsters with
  normal effects (or "+X ATK per material", which is new but small).
- **Frame**: black frame; rank shown instead of level (text only).

## 5. What has to be built (both)

| Part | Synchro | Xyz | Notes |
|---|---|---|---|
| Rule data on the card | new fields: kind (fusion/synchro/xyz), Tuner flag, result list by level | rank table | Content: `content_mods.add_card` + `item_template.ace`. New AMF fields need the new APK; old clients must not get the new content (check how a 1.1.0 client reacts to unknown fields, unknown) |
| Rule check | extend `FusionUtil` | extend `FusionUtil` | Used by hand, field, AI, live duels alike |
| Resolve | reuse `CreateFusionCard` | same + attach | |
| Frame | 4 pictures + `IsFusionCard` split into kind | same | `CardVisual`, `DuelCard`, `FullCardVisual`, `ZoomedCard`, `DetailedCardVisual` |
| Glow / animation | reuse fusion glow and animation, maybe tinted | same | `cardbattleanim_available_fusion_glow_anim`, `CardFusionFeedback` |
| Card popup preview | reuse (`FullCardPopup`, `BuyCardPopup` show the result) | list of possible Xyz | |
| AI | `CardGameAI.IsFusionPossible` follows `FusionUtil` | same | |
| Material effects | - | new effect kind | the big one |
| Tutorial popup | optional | optional | `FusionTutorialPopup` text pattern |
| New cards | Tuners, Synchros + art | Xyz + art | art from the YGOPRODeck download (cropped images) |

Effort guess: Synchro M (mostly frame work + rule check), Xyz without material effects M, with material effects L.
Everything stays inside the duel code both phones run, so live duels need both players on the new APK (the
version check already handles that).

## 6. Owner decisions (2026-11-01)

- **No extra deck.** Rules pick the result.
- **Synchro**: each Tuner has its own list, one result per level total (Tuner level + other monster's level).
- **Results as material**: Fusion/Synchro/Xyz results can be the base of another Synchro or Xyz (the ingredient
  list is carried over, VERIFIED `GameMatBO.AddCardToIngredientList`).
- **Xyz**: picked by type/attribute match; what happens when several match is still open (section 8).
- **Material effects** (detach / check materials) are fine to build.

Second round (same day):
- **No split release**: Synchro and Xyz ship together, in one APK, once everything works.
- **Picker for both**: when a drop can make more than one result, a picker shows the choices (it plays the role of
  the extra deck). Also used when a pair could make a Fusion **or** an Xyz/Synchro: the player picks.
- **Only cards you own** show in the picker, if that doesn't break the game (section 9: it doesn't). So Synchro and
  Xyz cards are pulled from packs/rewards, but can't go into decks.
- **No attaching**: dropping a monster on an Xyz never adds a material; only card effects can (new material
  effects in the duel engine).
- **Xyz rank = level** (counts as its level when it is material for something else).
- **Both generic and type/attribute Xyz** exist; the picker handles the choice.

## 7. Does this need a new APK?

Yes, for both. All duel rules, card frames and the AI live in the game code inside the APK (`MobileGame.swf`,
patched through tools/as3_patches.py / new classes). The server only sends card data and passes live-duel moves
through (server/livepvp.py l.218-231). VERIFIED

| Can be done without a new APK | Needs a new APK |
|---|---|
| New cards, art, stats, effects built from the existing six effect pieces (content) | Synchro rule by level total, Tuner flag, white frame |
| A Synchro done as a plain fusion: Tuner + level N → one fixed result, purple frame (VERIFIED: the level condition exists) | Xyz rule table, black frame, attaching materials |
| Which Synchro/Xyz cards exist and their rules, **once the APK has the code** | Detach / count-materials effects (new effect kind) |

Release plan that follows from this (INFERRED):
- Build Synchro and Xyz in the same code. The next APK (1.2.0) ships with Synchro cards in the content.
- If the Xyz code is finished and tested by then, it goes into 1.2.0 switched off: no Xyz cards or rank table in
  the content means no Xyz can happen. Xyz then releases later **through content only, no second APK**.
- If Xyz code isn't done in time, Xyz comes with a later APK.
- New AMF fields (Tuner flag, kind, rank table) are only understood by the new APK. The server's version gate
  (server/content.py l.84, `minimum APK version`) already sends older APKs to the update screen, so 1.1.0 players
  are asked to update and never read the new data. VERIFIED (gate) / INFERRED (that this covers it)

## 8. Xyz: who can make one, and which one

Card pool (base data, `item_template.ace`, 928 monsters without fusion results) [VERIFIED]: levels 1-12, every
level 1-11 has 42-145 monsters (level 12: 2). Level 4: 97 monsters, 37 different type+attribute pairs; level 3:
103 monsters, 40 pairs. So almost any two cards of a level share a level, and type+attribute matches are rare.

### "Every card can be material"

The rule doesn't sit on cards: it sits on the Xyz monsters. Each Xyz card lists: rank, and optionally a type and/or
attribute its materials must have. A pair can make an Xyz only if some Xyz in the content accepts it. That keeps
it under control:
- Ranks with no Xyz cards: nothing happens, same as today.
- The content decides how open it is: one generic Xyz per rank makes every same-level pair work; only
  type/attribute Xyz make it rare.
- Drop glow: the same-channel glow appears only when a real Xyz is possible (same check as fusion today:
  `LocalPlayerHand.WillFusionOccur`). Optionally a dark glow for Xyz.

### Several Xyz match: options

| | How | Good | Bad |
|---|---|---|---|
| A. Best match + fixed order | Score: type and attribute both match > one matches > generic. Ties: an order set in the data (e.g. by card number). | No new screen, deterministic, live duels need no message change | Same pair always gives the same card; tied cards lower in the order can never be made |
| **B. Player picks (recommended)** | Matching narrows the list (only Xyz whose conditions fit). One left: made directly. Several left: a small picker shows them when you drop the card. AI takes its best one. | Closest to the real game, every Xyz is reachable, also settles pairs that could make a Fusion **or** an Xyz | One new popup; the choice is sent as a 4th entry in the live-duel placement (`[slot, card, second card, chosen result]`; server passes it through already, VERIFIED server/livepvp.py l.218) and read in `AwayPlayer.OnBamReadyNotification` |
| C. Random | Seeded by the duel | Simple | Feels unfair, can't plan |

B can start as A (no picker) and get the picker later: the rule check is the same, only the tie-breaker changes.

### Still to decide

1. Tie between Xyz cards: A (fixed order), B (player picks) or A first then B?
2. A pair that could make a Fusion and an Xyz (or Synchro): fusion first, or let the player pick (B)?
3. Dropping a same-level monster on an Xyz of that rank: always **attach** (Xyz gets a material), or can it make
   a new Xyz on top?
4. Does an Xyz count its rank as level when it is the base for a Synchro or another Xyz?
5. Generic Xyz per rank (every pair works) or only type/attribute Xyz (rare)?
6. Starter set of cards for Synchro (e.g. 2-3 Tuners, their results per level total).

## 9. Owning Synchro/Xyz cards without putting them in decks: doable

Verdict: **yes, low risk.** The original game was already built for owning fusion results that can't be played
from the deck: several places skip cards whose template has `fusionResult = true`. Synchro/Xyz cards get the same
flag (plus a kind), so they inherit all of it.

Already handled by the game (VERIFIED, paths under `work/as3/scripts/com/frimastudio/`):

| Place | Code | Effect for an owned Synchro/Xyz |
|---|---|---|
| Card list behind "my cards" filters | `snowstorm/project/inventory/InventoryManagerGame.as` `GetCompleteDifferentFloatingCardList` l.146 | skipped |
| Instant decks (Attack/Defense/Balanced) | `utils/instantdeck/InstantDeckUtils.as` `CreateUsableCardList` l.37 | skipped |
| End-of-duel collection count "x/y" | `snowstorm/project/popup/popups/EndGamePopup.as` l.205 | not counted |
| Collection (revival screen) | `tools/as3_patches.py` `UpdateCollectionList` (~l.1493) via `CardTemplateListUtil.GenerateCardTemplateDataList` | listed with the owned count, owned first; good, that's where you see them |

Needs a change:

| Place | Problem | Fix | Size |
|---|---|---|---|
| Deck builder card list | `snowstorm/module/deckbuilder/screens/EditDeckScreen.as` l.274 lists **every** card template with its owned count (`CardTemplateListUtil.GenerateCardTemplateDataList`), no `fusionResult` check: owned Synchro/Xyz could be dragged into a deck (VERIFIED) | drop `fusionResult` templates from that list (one patch) | S |
| Server "best cards" deck | `server/game.py` `deck_source` (fallback when no deck is set) takes the strongest owned cards (VERIFIED l.385-391): Synchro/Xyz would be picked | skip result cards (template list from content) | S |
| Server card counts | `server/profiles.py` l.128 `cards_unique` counts all owned cards | fine either way; matches the Collection | none |
| Sell screen | `snowstorm/module/shop/view/ShopSellView.as` l.219 lists owned cards with the same util: Synchro/Xyz could be sold for coins | owner's call: allow (normal card) or hide | S |
| Profile picture | `server/profiles.py` `owned_cards` | a Synchro/Xyz you own can be your picture; nothing to do | none |
| Decks that already contain one | can't happen through the game after the deck builder fix; a hand-edited save would just play it as a normal monster | nothing | none |

In the duel:
- **Your picker**: the duel can read your inventory (`GameMatBO` has `mInventoryManager`; `InventoryManagerGame
  .GetCompleteCardList`) VERIFIED. The picker lists results that fit the pair **and** that you own (any copy, in
  any container). Nothing owned fits: no glow, no summon, as today without a fusion partner.
- **Live duels**: the other phone doesn't need to know what you own: your choice travels as the 4th placement entry
  and the other phone only checks that it fits the pair (same rule code). The server passes it through
  (server/livepvp.py l.218) and could check ownership against your online save if cheating ever matters. INFERRED
- **AI opponents** (story, arena, friend decks): no inventory of their own; they pick from **all** results that
  fit (or a per-duel list in the content if that is too strong). INFERRED, owner's call.
- **Getting them**: normal cards for the loot side: booster loot tables, card shop, Arena/tournament rewards,
  `cardsources.json` texts ("where to get"). Content only.

So the owner's balance idea works without breaking the deck/collection mechanics: one client patch (deck builder
list), one server fix (best-cards fallback), and a decision on selling.

## 10. Owner decisions, third round (2026-11-01)

- Synchro/Xyz cards **show** in the Collection and the **sell** menu. They **don't show** anywhere else that
  builds or fills a deck: deck builder card list, instant decks, the server's strongest-cards deck.
- **AI**: by default an AI opponent may Synchro (from all results that fit) but **not Xyz**. Optional per-duel
  settings allow Xyz, and/or give an exact list of the Synchro/Xyz results it may make (balancing, bosses).

### Where the AI settings go

Story duels (incl. bosses) are configured by map node properties in the map XML (content, server-side):
`XMLNode.GetDuelData` (`snowstorm/module/map/node/XMLNode.as` l.243-268) reads `deckid`, `aimissratio`,
`powerupid`, `characterid`, ... into `DuelData` (`snowstorm/module/map/node/DuelData.as`), which the duel gets
as `DuelInfo`. VERIFIED. Proposal (INFERRED, names to fix when building):

| Node property | Default (missing) | Meaning |
|---|---|---|
| `aixyz` | 0 | 1 = the AI may make Xyz monsters |
| `aiextra` | empty | comma-separated card ids: the AI may make **only** these Synchro/Xyz results (an Xyz in the list counts as allowed even without `aixyz`) |

Both become two new `DuelData` fields (copied in `DuelData.Clone`, l.~177) that the AI's rule check reads
(`CardGameAI.IsFusionPossible`, l.323, and the AI's picker choice). Other duel kinds keep the default (Synchro yes,
Xyz no): arena (`ArenaModule` l.733), friend decks (`DuelGroundModule` l.449), tournaments, duel stars. They can get
the same two settings later if wanted (arena data comes from the server, so the server could send them).
Live duels have no AI: both players pick for themselves (only owned cards).
