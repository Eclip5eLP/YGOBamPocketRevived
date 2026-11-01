# Series 3 card list (2026-11-01)

**577 cards: the 246 archetype cards below (all kept, owner's choice, including the later prints) + 331
standalone 5D's-era cards** (end of this file; `content/series3/standalone_cards.json`), next to Series 2's 567.

Archetypes: Stardust / Junk / Synchron, Red Dragon Archfiend (with Resonators), Black Rose, Ice Barrier, T.G.,
Koa'ki Meiru. Machine-readable copy: `content/series3/archetype_cards.json` (YGOPRODeck ids, kinds, real stats).
Already in the game and left out: 3 Ice Barrier cards (series 1), 8 Koa'ki Meiru cards (series 2), Trishula, Dragon
of the Ice Barrier (series 99).

**246 cards: 55 Tuners, 79 other monsters, 49 Synchro, 2 Fusion, 38 spells, 23 traps.** 89 of them were only printed
after the 5D's/ZEXAL era ("later" below, e.g. Junk Warrior Extreme, Stardust Warrior): keep or drop per card.
Without them: 157 cards. Series 3 then needs about 320-410 standalone cards from the 5D's era to reach ~570.

## Conversion rules (from Series 2, VERIFIED item_template.ace vs YGOPRODeck)

- ATK = the real ATK, life points (the game's "DEF") = the real DEF: Series 2 matches exactly (median ratio 1.0).
- Game level is not the real level: in Series 2 it is a power tier, usually about 2 above the real level (only 41 of
  405 match), and it rises with ATK/LP and rarity. Series 3 uses the **real level** so Synchro sums read like the
  real game (Junk Synchron 3 + level 2 = Junk Warrior 5); World 2 allows Series 3 decks only, so the two level
  scales don't meet there.
- Traps become spells (the game has monsters and spells only); every card gets an effect built from the game's six
  effect pieces (stat change, life points, destroy, immunity, break immunity, resurrect), with material effects for
  Synchro/Xyz where they fit.
- Rarity: to choose per card (Series 2 split: 215 common, 150 rare, 124 ultra rare, 78 legend).

### Stardust / Junk / Synchron

| Card | Kind | Level | ATK | DEF | Era print? |
|---|---|---|---|---|---|
| Changer Synchron | Tuner | 1 | 0 | 0 | yes |
| Cyberse Synchron | Tuner | 1 | 100 | 100 | **later** |
| Jet Synchron | Tuner | 1 | 500 | 0 | **later** |
| Junk Mail | Tuner | 1 | 400 | 100 | **later** |
| Mono Synchron | Tuner | 1 | 0 | 0 | yes |
| Turbo Synchron | Tuner | 1 | 100 | 500 | yes |
| Unknown Synchron | Tuner | 1 | 0 | 0 | yes |
| Assault Synchron | Tuner | 2 | 700 | 0 | **later** |
| Fleur Synchron | Tuner | 2 | 400 | 200 | **later** |
| Junk Anchor | Tuner | 2 | 0 | 0 | **later** |
| Necro Synchron | Tuner | 2 | 200 | 400 | **later** |
| Nitro Synchron | Tuner | 2 | 300 | 100 | yes |
| Satellite Synchron | Tuner | 2 | 700 | 100 | **later** |
| Drill Synchron | Tuner | 3 | 800 | 300 | yes |
| Junk Changer | Tuner | 3 | 1500 | 900 | **later** |
| Junk Synchron | Tuner | 3 | 1300 | 500 | yes |
| Starjunk Synchron | Tuner | 3 | 1300 | 500 | **later** |
| Steam Synchron | Tuner | 3 | 600 | 800 | yes |
| Bri Synchron | Tuner | 4 | 1500 | 1100 | yes |
| Hyper Synchron | Tuner | 4 | 1600 | 800 | yes |
| Road Synchron | Tuner | 4 | 1600 | 800 | yes |
| Stardust Synchron | Tuner | 4 | 1500 | 1000 | **later** |
| Quickdraw Synchron | Tuner | 5 | 700 | 1400 | yes |
| Junkuriboh | Monster | 1 | 300 | 200 | **later** |
| Stardust Phantom | Monster | 1 | 0 | 0 | yes |
| Stardust Wurm | Monster | 1 | 0 | 0 | **later** |
| Stardust Xiaolong | Monster | 1 | 100 | 100 | yes |
| Junk Armor | Monster | 2 | 600 | 1200 | **later** |
| Junk Converter | Monster | 2 | 400 | 200 | **later** |
| Synchron Carrier | Monster | 2 | 0 | 1000 | **later** |
| Synchron Explorer | Monster | 2 | 0 | 700 | yes |
| Junk Defender | Monster | 3 | 500 | 1800 | yes |
| Junk Forward | Monster | 3 | 900 | 1500 | yes |
| Junk Blader | Monster | 4 | 1800 | 1000 | yes |
| Junk Breaker | Monster | 4 | 1800 | 1000 | **later** |
| Junk Meister | Monster | 4 | 100 | 2300 | **later** |
| Junk Servant | Monster | 4 | 1500 | 1000 | yes |
| Stardust Trail | Monster | 4 | 500 | 2000 | **later** |
| Junk Collector | Monster | 5 | 1000 | 2200 | **later** |
| Junk Dragonlet | Monster | 5 | 2100 | 1800 | **later** |
| Junk Giant | Monster | 6 | 2000 | 2400 | yes |
| Formula Synchron | Synchro | 2 | 200 | 1500 | yes |
| Accel Synchron | Synchro | 5 | 500 | 2100 | **later** |
| Catapult Warrior | Synchro | 5 | 1000 | 1500 | yes |
| Junk Warrior | Synchro | 5 | 2300 | 1300 | yes |
| Junk Gardna | Synchro | 6 | 1400 | 2600 | **later** |
| Stardust Assault Warrior | Synchro | 6 | 2100 | 1200 | **later** |
| Stardust Charge Warrior | Synchro | 6 | 2000 | 1300 | **later** |
| Junk Archer | Synchro | 7 | 2300 | 2000 | yes |
| Junk Berserker | Synchro | 7 | 2700 | 1800 | yes |
| Accel Synchro Stardust Dragon | Synchro | 8 | 2500 | 2000 | **later** |
| Junk Destroyer | Synchro | 8 | 2600 | 2500 | yes |
| Junk Warrior Extreme | Synchro | 8 | 2900 | 2300 | **later** |
| Stardust Dragon | Synchro | 8 | 2500 | 2000 | yes |
| Stardust Dragon - Victim Sanctuary | Synchro | 8 | 2500 | 2000 | **later** |
| Stardust Spark Dragon | Synchro | 8 | 2500 | 2000 | yes |
| Stardust Chronicle Spark Dragon | Synchro | 10 | 3000 | 2500 | **later** |
| Stardust Warrior | Synchro | 10 | 3000 | 2500 | **later** |
| Stardust Sifr Divine Dragon | Synchro | 12 | 4000 | 4000 | yes |
| Arrive in Light | Spell |  |  |  | **later** |
| Junk Barrage | Spell |  |  |  | yes |
| Junk Box | Spell |  |  |  | yes |
| Junk Signal | Spell |  |  |  | **later** |
| Machine Assembly Line | Spell |  |  |  | yes |
| Scrap Fist | Spell |  |  |  | **later** |
| Stardust Illumination | Spell |  |  |  | **later** |
| Stardust Shimmer | Spell |  |  |  | yes |
| Starlight Junktion | Spell |  |  |  | **later** |
| Synchronized Realm | Spell |  |  |  | yes |
| Junk Sleep | Trap |  |  |  | **later** |
| Scrap-Iron Statue | Trap |  |  |  | **later** |
| Stardust Flash | Trap |  |  |  | **later** |
| Stardust Mirage | Trap |  |  |  | **later** |
| Stardust Re-Spark | Trap |  |  |  | yes |
| Stardust Wish | Trap |  |  |  | **later** |

75 cards, 40 only in later sets.

### Red Dragon Archfiend

| Card | Kind | Level | ATK | DEF | Era print? |
|---|---|---|---|---|---|
| Barrier Resonator | Tuner | 1 | 300 | 800 | yes |
| Chain Resonator | Tuner | 1 | 100 | 100 | yes |
| Double Resonator | Tuner | 1 | 0 | 0 | **later** |
| Mirror Resonator | Tuner | 1 | 0 | 0 | yes |
| Synkron Resonator | Tuner | 1 | 100 | 100 | yes |
| Crimson Resonator | Tuner | 2 | 800 | 300 | **later** |
| Force Resonator | Tuner | 2 | 500 | 500 | yes |
| Red Resonator | Tuner | 2 | 600 | 200 | yes |
| Vision Resonator | Tuner | 2 | 400 | 400 | **later** |
| Clock Resonator | Tuner | 3 | 1200 | 600 | yes |
| Creation Resonator | Tuner | 3 | 800 | 600 | yes |
| Dark Resonator | Tuner | 3 | 1300 | 300 | yes |
| Darkness Resonator | Tuner | 3 | 1300 | 300 | **later** |
| Flare Resonator | Tuner | 3 | 300 | 1300 | yes |
| Soul Resonator | Tuner | 3 | 500 | 200 | **later** |
| Red Warg | Monster | 6 | 1400 | 2200 | yes |
| Red Dragon Archfiend/Assault Mode | Monster | 10 | 3500 | 2500 | yes |
| Red Rising Dragon | Synchro | 6 | 2100 | 1600 | **later** |
| Red Wyvern | Synchro | 6 | 2400 | 2000 | yes |
| Hot Red Dragon Archfiend | Synchro | 8 | 3000 | 2000 | yes |
| Red Dragon Archfiend | Synchro | 8 | 3000 | 2000 | yes |
| Scarlight Red Dragon Archfiend | Synchro | 8 | 3000 | 2500 | yes |
| Hot Red Dragon Archfiend Abyss | Synchro | 9 | 3200 | 2500 | yes |
| Hot Red Dragon Archfiend Bane | Synchro | 10 | 3500 | 3000 | yes |
| Majestic Red Dragon | Synchro | 10 | 4000 | 3000 | yes |
| Tyrant Red Dragon Archfiend | Synchro | 10 | 3500 | 3000 | yes |
| Hot Red Dragon Archfiend King Calamity | Synchro | 12 | 4000 | 3500 | yes |
| Red Nova Dragon | Synchro | 12 | 3500 | 3000 | yes |
| Resonant Destruction | Spell |  |  |  | yes |
| Resonator Call | Spell |  |  |  | yes |
| Resonator Command | Spell |  |  |  | **later** |
| Resonator Engine | Spell |  |  |  | yes |
| Red Carpet | Trap |  |  |  | yes |
| Red Dragon Archfiend's Chains | Trap |  |  |  | **later** |

34 cards, 8 only in later sets.

### Black Rose

| Card | Kind | Level | ATK | DEF | Era print? |
|---|---|---|---|---|---|
| Red Rose Dragon | Tuner | 3 | 1000 | 1800 | **later** |
| Twilight Rose Knight | Tuner | 3 | 1000 | 1000 | yes |
| Rose, Warrior of Revenge | Tuner | 4 | 1600 | 600 | yes |
| Witch of the Black Rose | Tuner | 4 | 1700 | 1200 | yes |
| Rose Lover | Monster | 1 | 800 | 800 | yes |
| Rose Archer | Monster | 3 | 1000 | 100 | yes |
| Rose Fairy | Monster | 3 | 600 | 1200 | yes |
| Bird of Roses | Monster | 4 | 1800 | 1500 | yes |
| Blue Rose Dragon | Monster | 4 | 1600 | 1200 | yes |
| Revival Rose | Monster | 4 | 1300 | 1300 | yes |
| Rose Paladin | Monster | 4 | 1800 | 200 | yes |
| Rose Witch | Monster | 4 | 1600 | 1000 | yes |
| White Rose Dragon | Monster | 4 | 1200 | 1000 | **later** |
| Rose Tentacles | Monster | 6 | 2200 | 1200 | yes |
| Regenerating Rose | Monster | 7 | 0 | 1500 | **later** |
| Garden Rose Maiden | Synchro | 5 | 1600 | 2400 | **later** |
| Splendid Rose | Synchro | 6 | 2200 | 2000 | yes |
| Black Rose Dragon | Synchro | 7 | 2400 | 1800 | yes |
| Black Rose Moonlight Dragon | Synchro | 7 | 2400 | 1800 | yes |
| Rose Spectre of Dunn | Fusion | 6 | 2000 | 1800 | **later** |
| Black Garden | Spell |  |  |  | yes |
| Frozen Rose | Spell |  |  |  | **later** |
| Mark of the Rose | Spell |  |  |  | yes |
| Thorn of Malice | Spell |  |  |  | yes |
| White Rose Cloister | Spell |  |  |  | **later** |
| Blooming of the Darkest Rose | Trap |  |  |  | **later** |

26 cards, 8 only in later sets.

### Ice Barrier

| Card | Kind | Level | ATK | DEF | Era print? |
|---|---|---|---|---|---|
| Hexa Spirit of the Ice Barrier | Tuner | 1 | 400 | 200 | **later** |
| Cryomancer of the Ice Barrier | Tuner | 2 | 1300 | 0 | yes |
| Dewdark of the Ice Barrier | Tuner | 2 | 1200 | 800 | yes |
| Mirror Mage of the Ice Barrier | Tuner | 2 | 1000 | 400 | **later** |
| Defender of the Ice Barrier | Tuner | 3 | 200 | 1600 | yes |
| Geomancer of the Ice Barrier | Tuner | 3 | 800 | 1200 | yes |
| Georgius, Swordman of the Ice Barrier | Tuner | 6 | 2000 | 1200 | **later** |
| Blizzed, Defender of the Ice Barrier | Monster | 1 | 300 | 500 | yes |
| Prior of the Ice Barrier | Monster | 2 | 1000 | 400 | yes |
| Secret Guards of the Ice Barrier | Monster | 2 | 100 | 1600 | yes |
| Zuijin of the Ice Barrier | Monster | 2 | 500 | 300 | **later** |
| Shock Troops of the Ice Barrier | Monster | 3 | 1500 | 800 | yes |
| Warlock of the Ice Barrier | Monster | 3 | 400 | 1000 | yes |
| Dance Princess of the Ice Barrier | Monster | 4 | 1700 | 900 | yes |
| Judge of the Ice Barrier | Monster | 4 | 1800 | 900 | **later** |
| Numbing Grub in the Ice Barrier | Monster | 4 | 1300 | 1800 | yes |
| Pilgrim of the Ice Barrier | Monster | 4 | 1500 | 1000 | yes |
| Revealer of the Ice Barrier | Monster | 4 | 1700 | 1000 | **later** |
| Samurai of the Ice Barrier | Monster | 4 | 1800 | 1500 | yes |
| Speaker for the Ice Barriers | Monster | 4 | 1000 | 1800 | **later** |
| Spellbreaker of the Ice Barrier | Monster | 4 | 1200 | 2000 | yes |
| Strategist of the Ice Barrier | Monster | 4 | 1600 | 1600 | yes |
| General Wayne of the Ice Barrier | Monster | 5 | 2100 | 400 | **later** |
| Dai-sojo of the Ice Barrier | Monster | 6 | 1600 | 2200 | yes |
| General Raiho of the Ice Barrier | Monster | 6 | 2100 | 2300 | yes |
| General Gantala of the Ice Barrier | Monster | 7 | 2700 | 2000 | yes |
| Medium of the Ice Barrier | Monster | 7 | 2200 | 1600 | yes |
| General Grunard of the Ice Barrier | Monster | 8 | 2800 | 1000 | yes |
| Brionac, Dragon of the Ice Barrier | Synchro | 6 | 2300 | 1400 | yes |
| Dewloren, Tiger King of the Ice Barrier | Synchro | 6 | 2000 | 1400 | yes |
| Gungnir, Dragon of the Ice Barrier | Synchro | 7 | 2500 | 1700 | yes |
| Ekhajar, Descendant Dragon of the Ice Barrier | Synchro | 9 | 3000 | 1000 | **later** |
| Trishula, Zero Dragon of the Ice Barrier | Synchro | 11 | 2700 | 2000 | **later** |
| Trishula, the Dragon of Icy Imprisonment | Fusion | 9 | 2700 | 2000 | **later** |
| Freezing Chains of the Ice Barrier | Spell |  |  |  | **later** |
| Magic Triangle of the Ice Barrier | Spell |  |  |  | yes |
| Medallion of the Ice Barrier | Spell |  |  |  | yes |
| Mirror of the Ice Barrier | Spell |  |  |  | yes |
| Winds Over the Ice Barrier | Spell |  |  |  | **later** |
| Frozen Domain of the Ice Barrier | Trap |  |  |  | **later** |
| Ice Barrier | Trap |  |  |  | **later** |
| Terror of Trishula | Trap |  |  |  | **later** |

42 cards, 16 only in later sets.

### T.G.

| Card | Kind | Level | ATK | DEF | Era print? |
|---|---|---|---|---|---|
| T.G. Cyber Magician | Tuner | 1 | 0 | 0 | yes |
| T.G. Gear Zombie | Tuner | 1 | 600 | 0 | **later** |
| T.G. Tank Grub | Tuner | 1 | 0 | 0 | **later** |
| T.G. Striker | Tuner | 2 | 800 | 0 | yes |
| T.G. Jet Falcon | Tuner | 3 | 1400 | 1200 | yes |
| T.G. Screw Serpent | Tuner | 4 | 1300 | 500 | **later** |
| T.G. Booster Raptor | Monster | 1 | 400 | 300 | **later** |
| T.G. Drill Fish | Monster | 1 | 100 | 800 | **later** |
| T.G. Rocket Salamander | Monster | 1 | 600 | 600 | **later** |
| T.G. Catapult Dragon | Monster | 2 | 900 | 1300 | yes |
| T.G. Metal Skeleton | Monster | 2 | 1100 | 0 | **later** |
| T.G. Warwolf | Monster | 3 | 1200 | 0 | yes |
| T.G. Rush Rhino | Monster | 4 | 1600 | 800 | yes |
| T.G. Mighty Striker | Synchro | 2 | 1800 | 0 | **later** |
| T.G. Recipro Dragonfly | Synchro | 2 | 300 | 300 | yes |
| T.G. Hyper Librarian | Synchro | 5 | 2400 | 1800 | yes |
| T.G. Over Dragonar | Synchro | 5 | 2100 | 1900 | **later** |
| T.G. Power Gladiator | Synchro | 5 | 2300 | 1000 | yes |
| T.G. Star Guardian | Synchro | 5 | 100 | 2200 | **later** |
| T.G. Wonder Magician | Synchro | 5 | 1900 | 0 | yes |
| Shooting Star Dragon T.G. EX | Synchro | 10 | 3300 | 2500 | **later** |
| T.G. Blade Blaster | Synchro | 10 | 3300 | 2200 | yes |
| T.G. Glaive Blaster | Synchro | 12 | 4000 | 4000 | **later** |
| T.G. Halberd Cannon | Synchro | 12 | 4000 | 4000 | yes |
| T.G. All Clear | Spell |  |  |  | **later** |
| T.G. Limiter Removal | Spell |  |  |  | **later** |
| TGX1-HL | Spell |  |  |  | yes |
| TGX300 | Spell |  |  |  | yes |
| Sonic Stun | Trap |  |  |  | **later** |
| T.G. Close | Trap |  |  |  | **later** |
| TG-SX1 | Trap |  |  |  | yes |
| TG1-EM1 | Trap |  |  |  | yes |
| TGX3-DX2 | Trap |  |  |  | yes |

33 cards, 16 only in later sets.

### Koa'ki Meiru

| Card | Kind | Level | ATK | DEF | Era print? |
|---|---|---|---|---|---|
| Koa'ki Meiru Doom | Monster | 3 | 1700 | 800 | yes |
| Koa'ki Meiru Hydro Barrier | Monster | 3 | 1000 | 1900 | yes |
| Koa'ki Meiru Speeder | Monster | 3 | 1200 | 2200 | yes |
| Koa'ki Meiru Beetle | Monster | 4 | 1900 | 1500 | yes |
| Koa'ki Meiru Bergzak | Monster | 4 | 2000 | 200 | yes |
| Koa'ki Meiru Crusader | Monster | 4 | 1900 | 1300 | yes |
| Koa'ki Meiru Drago | Monster | 4 | 1900 | 1600 | yes |
| Koa'ki Meiru Gravirose | Monster | 4 | 1900 | 1300 | yes |
| Koa'ki Meiru Ice | Monster | 4 | 1900 | 1200 | yes |
| Koa'ki Meiru Overload | Monster | 4 | 1900 | 1200 | yes |
| Koa'ki Meiru Powerhand | Monster | 4 | 2100 | 1600 | yes |
| Koa'ki Meiru Sea Panther | Monster | 4 | 1900 | 1200 | yes |
| Koa'ki Meiru Supplier | Monster | 4 | 1400 | 1600 | **later** |
| Koa'ki Meiru Tornado | Monster | 4 | 1500 | 1200 | yes |
| Koa'ki Meiru Urnight | Monster | 4 | 2000 | 1500 | yes |
| Koa'ki Meiru War Arms | Monster | 4 | 1400 | 1200 | yes |
| Koa'ki Meiru Ghoulungulate | Monster | 5 | 2500 | 1700 | yes |
| Koa'ki Meiru Rooklord | Monster | 7 | 2800 | 2200 | yes |
| Koa'ki Meiru Maximus | Monster | 8 | 3000 | 2500 | yes |
| Koa'ki Meiru Valafar | Monster | 8 | 3000 | 2100 | yes |
| Core Blaster | Spell |  |  |  | yes |
| Core Compression | Spell |  |  |  | yes |
| Core Overclock | Spell |  |  |  | yes |
| Core Transport Unit | Spell |  |  |  | yes |
| Diamond Core of Koa'ki Meiru | Spell |  |  |  | yes |
| Iron Core Armor | Spell |  |  |  | yes |
| Iron Core Immediate Disposal | Spell |  |  |  | yes |
| Iron Core Specimen Lab | Spell |  |  |  | yes |
| Koa'ki Ring | Spell |  |  |  | yes |
| Urgent Synthesis | Spell |  |  |  | yes |
| Automatic Laser | Trap |  |  |  | yes |
| Core Blast | Trap |  |  |  | yes |
| Core Reinforcement | Trap |  |  |  | yes |
| Iron Core Luster | Trap |  |  |  | yes |
| Nega-Ton Corepanel | Trap |  |  |  | yes |
| Reckoned Power | Trap |  |  |  | yes |

36 cards, 1 only in later sets.


## Standalone cards (331)

Chosen from cards printed in the 5D's core boosters (TDGS-EXVC), not in an archetype, not in the game: all 28
Synchro, 39 Tuners, 5 Fusion, 2 Ritual; 164 other monsters spread over levels 1-12; 55 spells, 38 traps. Cards whose
real effect maps onto the game's effect pieces (destroy, damage, life points, ATK up/down, revive, protection) were
preferred: 258 of 331. Any card can be swapped.

### Synchro (28)

Sun Dragon Inti (Lv8), Black-Winged Dragon (Lv8), Nitro Warrior (Lv7), Doomkaiser Dragon (Lv6), Exploder Dragonwing (Lv7), Ancient Fairy Dragon (Lv7), Arcanite Magician (Lv7), Turbo Cannon (Lv3), Shooting Star Dragon (Lv10), Black Brutdrago (Lv8), Trident Dragion (Lv10), Lightning Tricorn (Lv8), Dark Strike Fighter (Lv7), Light End Dragon (Lv8), Explosive Magician (Lv6), Moon Dragon Quilla (Lv6), Voltic Bicorn (Lv7), Revived King Ha Des (Lv6), Drill Warrior (Lv6), Psychic Nightmare (Lv6), Underground Arachnid (Lv6), Tempest Magician (Lv6), Thunder Unicorn (Lv5), Ancient Sacred Wyvern (Lv7), Vortex the Whirlwind (Lv5), Turbo Warrior (Lv6), Zeman the Ape King (Lv7), Queen of Thorns (Lv6)

### Tuner (39)

Egotistical Ape (Lv5), Turbo Rocket (Lv2), Fire Ant Ascator (Lv3), Spore (Lv1), Snyffus (Lv1), Trap Eater (Lv4), Delta Flyer (Lv3), Night's End Sorcerer (Lv2), Nettles (Lv2), Sword Master (Lv3), Dread Dragon (Lv2), Top Runner (Lv4), Cherry Inmato (Lv2), Comrade Swordsman of Landstar (Lv3), Elephun (Lv2), Counselor Lily (Lv3), Sinister Sprocket (Lv1), Sunny Pixie (Lv1), Key Mouse (Lv1), Attack Gainer (Lv1), Emissary from Pandemonium (Lv7), Royal Swamp Eel (Lv4), Krebons (Lv2), Dark Tinker (Lv2), Debris Dragon (Lv4), Synchro Magnet (Lv3), Mental Seeker (Lv3), Jutte Fighter (Lv2), Torapart (Lv2), Esper Girl (Lv2), Supay (Lv1), Deep Sea Diva (Lv2), Hanewata (Lv1), Black Salvo (Lv3), Glow-Up Bulb (Lv1), Mind Master (Lv1), Copy Plant (Lv1), Effect Veiler (Lv1), Uni-Horned Familiar (Lv2)

### Fusion (5)

Ultimate Axon Kicker (Lv10), Supreme Arcanite Magician (Lv10), Chimera the Flying Mythical Beast (Lv6), Dragon Knight Draco-Equiste (Lv10), Multiple Piece Golem (Lv7)

### Ritual (2)

Divine Grace - Northwemko (Lv7), Garlandolf, King of Destruction (Lv7)

### Monster (164)

Black Potan (Lv1), Mecha Bunny (Lv2), Pursuit Chaser (Lv3), Dark Hunter (Lv4), Summon Reactor SK (Lv5), Psychic Emperor (Lv6), Ancient Crimson Ape (Lv7), Ice Queen (Lv8), White Potan (Lv1), Playful Possum (Lv2), Mermaid Archer (Lv3), Hardened Armed Dragon (Lv4), Handcuffs Dragon (Lv5), Strong Wind Dragon (Lv6), Greed Quasar (Lv7), Fiendish Engine Omega (Lv8), Buster Blaster (Lv1), Damage Eater (Lv2), Spell Reactor RE (Lv3), Zombie Mammoth (Lv4), Gigastone Omega (Lv5), Ido the Supreme Magical Force (Lv6), Puppet King (Lv7), Montage Dragon (Lv8), Cursed Fig (Lv1), Necro Defender (Lv2), Mine Mole (Lv3), Apocatequil (Lv4), Final Psychic Ogre (Lv5), Power Giant (Lv6), Yellow Baboon, Archer of the Forest (Lv7), White Night Dragon (Lv8), Dark Bug (Lv1), Shield Wing (Lv2), Shield Warrior (Lv3), Catoblepas and the Witch of Fate (Lv4), Prime Material Falcon (Lv5), Yamato-no-Kami (Lv6), King of the Beasts (Lv7), Dark Voltanis (Lv8), Evil Thorn (Lv1), Tree Otter (Lv2), Trigon (Lv3), Max Warrior (Lv4), Memory Crush King (Lv5), Il Blud (Lv6), Red Ogre (Lv7), Light and Darkness Dragon (Lv8), Mirror Ladybug (Lv1), Doppelwarrior (Lv2), Hedge Guard (Lv3), Battlestorm (Lv4), Salvage Warrior (Lv5), Brain Golem (Lv6), Zeta Reticulant (Lv7), Splendid Venus (Lv8), Moja (Lv1), Needle Ball (Lv2), Oyster Meister (Lv3), Energy Bravery (Lv4), Oracle of the Sun (Lv5), Ambitious Gofer (Lv6), Ice Master (Lv8), Dark Spider (Lv1), Noisy Gnat (Lv2), Seed of Flame (Lv3), Maiden of Macabre (Lv4), Tethys, Goddess of Light (Lv5), Tiger Dragon (Lv6), The Dark Creator (Lv8), Darksea Float (Lv1), Ally Salvo (Lv2), Fairy Archer (Lv3), Bone Crusher (Lv4), Power Invader (Lv5), Storm Caller (Lv6), Clear Vice Dragon (Lv8), Synchro Soldier (Lv1), Horseytail (Lv2), Oshaleon (Lv3), Card Guard (Lv4), Big Piece Golem (Lv5), Gaap the Divine Soldier (Lv6), Kasha (Lv8), Turbo Booster (Lv1), Oilman (Lv2), Rai-Mei (Lv3), Stygian Street Patrol (Lv4), Divine Dragon Aquabizarre (Lv5), Knight of the Red Lotus (Lv6), Sauropod Brachion (Lv8), Level Eater (Lv1), Power Supplier (Lv2), Serene Psychic Witch (Lv3), Spyder Spider (Lv4), Majioshaleon (Lv5), Dragon Queen of Tragic Endings (Lv6), Bee List Soldier (Lv1), Relinquished Spider (Lv2), Woodland Archer (Lv3), Jade Knight (Lv4), The Tricky (Lv5), Akz, the Pumer (Lv6), Kinka-byo (Lv1), Wall of Ivy (Lv2), Spined Gillman (Lv3), Vice Berserker (Lv4), Earthquake Giant (Lv5), Mother Spider (Lv6), Kuribon (Lv1), Bicular (Lv2), Monoceros (Lv3), Trap Reactor Y FI (Lv4), Berfomet (Lv5), Izanagi (Lv6), A/D Changer (Lv1), Card Breaker (Lv2), Second Booster (Lv3), Viser Des (Lv4), Turret Warrior (Lv5), Minoan Centaur (Lv6), Cosmic Compass (Lv1), Dark Verger (Lv2), Dash Warrior (Lv3), Ghost Gardna (Lv4), Scary Moth (Lv6), Needle Soldier (Lv1), Dark Desertapir (Lv2), Tricular (Lv3), Zero Gardna (Lv4), Puppet Master (Lv6), Unicycular (Lv1), Phoenixian Seed (Lv2), Mind Protector (Lv3), Rai-Jin (Lv4), Battle Fader (Lv1), Quillbolt Hedgehog (Lv2), Inmato (Lv3), Skull Conductor (Lv4), Darksea Rescue (Lv1), Synchro Fusionist (Lv2), Gonogo (Lv3), Cactus Fighter (Lv4), Droll & Lock Bird (Lv1), Psi-Beast (Lv2), Botanical Girl (Lv3), Power Breaker (Lv4), Mystic Piper (Lv1), Extra Veiler (Lv2), Lock Cat (Lv3), Gigantic Cephalotus (Lv4), Swift Scarecrow (Lv1), Magicat (Lv2), Small Piece Golem (Lv3), Anarchist Monk Ranshin (Lv4), Testudo erat Numen (Lv1), Necro Linker (Lv2), Tour Guide From the Underworld (Lv3), Rockstone Warrior (Lv4), Scanner (Lv1), Totem Dragon (Lv2), Spellstone Sorcerer Karood (Lv3), Biofalcon (Lv4), Silent Strider (Lv2)

### Spell (55)

Axe of Fools, Cursed Bill, Electromagnetic Shield, Emergency Assistance, Fighting Spirit, Molting Escape, Orb of Yasaka, Pestilence, Pyramid of Wonders, Raging Mad Plants, Rocket Pilder, Silver Wing, Temple of the Sun, The Fountain in the Sky, The World Tree, Ancient Forest, Arcane Barrier, Assault Armor, Beast Rage, Break! Draw!, Clear World, Cursed Armaments, Darkworld Shackles, Domino Effect, Double Cyclone, Dragon Laser, ESP Amplifier, Everliving Underworld Cannon, Faustian Bargain, Fragrance Storm, Gemini Spark, Hydro Pressure Cannon, Makiu, the Magical Mist, Miracle Fertilizer, Miracle Synchro Fusion, Mirror of Yata, Out of the Blue, Paralyzing Chain, Power Pickaxe, Prevention Star, Psychokinesis, Release Restraint Wave, Ritual Cage, Ritual of Destruction, Savage Colosseum, Seed Cannon, Solidarity, Spirit Burner, Spiritual Forest, Summoning Curse, Super Solar Nutrient, Supremacy Berry, Telekinetic Power Well, Token Sundae, Unstable Evolution

### Trap (38)

Ebon Arrow, Fake Explosion, Overdoom Line, Token Stampede, Blossom Bombardment, Bone Temple Block, Destruct Potion, Gemini Booster, Guard Mines, Horn of the Phantom Beast, Howl of the Wild, Plant Food Chain, Psi-Curse, Safe Zone, Trap of the Imperial Tomb, Barrier Wave, Brain Hazard, Broken Blocker, Call of the Reaper, Chain Whirlwind, Darkfall, Depth Amulet, Desperate Tag, Fairy Wind, Fiendish Chain, Fish Depth Charge, Full House, Gemini Counter, Graceful Revival, Gravity Collapse, Ivy Shackles, Judgment of Thunder, Lair Wire, Lineage of Destruction, Meteor Flare, Mind Over Matter, Miracle Locus, Miracle's Wake

