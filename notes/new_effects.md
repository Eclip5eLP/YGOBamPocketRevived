# New card effects worth adding (Series 3/4, 2026-11-01)

Collected during the per-card effect review (`content/series3/archetype_cards.json`: every reviewed card has
`effects` = buildable now from existing keywords, and optionally `effect_idea` = the new effect below that would fit
the real card better). Cards ship with `effects`; an idea replaces or joins them once the effect exists.

How effects work [VERIFIED]: an effect row is effect type + trigger + target + operator/amount + filters
(family/element/level) + flags (work/as3/.../inventory/enumeration/CardEffectTypes.as, EffectTriggers.as,
TargetTypes.as, Operators.as; rows in config/ace/inventory/item_template.ace). Keywords like BOOST 300 are just the
name/description texts of a row. So some "new" effects are only a new combination of existing pieces (data only),
others need engine code.

## Approved by the owner (todo, 2026-11-01)

To build (code or data, whichever each needs); the review already uses these names in `effect_idea`:

- [x] **ON SYNCHRO / ON XYZ / ON FUSION: X** - "When this Monster is Synchro/Xyz/Fusion Summoned, X." (A1 below)
- [x] **MATERIAL: X** - "When this card is used for a Summon, the new Monster gets X." (B1)
- [x] **LEVEL UP n / LEVEL DOWN n / LEVEL SET n** - Level for Synchro totals and Xyz ranks, this Round. (B2)
- [x] **REBIRTH** - "When this Monster is destroyed, it is shuffled back into your Deck." (B3)
- [x] **GUARDIAN** - "When another of your cards would be destroyed, this Monster is destroyed instead." (B4)
- [x] **BOOST ALL SYNCHROS / XYZ / FUSIONS** (plus IMMUNE/CRIPPLE variants where cards need them) - target filter
  on the summon kind. (B6)
- [x] **ON SYNCHRO SUMMON / ON XYZ SUMMON / ON FUSION SUMMON: X** - "Every time you Synchro Summon, X." on any of
  your cards in play (a Spell or another Monster). (B10)

Not approved for now: DRAW, BANISH, CLEAVE, PIERCE (cards keep their existing-keyword effects).

### Built (2026-11-01)

All seven are rules on effect rows in config/summons.json "effects" (like the material effects), written by
`content_mods.effect_row` (a new row copied from an existing keyword's row: own id and texts, trigger/target changed,
rule added). Behaviour: `as3_new/com/revival/summon/Summon.as` ("New effects") and `LevelEffect.as`; engine hooks:
`tools/as3_patches.py` NEW_EFFECT_EDITS.

| Effect | Row | Hook | Emulator (Arena, test deck, 2026-11-01) |
|---|---|---|---|
| ON SYNCHRO/XYZ/FUSION | trigger ON_FUSION (32), dispatcher self | none (RoundHandler.DoFusionLaunch already launches it) | VERIFIED: Stardust Dragon made, opponent -1000 at once |
| ON ... SUMMON | trigger 32, dispatcher player, rule summonKind | DoFusionLaunch adds the owner to the dispatchers; Summon.CanResolveEffect | VERIFIED: Synchro -> -500; an Xyz (Utopia) -> nothing |
| BOOST ALL SYNCHROS | any boost row, rule targetKind | TargetRetreiver.GetEffectTarget filter | VERIFIED: Stardust +600 at round start; Utopia (Xyz) unchanged |
| MATERIAL | row on the material, trigger none, target self, rule material | Summon.OnSummoned -> CardBO.RevivalAddEffects (fires with ON_FUSION) | VERIFIED: Stardust 2500 -> 3100 from Junk Synchron |
| LEVEL UP/DOWN/SET | row with no modifier, rule level/levelSet (oncePerGame for SET) | EffectCreater makes a LevelEffect; CardBO.RevivalLevel, saved in CardSaveState | VERIFIED: Ansatsu set to 3 no longer pairs with a level 4 Warrior; the control pair (two level 4) still makes Utopia |
| REBIRTH | text row, trigger none, rule rebirth | RoundHandler.ClearDeadCards flags the card (a result: its materials) like a resurrection | VERIFIED: Stardust destroyed -> "Resurrected", both materials back in the Deck (deck count +2) |
| GUARDIAN | text row, trigger none, rule guardian | EffectHandler.ResolveDestroyCard / ResolveNormalAttack: Summon.Destroyed | not seen yet: the AI killed by Power loss (ATK to 0), which GUARDIAN does not cover |

