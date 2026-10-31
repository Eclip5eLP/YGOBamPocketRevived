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
    "world": "asset/world/",
    "mappreview": "asset/misc/mappreview/",
    "hud": "asset/module/hud/",
    "mainmenu": "asset/module/mainmenu/",
}


def free_bam_pro(ctx):
    """BAM Pro popup price line (key bam_pro_price, EBamProLoc.as:18, BamProPopup.as:109)."""
    for lang, text in (("en", "FREE OF CHARGE!"), ("fr", "TOTALEMENT GRATUIT !")):
        ctx.set_text(lang, "bam_pro", "bam_pro_price", text)



def settings_github_text(ctx):
    """Settings support button opens GitHub (as3_patches OPTION_POPUP_EDITS); label keys of OptionPopup.as:240,246."""
    for lang in ("en", "fr"):
        ctx.set_text(lang, "option", "option_visit_forum", "GitHub")


def star_duel_button_text(ctx):
    """Duel star popup buttons say DUEL like the duel popup (key map/star_duel_popup_button, DuelNode.as:224; was OK)."""
    for lang in ("en", "fr"):
        ctx.set_text(lang, "map", "star_duel_popup_button", "DUEL")

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


def add_atlas_frames(ctx, package, atlas, list_path, frames, version, first_page=None):
    """Add texture frames to a module as a second atlas page <atlas>_2 (Starling merges all pages of a module,
    AssetManager.getTextureNames sorts names across atlases, so e.g. shop_booster_covers_0011 becomes frame 11).

    frames: {frame name: PIL image}. The page is added to the module's asset list (asset/list/..., game data)
    and shipped in the module's package (version = new package version). first_page: list name of the original
    page when it is not <atlas>_1 (e.g. hud_all)."""
    first_page = first_page or f"{atlas}_1"
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
    first = re.search(rf'<Asset name="{first_page}" path="([^"]+)"[^>]*/>', lst)
    entry = first.group(0).replace(f'name="{first_page}"', f'name="{atlas}_2"').replace(
        f"/{first_page}.png", f"/{atlas}_2.png")
    ctx.replace_file(list_path, lst.replace(first.group(0), first.group(0) + "\n    " + entry).encode("utf-8"))


def atlas_frame(package_dir, atlas, frame):
    """A frame of an original atlas as a PIL image (for building new art from existing art)."""
    from PIL import Image
    xml = (LOCAL_STORE / package_dir / f"{atlas}.xml").read_text(encoding="utf-8")
    m = re.search(rf'<SubTexture name="{frame}" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', xml)
    x, y, w, h = map(int, m.groups())
    return Image.open(LOCAL_STORE / package_dir / f"{atlas}.png").convert("RGBA").crop((x, y, x + w, y + h))


def card_art(ctx, template_id):
    """A card's illustration (Local Store asset/cards/<name>_1.jpg via representation/*.ace) as a PIL image."""
    from PIL import Image
    links = ctx.ace("config/ace/representation/item_template_to_asset.ace")
    assets = {a["id"]: a for a in ctx.ace("config/ace/representation/asset.ace")}
    for link in links:
        if link["itemTemplateId"] == template_id and link["assetId"] in assets:
            path = assets[link["assetId"]]["path"]
            path = path[:path.rfind(".")]
            path = (path if "_1" in path else path + "_1") + ".jpg"
            f = LOCAL_STORE / "asset" / "cards" / path
            if f.exists():
                return Image.open(f).convert("RGBA")
    raise RuntimeError(f"no art for card {template_id}")


SERIES_2_COVERS = [6, 7, 8, 9, 10]  # original series 2 covers in shop_booster_covers_00NN (same layout)


