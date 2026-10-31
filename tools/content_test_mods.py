"""
Test content, applied by tools/build_content.py only with env YGO_TEST_CONTENT=1 (never in a release build).

test_new_card: "Number 3: Cicada King", a new card (template 9001, a copy of Insect Soldiers of the Sky) with its
picture cut from an official card scan (content_mods.add_card, series3 package), on sale in the card shop for 1 DP so
it shows without owning it. The scan comes from YGO_CARD_SCANS (default: content/card_scans/, not in git: official
scans are Konami's art); without it the mod does nothing.
"""

import copy
import os
import time
from pathlib import Path

from content_mods import SALE_END, SALE_START, add_card

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


MODS = [test_new_card]