Level display (owner request): while a card's duel Level differs from its printed one, the duel card shows a gold
"Lv N" badge (DuelCard.RevivalLevel, under the Xyz material badge) and the zoomed card shows the duel Level
(DetailedCardVisual.RevivalLevelOverride via CardZoomingHandler). A Level change lasts while the card is on the field:
GameMatBO.PlaceCardInGraveyard resets it (every way into the graveyard passes there); drawing a card resets it too
(CardBO.ResetCardValue). VERIFIED emulator: badge on a Level-3 Ansatsu (own and opponent's), zoom shows 3, badge gone
once it is in the graveyard.
GUARDIAN covers destruction by an effect and by battle only, not a card whose Power drops to 0 (owner decision). Real Series 3 cards get these rows when the cards are built (their `effect_idea`).

## A. Data only (new rows from existing engine pieces; need an emulator test)

| Effect | Text (game style) | How | Cards |
|---|---|---|---|
| ON SYNCHRO / ON XYZ: X | "When this Monster is Synchro Summoned, ..." | trigger ON_FUSION (32): RoundHandler.DoFusionLaunch launches it for the new card (work/as3/.../round/RoundHandler.as:370), our Synchro/Xyz go through the same code (tools/as3_patches.py RoundHandler edit) [VERIFIED]. No original card uses trigger 32 [VERIFIED trigger counts], so whether the result's own row fires is INFERRED: test first | Formula Synchron (draw → see DRAW), Junk Warrior, Junk Destroyer, Stardust Assault Warrior, Accel Synchro Stardust Dragon; many Series 3/4 Synchros and Xyz |
| per-ally "+" amounts | "Your Monster gains Power." (+ per ally) | friendEffect flag with friendMultiplierValue/maxNbFriend, as BOOST 100 + (Common Soul) [VERIFIED] | Junk Warrior (BOOST 300 +, used now) |
| new amounts | e.g. BOOST ALL MACHINES 200 | copy a row, new modifier + name text | used now: NECRO BOOST 100, BOOST 300 +, BOOST ALL MACHINES 200 |

Not usable: COWARDICE_COURAGE (type 49, "gains Power when the opponent has 1 or less monster") is in the enum but
no card uses it and nothing under module/ references it [VERIFIED grep] → unimplemented.

## B. Engine (new code, like the material effects in com.revival.summon.Summon)

Ordered by how many Series 3/4 cards would use them.

1. **MATERIAL: X** - "When this card is used for a Synchro or Xyz Summon, the new Monster gets X." The material's
   effect row is applied to the result after `CreateFusionCard` (Summon already knows both materials). Rules
   would sit in config/summons.json `effects` like the existing needs/cost rules (`{"material": true}`).
   Cards: Bri Synchron (BOOST 600), Hyper Synchron (BOOST 800), Junk Mail (IMMUNE), Changer Synchron, Fleur
   Synchron, Junk Converter, Nitro Synchron; many Tuners of Series 3, Xyz material support in Series 4.
2. **LEVEL UP n / LEVEL DOWN n / LEVEL SET n** - "Your Monster's Level rises by n this Round." Changes the Level
   used for Synchro totals and Xyz ranks. Needs a runtime level on CardBO that `Summon.Candidates` reads instead of
   the template level. Cards: Junk Changer, Road Synchron, Necro Synchron, Satellite Synchron, Cyberse Synchron,
   Mono Synchron, Junk Meister, Accel Synchron, Stardust Illumination; Series 4 rank tricks.
3. **REBIRTH** - "When this Monster is destroyed, it is shuffled back into your Deck." A RESURRECT that takes this
   card instead of a random one. Cards: Stardust Dragon, Stardust Warrior, Jet Synchron; Red Dragon Archfiend
   and Black Rose cards with the same "returns at the End Phase" text.
4. **GUARDIAN** - "When another of your cards would be destroyed, this Monster is destroyed instead." Cards:
   Stardust Dragon (with REBIRTH it is the real card), Stardust Phantom, Cyberse Synchron.
5. **DRAW n** - "Draw n more cards next Round." Cards: Formula Synchron, Nitro Synchron, Stardust Charge Warrior,
   Stardust Re-Spark; common in Series 3 standalone spells. Hand size rules: unknown, to look up.
6. **BOOST ALL SYNCHROS / XYZ** (and IMMUNE/CRIPPLE variants) - a target filter on the summon kind
   (Summon.Kind). Cards: Junk Dragonlet, Junk Armor, Junk Signal, Stardust Wish; Series 4 Utopia/Photon support.
7. **BANISH** - "Your Opponent's Monster leaves the battle this Round and comes back next Round." Cards: Junk
   Archer; many Series 4 cards.
8. **CLEAVE** - "Also attacks the Opponent's Monsters in the other channels." Cards: Stardust Charge Warrior.
9. **PIERCE** - "Excess Power goes through to the Opponent's Life Points." Whether the game already carries
   excess battle damage over: unknown, check RoundHandler's battle code first. Cards: Drill Synchron, Stardust
   Assault Warrior (SHOCK used now).
10. **ON ANY SYNCHRO** - "Every time you Synchro Summon, ..." on a Spell or other monster. Probably ON_FUSION with
    the player as dispatcher filter; may be data only (test). Cards: Synchronized Realm.

## Review rules learned

- Whole-board keywords (ANNIHILATE MONSTERS, SACRIFICE ALL MONSTERS) are only on spells in the original data, on
  trigger CARD_ATTACK (11) of the card itself [VERIFIED item_template.ace: Raigeki, Crystal Raigeki, Heavy Storm]. On a
  monster that trigger fires on every attack, so board-wipe monsters (Black Rose Dragon, Hot Red Dragon Archfiend,
  Tyrant Red Dragon Archfiend) get a strong CRIPPLE ALL now and the wipe as ON SYNCHRO once that exists.
- `python tools/effect_mapper.py --check content/series3/archetype_cards.json` lists every keyword that is not in the
  original data: a new amount (BOOST ALL MACHINES 200) or a new target (BOOST ALL PLANTS 200) is a copied row with a
  new modifier or family filter and a new name text; UNKNOWN must not happen.

- Real cards with "?" ATK/DEF (-1 in YGOPRODeck: Greed Quasar, Montage Dragon, Clear Vice Dragon, Kasha, Rai-Jin,
  Scanner) get fixed stats in the card data (`stats_fixed: true`), chosen from their real effect.
- Traps become spells and use keywords the original spells use (no SHOCK/SNEAK/OSMOSIS on spells).

## Review progress

| Group | Cards | Reviewed |
|---|---|---|
| Stardust / Junk / Synchron | 75 | yes (2026-11-01) |
| Red Dragon Archfiend | 34 | yes (2026-11-01) |
| Black Rose | 26 | yes (2026-11-01) |
| Ice Barrier | 42 | yes (2026-11-01) |
| T.G. | 33 | yes (2026-11-01) |
| Koa'ki Meiru | 36 | yes (2026-11-01) |
| Standalone | 331 | yes (2026-11-01) |

Series 3 cards waiting for an approved new effect (`effect_idea`, archetype + standalone): LEVEL 27, MATERIAL 20, ON 18, REBIRTH 15, GUARDIAN 8, BOOST 2, IMMUNE 2 (92 of 577 cards).
