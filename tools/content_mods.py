"""
Content mods applied in order by tools/build_content.py. Each mod takes the build Context and edits data files
(ctx.ace / ctx.raw_replace / ctx.strings) or art packages (ctx.package_file). Mods hold only our own changes.
"""

import copy
import io
import json
import re
from pathlib import Path

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


LOCAL_STORE = (Path(__file__).resolve().parent.parent / "input" / "data" / "data" / "air.com.konami.ygo" /
               "com.konami.ygo" / "Local Store")


def add_atlas_frames(ctx, package, atlas, list_path, frames, version):
    """Add texture frames to a module as a second atlas page <atlas>_2 (Starling merges all pages of a module,
    AssetManager.getTextureNames sorts names across atlases, so e.g. shop_booster_covers_0011 becomes frame 11).

    frames: {frame name: PIL image}. The page is added to the module's asset list (asset/list/..., game data)
    and shipped in the module's package (version = new package version)."""
    from PIL import Image
    pad = 2
    width = max(img.width for img in frames.values()) + 2 * pad
    height = sum(img.height + pad for img in frames.values()) + pad
    page = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    xml = [f'<TextureAtlas imagePath="{atlas}_2.png">']
    y = pad
    for name, img in sorted(frames.items()):
        page.paste(img, (pad, y))
        xml.append(f'    <SubTexture name="{name}" x="{pad}" y="{y}" width="{img.width}" height="{img.height}"/>')
        y += img.height + pad
    xml.append("</TextureAtlas>")
    buf = io.BytesIO()
    page.save(buf, "PNG")
    ctx.package_file(package, f"{atlas}_2.png", buf.getvalue(), version)
    ctx.package_file(package, f"{atlas}_2.xml", ("\n".join(xml) + "\n").encode("utf-8"), version)
    lst = ctx.original(list_path).decode("utf-8")
    first = re.search(rf'<Asset name="{atlas}_1" path="([^"]+)"[^>]*/>', lst)
    entry = first.group(0).replace(f"{atlas}_1", f"{atlas}_2")
    ctx.replace_file(list_path, lst.replace(first.group(0), first.group(0) + "\n    " + entry).encode("utf-8"))


def atlas_frame(package_dir, atlas, frame):
    """A frame of an original atlas as a PIL image (for building new art from existing art)."""
    from PIL import Image
    xml = (LOCAL_STORE / package_dir / f"{atlas}.xml").read_text(encoding="utf-8")
    m = re.search(rf'<SubTexture name="{frame}" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', xml)
    x, y, w, h = map(int, m.groups())
    return Image.open(LOCAL_STORE / package_dir / f"{atlas}.png").convert("RGBA").crop((x, y, x + w, y + h))


def write_boosterpacks(ctx):
    """Last: config/boosterpacks.json for EBoosterPackInfo.LoadExtraPacks (tools/as3_patches.py)."""
    ctx.new_file("config/boosterpacks.json", json.dumps(ctx.boosterpacks, separators=(",", ":")).encode("utf-8"))


MODS = [
    free_bam_pro,
    wings_of_destiny,
    write_boosterpacks,
]
