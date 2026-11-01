"""
Content mods applied in order by tools/build_content.py. Each mod takes the build Context and edits data files
(ctx.ace / ctx.raw_replace / ctx.strings) or art packages (ctx.package_file). Mods hold only our own changes.
"""

import collections
import copy
import io
import json
import re
import time
from pathlib import Path

# Asset package -> directory under Local Store (server/server.py PACKAGE_PATHS, EExternalAsset.as:10-60)
PACKAGE_DIRS = {
    "shop": "asset/module/shop/",
    "world": "asset/world/",
    "mappreview": "asset/misc/mappreview/",
    "hud": "asset/module/hud/",
    "mainmenu": "asset/module/mainmenu/",
    "common": "asset/common/",
    # pictures of new cards only (add_card); unpacks into asset/cards/ next to series1/series2 (EExternalAsset
    # SERIES3, tools/as3_patches.py). None: no original files to start from.
    "series3": None,
}
NEW_CARDS_VERSION = "1.0.1"  # series3 package version: raise it whenever a card picture is added or changed


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


def add_atlas_frames(ctx, package, atlas, list_path, frames, version, first_page=None, subdir=""):
    """Add texture frames to a module as a second atlas page <atlas>_2 (Starling merges all pages of a module,
    AssetManager.getTextureNames sorts names across atlases, so e.g. shop_booster_covers_0011 becomes frame 11).

    frames: {frame name: PIL image}. The page is added to the module's asset list (asset/list/..., game data)
    and shipped in the module's package (version = new package version). first_page: list name of the original
    page when it is not <atlas>_1 (e.g. hud_all). subdir: the atlas folder inside the package (common: "common/").
    Frames go in columns at most 2048 px high (the largest texture the game's GPU profile takes). Several calls for
    the same atlas add up (the page is rebuilt with all frames so far)."""
    first_page = first_page or f"{atlas}_1"
    from PIL import Image
    pages = ctx.__dict__.setdefault("atlas_pages", {})
    frames = {**pages.get((package, atlas), {}), **frames}
    pages[(package, atlas)] = frames
    pad, max_height = 2, 2048
    places, x, y, column_width = {}, pad, pad, 0
    for name, img in sorted(frames.items()):
        if y + img.height + pad > max_height:
            x, y, column_width = x + column_width + pad, pad, 0
        places[name] = (x, y)
        y += img.height + pad
        column_width = max(column_width, img.width)
    width = max(px + frames[n].width for n, (px, _) in places.items()) + pad
    height = max(py + frames[n].height for n, (_, py) in places.items()) + pad
    page = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    xml = [f'<TextureAtlas imagePath="{atlas}_2.png">']
    for name, img in sorted(frames.items()):
        px, py = places[name]
        page.paste(img, (px, py))
        xml.append(f'    <SubTexture name="{name}" x="{px}" y="{py}" width="{img.width}" height="{img.height}"/>')
    xml.append("</TextureAtlas>")
    buf = io.BytesIO()
    page.save(buf, "PNG")
    ctx.package_file(package, f"{subdir}{atlas}_2.png", buf.getvalue(), version)
    ctx.package_file(package, f"{subdir}{atlas}_2.xml", ("\n".join(xml) + "\n").encode("utf-8"), version)
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
            new = ctx.packages.get("series3", {}).get(path)
            if new is not None:
                return Image.open(io.BytesIO(new)).convert("RGBA")
            f = LOCAL_STORE / "asset" / "cards" / path
            if f.exists():
                return Image.open(f).convert("RGBA")
    raise RuntimeError(f"no art for card {template_id}")


NEW_CARD_NAME_IDS = 20_000_000_000_000  # name resource id of a new card = this + its template id


