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

## 6. Open questions for the owner

1. No extra deck (rules decide) — OK? Or the "must own the result" middle way?
2. Synchro by level total (several Synchros per Tuner) or one fixed Synchro per Tuner?
3. Xyz: how should the result be picked when a rank has several Xyz monsters (type/attribute match, or one per rank)?
4. Xyz material effects in the first version, or later?
5. Which cards first (a small starter set: e.g. 2-3 Tuners, 3 Synchros, 3 Xyz)?
