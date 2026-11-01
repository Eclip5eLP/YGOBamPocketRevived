# New card effects worth adding (Series 3/4, 2026-11-01)

Collected during the per-card effect review (`content/series3/archetype_cards.json`: every reviewed card has
`effects` = buildable now from existing keywords, and optionally `effect_idea` = the new effect below that would fit
the real card better). Cards ship with `effects`; an idea replaces or joins them once the effect exists.

How effects work [VERIFIED]: an effect row is effect type + trigger + target + operator/amount + filters
(family/element/level) + flags (work/as3/.../inventory/enumeration/CardEffectTypes.as, EffectTriggers.as,
TargetTypes.as, Operators.as; rows in config/ace/inventory/item_template.ace). Keywords like BOOST 300 are just the
name/description texts of a row. So some "new" effects are only a new combination of existing pieces (data only),
others need engine code.

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

## Review progress

| Group | Cards | Reviewed |
|---|---|---|
| Stardust / Junk / Synchron | 75 | yes (2026-11-01) |
| Red Dragon Archfiend | 34 | |
| Black Rose | 26 | |
| Ice Barrier | 42 | |
| T.G. | 33 | |
| Koa'ki Meiru | 36 | |
| Standalone | 331 | |