def add_card(ctx, template_id, base_template_id, name, scan, **fields):
    """A new card: a copy of an existing card (stats, effects, rarity...) with its own id, name and picture.

    scan is an official card scan (full card); its art box becomes the card picture (tools/card_art.py) in the
    series3 package. A square image is taken as the art itself (YGOPRODeck cards_cropped). fields override template fields (atkStat, defStat, cardLevel, cardRarityId,
    cardElementId, cardFamilyId, cardSerieId...). Effects are copied with new effect ids (they are unique in the
    data); their texts stay those of the base card. Returns the new template."""
    from PIL import Image
    import card_art as cutter
    templates = ctx.ace("config/ace/inventory/item_template.ace")
    if any(t["id"] == template_id for t in templates):
        raise RuntimeError(f"card template {template_id} exists")
    base = next(t for t in templates if t["id"] == base_template_id)
    card = copy.deepcopy(base)
    next_effect = max(e["effect"]["id"] for t in templates for e in (t.get("effects") or [])) + 1
    for e in card.get("effects") or []:
        e["effect"]["id"] = next_effect
        next_effect += 1
    card.update(id=template_id, resourceNameId=type(base["resourceNameId"])(NEW_CARD_NAME_IDS + template_id),
                fusionData=None, fusionResult=False, cardNumber=0)
    card.update(fields)
    templates.append(card)
    for lang in ("en", "fr"):
        ctx.set_text(lang, "inventory", str(NEW_CARD_NAME_IDS + template_id), name,
                     resource_id=NEW_CARD_NAME_IDS + template_id)

    picture = f"revival{template_id}_1"
    assets = ctx.ace("config/ace/representation/asset.ace")
    links = ctx.ace("config/ace/representation/item_template_to_asset.ace")
    # rows are typed AMF objects (ace.AceObject with the game's class alias): copy one of the base card's, a plain
    # dict would reach the game as an untyped Object and break every card list that resolves pictures
    base_link = next(x for x in links if x["itemTemplateId"] == base_template_id)
    asset = copy.deepcopy(next(a for a in assets if a["id"] == base_link["assetId"]))
    asset.update(id=max(a["id"] for a in assets) + 1, path=f"{picture}.swf")
    assets.append(asset)
    link = copy.deepcopy(base_link)
    link.update(id=max(x["id"] for x in links) + 1, itemTemplateId=template_id, assetId=asset["id"])
    links.append(link)
    buf = io.BytesIO()
    image = Image.open(scan)
    art = image.convert("RGB") if abs(image.height / image.width - 1) < 0.05 else cutter.cut_art(image)
    cutter.game_picture(art).save(buf, "JPEG", quality=90)
    ctx.package_file("series3", f"{picture}.jpg", buf.getvalue(), NEW_CARDS_VERSION)
    return card


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
                     {"shop_booster_covers_0011": cover}, version=SHOP_VERSION)
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


def card_icons(ctx):
    """Profile pictures from any card the player owns (server only, served at /fb/graph/revival_cards/<id> and as
    /fb/graph/<uid>/picture): square crops of every card's art, 128 px JPEG, and cards/cards.json
    {template id: name} for the picture chooser. The preset pictures (profile_icons) stay for players who
    picked one before."""
    import io
    from PIL import Image
    _, by_id, _ = ctx.strings("en", "inventory")
    names = {}
    for t in ctx.ace("config/ace/inventory/item_template.ace"):
        if "cardRarityId" not in t:
            continue
        try:
            art = card_art(ctx, t["id"])
        except RuntimeError:
            continue
        side = min(art.width, art.height)
        left, top = (art.width - side) // 2, (art.height - side) // 2
        icon = art.crop((left, top, left + side, top + side)).resize((128, 128), Image.LANCZOS).convert("RGB")
        buf = io.BytesIO()
        icon.save(buf, "JPEG", quality=85)
        ctx.server_files[f"cards/{t['id']}.jpg"] = buf.getvalue()
        names[str(t["id"])] = by_id.get(int(t["resourceNameId"])) or GOD_CARDS.get(t["id"]) or f"Card {t['id']}"
    ctx.server_files["cards/cards.json"] = json.dumps(names, indent=0, sort_keys=True).encode("utf-8")

SALE_START, SALE_END = 1388534400000.0, 4102444800000.0  # 2014-01-01 .. 2100-01-01 (ms)
SHOP_UNLOCKS = Path(__file__).resolve().parent.parent / "as3_new" / "com" / "revival" / "shop" / "ShopUnlocks.as"
# template ids of the God cards (series 98, no English name in the data): special tournament rewards
GOD_CARDS = {1195: "The Winged Dragon of Ra", 1196: "Obelisk the Tormentor"}


