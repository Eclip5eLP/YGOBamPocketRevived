"""
Test content, applied by tools/build_content.py only with env YGO_TEST_CONTENT=1 (never in a release build).

second_world_map: world map template 2 with one node that opens a new chapter (story map template 60, a copy of
chapter 1 = story map template 2), to exercise several world maps, save migration and new chapters end to end.
"""

import copy
import re

from content_mods import LOCAL_STORE

WORLD_MAP = 2
CHAPTER = 60          # new story map template id
BASE_CHAPTER = 2      # copied chapter (the first story chapter)
WORLD_NODE = 100      # new world node template id


def second_world_map(ctx):
    a = "config/ace/worldmap/"
    world_nodes = ctx.ace(a + "worldnodetemplate.ace")
    maps = ctx.ace(a + "storymaptemplate.ace")
    nodes = ctx.ace(a + "storynodetemplate.ace")

    node = copy.deepcopy(next(n for n in world_nodes if n["id"] == 1))
    node.update(id=WORLD_NODE, worldMapTemplateId=WORLD_MAP, unlockedByNodeId=0, storyMapTemplateId=CHAPTER,
                locked=False, xmlNodeName=1, unlockStartDate=None, unlockEndDate=None)
    world_nodes.append(node)

    chapter = copy.deepcopy(next(m for m in maps if m["id"] == BASE_CHAPTER))
    chapter["id"] = CHAPTER
    maps.append(chapter)

    next_node = max(n["id"] for n in nodes) + 1
    next_star = max([s["id"] for n in nodes for s in n["storyNodeStarTemplates"]] or [0]) + 1
    for base in [n for n in nodes if n["storyMapTemplateId"] == BASE_CHAPTER]:
        new = copy.deepcopy(base)
        new["id"] = next_node
        new["storyMapTemplateId"] = CHAPTER
        for star in new["storyNodeStarTemplates"]:
            star["id"] = next_star
            star["storyNodeTemplateId"] = next_node
            next_star += 1
        nodes.append(new)
        next_node += 1

    # layouts (world package): world map 2 = the world map with only its first node, opening the new chapter;
    # the chapter layout is loaded as Map<template id - 1>_level1.xml (StoryMap.CreateContent)
    world = (LOCAL_STORE / "asset/world/worldmap.xml").read_text(encoding="utf-8")
    objects = re.findall(r'\s*<object [^>]*classname="WorldNode">.*?</object>', world, re.S)
    first = re.sub(r'(name="maptoload" value=")\d+', rf"\g<1>{CHAPTER}", objects[0])
    world2 = world.replace("".join(objects), first) if "".join(objects) in world else None
    if world2 is None:  # nodes not contiguous: drop each one
        world2 = world
        for obj in objects:
            world2 = world2.replace(obj, "")
        world2 = world2.replace('<layer name="Node" type="1">', '<layer name="Node" type="1">' + first, 1)
    ctx.package_file("world", f"worldmap{WORLD_MAP}.xml", world2.encode("utf-8"), "1.1.10")
    ctx.package_file("world", f"map{CHAPTER - 1}_level1.xml",
                     (LOCAL_STORE / f"asset/world/map{BASE_CHAPTER - 1}_level1.xml").read_bytes(), "1.1.10")

    # chapter preview (mappreview package): copy of chapter 1's preview under the new id
    pdir = LOCAL_STORE / "asset/misc/mappreview"
    ctx.package_file("mappreview", f"mappreview_preview{CHAPTER - 1}.png",
                     (pdir / f"mappreview_preview{BASE_CHAPTER - 1}.png").read_bytes(), "1.1.7")
    ctx.package_file("mappreview", f"mappreview_preview{CHAPTER - 1}.xml", (
        f'<TextureAtlas imagePath="mappreview_preview{CHAPTER - 1}.png">\n'
        f'    <SubTexture name="mappreview_preview{CHAPTER - 1}0000" x="0" y="0" width="150" height="150"/>\n'
        "</TextureAtlas>\n").encode("utf-8"), "1.1.7")

    # texts: chapter dialogue section MAP_0<id-1> copied from chapter 1's, node description in the map section
    for lang in ("en", "fr"):
        sections = ctx.ace(f"config/ace/resource/{lang}/localization_section.ace")
        base = next(s for s in sections if s["sectionName"] == f"map_{BASE_CHAPTER - 1:03d}")
        new = copy.deepcopy(base)
        new["sectionName"] = f"map_{CHAPTER - 1:03d}"
        sections.append(new)
        ctx.set_text(lang, "map", f"WORLD_NODE_INFO_MAP_ID_{CHAPTER - 1}", "Test chapter on world map 2")
        ctx.set_text(lang, "world_map", f"NAME_CHAPTER{CHAPTER - 1}", "W2-1. Test Chapter")


MODS = [second_world_map]
