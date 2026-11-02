#!/usr/bin/env python3
"""
Series 3 balance pass (notes/content_patch_series3.md): game stats, effect amounts and rarity floors for the cards of
content/series3/*.json, measured on Series 1/2 (VERIFIED item_template.ace), then the owner's review
(content/series3/owner_review.json) on top. Re-runnable: the real stats stay in "real_atk"/"real_def".

  python tools/series3_balance.py        rewrites the card data, prints what changed

Stats (monsters): ATK = Series 2 median ATK of the card's rarity + 30% of the gap to the real ATK, minus 200 for a
strong removal/protection effect; LP the same with the LP medians. Rounded to 100, ATK at least 100 (an ATK 0 monster
dies as soon as it is played). Matches the owner's first review wave (e.g. Ancient Crimson Ape 2600 -> 1900,
Bicular 200 -> 700, Arcanite Magician 400 -> 1400).
Effects: an amount above its rarity's cap (Series 1/2 amounts per keyword family) comes down to the cap; a BAM legend
gets at least the common cap. Rarity floors for strong keywords (Series 1/2 never has them lower).
Owner review: {"<card name>": {"atk": n, "def": n, "effects": [...] (the full list), "effect_idea": "..." or null,
"rarity": n}}; reviewed cards skip the automatic changes. The owner's notes read: a plain keyword replaces the same
keyword (other amount) if the card has it, else it is added; "remove"/"add" are explicit. "effects" here is the
resulting full list.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "content" / "series3" / "archetype_cards.json", ROOT / "content" / "series3" / "standalone_cards.json"]
OWNER = ROOT / "content" / "series3" / "owner_review.json"

# Series 2 monster medians per rarity (VERIFIED item_template.ace, monsters with ATK > 0)
ATK_MEDIAN = {1: 1000, 2: 1600, 3: 1800, 4: 2000}
HP_MEDIAN = {1: 800, 2: 1000, 3: 1400, 4: 2100}
PULL = 0.3
STRONG = ("SNEAK", "DESTROY MONSTER", "ANNIHILATE", "SHARED FATE ALL", "IMMUNE ALL", "GROWTH", "ON SYNCHRO: ANNIHILATE")

# amount caps per rarity 1..4 (Series 1/2 amounts per family, rounded up)
CAPS = [
    (("BOOST ALL", "CRIPPLE ALL", "NECRO"), (300, 400, 600, 900)),
    (("BOOST", "CRIPPLE"), (500, 700, 1000, 1500)),
    (("DRAIN", "RAGE", "OSMOSIS", "EMPATHY"), (300, 400, 600, 1000)),
    (("HURT OPPONENT", "HEAL"), (800, 1200, 1600, 2500)),
    (("SHOCK", "FAREWELL", "PARTING GIFT", "COURAGE", "FIRST STRIKE", "POWER REDISTRIBUTION", "REQUIEM", "SOOTHE",
      "MIRROR", "BLOODLUST", "SHOCKWAVE", "ACID JET"), (600, 900, 1200, 2000)),
]
# rarity floors (Series 1/2 has these keywords only from this rarity up)
FLOORS = [("ANNIHILATE MONSTERS", 3), ("SHARED FATE ALL", 2), ("IMMUNE ALL", 2), ("BREAK IMMUNITY ALL", 2),
          ("RESURRECT MONSTERS", 2)]


def _round(v):
    return int(round(v / 100.0)) * 100


def _cap(name, rarity):
    keyword = re.sub(r"^(MATERIAL|ON [A-Z ]+): ", "", name)
    m = re.match(r"(.*?)\s*(\d+)(\s*\+)?$", keyword)
    if not m:
        return name
    head, amount = m.group(1), int(m.group(2))
    for prefixes, caps in CAPS:
        if head.startswith(prefixes):
            limit = caps[rarity - 1]
            new = min(amount, limit)
            if rarity == 4:
                new = max(new, caps[0])
            return name.replace(f"{head} {amount}", f"{head} {new}") if new != amount else name
    return name


def balance(card):
    changes = []
    floor = max([f for k, f in FLOORS if any(e.startswith(k) for e in card.get("effects", []))] or [0])
    if floor > card["rarity"]:
        changes.append(f"rarity {card['rarity']} -> {floor}")
        card["rarity"] = floor
    if card["kind"] not in ("Spell", "Trap"):
        card.setdefault("real_atk", card["atk"])
        card.setdefault("real_def", card["def"])
        strong = any(e.startswith(STRONG) for e in card.get("effects", []) + [card.get("effect_idea") or ""])
        r = card["rarity"]
        atk = max(100, _round(ATK_MEDIAN[r] + PULL * ((card["real_atk"] or 0) - ATK_MEDIAN[r]) - (200 if strong else 0)))
        hp = max(0, _round(HP_MEDIAN[r] + PULL * ((card["real_def"] or 0) - HP_MEDIAN[r])))
        if (atk, hp) != (card["atk"], card["def"]):
            changes.append(f"{card['atk']}/{card['def']} -> {atk}/{hp}")
        card["atk"], card["def"] = atk, hp
    effects = [_cap(e, card["rarity"]) for e in card.get("effects", [])]
    if effects != card.get("effects", []):
        changes.append(f"{card['effects']} -> {effects}")
        card["effects"] = effects
    if card.get("effect_idea"):
        idea = _cap(card["effect_idea"], card["rarity"])
        if idea != card["effect_idea"]:
            changes.append(f"idea {card['effect_idea']} -> {idea}")
            card["effect_idea"] = idea
    return changes


def main():
    owner = json.loads(OWNER.read_text(encoding="utf-8")) if OWNER.is_file() else {}
    data = [json.loads(p.read_text(encoding="utf-8")) for p in FILES]
    names = {c["name"] for d in data for c in d}
    unknown = set(owner) - names
    if unknown:
        raise SystemExit(f"owner_review.json: unknown cards {sorted(unknown)}")
    count = 0
    for d in data:
        for card in d:
            if card["name"] in owner:
                if card["kind"] not in ("Spell", "Trap"):
                    card.setdefault("real_atk", card["atk"])
                    card.setdefault("real_def", card["def"])
                review = owner[card["name"]]
                for key in ("atk", "def", "effects", "rarity"):
                    if key in review:
                        card[key] = review[key]
                if "effect_idea" in review:
                    if review["effect_idea"]:
                        card["effect_idea"] = review["effect_idea"]
                    else:
                        card.pop("effect_idea", None)
                card["owner_reviewed"] = True
                continue
            changes = balance(card)
            if changes:
                count += 1
                print(f"{card['name']}: " + "; ".join(changes))
    for p, d in zip(FILES, data):
        p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{count} cards changed, {len(owner)} owner-reviewed")


if __name__ == "__main__":
    main()