def _shop_unlocks():
    """{card template id: chapter} from ShopUnlocks.CHAPTERS (the client checks it, so it is the one source)."""
    text = SHOP_UNLOCKS.read_text(encoding="utf-8")
    table = text.split("CHAPTERS:Object = {", 1)[1].split("}", 1)[0]
    return {int(k): int(v) for k, v in re.findall(r"(\d+)\s*:\s*(\d+)", table)}


def revival_rewards(ctx):
    """Former Arena reward cards and cards without a source (notes/pack_split_proposal.md, owner's choice
    2026-10-31): card shop entries that show once a chapter is cleared (ShopUnlocks), the Arena weekly reward sets
    and the God card milestones for the server (server/rewards.py, <content>/server/rewards.json), and names for
    the God cards."""
    items = {i["id"]: i for i in ctx.ace("config/ace/inventory/item_template.ace")}

    def usable(tid):
        if tid not in items:
            return False
        try:
            card_art(ctx, tid)
            return True
        except RuntimeError:
            return False

    # card shop (group 5): the card's own entry if it has one (most have dead dates), else a new DP entry modelled
    # on one that is on sale. ShopManager drops entries whose
    # startDate..endDate does not include today (core/shop/ShopManager.as:450-474); most card shop entries carry
    # placeholder dates around the year 3012, so only 155 of 1148 are on sale. Ours run 2014-2100.
    shop = ctx.ace("config/ace/shop/shop.ace")
    group = next(g for sh in shop for g in sh["shopItemGroups"] if g["id"] == 5)
    now = time.time() * 1000
    model = next(it for it in group["shopItem"] if it["startDate"] <= now <= it["endDate"]
                 and it["shopItemConversions"][0]["currencyTypeId"] == -1)
    listed = {it["itemTemplateId"] for it in group["shopItem"] if it["startDate"] <= now <= it["endDate"]}
    next_id = 3001  # our card shop entries: 3001+ (packs use 2001+)
    added = []
    for tid, chapter in sorted(_shop_unlocks().items()):
        if tid in listed or not usable(tid):
            raise RuntimeError(f"ShopUnlocks card {tid}: already on sale in the card shop or no card art")
        it = next((x for x in group["shopItem"] if x["itemTemplateId"] == tid), None)
        if it is None:  # no entry yet: a new one
            it = copy.deepcopy(model)
            it.update(id=next_id, itemTemplateId=tid)
            it["shopItemConversions"][0]["cost"] = 60 if items[tid]["cardSerieId"] == 99 else (
                30 if items[tid]["cardRarityId"] == 4 else 10)
            group["shopItem"].append(it)
            next_id += 1
        elif it["shopItemConversions"][0]["cost"] >= 999:  # the original "not for sale" price
            it["shopItemConversions"][0]["cost"] = 60
        it.update(startDate=type(model["startDate"])(SALE_START), endDate=type(model["endDate"])(SALE_END),
                  leagueRequired=1)  # the chapter is the only condition
        added.append((tid, chapter, it["shopItemConversions"][0]["cost"]))
    print("  card shop, unlocked by chapter (card, chapter, DP):", added)

    # Arena weekly reward sets: the original ARENA_REWARD bundles (type 6), grouped as in the data (consecutive
    # bundles whose cards are a subset of the first: tiers of 3/3/3/2/1 cards), only cards that exist and have art
    bundles = sorted((b for b in ctx.ace("config/ace/bundle/bundle_template.ace") if b["bundleTypeId"] == 6),
                     key=lambda b: b["id"])
    sets = []
    for b in bundles:
        cards = sorted({p.get("itemTemplateId") for p in b["products"] if p.get("itemTemplateId")})
        prev = sets[-1] if sets else None
        if prev and b["id"] == prev["bundles"][-1] + 1 and set(cards) <= set(prev["all"]) and \
                len(cards) <= len(prev["raw"][-1]):
            prev["bundles"].append(b["id"])
            prev["raw"].append(cards)
        else:
            sets.append({"bundles": [b["id"]], "all": cards, "raw": [cards]})
    arena = []
    for st in sets:
        tiers = [[c for c in tier if usable(c)] for tier in st["raw"]]
        if any(tiers):
            arena.append({"bundles": st["bundles"], "tiers": tiers})
    rewards = {"arena_sets": arena, "god_cards": {"obelisk": 1196, "ra": 1195}}
    ctx.server_files["rewards.json"] = json.dumps(rewards, indent=1).encode("utf-8")
    print("  arena reward sets:", len(arena), [s["tiers"][0] for s in arena])

    for tid, name in GOD_CARDS.items():
        ctx.set_text("en", "inventory", f"revival_card_{tid}", name, resource_id=items[tid]["resourceNameId"])


