"""
Series 3 cards (notes/content_patch_series3.md): every card of content/series3/archetype_cards.json and
standalone_cards.json becomes a card template, built by tools/build_content.py with env YGO_SERIES3=1 (until the
Series 3 booster packs exist; then it joins content_mods.MODS).

Per card (fields of the reviewed data):
  template id    FIRST_ID + its index (archetype cards first, then standalone; append new cards at the end only)
  stats          real level, ATK, DEF (LP), Attribute -> element, Type -> family, "rarity", series 3; Synchro/Fusion
                 monsters are results (fusionResult: made in duels, never in decks); spells: "single_use" ->
                 selfDestruct (a single-use spell dies at round end, the others stay on the field)
  effects        "effects": existing keywords; a new amount or a new target of an existing keyword is a copied row
                 with the amount / family filter and its own texts. "effect_idea": the new effects
                 (notes/new_effects.md); MATERIAL / ON ... rows replace the card's first effect (it stood in for
                 them), LEVEL / REBIRTH / GUARDIAN rows are added
  picture        YGOPRODeck art crop (YGO_CARD_PICS: pics/cropped/<id>.jpg, else the full card pics/<id>.jpg)
  shop           a backorder card shop item (every card list skips cards without one, content_mods.write_summons)
Synchro rules (content_mods.SUMMONS): from the real material lines: '"Junk Synchron" + ...' only with that Tuner,
"1 Tuner Synchro Monster + ..." with the Synchro Tuners, anything else with every Tuner; level total = the Synchro's
level. Fusion recipes (FUSIONS): like the original game, on one material (template fusionData: the other material
matched by card list, Type or Attribute) with a "FUSION - ..." text row on it; materials that were only Series 1
cards (Feral Imp, Snakeyashi, Gazelle) have Series 3 copies, Medium Piece Golem is new ("fusion_material" in data).
"""

import copy
import json
import os
import re
import time
from pathlib import Path

import content_mods as cm

ROOT = Path(__file__).resolve().parent.parent
CARD_PICS = Path(os.environ.get("YGO_CARD_PICS", ROOT / "content" / "card_pics"))
FILES = [ROOT / "content" / "series3" / "archetype_cards.json", ROOT / "content" / "series3" / "standalone_cards.json"]
FIRST_ID = 3001          # template ids 3001.. (originals end at 1774, test cards 9001+)
FIRST_SHOP_ITEM = 30001
MONSTER_BASE, SPELL_BASE = 1236, 1249  # Blackwing - Damascus the Polar Night / Blackwing - Backlash (fields copied)

FAMILY = {"Aqua": 1, "Beast": 2, "Beast-Warrior": 3, "Dinosaur": 4, "Dragon": 6, "Fairy": 7, "Fiend": 8, "Fish": 9,
          "Insect": 10, "Machine": 11, "Plant": 12, "Psychic": 13, "Pyro": 14, "Reptile": 15, "Rock": 16,
          "Sea Serpent": 17, "Spellcaster": 18, "Thunder": 19, "Warrior": 20, "Winged Beast": 21, "Zombie": 22,
          "Cyberse": 11}  # CardFamilies; no Cyberse type in the game: Machine
ELEMENT = {"WIND": 1, "WATER": 2, "EARTH": 3, "FIRE": 4, "DARK": 5, "LIGHT": 6, "DIVINE": 7}  # CardElements
# target words of keywords -> (family, element, plural for texts)
TARGET_WORDS = {
    "AQUA MONSTER": (1, 0, "Aqua Monsters"), "AQUA MONSTERS": (1, 0, "Aqua Monsters"), "BEASTS": (2, 0, "Beasts"),
    "BEAST": (2, 0, "Beast"), "BEAST-WARRIOR": (3, 0, "Beast-Warrior"), "BEAST-WARRIORS": (3, 0, "Beast-Warriors"),
    "DRAGON": (6, 0, "Dragon"), "DRAGONS": (6, 0, "Dragons"), "FAIRIES": (7, 0, "Fairies"), "FIENDS": (8, 0, "Fiends"),
    "INSECT": (10, 0, "Insect"), "INSECTS": (10, 0, "Insects"), "MACHINES": (11, 0, "Machines"),
    "PLANTS": (12, 0, "Plants"), "PSYCHIC MONSTERS": (13, 0, "Psychic Monsters"), "PYRO MONSTERS": (14, 0, "Pyro Monsters"),
    "ROCK MONSTERS": (16, 0, "Rock Monsters"), "SPELLCASTERS": (18, 0, "Spellcasters"), "WARRIOR": (20, 0, "Warrior"),
    "WARRIORS": (20, 0, "Warriors"), "WINGED BEAST": (21, 0, "Winged Beast"), "WINGED BEASTS": (21, 0, "Winged Beasts"),
    "ZOMBIE": (22, 0, "Zombie"), "ZOMBIES": (22, 0, "Zombies"), "DARK MONSTERS": (0, 5, "DARK Monsters"),
    "LIGHT MONSTERS": (0, 6, "LIGHT Monsters"), "WATER MONSTERS": (0, 2, "WATER Monsters"),
}
TARGET_TEXTS = {"BOOST ALL": "All your {} gain Power.", "CRIPPLE ALL": "All your Opponent's {} lose Power.",
                "IMMUNE ALL": "Your {} cannot lose Power or be destroyed.",
                "RESURRECT": "One random {} from your Graveyard is shuffled into your Deck."}
