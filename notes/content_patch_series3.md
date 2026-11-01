# Next content patch: World 2 + Series 3 (plan, 2026-11-01)

Owner's goal: a new world map with new chapters, new Series 3 cards, new prebuilt decks (in the shop and offered by a
popup when the new world opens), new booster packs for Series 3. Ships together with Synchro/Xyz
(notes/synchro_xyz.md) as one APK + content release (1.2.0).

Paths below are under `work/as3/scripts/com/frimastudio/snowstorm/` unless they start with `tools/`, `server/` or
`notes/`. VERIFIED = seen in code/data, INFERRED = my reading.

## What already exists (the game grew this way once: series 2 + chapters 33-47)

| Piece | Status | Where |
|---|---|---|
| Several world maps, switch button, save migration | built by us, tested with a throwaway world 2 (removed) | findings 6.35, 6.55; tools/as3_patches.py WORLDMAP_* edits |
| World map art | data only: background objects `backgroundWorldN` load `asset/misc/mapbackground/mapbackground_<classname>.png` | `scrollingengine2d/main/ScrollingEngine2D.as` l.326-333, 386-390 VERIFIED |
| Chapters | data: story map/node rows + `asset/world/map<N>_level1.xml` (duels: `deckid` opponent deck, `characterid` portrait, `stringid` dialogue, rewards, `Rules`) | findings 6.32 |
| Series limit per chapter | exists (`cardSerieLimit` on world/duel nodes; DuelInfoPopup shows a restriction icon), never used: every original map has 0 | `module/map/node/XMLNode.as` l.471, `common/deck/DeckUtil.as` IsSeriesEnabledForDeck VERIFIED |
| "New series unlocked" popup | `Series2UnlockedPopup` when world node 33 unlocks, LET'S SEE moves the map pointer there | `project/contextual/YGOMContextualUtil.as` l.31, ValidateContextualSeries2Unlock VERIFIED |
| Free series deck + popup | world map bundle 1801 builds `EStarterPack.STARTER_PACK_WORLD2_01`, makes it the play deck, shows `Series2StarterDeckPopup` | `project/bundle/BundleManagerProject.as` l.311-350 VERIFIED |
| Deck offer after a chapter | `ContextualDeckPopup` offers the starter deck whose "chapter completed" matches | `YGOMContextualUtil.ValidateContextualDeckOffer`, `project/worldmap/WorldmapManagerYGO.as` l.441 VERIFIED |
| Starter decks in the shop | 8 decks hard-coded in `module/shop/view/enum/EStarterPack.as` (cards, cost, shop item 775-781, cover frame, chapter unlock) | VERIFIED |
| Booster packs | data-driven by us (`config/boosterpacks.json`, `content_mods.add_booster_pack`, `create_loot_table`, `compose_cover`) | findings 6.33, 6.60s |
| New cards + art | `content_mods.add_card` + YGOPRODeck download (`dl/YGOCardDl.py`: 14,825 cards, art-only crops) | findings 6.55, 6.68 |
| Synchro / Xyz | built, tested (emulator, AI, live) | notes/synchro_xyz.md, findings 6.70 |

## What has to be built

### A. Series 3 in the game code (APK)
1. `CardSeries.SERIE_3` (enumeration has 1, 2, 98/99 only). VERIFIED
2. Rarity icon: `CardRarityUtil.GetRarityIconFrame` = rarity + (series-1) x 4, series > 2 lands on the Arena icons
   (`NBR_SERIE` = 2). Needs 4 new icon frames (recolour of the series 2 set) and the frame math patched. VERIFIED
3. Card filter menu: `EContextMenu.SERIES` lists Series 1 and 2 only; add Series 3. VERIFIED
4. Deck rule for series-limited chapters: `DeckUtil.IsSeriesEnabledForDeck` / `IsAllSeriesEnabledForDeck` (15 cards
   of the series) have **no caller**: the original game never enforced `cardSerieLimit`; it only shows a restriction
   icon in the duel popup and limits instant decks to the series. Enforcing a limit (decision 4) = new code (block
   the duel button when the play deck breaks it). VERIFIED (grep: no call sites)
5. Series 2 is BAM Pro gated in the shop (`BuyCardShopDisplay`, `BuyCardPopup`, `ContextualCardPopup`); BAM Pro is
   free (content mod `free_bam_pro`), so no change needed. VERIFIED

### B. Prebuilt decks from data (APK, once)
- `EStarterPack` reads extra decks from `config/starterdecks.json` (same pattern as boosterpacks.json):
  id, name, two description texts, card list, bonus cards, cost, shop item, cover frame, chapter that unlocks it.
