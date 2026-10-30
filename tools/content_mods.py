"""
Content mods applied in order by tools/build_content.py. Each mod takes the build Context and edits data files
(ctx.ace / ctx.raw_replace / ctx.strings) or art packages (ctx.package_file). Mods hold only our own changes.
"""

import copy
import json

# Asset package -> directory under Local Store (server/server.py PACKAGE_PATHS, EExternalAsset.as:10-60)
PACKAGE_DIRS = {
    "shop": "asset/module/shop/",
}


def free_bam_pro(ctx):
    """BAM Pro popup price line (key bam_pro_price, EBamProLoc.as:18, BamProPopup.as:109)."""
    for lang, text in (("en", "FREE OF CHARGE!"), ("fr", "TOTALEMENT GRATUIT !")):
        ctx.set_text(lang, "bam_pro", "bam_pro_price", text)


def _shop_items(ctx):
    """All shop item objects of shop.ace with their group."""
    for shop in ctx.ace("config/ace/shop/shop.ace"):
        for group in shop["shopItemGroups"]:
            for item in group["shopItem"] or []:
                yield group, item


def _loot_cards(ctx, loot_id):
    loot = next(t for t in ctx.ace("config/ace/loot/loot_template.ace") if t["id"] == loot_id)
    return [li["itemTemplate"] for g in loot["lootGroups"] for li in g["lootItemTemplates"]]


def add_booster_pack(ctx, pack, loot_id, template_shop_item, visual_card):
    """Sell a booster pack: shop.ace item (copy of an existing pack item) + config/boosterpacks.json entry.

    pack: boosterpacks.json fields except "cards" (taken from the loot table that opens the pack)."""
    links = {r["shopItemId"]: r["id"] for r in ctx.ace("config/ace/loot/loot_shop_item_template.ace")}
    if links.get(pack["shopItemId"]) != loot_id:
        raise RuntimeError(f"shop item {pack['shopItemId']} does not open loot {loot_id}")
    group, base = next((g, i) for g, i in _shop_items(ctx) if i["id"] == template_shop_item)
    if any(i["id"] == pack["shopItemId"] for _, i in _shop_items(ctx)):
        raise RuntimeError(f"shop item {pack['shopItemId']} already exists")
    item = copy.deepcopy(base)
    item["id"] = pack["shopItemId"]
    item["itemTemplateId"] = loot_id  # pack shop items reference their loot template (e.g. 1269 -> 19)
    item["visualItemTemplateId"] = visual_card
    item["shopItemConversions"][0]["cost"] = pack["cost"]
    group["shopItem"].append(item)
    ctx.boosterpacks.append({**pack, "cards": _loot_cards(ctx, loot_id)})


def wings_of_destiny(ctx):
    """Unreleased series 2 pack 4 "Wings of Destiny" (PACK_4_SERIES_2): complete in the original data except
    for the shop entry and the code-side pack info. Loot 26 (shop item 1414): 43 common x5, 28 rare x3,
    16 ultra rare + 8 BAM legend (weight 70 vs 100) x1; cover frame 9 (Galaxy-Eyes Photon Dragon)."""
    add_booster_pack(ctx, {
        "shopItemId": 1414, "currency": "RMT", "cost": 15, "id": 10,
        "name": "PACK_4_SERIES_2", "description": "PACK_4_SERIES_2_DESC",
        "guaranteed": [[1, "5"], [2, "3"], [3, "1"]],
        "bonus": [[4, "1:4"]],  # 8*70 / (16*100 + 8*70) = 0.26 per pack
        "frame": 9, "series": 2,
    }, loot_id=26, template_shop_item=1269, visual_card=_card_by_name(ctx, "Galaxy-Eyes Photon Dragon"))


def _card_by_name(ctx, name):
    by_key, by_id, _ = ctx.strings("en", "inventory")
    for t in ctx.ace("config/ace/inventory/item_template.ace"):
        if "cardRarityId" in t and by_id.get(int(t["resourceNameId"])) == name:
            return t["id"]
    raise RuntimeError(f"no card named {name}")


def write_boosterpacks(ctx):
    """Last: config/boosterpacks.json for EBoosterPackInfo.LoadExtraPacks (tools/as3_patches.py)."""
    ctx.new_file("config/boosterpacks.json", json.dumps(ctx.boosterpacks, separators=(",", ":")).encode("utf-8"))


MODS = [
    free_bam_pro,
    wings_of_destiny,
    write_boosterpacks,
]
