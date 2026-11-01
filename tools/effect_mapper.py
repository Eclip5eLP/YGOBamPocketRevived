#!/usr/bin/env python3
"""
Suggest BAM effects for real Yu-Gi-Oh! cards (Series 3/4, notes/content_patch_series3.md).

BAM cards carry named effect keywords with an amount (BOOST 300, CRIPPLE ALL 200, SHOCK 500, SNEAK, IMMUNE,
RESURRECT DRAGON, ...): an effect row of item_template.ace with its own name/description texts. A new card copies an
existing row of the keyword it gets (content_mods.add_card), so the texts are already written. This module reads a
card's real text and picks keywords: rules below, first matches win (max 2 per card), amounts from the text's numbers
rounded to the 100s the game uses.

    python tools/effect_mapper.py content/series3/archetype_cards.json [N]   prints N suggestions
"""
import json
import re
import sys

ROOT_CARDINFO = "I:/Users/Dustin/Downloads/cards/dl/pics/cardinfo.json"

RACE_PLURAL = {"Dragon": "DRAGONS", "Warrior": "WARRIORS", "Machine": "MACHINES", "Beast": "BEASTS",
               "Winged Beast": "WINGED BEASTS", "Fairy": "FAIRIES", "Zombie": "ZOMBIES", "Insect": "INSECTS",
               "Spellcaster": "SPELLCASTERS", "Aqua": "AQUA MONSTERS", "Psychic": "PSYCHIC MONSTERS",
               "Beast-Warrior": "BEAST-WARRIORS", "Rock": "ROCK MONSTERS", "Pyro": "PYRO MONSTERS",
               "Reptile": "REPTILES", "Sea Serpent": "SEA SERPENTS", "Dinosaur": "DINOSAURS", "Plant": "PLANTS"}


def _amount(text, default):
    nums = [int(n) for n in re.findall(r"(\d{3,4})", text)]
    value = nums[0] if nums else default
    return max(100, min(1500, round(value / 100) * 100))


# (keyword template, test on the lowercase text, default amount); {n} = amount, {race} = the card's race plural
RULES = [
    ("SNEAK", lambda t: re.search(r"destroy[^.]*monster", t) and "summoned" in t, 0),
    ("DESTROY SPELL", lambda t: re.search(r"destroy[^.]*(spell|trap)", t), 0),
    ("DESTROY MONSTER", lambda t: re.search(r"destroy[^.]*(target|1) [^.]*monster", t), 0),
    ("SHOCK {n}", lambda t: "inflict" in t and "battle damage" not in t and "attack" in t, 500),
    ("HURT OPPONENT {n}", lambda t: re.search(r"inflict \d+ damage", t), 500),
    ("PARTING GIFT {n}", lambda t: "inflict" in t and "destroyed" in t, 500),
    ("HEAL {n}", lambda t: re.search(r"gain \d+ (life points|lp)", t), 500),
    ("BOOST ALL {n}", lambda t: re.search(r"(all|each) [^.]*monsters? you control gains?", t), 300),
    ("BOOST {n}", lambda t: re.search(r"gains? \d+ atk|atk becomes", t), 300),
    ("CRIPPLE ALL {n}", lambda t: re.search(r"(all|each) [^.]*monsters? your opponent controls lose", t), 300),
    ("CRIPPLE {n}", lambda t: re.search(r"loses? \d+ atk", t), 300),
    ("RESURRECT MONSTER", lambda t: re.search(r"special summon[^.]*(graveyard|gy)", t), 0),
    ("IMMUNE", lambda t: "cannot be destroyed" in t, 0),
    ("BREAK IMMUNITY", lambda t: "negate" in t, 0),
]


def suggest(card):
    text = (card.get("desc") or "").lower()
    out = []
    for template, test, default in RULES:
        if len(out) == 2:
            break
        if test(text):
            kw = template.format(n=_amount(text, default), race=RACE_PLURAL.get(card.get("race"), "MONSTERS"))
            if kw.split()[0] not in {o.split()[0] for o in out}:
                out.append(kw)
    if not out:  # no mappable text: a stat keyword by level (vanilla-like cards)
        level = card.get("level") or 4
        out.append(f"BOOST {min(1000, 100 * level)}" if card.get("type", "").startswith("Spell") is False else "BOOST 300")
    return out


def main():
    cards = json.load(open(sys.argv[1], encoding="utf-8"))
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    real = {c["id"]: c for c in json.load(open(ROOT_CARDINFO, encoding="utf-8"))}
    for c in cards[:n]:
        r = real[c["id"]]
        print(f"{c['name'][:38]:38s} {c['kind']:8s} -> {', '.join(suggest(r)):35s} | {r.get('desc', '')[:90]!r}")


if __name__ == "__main__":
    main()