# Series 2 cardScore means per card type and rarity (VERIFIED item_template.ace); InstantDeckCreator ranks by it
CARD_SCORE = {(1, 1): 32, (1, 2): 53, (1, 3): 72, (1, 4): 89, (2, 1): 43, (2, 2): 75, (2, 3): 91, (2, 4): 146}
RESULT_KINDS = {"Synchro", "Fusion"}


def _amount(name):
    m = re.search(r"(\d+)\s*(\+)?\s*$", name)
    return int(m.group(1)) if m else None


def _family(name):
    return re.sub(r"\s*\d+\s*(\+)?\s*$", lambda m: " N" + (" +" if m.group(1) else ""), name.strip())


class Rows:
    """Effect rows of the original data by keyword name, and new rows made from them."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.templates = ctx.ace("config/ace/inventory/item_template.ace")
        _, self.by_id, _ = ctx.strings("en", "inventory")
        self.rows = []  # (name, row, owner card type)
        for t in self.templates:
            for e in t.get("effects") or []:
                name = self.by_id.get(int(e["effect"]["resourceNameId"]), "").strip()
                if name:
                    self.rows.append((name, e, t["cardTypeId"]))
        self.next_id = max(e["effect"]["id"] for t in self.templates for e in (t.get("effects") or [])) + 1

    def text(self, row, key):
        return self.by_id.get(int(row["effect"][key]), "")

    def _pick(self, matches, card_type, amount=None):
        same = [m for m in matches if m[2] == card_type] or matches
        if amount is not None:
            same.sort(key=lambda m: abs((_amount(m[0]) or 0) - amount))
        return same[0]

    def copy(self, source, name=None, description=None):
        """A copy of row source with a new effect id; new name/description texts when given."""
        row = copy.deepcopy(source)
        row["effect"]["id"] = self.next_id
        self.next_id += 1
        if name is not None:
            self.set_texts(row, name, description if description is not None else self.text(source, "resourceDescId"))
        return row

    def set_texts(self, row, name, description):
        for key, text in (("resourceNameId", name), ("resourceDescId", description)):
            rid = cm.NEW_EFFECT_TEXT_IDS + 2 * row["effect"]["id"] + (key == "resourceDescId")
            row["effect"][key] = type(row["effect"][key])(rid)
            for lang in ("en", "fr"):
                self.ctx.set_text(lang, "inventory", str(rid), text, resource_id=rid)

    def keyword(self, name, card_type):
        """A new row for keyword name (exact, new amount or new target of an original keyword)."""
        exact = [m for m in self.rows if m[0] == name]
        if exact:
            return self.copy(self._pick(exact, card_type)[1])
        amount = _amount(name)
        family = [m for m in self.rows if _family(m[0]) == _family(name)]
        if family:
            source_name, source, _ = self._pick(family, card_type, amount)
            row = self.copy(source, name)
            old = _amount(source_name)
            for field in ("atkModifier", "defModifier", "hpModifier", "friendMultiplierValue"):
                value = row["effect"][field]
                if old and value and abs(value) == old:
                    row["effect"][field] = type(value)(amount if value > 0 else -amount)
            return row
        for prefix, text in TARGET_TEXTS.items():
            rest = name[len(prefix):].strip() if name.startswith(prefix + " ") else None
            if rest is None:
                continue
            word = re.sub(r"\s*\d+$", "", rest)
            family_id, element_id, plural = TARGET_WORDS[word]
            sources = [m for m in self.rows if m[0].startswith(prefix + " ") and
                       (m[1]["targetFamilyId"] or m[1]["targetElementId"]) and
                       (_amount(m[0]) is not None) == (amount is not None)]
            source_name, source, _ = self._pick(sources, card_type, amount)
            row = self.copy(source, name, text.format(plural))
            row["targetFamilyId"], row["targetElementId"] = family_id, element_id
            old = _amount(source_name)
            for field in ("atkModifier", "defModifier", "hpModifier"):
                value = row["effect"][field]
                if old and value and abs(value) == old:
                    row["effect"][field] = type(value)(amount if value > 0 else -amount)
            return row
        raise RuntimeError(f"series3: no row for keyword {name!r}")


# --- New effects from "effect_idea" (notes/new_effects.md) ------------------------------------------------------------
REPLACING = ("MATERIAL", "ON SYNCHRO", "ON XYZ", "ON FUSION", "BOOST ALL SYNCHROS", "IMMUNE ALL SYNCHROS")


def _idea_rows(rows, card, card_type, is_result):
    """[(row, rule)] for the card's effect_idea, and whether they replace its first effect. Ideas the engine can't do
    (ON SUMMON of a Ritual or a normal summon: no ON_FUSION) give nothing."""
    idea = card.get("effect_idea")
    if not idea:
        return [], False
    out = []
    # "GUARDIAN + REBIRTH": two ideas; "ON SYNCHRO: A + B": one idea with two keywords
    parts = [idea] if ":" in idea else [p.strip() for p in re.split(r"\s\+\s(?=[A-Z])", idea)]
    for part in parts:
        part = re.sub(r"\s*\(.*?\)", "", part)
        m = re.match(r"(ON SYNCHRO SUMMON|ON XYZ SUMMON|ON FUSION SUMMON|ON SYNCHRO|ON XYZ|ON FUSION|MATERIAL): (.+)$", part)
        if m:
            head, keywords = m.groups()
            if head.startswith("ON") and not head.endswith("SUMMON") and not is_result:
                continue
            for kw in [k.strip() for k in keywords.split(" + ")]:
                kw = re.sub(r"\s*\(.*$", "", kw)
                if kw.startswith("BOOST 300 +"):
                    kw = "BOOST 300 +"
                row = rows.keyword(kw, card_type)
                kw_text = rows.text(row, "resourceDescId") or kw
                if head == "MATERIAL":
                    if kw.startswith(("BOOST", "IMMUNE")) and not kw.startswith(("BOOST ALL", "IMMUNE ALL")):
                        row["targetTypeId"] = cm.TARGET["self"]
                    row["triggerId"] = cm.TRIGGER["none"]
                    rows.set_texts(row, f"MATERIAL: {kw}", f"When this card is used for a Summon: {kw_text}")
                    out.append((row, {"material": True}))
                elif head.endswith("SUMMON"):
                    kind = head.split()[1].lower()
                    row["triggerId"], row["triggerDispatcherId"] = cm.TRIGGER["summon"], cm.TARGET["player"]
                    rows.set_texts(row, f"{head}: {kw}", f"Every time you {kind.capitalize()} Summon: {kw_text}")
                    out.append((row, {"summonKind": kind}))
                else:
                    kind = head.split()[1].capitalize()
                    row["triggerId"], row["triggerDispatcherId"] = cm.TRIGGER["summon"], cm.TARGET["self"]
                    rows.set_texts(row, f"{head}: {kw}", f"When this Monster is {kind} Summoned: {kw_text}")
                    out.append((row, None))
            continue
        m = re.match(r"(BOOST|IMMUNE) ALL (SYNCHROS|XYZ|FUSIONS)\s*(\d*)$", part)
        if m:
            what, kinds, amount = m.groups()
            row = rows.keyword(f"BOOST ALL {amount}" if what == "BOOST" else "IMMUNE ALL", card_type)
            label = kinds.capitalize() if kinds != "XYZ" else "Xyz"
            rows.set_texts(row, part, f"All your {label} gain Power." if what == "BOOST" else
                           f"Your {label} cannot lose Power or be destroyed.")
            out.append((row, {"targetKind": {"SYNCHROS": "synchro", "XYZ": "xyz", "FUSIONS": "fusion"}[kinds]}))
            continue
        m = re.match(r"LEVEL (UP|DOWN|SET)\s*(\d*)", part)
        if m:
            how, n = m.group(1), int(m.group(2) or 0)
            if how == "SET" and not n:
                continue  # copies another monster's Level: not possible yet
            n = n or 1
            row = rows.keyword("BOOST 300", card_type)
            row["effect"]["atkModifier"], row["effect"]["atkOperatorId"] = type(row["effect"]["atkModifier"])(0), 0
            row["effect"]["oncePerGame"] = True
            row["triggerId"], row["triggerDispatcherId"], row["targetTypeId"] = 1, cm.TARGET["player"], cm.TARGET["self"]
            text = {"UP": f"This Monster's Level rises by {n}.", "DOWN": f"This Monster's Level drops by {n}.",
                    "SET": f"This Monster's Level becomes {n}."}[how]
            rows.set_texts(row, f"LEVEL {how} {n}", text)
            out.append((row, {"level": n if how == "UP" else -n} if how != "SET" else {"levelSet": n}))
            continue
        if part in ("REBIRTH", "GUARDIAN"):
            row = rows.keyword("RESURRECT MONSTER" if part == "REBIRTH" else "SPIRIT PROTECTION", card_type)
            row["triggerId"] = cm.TRIGGER["none"]
            row["effect"]["resurrect"] = row["effect"]["grantImmunity"] = False
            text = ("When this Monster is destroyed, its materials are shuffled back into your Deck." if is_result else
                    "When this Monster is destroyed, it is shuffled back into your Deck.") if part == "REBIRTH" else \
                "When another of your Monsters would be destroyed, this Monster is destroyed instead."
            rows.set_texts(row, part, text)
            out.append((row, {"rebirth": True} if part == "REBIRTH" else {"guardian": True}))
            continue
        print(f"  series3: effect idea not built for {card['name']}: {part}")
    replacing = any(idea.startswith(p) for p in REPLACING)
    return out, replacing and bool(out)


def _picture(card_id):
    for path in (CARD_PICS / "cropped" / f"{card_id}.jpg", CARD_PICS / f"{card_id}.jpg"):
        if path.is_file():
            return path
    raise RuntimeError(f"series3: no picture for card {card_id}")


def load_cards():
    cards = []
    for path in FILES:
        cards += json.loads(path.read_text(encoding="utf-8"))
    return cards


def _synchro_rules(cards, ids, info):
    """content_mods.SUMMONS["synchro"] entries for the Series 3 Tuners and Synchros."""
    tuners = {c["name"] for c in cards if c["kind"] == "Tuner"}
    synchro_tuners = {c["name"] for c in cards if "Tuner" in info[c["id"]].get("type", "") and c["kind"] == "Synchro"}
    level = {c["name"]: c["level"] for c in cards}
    rules = {}
    for c in cards:
        if c["kind"] != "Synchro":
            continue
        materials = info[c["id"]].get("desc", "").split("\n")[0]
        named = re.match(r'"([^"]+)"\s*\+', materials)
        if named and named.group(1) in tuners | synchro_tuners:
            allowed = {named.group(1)}
        elif "Tuner Synchro Monster" in materials:
            allowed = synchro_tuners
        else:
            allowed = tuners
        for tuner in allowed:
            if level[tuner] < c["level"]:
                rules.setdefault(ids[tuner], {}).setdefault(c["level"], []).append(ids[c["name"]])
    return rules


# result: (material holding the recipe, partner: {"cards": [names]} / {"family": id} / {"element": id}, partner text)
# Generic real recipes ("1 Dragon Synchro + 1 Warrior") are two cards here: one named Synchro plus the generic partner.
FUSIONS = {
    "Rose Spectre of Dunn": ("Snakeyashi", {"cards": ["Feral Imp"]}, "Feral Imp"),
    "Chimera the Flying Mythical Beast": ("Berfomet", {"cards": ["Gazelle the King of Mythical Beasts"]},
                                          "Gazelle the King of Mythical Beasts"),
    "Multiple Piece Golem": ("Big Piece Golem", {"cards": ["Medium Piece Golem"]}, "Medium Piece Golem"),
    "Ultimate Axon Kicker": ("Psychic Nightmare", {"family": 13}, "a Psychic Monster"),
    "Supreme Arcanite Magician": ("Arcanite Magician", {"family": 18}, "a Spellcaster"),
    "Dragon Knight Draco-Equiste": ("Stardust Dragon", {"family": 20}, "a Warrior"),
    "Trishula, the Dragon of Icy Imprisonment": ("Gungnir, Dragon of the Ice Barrier", {"element": 2},
                                                 "a WATER Monster"),
}


def _fusions(ctx, rows, ids):
    templates = {t["id"]: t for t in ctx.ace("config/ace/inventory/item_template.ace")}
    model = next(t["fusionData"] for t in templates.values() if t.get("fusionData"))
    next_id = max(t["fusionData"]["id"] for t in templates.values() if t.get("fusionData")) + 1
    for result, (base, partner, partner_text) in FUSIONS.items():
        card = templates[ids[base]]
        if card.get("fusionData"):
            raise RuntimeError(f"series3: {base} already holds a fusion recipe")
        data = copy.deepcopy(model)
        data.update(id=next_id, cardTemplateId=ids[base], resultCardTemplateId=ids[result], ingredientCardTypeId=1,
                    ingredientElementId=partner.get("element", 0), ingredientFamilyId=partner.get("family", 0),
                    ingredientCardLevelId=0, ingredientCondition=True,
                    ingredientCardTemplateList=[ids[n] for n in partner.get("cards", [])])
        next_id += 1
        card["fusionData"] = data
        row = rows.copy(next(m[1] for m in rows.rows if m[0] == "FUSION - MONSTER"))  # text only
        rows.set_texts(row, f"FUSION - {result}", f"Fuse with {partner_text} to create {result}.")
        row["displayOrder"] = 0
        card["effects"].insert(0, row)
        for order, r in enumerate(card["effects"], 1):
            r["displayOrder"] = order


def build(ctx):
    if not (CARD_PICS / "cardinfo.json").is_file():
        print("  no", CARD_PICS / "cardinfo.json", "- Series 3 cards skipped")
        return
    info = {c["id"]: c for c in json.loads((CARD_PICS / "cardinfo.json").read_text(encoding="utf-8"))}
    cards = load_cards()
    rows = Rows(ctx)
    ids = {}
    group = next(g for sh in ctx.ace("config/ace/shop/shop.ace") for g in sh["shopItemGroups"] if g["id"] == 5)
    now = time.time() * 1000
    model = next(it for it in group["shopItem"] if it["startDate"] <= now <= it["endDate"]
                 and it["shopItemConversions"][0]["currencyTypeId"] == -1)
    for n, c in enumerate(cards):
        template_id = FIRST_ID + n
        ids[c["name"]] = template_id
        spell = c["kind"] in ("Spell", "Trap")
        card_type = 2 if spell else 1
        is_result = c["kind"] in RESULT_KINDS
        fields = dict(cardSerieId=3, cardRarityId=c["rarity"], cardScore=CARD_SCORE[(card_type, c["rarity"])],
                      effects=[])
        if spell:
            fields.update(cardLevel=0, atkStat=0, defStat=0, cardElementId=0, cardFamilyId=0,
                          selfDestruct=c["single_use"])
        else:
            fields.update(cardLevel=c["level"] or 1, atkStat=max(0, c["atk"] or 0), defStat=max(0, c["def"] or 0),
                          cardElementId=ELEMENT[c["attribute"]], cardFamilyId=FAMILY[c["race"]],
                          fusionResult=is_result, selfDestruct=False)
        card = cm.add_card(ctx, template_id, SPELL_BASE if spell else MONSTER_BASE, c["name"], _picture(c["id"]),
                           **fields)
        effect_rows = [(rows.keyword(k, card_type), None) for k in c.get("effects", [])]
        ideas, replacing = _idea_rows(rows, c, card_type, is_result)
        if replacing and effect_rows:
            effect_rows = effect_rows[1:]
            effect_rows[0:0] = ideas
        else:
            effect_rows += ideas
        card["effects"] = []
        for order, (row, rule) in enumerate(effect_rows, 1):
            row["displayOrder"] = order
            card["effects"].append(row)
            if rule:
                cm.SUMMONS["effects"][row["effect"]["id"]] = rule
        item = copy.deepcopy(model)
        item.update(id=FIRST_SHOP_ITEM + n, itemTemplateId=template_id, backorder=True,
                    startDate=type(model["startDate"])(cm.SALE_START), endDate=type(model["endDate"])(cm.SALE_END))
        group["shopItem"].append(item)
    _fusions(ctx, rows, ids)
    for tuner, totals in _synchro_rules(cards, ids, info).items():
        cm.SUMMONS["synchro"].setdefault(tuner, {})
        for total, results in totals.items():
            cm.SUMMONS["synchro"][tuner].setdefault(total, []).extend(results)
    print(f"  series3: {len(cards)} cards ({FIRST_ID}-{FIRST_ID + len(cards) - 1}),",
          sum(len(v) for t in cm.SUMMONS["synchro"].values() for v in t.values()), "Synchro rule entries")