- Content mod `add_starter_deck`: shop item + bundle rows + text + cover art (new frames on the shop atlas).
- Shop: shows them with the originals (shop entries filtered by chapter as today).
- Popup on reaching the new world: reuse the series 2 flow, made data-driven: when the first World 2 chapter unlocks,
  "Series 3 unlocked" popup (text from data) + LET'S SEE; the Series 3 starter deck(s) are offered with the existing
  `ContextualDeckPopup` (buy) — or given free like series 2 (owner's choice, section D).

### C. World 2 content (data + art, no APK beyond what exists)
- `worldmap2.xml`: chapter nodes and paths, background object(s) `backgroundWorld3/4`.
- Chapters (ids 49+): story map/node/star rows, `map<id-1>_level1.xml` per chapter (duel nodes, treasure, boss),
  opponent decks (Series 3 cards), dialogue (`map_0NN` sections), chapter names, preview art.
- Opponents: character portraits (`mapcharacter_duelcharacterN`, 85 exist) and duel backgrounds
  (`mapbackground_backgroundmapN`, 47 exist). New ones = art.
- Bosses may use Synchro/Xyz (`aixyz` / `aiextra` on the node).
- Unlock: World 2's first chapter opens when a World 1 chapter is cleared (`UnlockByNodeId`).
- A content-mod helper that builds all of this from a compact chapter definition (list of duels: opponent deck,
  portrait, dialogue, reward), so writing a chapter is a few lines of data, not hand-made XML.

### D. Series 3 cards and packs (data + art)
- Cards via `add_card` from YGOPRODeck pictures (art-only crops), stats/effects from the existing six effect pieces,
  texts. Includes Tuners, Synchro and Xyz monsters (rules in `SUMMONS`).
- Size reference: series 2 = 567 cards (416 monsters, 151 spells; rarities 215/150/124/78). Series 3 can start
  smaller and grow per patch.
- Booster packs: `add_booster_pack` / `create_loot_table` / `compose_cover` (Series 3 icon on the cover).
- Card sources text (`cardsources.json`) and card shop entries (Synchro/Xyz need one, write_summons checks).

## Effort (INFERRED)

| Part | Size | Blocked by |
|---|---|---|
| A. Series 3 code | S | — |
| B. Data-driven starter decks + series popup | M | — |
| C. Chapter builder tool | M | — |
| C. World 2 map + chapters | L (per chapter: small once the tool exists) | story, art |
| D. Series 3 card set | L (card choice + effect design) | card list |
| D. Packs, decks, shop | S once cards exist | card list |
| Art: world background, chapter previews, portraits, deck/pack covers, rarity icons | M-L | art source |

## Owner decisions (open)

1. **Card list**: theme and size of Series 3 (e.g. 5D's/ZEXAL-era cards around Synchro/Xyz, ~100-150 cards to start)?
   Hand-picked by you, or I propose a list by archetype?
2. **World 2 size**: how many chapters (World 1 has 47; series 2 started at chapter 33)?
3. **Unlock**: open World 2 after which World 1 chapter (47 = the last)?
4. **Series limit**: should World 2 duels require Series 3-only decks (the original game had the rule but never used
   it), or allow any deck?
5. **Starter decks**: free like the series 2 deck, or bought (DP) and only offered by the popup? How many decks?
6. **Art**: world background, chapter previews, opponent portraits: reuse/recolour existing art for now, compose from
   card art (like the pack covers), or will you provide art?
7. **Story text**: opponents' dialogue and chapter names — you write them, or I draft placeholders?

## Order of work (proposal)

1. A + B (code, independent of the decisions) and the chapter builder tool, tested with placeholder content.
2. Card list (decision 1) -> cards, Synchro/Xyz rules, packs, decks.
3. World 2 chapters with the cards (decisions 2-7).
4. One APK (1.2.0) + content release: Synchro/Xyz + World 2 + Series 3.

## Progress

- 2026-11-01 part A (code, not yet tested in the emulator): `CardSeries.SERIE_3`, rarity icon frames 12-15
  (`CardRarityUtil` patch; hexagon gems drawn by `content_mods.series3_rarity_icons`, common atlas page 2), "Series 3"
  filter entry (`EContextMenu`, text `card_filtering/SERIES_3_FILTER`), shop pack art for series 3
  (`shop_booster_rarities_0002`, `shop_booster_series_icon_0002`, text `shop/shop_booster_serie3`;
  `content_mods.series3_shop_art`).
- Part B (code, building): `EStarterPack` reads `config/starterdecks.json`; `content_mods.add_starter_deck` (shop item
  copy of 775, bundle with the 15 cards, texts, cover) and `compose_deck_cover` (cover 6 recoloured, card art in the
  window). Decks without an unlock quest are on sale at once (`BuyStarterDeckShopDisplay` patch). Cover frames must be
  numbered without gaps: originals 0-6, new decks 7+ (the original series 2 free deck refers to frame 7, which never
  existed; it will now show the first new cover).
- `add_atlas_frames` accumulates frames per atlas across mods (one page 2 per atlas).
- Found [VERIFIED code]: `DeckUtil.IsSeriesEnabledForDeck` has no caller (series limits were never enforced).
