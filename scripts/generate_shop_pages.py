#!/usr/bin/env python3
"""
Generate Jekyll collection files for individual shop detail pages.
Output: _shop_pages/<id>.md (one file per shop in data/shops.json)
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOPS_JSON = os.path.join(ROOT, "data", "shops.json")
OUT_DIR = os.path.join(ROOT, "_shop_pages")

os.makedirs(OUT_DIR, exist_ok=True)

with open(SHOPS_JSON, encoding="utf-8") as f:
    shops = json.load(f)

def yaml_str(value):
    """Wrap a string in double-quotes, escaping backslashes and double-quotes."""
    if value is None:
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'

def yaml_list(lst):
    if not lst:
        return "[]"
    items = "\n".join(f'  - {yaml_str(v)}' for v in lst)
    return f"\n{items}"

def yaml_affiliate(links):
    if not links:
        return "[]"
    lines = []
    for lnk in links:
        label = yaml_str(lnk.get("label", ""))
        url   = yaml_str(lnk.get("url", ""))
        lines.append(f'  - label: {label}\n    url: {url}')
    return "\n" + "\n".join(lines)

generated = 0
for shop in shops:
    shop_id = shop.get("id", "")
    if not shop_id:
        continue

    lines = ["---", f"layout: shop", f"title: {yaml_str(shop.get('name',''))}"]

    # description for <title> / og:description
    desc = shop.get("description") or ""
    if not desc:
        parts = []
        if shop.get("genre"):
            parts.append(shop["genre"])
        if shop.get("prefecture") or shop.get("city"):
            parts.append((shop.get("city") or "") + (shop.get("prefecture") or ""))
        if shop.get("group"):
            g = shop["group"]
            label_map = {
                "yonino":"よにのちゃんねる","snowman":"Snow Man","sixtones":"SixTONES",
                "naniwa":"なにわ男子","kamenashi":"亀梨和也","kamaitachi":"かまいたち",
                "equal_love":"イコラブ","notme":"≠ME","neajoy":"≒JOY",
                "nogizaka46":"乃木坂46","hinatazaka46":"日向坂46","sakurazaka46":"櫻坂46",
                "ginga":"中丸雄一銀河チャンネル",
            }
            parts.append(f'{label_map.get(g, g)}が訪問')
        desc = "・".join(parts) if parts else shop.get("name","")
    lines.append(f"description: {yaml_str(desc)}")

    # scalar fields
    for key in ["id","name","genre","prefecture","city","address",
                "nearest_station","price_range","visited_date",
                "youtube_id","source_video_title","source_video_url",
                "group","tabelog_url","hotpepper_url","google_maps_url"]:
        v = shop.get(key)
        if v is not None and v != "":
            lines.append(f"{key}: {yaml_str(v)}")

    # numeric fields
    for key in ["lat","lng"]:
        v = shop.get(key)
        if v is not None:
            lines.append(f"{key}: {v}")

    # list fields
    for key in ["members","groups","tags"]:
        v = shop.get(key)
        if v:
            lines.append(f"{key}:{yaml_list(v)}")

    # affiliate_links
    al = shop.get("affiliate_links")
    if al:
        lines.append(f"affiliate_links:{yaml_affiliate(al)}")

    lines.append("---")
    lines.append("")  # empty body — all content is in the layout

    out_path = os.path.join(OUT_DIR, f"{shop_id}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    generated += 1

print(f"Generated {generated} shop pages in {OUT_DIR}")