def card_sources(ctx):
    """config/cardsources.json {card template id: "how to get it"} for the card popup (com.revival.shop.CardSource,
    BuyCardPopup patched). The game itself only knows the card shop, crafting, its booster packs and tournament
    themes and shows "Coming soon!" for everything else; this covers the rest: story duel rewards (first win / replays,
    by chapter), objectives, shop bundles (starter decks, deals), Arena weekly rewards and the God card milestones
    (server/rewards.py). Chapter-locked card shop cards are handled by the client (ShopUnlocks). Runs after
    revival_rewards (it reads rewards.json)."""
    now = time.time() * 1000
    cards = {t["id"] for t in ctx.ace("config/ace/inventory/item_template.ace") if "cardRarityId" in t}
    # chapter of a story map: the world map 1 node that opens it (ShopUnlocks counts chapters the same way)
    chapter_of_map = {n["storyMapTemplateId"]: n["xmlNodeName"] for n in ctx.ace("config/ace/worldmap/worldnodetemplate.ace")
                      if n.get("worldMapTemplateId") == 1}
    map_of_node = {n["id"]: n["storyMapTemplateId"] for n in ctx.ace("config/ace/worldmap/storynodetemplate.ace")}
    shop = ctx.ace("config/ace/shop/shop.ace")
    on_sale = {it["id"]: g["id"] for sh in shop for g in sh["shopItemGroups"] for it in g["shopItem"]
               if it["startDate"] <= now <= it["endDate"]}
    found = collections.defaultdict(dict)  # card -> kind -> best value (lowest chapter, first objective name)
    _, quest_names, _ = ctx.strings("en", "quest")
    quest_name = {q["id"]: quest_names.get(int(q["resourceNameId"]), "") for q in ctx.ace("config/ace/quest/quest_template.ace")}

    def add(card, kind, value=0):
        if card in cards and (kind not in found[card] or value < found[card][kind]):
            found[card][kind] = value

    for b in ctx.ace("config/ace/bundle/bundle_template.ace"):
        for p in b["products"]:
            card = p.get("itemTemplateId")
            if not card:
                continue
            kind = b["bundleTypeId"]
            if kind in (1, 2):  # NODE_REWARD (first win of a duel), NODE_COMPLETION (replays)
                chapter = chapter_of_map.get(map_of_node.get(b.get("storyNodeTemplateId")))
                if chapter:
                    add(card, "story" if kind == 1 else "replay", chapter)
            elif kind == 4:  # QUEST_REWARD
                add(card, "objective", quest_name.get(b.get("questTemplateId"), "") or "~")
            elif kind == 3 and b.get("shopItemId") in on_sale:  # SHOP_BUNDLE on sale (starter decks, deals)
                add(card, "bundle")
    rewards = json.loads(ctx.server_files["rewards.json"])
    for s in rewards["arena_sets"]:
        for tier in s["tiers"]:
            for card in tier:
                add(card, "arena")
    for rank, card in ((10, rewards["god_cards"]["obelisk"]), (5, rewards["god_cards"]["ra"])):
        add(card, "god", rank)

    texts = {}
    for card, kinds in found.items():
        lines = []
        if "story" in kinds:
            lines.append(f"Story mode reward: win its duel in chapter {kinds['story']}.")
        if "replay" in kinds and "story" not in kinds:
            lines.append(f"Story mode: can be won by replaying duels in chapter {kinds['replay']}.")
        if "objective" in kinds:
            name = kinds["objective"]
            lines.append(f"Objective reward: {name}." if name != "~" else "Reward for completing an objective.")
        if "bundle" in kinds:
            lines.append("Comes in a deck or bundle in the shop.")
        if "arena" in kinds:
            lines.append("Weekly Arena reward for the top players.")
        if "god" in kinds:
            lines.append(f"Tournament: reach rank {kinds['god']}.")
        texts[str(card)] = " ".join(lines[:2])
    ctx.new_file("config/cardsources.json", json.dumps(texts, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    print(f"  card sources: {len(texts)} card(s) with a source text")


COMMON_VERSION = "1.1.11"  # common package (original 1.1.9): raise when its overlay changes

# Synchro/Xyz frame colours: the fusion pictures' brightness mapped onto dark..light (common_frames)
SUMMON_TINTS = {
    "synchro": {"frame": ("#77777d", "#ffffff"), "preview": ("#9a9aa0", "#ffffff"), "bar": ("#000000", "#a9a9b0")},
    "xyz": {"frame": ("#050506", "#5c5c66"), "preview": ("#55555e", "#d2d2da"), "bar": ("#000000", "#3e3e48")},
}


def common_frames(ctx):
    """White (Synchro) and black (Xyz) versions of the fusion card pictures, as a second common atlas page. Names:
    the fusion picture's with "fusion" -> "synchro"/"xyz" (com.revival.summon.Summon.FrameName); the bar under the
    art becomes frames 2/3 of common_card_template_bar_bottom (FullCardVisual patch). The beige text box of the big
    card keeps its colour."""
    from PIL import Image, ImageOps

    def tint(img, colours, keep_beige=False):
        rgb = img.convert("RGB")
        grey = ImageOps.autocontrast(ImageOps.grayscale(rgb))
        out = ImageOps.colorize(grey, *colours).convert("RGBA")
        out.putalpha(img.getchannel("A"))
        if keep_beige:  # text box and its edge: red clearly above blue (the fusion frame is blue/purple)
            src, dst = img.load(), out.load()
            for yy in range(img.height):
                for xx in range(img.width):
                    r, _, b, a = src[xx, yy]
                    if r > b + 30:
                        dst[xx, yy] = (*src[xx, yy][:3], a)
        return out

    common = "asset/common/common"
    duel = atlas_frame(common, "common_all_1", "common_duel_fusion_card_0000")
    big = atlas_frame(common, "common_all_1", "common_cardtemplate_card_fusion_0000")
    preview = atlas_frame(common, "common_all_1", "common_fusion_preview_card_background_0000")
    bar = atlas_frame(common, "common_all_1", "common_card_template_bar_bottom_0001")
    frames = {}
    for n, kind in ((2, "synchro"), (3, "xyz")):
        t = SUMMON_TINTS[kind]
        frames[f"common_duel_{kind}_card_0000"] = tint(duel, t["frame"])
        frames[f"common_cardtemplate_card_{kind}_0000"] = tint(big, t["frame"], keep_beige=True)
        frames[f"common_{kind}_preview_card_background_0000"] = tint(preview, t["preview"])
        frames[f"common_card_template_bar_bottom_000{n}"] = tint(bar, t["bar"])
    frames.update(series3_rarity_icons())
    add_atlas_frames(ctx, "common", "common_all", "asset/list/common/common_list.xml", frames,
                     version=COMMON_VERSION, subdir="common/")
    for lang, text in (("en", "Series 3"), ("fr", "Série 3")):
        ctx.set_text(lang, "card_filtering", "SERIES_3_FILTER", text)


# Series 3 rarity icons, frames 12-15 of common_rarity_all (CardRarityUtil patch): hexagons in the colours of the
# series 1/2 icons (common, rare, ultra rare, legend), 42x45 like the originals' untrimmed frame
SERIES3_ICON_COLOURS = [("#e8e8ea", "#c4c4c8", "#9a9aa0"), ("#f7a8c6", "#d9628f", "#8f2f55"),
                        ("#a6c8ff", "#4f7ff0", "#2a30bf"), ("#ffe9a0", "#f2c23c", "#b8800f")]


def hexagon_gem(size, colours, ring="#ffffff"):
    """A series 3 gem: white-rimmed hexagon, light top facets, dark bottom facets (size x size, transparent)."""
    import math
    from PIL import Image, ImageDraw
    light, mid, dark = colours
    scale = 4  # drawn large, then scaled down for smooth edges
    img = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r = size * scale / 2, size * scale * 0.48
    hexagon = [(c + r * math.cos(math.radians(60 * k + 30)), c + r * math.sin(math.radians(60 * k + 30)))
               for k in range(6)]
    d.polygon(hexagon, fill=ring)
    inner = [(c + (x - c) * 0.74, c + (y - c) * 0.74) for x, y in hexagon]
    d.polygon(inner, fill=mid)
    d.polygon([inner[3], inner[4], inner[5], (c, c)], fill=light)  # top facets
    d.polygon([inner[0], inner[1], inner[2], (c, c)], fill=dark)   # bottom facets
    return img.resize((size, size), Image.LANCZOS)


def _sparkle(width, height):
    """The light blue sparkle of the series 2 legend icon (its top right corner, gold gem pixels removed)."""
    sparkle = atlas_frame("asset/common/common", "common_all_1", "common_rarity_all_0007")
    corner = sparkle.crop((sparkle.width - 22, 0, sparkle.width, 20))
    px = corner.load()
    for yy in range(corner.height):
        for xx in range(corner.width):
            if px[xx, yy][0] > px[xx, yy][2] + 10:
                px[xx, yy] = (0, 0, 0, 0)
    return corner.resize((width, height))


def series3_rarity_icons():
    from PIL import Image
    icons = {}
    for n, colours in enumerate(SERIES3_ICON_COLOURS):
        icon = Image.new("RGBA", (42, 45), (0, 0, 0, 0))
        icon.alpha_composite(hexagon_gem(32, colours), (4, 12))
        if n == 3:  # the legend icons carry a sparkle at the top right
            icon.alpha_composite(_sparkle(22, 20), (42 - 22, 0))
        icons[f"common_rarity_all_{12 + n:04d}"] = icon
    return icons


SHOP_VERSION = "1.1.13"  # shop package (original 1.1.9)

# Starter deck cover (common_starterdeck_covers_NNNN, 219x318, StarterDeck.as:47): the window that shows the monster
# and the label plate drawn over it, measured on cover 6 (Blue-Eyes)
DECK_COVER_WINDOW = (26, 64, 194, 282)
DECK_COVER_PLATE = (48, 259, 170, 297)


def compose_deck_cover(art, hue):
    """A starter deck cover from card art: cover 6 with its cyan recoloured to `hue` (0-360), the art filling the
    window, the label plate redrawn on top."""
    from PIL import Image
    base = atlas_frame("asset/common/common", "common_all_1", "common_starterdeck_covers_0006")
    hsv = base.convert("RGB").convert("HSV")
    h, s, v = hsv.split()
    shift = int((hue - 180) * 255 / 360)  # cover 6 is cyan (~180 deg)
    h = h.point(lambda x: (x + shift) % 256)
    cover = Image.merge("HSV", (h, s, v)).convert("RGBA")
    cover.putalpha(base.getchannel("A"))
    left, top, right, bottom = DECK_COVER_WINDOW
    w, h2 = right - left, bottom - top
    side = min(art.width, art.height * w // h2)
    crop = art.crop(((art.width - side) // 2, 0, (art.width + side) // 2, min(art.height, side * h2 // w)))
    cover.paste(crop.convert("RGBA").resize((w, h2), Image.LANCZOS), (left, top))
    cover.alpha_composite(_plate(base, shift), DECK_COVER_PLATE[:2])
    return cover


def _plate(base, shift):
    from PIL import Image
    plate = base.crop(DECK_COVER_PLATE)
    h, s, v = plate.convert("RGB").convert("HSV").split()
    out = Image.merge("HSV", (h.point(lambda x: (x + shift) % 256), s, v)).convert("RGBA")
    out.putalpha(plate.getchannel("A"))
    return out


def series3_shop_art(ctx):
    """Shop art for series 3 booster packs (frame = series - 1, BuyBoosterPackShopDisplay / ShopCollectionView):
    shop_booster_rarities_0002 (the four rarity gems, 2x2 like the series 2 frame) and shop_booster_series_icon_0002
    (the gold laurel badge with a gold hexagon), plus the "Series 3" pack label."""
    from PIL import Image
    shop = "asset/module/shop"
    rarities = Image.new("RGBA", (209, 226), (0, 0, 0, 0))
    for n, colours in enumerate(SERIES3_ICON_COLOURS):  # same grid as series 2's frame: 2 per row
        rarities.alpha_composite(hexagon_gem(88, colours), (8 + (n % 2) * 112, 10 + (n // 2) * 112))
    rarities.alpha_composite(_sparkle(40, 36), (165, 116))
    badge = atlas_frame(shop, "shop_all_1", "shop_booster_series_icon_0001").copy()
    px = badge.load()
    for yy in range(badge.height):  # clear the pentagon in the middle, keep the laurels
        for xx in range(38, 84):
            px[xx, yy] = (0, 0, 0, 0)
    badge.alpha_composite(hexagon_gem(48, ("#fff1b0", "#f2c23c", "#b8800f"), ring="#8a5a00"), (37, 4))
    add_atlas_frames(ctx, "shop", "shop_all", "asset/list/module/shop_list.xml",
                     {"shop_booster_rarities_0002": rarities, "shop_booster_series_icon_0002": badge},
                     version=SHOP_VERSION)
    for lang, text in (("en", "Series 3"), ("fr", "Série 3")):
        ctx.set_text(lang, "shop", "shop_booster_serie3", text)


# Synchro/Xyz rules, written to config/summons.json (com.revival.summon.Summon):
#   "synchro": {tuner template id: {level total: [result ids]}}
#   "xyz": [{"id": result id, "rank": level of both materials, "family": 0 or monster type, "element": 0 or attribute}]
#   "effects": {effect id: {"needs": n, "cost": n, "perMaterial": 1, "attach": n}}  material effects on effect rows of
#              a result card (meaning: com.revival.summon.Summon, "Material effects")
# Result cards are added with add_card(..., fusionResult=True): made in duels, never in decks (Collection and the
# sell menu show the ones you own). Test cards: tools/content_test_mods.py.
SUMMONS = {"synchro": {}, "xyz": [], "effects": {}}


def write_summons(ctx):
    """config/summons.json from SUMMONS (after the test mods, which may add test rules). Checks every id is a card."""
    items = {i["id"]: i for i in ctx.ace("config/ace/inventory/item_template.ace")}
    ids = [int(t) for t in SUMMONS["synchro"]] + [x["id"] for x in SUMMONS["xyz"]]
    ids += [r for levels in SUMMONS["synchro"].values() for results in levels.values() for r in results]
    for i in ids:
        if i not in items:
            raise RuntimeError(f"summons: unknown card {i}")
    effect_ids = {e["effect"]["id"] for t in items.values() for e in (t.get("effects") or [])}
    for effect_id, rule in SUMMONS["effects"].items():
        if effect_id not in effect_ids or set(rule) - {"needs", "cost", "perMaterial", "attach"}:
            raise RuntimeError(f"summons: bad material effect {effect_id}: {rule}")
    # every card list starts from CardFiltering.FilterCardTemplateList, which drops cards without a shop item: a
    # Synchro/Xyz card without one would never show in the Collection or the sell menu (a backorder item is enough)
    shop = {i["itemTemplateId"] for _, i in _shop_items(ctx)}
    results = {x["id"] for x in SUMMONS["xyz"]}
    results |= {r for levels in SUMMONS["synchro"].values() for rs in levels.values() for r in rs}
    if results - shop:
        raise RuntimeError(f"summons: no shop item for {sorted(results - shop)}")
    for x in SUMMONS["xyz"]:
        if items[x["id"]]["cardLevel"] != x["rank"]:
            raise RuntimeError(f"summons: Xyz {x['id']} level {items[x['id']]['cardLevel']} != rank {x['rank']}")
    data = {"synchro": {str(t): {str(lv): r for lv, r in levels.items()} for t, levels in SUMMONS["synchro"].items()},
            "xyz": SUMMONS["xyz"], "effects": {str(e): r for e, r in SUMMONS["effects"].items()}}
    if SUMMONS.get("test"):  # test duels, set only by tools/content_test_mods.py (Summon.TestDraw / TestHp)
        data["test"] = SUMMONS["test"]
    ctx.new_file("config/summons.json", json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    # server: cards made in duels (fusionResult), left out of the strongest-cards deck (server/game.py deck_source)
    results = sorted(i for i, t in items.items() if t.get("fusionResult"))
    ctx.server_files["result_cards.json"] = json.dumps(results).encode("utf-8")


STARTER_DECK_SHOP_GROUP = 11  # shop.ace group of the starter decks (ShopItemGroupEnum.STARTER_DECK)
STARTER_DECK_MODEL = 775      # original starter deck shop item, copied for new decks (bundle 1688 = its 15 cards)


def add_starter_deck(ctx, deck, cover):
    """A prebuilt deck in the shop (EStarterPack data patch, tools/as3_patches.py STARTER_PACK_EDITS).

    deck: {"id", "shopItemId", "bundleId", "cards" (15 template ids), "cost" (DP), "frame" (cover frame, 7+),
    "name", "description", "contents" (texts), "chapter" (completing it offers the deck in the contextual deck popup;
    0 = no popup), "worth" (DP value shown in that popup), "quest" (quest that unlocks it in the shop; 0 = always)}.
    cover: PIL image (compose_deck_cover). Adds the shop item (copy of 775), the shop bundle with one product per
    card (copy of bundle 1688), the texts (shop section), the cover frame (common atlas page 2) and the
    config/starterdecks.json entry."""
    if len(deck["cards"]) != 15:
        raise RuntimeError(f"starter deck {deck['name']}: {len(deck['cards'])} cards, needs 15")
    items = {i["id"] for i in ctx.ace("config/ace/inventory/item_template.ace")}
    if set(deck["cards"]) - items:
        raise RuntimeError(f"starter deck {deck['name']}: unknown cards {set(deck['cards']) - items}")
    group, base = next((g, i) for g, i in _shop_items(ctx) if i["id"] == STARTER_DECK_MODEL)
    if any(i["id"] == deck["shopItemId"] for _, i in _shop_items(ctx)):
        raise RuntimeError(f"shop item {deck['shopItemId']} already exists")
    item = copy.deepcopy(base)
    item["id"] = deck["shopItemId"]
    item["shopItemConversions"][0]["cost"] = deck["cost"]
    group["shopItem"].append(item)
    bundles = ctx.ace("config/ace/bundle/bundle_template.ace")
    model = next(b for b in bundles if b.get("shopItemId") == STARTER_DECK_MODEL)
    bundle = copy.deepcopy(model)
    next_product = max(p["id"] for b in bundles for p in (b.get("products") or [])) + 1
    bundle["id"], bundle["shopItemId"] = deck["bundleId"], deck["shopItemId"]
    if any(b["id"] == deck["bundleId"] for b in bundles):
        raise RuntimeError(f"bundle {deck['bundleId']} already exists")
    products = []
    for n, card in enumerate(deck["cards"]):
        product = copy.deepcopy(model["products"][0])
        product.update(id=next_product + n, itemTemplateId=card, quantity=1)
        products.append(product)
    bundle["products"] = products
    bundles.append(bundle)
    key = f"shop_starterdeck_revival{deck['id']}"
    for lang in ("en", "fr"):
        ctx.set_text(lang, "shop", f"{key}_name", deck["name"])
        ctx.set_text(lang, "shop", f"{key}_description", deck["description"])
        ctx.set_text(lang, "shop", f"{key}_contents", deck["contents"])
        ctx.set_text(lang, "shop", f"{key}_unlock", deck.get("unlock_text", ""))
    add_atlas_frames(ctx, "common", "common_all", "asset/list/common/common_list.xml",
                     {f"common_starterdeck_covers_{deck['frame']:04d}": cover}, version=COMMON_VERSION,
                     subdir="common/")
    ctx.starterdecks.append({"id": deck["id"], "name": f"{key}_name", "description": f"{key}_description",
                             "contents": f"{key}_contents", "unlock": f"{key}_unlock", "cards": deck["cards"],
                             "bonus": [], "cost": deck["cost"], "shopItemId": deck["shopItemId"],
                             "frame": deck["frame"], "chapter": deck.get("chapter", 0),
                             "worth": deck.get("worth", 0), "quest": deck.get("quest", 0)})


def write_starterdecks(ctx):
    """config/starterdecks.json (EStarterPack.LoadExtraDecks), when a mod added decks."""
    if ctx.starterdecks:
        ctx.new_file("config/starterdecks.json", json.dumps(ctx.starterdecks, separators=(",", ":")).encode("utf-8"))


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
    revival_rewards,
    card_sources,
    blazing_wind,
    world_select_icon,
    mainmenu_icons,
    profile_icons,
    card_icons,
    common_frames,
    series3_shop_art,
    write_summons,  # test mods (YGO_TEST_CONTENT) run right before this one (build_content.py)
    write_starterdecks,
    write_boosterpacks,
]
