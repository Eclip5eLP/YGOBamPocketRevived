# Series 3 card list, draft (2026-11-01)

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

