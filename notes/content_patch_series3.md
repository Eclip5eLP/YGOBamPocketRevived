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
- [VERIFIED emulator] Test deck "Synchro Test Deck" (data deck, 1 DP) shows unlocked in Shop > Starter Decks with its
  composed cover; buying it builds and equips the deck ("Your new starter deck" popup). Series 3 hexagon gem shows in
  the card preview; Filters > Series lists Series 3 and filters to the 6 Series 3 test cards.
- Chapter builder `content_mods.add_chapter` (+ `chapter_slots`, `write_world_maps`): a chapter re-uses an existing
  chapter's layout and background (layouts follow paths drawn into the background art) and fills its duel nodes
  (deck, portrait, line, DP, AI Synchro/Xyz settings) and treasures; adds story map/node rows, world node, layout and
  preview files, texts (`map_0NN` section: intro HS01, outro HS12, one line per duel; chapter name; world map info).
  New world maps get `worldmap<N>.xml` with world 1's background and node places. Test: `content_test_mods
  .test_world2` (world map 2, chapter 60 on chapter 34's layout).
- Original data detail [VERIFIED map33_level1.xml]: the series 2 starter deck was handed out as a treasure node of
  chapter 34 (its 15 cards, node 3), not as a shop purchase.
- [VERIFIED emulator] World select shows World 1 / World 2; World 2's node 1 opens "W2-1. Test Chapter" (our name,
  info text, the layout chapter's preview picture), VISIT loads chapter 60 on chapter 34's background with our intro
  story text. World 2 looks like World 1 because the world map's hexagons and paths are painted into its background
  picture (backgroundWorld/backgroundWorld2): a real World 2 needs its own background art (decision 6).

## Owner decisions (2026-11-01, second round)

1. Series 3 about the size of Series 2 (567). Proposal of archetypes and standalone cards to choose from:
   notes/series3_card_proposal.md (Synchro/5D's and Xyz/ZEXAL era, ~1300 archetype cards + ~1100 standalone).
2. World 2 about the size of World 1; its chapter order may start elsewhere on the map.
3. World 2 opens after World 1's last Alba Litora main chapter (chapter 24).
4. Series limit enforced on World 2 (Series 3 decks only): `com.revival.map.SeriesRule`, checked in
   `StoryMap.EnergyCostNode` before a duel costs energy; popup names the number of off-series cards.
5. One free starter deck from a treasure node in World 2's first chapter (like series 2's in Tropica chapter 2,
   template 34, node 3), the other decks bought in the shop.
6. Art: reuse existing art (backgrounds, previews, portraits).
7. Story written by me in the game's style.
- Extra: objective (quest) DP rewards below 10 DP now pay 10 DP (`content_mods.objective_dp`, 198 rewards).

## World 1 structure [VERIFIED asset/world/worldmap.xml, world_map texts]

- Alba Litora: main chapters 1-24 (story maps 2-25) + 8 side chapters 5.1, 8.1, 10.1, 11.1, 16.1, 20.1, 22.1, 23.1
  (story maps 26-33), each opened by its main chapter.
- Tropica City: numbering restarts: main chapters 1-8 (story maps 34-41) + 7 side chapters 2.1, 2.2, 6.1, 6.2, 7.1,
  7.2, 8.1 (story maps 44, 47, 48, 50, 51, 58, 59). Tropica opens after Alba Litora chapter 15 (world node 33
  UnlockByNodeId 15), not 24.
- 47 chapters in all. World 2 numbering: to decide whether its first chapter is "25." (continuing Alba Litora) or
  "1." (like Tropica restarting).
- Series 2 limit on Tropica [VERIFIED data]: the chapter layouts embedded in storymaptemplate.ace mark chapters
  (story maps) 34-37, 40, 41, 47, 50, 51, 58 as cardSerieLimit 2, but the downloaded layout files the game actually
  loads (asset/world/Map<N>_level1.xml, StoryMap.CreateContent) say 0 for all of them, so the final game showed no
  limit there. Where a limit was set, the original only showed an icon and limited instant decks; custom decks were
  never checked.
- Deck covers: art clipped to the window's bevelled bottom (DECK_COVER_WINDOW_SHAPE), bottom band redrawn as the
  original's trapezoid, plate pasted with its own shape only.
- [VERIFIED emulator] Test chapter with cardSerieLimit 3: the duel popup shows the restriction icons with "Series 3
  Cards Only" (new text `map/TOOLTIP_CARD_SERIES_LIMITATION_3`); DUEL with a mixed play deck shows our popup ("Your
  play deck has 12 cards from other series") and the duel doesn't start. Dev note: a changed package must get a new
  version, or a device that has the same version installed keeps its old files (world 1.1.11, common 1.1.12,
  mappreview 1.1.8 now).

## Owner decisions (2026-11-01, third round)

- World 2's first chapter is numbered **25** (continuing Alba Litora's 1-24).
- **Series 4** planned as World 2 part 2 (like Tropica City is World 1 part 2).
- Chosen archetypes for Series 3 + 4 (counts = cards not yet in the game, notes/series3_card_proposal.md):

| Archetype | Cards | Era / summon |
|---|---|---|
| Stardust / Junk / Synchron | 75 | 5D's, Synchro |
| Red Dragon Archfiend (+ Resonators) | 34 | 5D's, Synchro |
| Black Rose / Rose Dragon | 26 | 5D's, Synchro |
| Ice Barrier | 42 | 5D's, Synchro |
| T.G. | 33 | 5D's, Synchro |
| Koa'ki Meiru | 36 | 5D's (no Synchro) |
| Utopia / Numbers / ZW | 58 | ZEXAL, Xyz |
| Photon / Galaxy | 33 | ZEXAL, Xyz |
| Madolche | 26 | ZEXAL, Xyz |
| Mermail / Atlantean | 26 | ZEXAL, Xyz |
| Ghostrick | 37 | ZEXAL, Xyz |
| Sylvan | 20 | ZEXAL, Xyz |

Proposed split (to confirm): **Series 3 = the six 5D's archetypes (246 cards, Synchro)**, filled to ~570 with
standalone 5D's-era cards (pool: 28 Synchro, 39 Tuners, 239 monsters, 120 spells, 146 traps). **Series 4 = the six
ZEXAL archetypes (200 cards, Xyz)**, filled with standalone ZEXAL-era cards (66 Xyz, 17 Synchro, 11 Tuners, 213
monsters, 91 spells, 107 traps). World 2 part 1 then teaches Synchro, part 2 Xyz, the way Tropica brought Series 2.
Archetypes need not be taken whole (later prints such as Stardust Sifr Divine Dragon can be left out).

World 2 shape (proposal, mirrors World 1): part 1 = main chapters 25-48 + 8 side chapters (x.1) with Series 3 limit;
part 2 = 8 main + 7 side chapters with Series 4 limit, opened from part 1 like Tropica opens from Alba Litora 15.
Series 4 needs the same small code as Series 3 (enum value, rarity icons, filter entry, shop pack art).
- 2026-11-01: owner confirmed the split (Series 3 = Synchro archetypes, Series 4 = Xyz archetypes). Series 4 support
  added (enum SERIE_4, rarity frames 16-19 as octagon gems, filter entry, shop pack art frames 3); gems are drawn by
  `content_mods.series_gem` (Series 3 hexagon, Series 4 octagon). Draft Series 3 list: notes/series3_card_list.md.

## Card effects for Series 3/4 (plan, 2026-11-01)

- BAM effects are named keywords with an amount and a fixed rules text, e.g. BOOST 300 ("Your Monster gains Power."),
  CRIPPLE ALL 200, SHOCK 500, SNEAK, IMMUNE, GROWTH, RESURRECT DRAGON, BOOST ALL WARRIORS 500, NECRO ..., FUSION - X
  [VERIFIED item_template.ace + inventory texts: 940 distinct effect texts, ~200 keywords; the original effects are
  simplified versions of the real card texts]. A new card copies an existing effect row of its keyword (texts come
  with it); a missing amount = a copied row with a new modifier and a new name text.
- `tools/effect_mapper.py`: suggests 1-2 keywords from a card's real text (destroy, damage, life points, ATK up/down,
  revive, protection, negate; amounts from the text). Prototype result: right for many (Thorn of Malice -> BOOST 600,
  TGX300 -> BOOST ALL 300), wrong for others (Koa'ki Meiru Drago destroys itself -> mapped to DESTROY MONSTER). So:
  mapper suggestions + a hand review of every card, archetype by archetype, written into the card data
  (`content/series3/*.json` gets an `effects` field), then `add_card` builds them.
- Synchro/Xyz monsters can also get material effects (needs/cost/perMaterial/attach, notes/synchro_xyz.md).
- 2026-11-01: Stardust / Junk / Synchron reviewed (75 cards): `effects` (existing keywords, 3 new amounts),
  `effect_note` (the real card in short), `effect_idea` for 26 cards where a proposed new effect fits better.
  The mapper's picks were mostly wrong for this engine-heavy group (summon/search/level texts), so the review is by
  hand. Proposed new effects (data-only vs engine code, with their cards): notes/new_effects.md.
- 2026-11-01: per-card effect review done for all 577 Series 3 cards (246 archetype + 331 standalone): every card has
  `effects` from existing keywords (new amounts/targets only as copied rows), 92 also an `effect_idea` for an approved
  new effect (notes/new_effects.md todo). Spells use only keywords original spells use. Next: rarities, Synchro/Xyz
  rules (`SUMMONS`) for the real Tuners/Synchros, then building the cards and the new effects.
- 2026-11-01: Series 3 cards built: `tools/series3_cards.py` (build_content.py with env YGO_SERIES3=1 until the Series 3
  boosters exist). 577 templates 3001-3577 (archetype cards first, then standalone; append only), real stats,
  "rarity" (computed once into the data with the Series 2 split per card type: monsters 173/111/88/51, spells
  46/42/39/27; edit freely), cardScore = Series 2 mean per type+rarity (InstantDeckCreator), spells' selfDestruct
  from "single_use", effect rows from the reviewed keywords and the approved new effects, art crops (series3
  package 1.0.2), a backorder card shop item each (30001+), Synchro rules from the real material lines (5134
  tuner/total/result entries). VERIFIED emulator: granted cards render with art, Series 3 gem, Synchro frame, type
  line, "Continuous Spell" + stay icon, effect texts.
  Open: Series 3 booster packs (then drop the env gate); the Summon picker shows at most 4 cards (a generic Tuner can
  reach more owned Synchros of one level total: needs paging); Fusion monsters (7) have no recipe; Garlandolf and
  Kasha keep their stand-in effect (ON SUMMON of a Ritual/normal summon has no trigger); a duel with the real cards.
- Note [VERIFIED TargetRetreiver.RemoveCardAccordingToLevel]: the level target filter keeps only cards of exactly
  that level, so original keywords like "CRIPPLE ALL LV 6 & More MONSTERS" only hit level 6 (Cryomancer of the Ice
  Barrier got CRIPPLE ALL 300 instead of a new "LV 4 & More" row).
- 2026-11-02: owner review wave 1 (28 cards) in `content/series3/owner_review.json`; balance pass
  `tools/series3_balance.py` (re-runnable; real stats kept in real_atk/real_def): monster ATK/LP = Series 2 median of
  the rarity + 30% of the gap to the real value (-200 ATK for strong removal/protection), min ATK 100 (no more ATK 0
  cards); effect amounts capped per rarity (Series 1/2 amounts per keyword family), BAM legends at least the common
  cap; rarity floors for ANNIHILATE MONSTERS (3), SHARED FATE ALL / IMMUNE ALL / BREAK IMMUNITY ALL / RESURRECT
  MONSTERS (2). Result per rarity (ATK p50 / LP p50): R1 800/600, R2 1500/1100, R3 1900/1500, R4 2200/2100 (Series 2:
  1000/800, 1600/1000, 1800/1400, 2000/2100). Review notes read: a plain keyword replaces the same keyword or is added.
