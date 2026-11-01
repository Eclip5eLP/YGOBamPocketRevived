"""
Test content, applied by tools/build_content.py only with env YGO_TEST_CONTENT=1 (never in a release build).

test_new_card: "Number 3: Cicada King", a new card (template 9001, a copy of Insect Soldiers of the Sky) with its
picture cut from an official card scan (content_mods.add_card, series3 package), on sale in the card shop for 1 DP so
it shows without owning it. The scan comes from YGO_CARD_SCANS (default: content/card_scans/, not in git: official
scans are Konami's art); without it the mod does nothing.
"""

import copy
import json
import os
import time
from pathlib import Path

from content_mods import SALE_END, SALE_START, SUMMONS, add_card

ROOT = Path(__file__).resolve().parent.parent
SCANS = Path(os.environ.get("YGO_CARD_SCANS", ROOT / "content" / "card_scans"))
TEST_CARD = 9001
TEST_SHOP_ITEM = 3901


def test_new_card(ctx):
    scan = SCANS / "cicada_king.jpg"
    if not scan.is_file():
        print("  no", scan, "- test card skipped")
        return
    add_card(ctx, TEST_CARD, 517, "Number 3: Cicada King", scan, atkStat=600, defStat=1250, cardLevel=3)
    group = next(g for sh in ctx.ace("config/ace/shop/shop.ace") for g in sh["shopItemGroups"] if g["id"] == 5)
    now = time.time() * 1000
    model = next(it for it in group["shopItem"] if it["startDate"] <= now <= it["endDate"]
                 and it["shopItemConversions"][0]["currencyTypeId"] == -1)
    it = copy.deepcopy(model)
    it.update(id=TEST_SHOP_ITEM, itemTemplateId=TEST_CARD, leagueRequired=1,
              startDate=type(model["startDate"])(SALE_START), endDate=type(model["endDate"])(SALE_END))
    it["shopItemConversions"][0]["cost"] = 1
    group["shopItem"].append(it)


# Card pictures from the YGOPRODeck download (owner's YGOCardDl.py: pics/<id>.jpg full cards, pics/cropped/<id>.jpg
# art only, pics/cardinfo.json names); not in git (Konami's art)
CARD_PICS = Path(os.environ.get("YGO_CARD_PICS", ROOT / "content" / "card_pics"))

# Synchro/Xyz test set (notes/synchro_xyz.md). Materials for a test deck: Junk Synchron (new Tuner, level 3) and the
# original level 4 Warriors Skull Stalker (317), Ansatsu (319), Millennium Shield (473), level 4 Dragon Petit Dragon
# (262), level 3 Warrior Axe Raider (314).
#   Junk Synchron + level 3 -> Junk Warrior (one result: no picker)
#   Junk Synchron + level 4 -> Stardust Dragon or Black Rose Dragon (picker)
#   two level 4 Warriors -> Number 39: Utopia or Heroic Champion - Excalibur (picker); level 4 Warrior + Dragon -> Utopia
TEST_SUMMON_CARDS = [  # (id, name, base template, fields)
    (9101, "Junk Synchron", 314, dict(cardLevel=3, atkStat=1300, defStat=500)),
    (9111, "Junk Warrior", 314, dict(cardLevel=6, atkStat=2300, defStat=1300, fusionResult=True)),
    (9112, "Stardust Dragon", 262, dict(cardLevel=7, atkStat=2500, defStat=2000, fusionResult=True)),
    (9113, "Black Rose Dragon", 262, dict(cardLevel=7, atkStat=2400, defStat=1800, cardElementId=4, fusionResult=True)),
    # the Xyz copy Tomozaurus (653): "At Round End, your Monster's Power doubles." (material effects below)
    (9121, "Number 39: Utopia", 653, dict(cardLevel=4, atkStat=3000, defStat=2000, cardElementId=6, cardFamilyId=20,
                                          fusionResult=True)),
    (9122, "Heroic Champion - Excalibur", 653, dict(cardLevel=4, atkStat=2500, defStat=2000, cardElementId=6,
                                                    cardFamilyId=20, fusionResult=True)),
]
TEST_SUMMON_SHOP_ITEMS = 3911  # first shop item id; one 1 DP shop entry per test card


def _card_picture(name):
    """pics/cropped/<id>.jpg (art only), else the full card pics/<id>.jpg, by name from pics/cardinfo.json."""
    info = json.loads((CARD_PICS / "cardinfo.json").read_text(encoding="utf-8"))
    card = next(c for c in info if c["name"] == name)
    for path in (CARD_PICS / "cropped" / f"{card['id']}.jpg", CARD_PICS / f"{card['id']}.jpg"):
        if path.is_file():
            return path
    raise RuntimeError(f"no picture for {name}")


def test_summons(ctx):
    if not (CARD_PICS / "cardinfo.json").is_file():
        print("  no", CARD_PICS / "cardinfo.json", "- Synchro/Xyz test cards skipped")
        return
    cards = {}
    for template_id, name, base, fields in TEST_SUMMON_CARDS:
        keep_effects = template_id in (9121, 9122)
        cards[template_id] = add_card(ctx, template_id, base, name, _card_picture(name),
                                      **(fields if keep_effects else dict(fields, effects=[])))
    # Utopia: doubles at round end while it can detach a material (2 materials: twice); Excalibur: while it has one
    SUMMONS["effects"][cards[9121]["effects"][0]["effect"]["id"]] = {"cost": 1}
    SUMMONS["effects"][cards[9122]["effects"][0]["effect"]["id"]] = {"needs": 1}
    # test duel: draw Skull Stalker, Ansatsu, Junk Synchron, Skull Stalker, Ansatsu first (Xyz on turn 1, Synchro and a
    # second Xyz next); AI opponents start with 60000 LP so result cards survive to round end
    SUMMONS["test"] = {"draw": [317, 319, 9101, 317, 319, 473], "aiHp": 60000}  # play a card each round: an empty round loses
    if os.environ.get("YGO_TEST_AI_XYZ"):  # AI may Xyz, as a map node with aixyz=1 (DuelData.AiXyz)
        SUMMONS["test"]["AiXyz"] = True
    SUMMONS["synchro"][9101] = {6: [9111], 7: [9112, 9113]}
    SUMMONS["xyz"] += [{"id": 9121, "rank": 4, "family": 0, "element": 0},
                       {"id": 9122, "rank": 4, "family": 20, "element": 0}]
    group = next(g for sh in ctx.ace("config/ace/shop/shop.ace") for g in sh["shopItemGroups"] if g["id"] == 5)
    now = time.time() * 1000
    model = next(it for it in group["shopItem"] if it["startDate"] <= now <= it["endDate"]
                 and it["shopItemConversions"][0]["currencyTypeId"] == -1)
    for n, (template_id, _, _, _) in enumerate(TEST_SUMMON_CARDS):
        it = copy.deepcopy(model)
        it.update(id=TEST_SUMMON_SHOP_ITEMS + n, itemTemplateId=template_id, leagueRequired=1,
                  startDate=type(model["startDate"])(SALE_START), endDate=type(model["endDate"])(SALE_END))
        it["shopItemConversions"][0]["cost"] = 1
        group["shopItem"].append(it)


MODS = [test_new_card, test_summons]