def _cover_template():
    """Per pixel of the series 2 covers: the median colour and how template-like the pixel is (0..255): 255 where
    the covers agree (logo, emblem, rail with rarity gems, frame), fading to 0 where they differ (each pack's art).
    The median and the soft edge keep the anti-aliased template edges clean (notes 6.51)."""
    from PIL import Image
    covers = [atlas_frame("asset/module/shop", "shop_all_1", f"shop_booster_covers_{n:04d}").load()
              for n in SERIES_2_COVERS]
    w, h = 220, 313
    alpha, median = Image.new("L", (w, h)), Image.new("RGBA", (w, h))
    ap, mp = alpha.load(), median.load()
    for y in range(h):
        for x in range(w):
            vals = [c[x, y] for c in covers]
            mp[x, y] = med = tuple(sorted(v[i] for v in vals)[len(vals) // 2] for i in range(4))
            d = sorted(max(abs(v[i] - med[i]) for i in range(3)) for v in vals)[-2]  # one outlier allowed
            ap[x, y] = 255 if d <= 16 else (0 if d >= 70 else int(255 * (70 - d) / 54))
    return median, alpha


def compose_cover(ctx, art, banner_hue, focus=(0.5, 0.45), zoom=1.0):
    """A booster cover in the style of the series 2 covers: the card art on a radial gradient in the pack colour,
    faded at its edges (the originals show a cut-out monster), under the shared template, with the banner
    recoloured to banner_hue (0-360). Card art is only 155 px (Local Store asset/cards), so the art is upscaled
    with a light sharpen; original quality would need a larger illustration (notes 6.51)."""
    from PIL import Image, ImageDraw, ImageFilter
    import colorsys
    base = atlas_frame("asset/module/shop", "shop_all_1", f"shop_booster_covers_{SERIES_2_COVERS[3]:04d}")
    w, h = base.size
    banner_top = int(h * 0.71)
    layer = Image.new("RGBA", (w, h))
    lp = layer.load()
    cx, cy = w * 0.5, h * 0.4
    for y in range(h):
        for x in range(w):
            t = min(1.0, (((x - cx) / w) ** 2 + ((y - cy) / h) ** 2) ** 0.5 * 1.9)
            r, g, b = colorsys.hls_to_rgb(banner_hue / 360, 0.62 - 0.38 * t, 0.85)
            lp[x, y] = (int(r * 255), int(g * 255), int(b * 255), 255)
    size = int(205 * zoom)
    big = art.resize((size, size), Image.BICUBIC).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((size * 0.04, size * 0.02, size * 0.96, size * 1.05), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(size * 0.07))
    layer.paste(big, (int(w * 0.46 - size * focus[0]), int(banner_top * 0.58 - size * focus[1])), mask)
    banner = base.crop((0, banner_top, w, h))
    bp = banner.load()
    for y in range(banner.height):
        for x in range(w):
            r, g, b, a = bp[x, y]
            _, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            nr, ng, nb = colorsys.hls_to_rgb(banner_hue / 360, ll, ss)
            bp[x, y] = (int(nr * 255), int(ng * 255), int(nb * 255), a)
    layer.paste(banner, (0, banner_top))
    median, alpha = _cover_template()
    out = Image.composite(median, layer, alpha)
    out.putalpha(base.getchannel("A"))
    return out


def create_loot_table(ctx, loot_id, shop_item_id, cards):
    """Loot table + shop link for a pack in the series 2 layout (copied from Wings of Destiny, loot 26): 5 common,
    3 rare, 1 of ultra rare (weight 100) / BAM legend (weight 70)."""
    tables = ctx.ace("config/ace/loot/loot_template.ace")
    links = ctx.ace("config/ace/loot/loot_shop_item_template.ace")
    if any(t["id"] == loot_id for t in tables):
        raise RuntimeError(f"loot table {loot_id} exists")
    items = {i["id"]: i for i in ctx.ace("config/ace/inventory/item_template.ace")}
    table = copy.deepcopy(next(t for t in tables if t["id"] == 26))
    table["id"] = loot_id
    table["shopItemId"] = shop_item_id  # LootManagerYGO looks tables up by shopItemId (GetLootShopItemTemplateByShopItemId)
    next_group = max(g["lootTemplateId"] for t in tables for g in t["lootGroups"] or []) + 1
    next_item = max(li["id"] for t in tables for g in t["lootGroups"] or [] for li in g["lootItemTemplates"]) + 1
    by_rarity = {1: [], 2: [], 3: [], 4: []}
    for c in cards:
        by_rarity[items[c]["cardRarityId"]].append(c)
    for group, rarities in zip(table["lootGroups"], ((1,), (2,), (3, 4))):
        model = group["lootItemTemplates"][0]
        group["lootTemplateId"] = next_group
        group["lootItemTemplates"].clear()
        for rarity in rarities:
            for c in by_rarity[rarity]:
                li = copy.deepcopy(model)
                li.update(id=next_item, lootGroupId=next_group, itemTemplate=c, weight=70 if rarity == 4 else 100)
                group["lootItemTemplates"].append(li)
                next_item += 1
        next_group += 1
    tables.append(table)
    link = copy.deepcopy(next(r for r in links if r["id"] == 26))
    link.update(id=loot_id, shopItemId=shop_item_id)
    links.append(link)
    return {r: len(v) for r, v in by_rarity.items()}


SPLIT = Path(__file__).resolve().parent.parent / "notes" / "pack_split_proposal.md"


def _split_cards(ctx, pack_title):
    """Pack card list from notes/pack_split_proposal.md: series 2 cards only, no fusion results (no original pack
    contains either)."""
    items = {i["id"]: i for i in ctx.ace("config/ace/inventory/item_template.ace")}
    text = SPLIT.read_text(encoding="utf-8")
    block = text.split("## " + pack_title, 1)[1].split("```", 2)[1]
    ids = [int(line.split()[0]) for line in block.splitlines() if line.strip()]
    return [i for i in ids if items[i]["cardSerieId"] == 2 and not items[i].get("fusionResult")]


def _legend_odds(counts):
    """Pack info line for BAM legends in the ultra rare/legend slot (weights 100/70), e.g. [[4, "1:9"]]; none
    when the pack has no legends."""
    if not counts[4]:
        return []
    return [[4, "1:%d" % round((counts[3] * 100 + counts[4] * 70) / (counts[4] * 70))]]


def immemorial_cataclysm(ctx):
    """Unreleased series 2 pack 5 (PACK_5_SERIES_2): new loot table 27 / shop item 2001, cards per
    notes/pack_split_proposal.md, new cover frame 11 (Poseidra, the Atlantean Dragon, ocean-teal banner)."""
    cards = _split_cards(ctx, "Immemorial Cataclysm")
    counts = create_loot_table(ctx, 27, 2001, cards)
    cover = compose_cover(ctx, card_art(ctx, _card_by_name(ctx, "Poseidra, the Atlantean Dragon")), banner_hue=192)
    add_atlas_frames(ctx, "shop", "shop_all", "asset/list/module/shop_list.xml",
                     {"shop_booster_covers_0011": cover}, version="1.1.12")
    add_booster_pack(ctx, {
        "shopItemId": 2001, "currency": "RMT", "cost": 15, "id": 11,
        "name": "PACK_5_SERIES_2", "description": "PACK_5_SERIES_2_DESC",
        "guaranteed": [[1, "5"], [2, "3"], [3, "1"]], "bonus": _legend_odds(counts),
        "frame": 11, "series": 2,
    }, loot_id=27, template_shop_item=1269, visual_card=_card_by_name(ctx, "Hyper-Ancient Shark Megalodon"))
    print("  Immemorial Cataclysm:", counts)


def blazing_wind(ctx):
    """Unreleased series 2 pack 6 (PACK_6_SERIES_2): new loot table 28 / shop item 2002, cards per
    notes/pack_split_proposal.md, original unused cover frame 10."""
    cards = _split_cards(ctx, "Blazing Wind")
    counts = create_loot_table(ctx, 28, 2002, cards)
    add_booster_pack(ctx, {
        "shopItemId": 2002, "currency": "RMT", "cost": 15, "id": 12,
        "name": "PACK_6_SERIES_2", "description": "PACK_6_SERIES_2_DESC",
        "guaranteed": [[1, "5"], [2, "3"], [3, "1"]], "bonus": _legend_odds(counts),
        "frame": 10, "series": 2,
    }, loot_id=28, template_shop_item=1269, visual_card=_card_by_name(ctx, "Brotherhood of the Fire Fist - Horse Prince"))
    print("  Blazing Wind:", counts)


def world_select_icon(ctx):
    """HUD button icon for the world selection menu (MapActionBar.AddWorldButton, tools/as3_patches.py): the main
    menu's story mode icon, scaled into the HUD buttons' 98x98 frame, as hud_worldbutton on a second hud page."""
    from PIL import Image
    icon = atlas_frame("asset/module/mainmenu", "mainmenu_all", "mainmenu_storymode_icon_0000")
    icon = icon.resize((int(icon.width * 0.78), int(icon.height * 0.78)), Image.LANCZOS)
    frame = Image.new("RGBA", (98, 98), (0, 0, 0, 0))
    frame.paste(icon, ((98 - icon.width) // 2, (98 - icon.height) // 2), icon)
    add_atlas_frames(ctx, "hud", "hud_all", "asset/list/module/hud_list.xml", {"hud_worldbutton_0000": frame},
                     version="1.1.5", first_page="hud_all")



def mainmenu_icons(ctx):
    """Icons and labels for the new main menu buttons (MainMenuView.CreateMainMenuButton reads <type>_icon and the
    MAINMENU text <type>_text): Collection = the shop's card stack, scaled to the other icons' height; Profile = the
    front figure of the Friends icon, mirrored from its left half (the right half is covered by the second figure)."""
    from PIL import Image, ImageOps
    cards = atlas_frame("asset/module/shop", "shop_all_1", "shop_cards_btn_0000")
    cards = cards.resize((int(cards.width * 91 / cards.height), 91), Image.LANCZOS)
    friends = atlas_frame("asset/module/mainmenu", "mainmenu_all", "mainmenu_friends_icon_0000")
    left = friends.crop((0, 0, 35, friends.height))
    profile = Image.new("RGBA", (70, friends.height), (0, 0, 0, 0))
    profile.paste(left, (0, 0))
    profile.paste(ImageOps.mirror(left), (35, 0))
    add_atlas_frames(ctx, "mainmenu", "mainmenu_all", "asset/list/module/mainmenu_list.xml",
                     {"mainmenu_collection_icon_0000": cards, "mainmenu_profile_icon_0000": profile},
                     version="1.1.11", first_page="mainmenu_all")
    for lang, collection, profile_text in (("en", "COLLECTION", "PROFILE"), ("fr", "COLLECTION", "PROFIL")):
        ctx.set_text(lang, "mainmenu", "mainmenu_collection_text", collection)
        ctx.set_text(lang, "mainmenu", "mainmenu_profile_text", profile_text)


PROFILE_ICON_CARDS = [
    "Dark Magician", "Blue-Eyes White Dragon", "Red-Eyes B. Dragon", "Dark Magician Girl", "Kuriboh",
    "Summoned Skull", "Celtic Guardian", "Gaia The Fierce Knight", "Time Wizard", "Harpie Lady", "Jinzo",
    "Mystical Elf", "Baby Dragon", "Flame Swordsman", "Black Luster Soldier", "Buster Blader", "Cyber Dragon",
    "Elemental HERO Neos", "Winged Kuriboh", "Poseidra, the Atlantean Dragon", "Dark Prisoner", "Air Eater",
    "Exodia the Forbidden One", "Thousand Dragon", "Curse of Dragon", "Giant Soldier of Stone",
]


def profile_icons(ctx):
    """Preset profile pictures (server only, served at /fb/graph/<uid>/picture and /fb/graph/revival_icons/<n>):
    square crops of card art, 128 px. Names that are not in the card list are skipped; icons.json lists
    {id, card} in order (id = position, stable as long as the list only grows at the end)."""
    import io
    from PIL import Image
    icons = []
    for name in PROFILE_ICON_CARDS:
        try:
            art = card_art(ctx, _card_by_name(ctx, name))
        except RuntimeError:
            continue
        side = min(art.width, art.height)
        left, top = (art.width - side) // 2, (art.height - side) // 2
        icon = art.crop((left, top, left + side, top + side)).resize((128, 128), Image.LANCZOS).convert("RGB")
        buf = io.BytesIO()
        icon.save(buf, "PNG")
        ctx.server_files[f"icons/{len(icons)}.png"] = buf.getvalue()
        icons.append({"id": len(icons), "card": name})
    ctx.server_files["icons/icons.json"] = json.dumps(icons, indent=1).encode("utf-8")

def write_boosterpacks(ctx):
    """Last: config/boosterpacks.json for EBoosterPackInfo.LoadExtraPacks (tools/as3_patches.py). Validates each
    pack first: a purchase charges before the pack is rolled, so a pack without a loot table would take DP and
    give nothing (seen in the emulator)."""
    tables = {t["shopItemId"]: t for t in ctx.ace("config/ace/loot/loot_template.ace")}
    items = {i["id"] for i in ctx.ace("config/ace/inventory/item_template.ace")}
    shop_ids = {i["id"] for _, i in _shop_items(ctx)}
    for pack in ctx.boosterpacks:
        sid = pack["shopItemId"]
        if sid not in tables or sid not in shop_ids:
            raise RuntimeError(f"pack {pack['name']}: shop item {sid} has no loot table or shop entry")
        loot = [li["itemTemplate"] for g in tables[sid]["lootGroups"] for li in g["lootItemTemplates"]]
        if not loot or any(c not in items for c in loot):
            raise RuntimeError(f"pack {pack['name']}: empty loot table or unknown card")
    ctx.new_file("config/boosterpacks.json", json.dumps(ctx.boosterpacks, separators=(",", ":")).encode("utf-8"))


MODS = [
    free_bam_pro,
    settings_github_text,
    star_duel_button_text,
    wings_of_destiny,
    immemorial_cataclysm,
    blazing_wind,
    world_select_icon,
    mainmenu_icons,
    profile_icons,
    write_boosterpacks,
]
