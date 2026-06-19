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

GROUP_LABELS_MAP = {
    'yonino':'よにのちゃんねる','snowman':'Snow Man','sixtones':'SixTONES',
    'naniwa':'なにわ男子','kamenashi':'亀梨和也','kamaitachi':'かまいたち',
    'equal_love':'=LOVE','notme':'≠ME','neajoy':'≒JOY','nogizaka46':'乃木坂46',
    'sakurazaka46':'櫻坂46','hinatazaka46':'日向坂46','ginga':'中丸雄一 銀河チャンネル',
    'kodoku_no_gurume':'孤独のグルメ','timelesz':'timelesz',
    'heysayjump':'Hey! Say! JUMP','kingprince':'King & Prince','shiori':'しおり',
    'arashi':'嵐','kimura':'木村拓哉',
    'kpop_enhypen':'ENHYPEN','kpop_seventeen':'SEVENTEEN',
    'kpop_riize':'RIIZE','kpop_nct':'NCT','kpop_bts':'BTS','kpop_twice':'TWICE',
    'kpop_straykids':'Stray Kids','kpop_lesserafim':'LE SSERAFIM','kpop_blackpink':'BLACKPINK',
    'kpop_aespa':'aespa','kpop_ive':'IVE',
    'kanjani':'関ジャニ∞',
}

def build_seo_description(shop):
    name       = shop.get('name', '')
    genre      = shop.get('genre', '')
    prefecture = shop.get('prefecture', '')
    city       = shop.get('city', '')
    score      = shop.get('tabelog_score')
    price      = shop.get('price_range', '')
    source_vid = shop.get('source_video_title', '')
    group      = shop.get('group', '')
    source_type = shop.get('source_type', '')
    youtube_id  = shop.get('youtube_id', '')
    members    = shop.get('members', [])

    group_label = GROUP_LABELS_MAP.get(group, group)
    location = f'{prefecture}{city}' if (prefecture or city) else ''

    # Opening: context of visit
    if source_vid and (source_type in ('tv', 'drama') or not youtube_id):
        opener = f'{source_vid}で紹介された'
    elif youtube_id and group_label:
        opener = f'{group_label}のYouTubeで紹介された'
    elif group_label:
        opener = f'{group_label}が訪れた'
    else:
        opener = ''

    # Core: genre + name + location
    if genre:
        core = f'{genre}「{name}」'
    else:
        core = f'「{name}」'
    if location:
        core += f'（{location}）'

    # Details: score, price
    details = []
    if score:
        details.append(f'食べログ{score}点')
    if price and price != '-':
        details.append(price)
    detail_str = '、'.join(details)

    # Assemble
    parts = [opener + core + '。']
    if detail_str:
        parts.append(detail_str + '。')
    parts.append('推し活グルメ巡礼スポット。')

    desc = ''.join(parts)
    return desc[:160]

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

    group_label = GROUP_LABELS_MAP.get(shop.get('group', ''), '')
    name = shop.get('name', '')
    if group_label:
        page_title = f'{group_label}が行った「{name}」'
    else:
        page_title = name
    lines = ["---", f"layout: shop", f"title: {yaml_str(page_title)}"]

    desc = build_seo_description(shop)
    lines.append(f"description: {yaml_str(desc)}")

    # shop_id: front matter name avoids collision with Jekyll's built-in page.id
    v = shop.get("id")
    if v:
        lines.append(f"shop_id: {yaml_str(v)}")

    # scalar fields
    for key in ["name","genre","prefecture","city","address",
                "nearest_station","price_range","visited_date",
                "youtube_id","source_video_title","source_video_url","source_url",
                "group","tabelog_url","hotpepper_url","google_maps_url",
                "thumbnail_url","source_type","seating_note",
                "business_hours"]:
        v = shop.get(key)
        if v is not None and v != "":
            lines.append(f"{key}: {yaml_str(v)}")

    # numeric fields
    for key in ["lat","lng","tabelog_score"]:
        v = shop.get(key)
        if v is not None:
            lines.append(f"{key}: {v}")

    # list fields
    for key in ["members","groups","tags","ordered_items"]:
        v = shop.get(key)
        if v:
            lines.append(f"{key}:{yaml_list(v)}")

    # affiliate_links
    al = shop.get("affiliate_links")
    if al:
        lines.append(f"affiliate_links:{yaml_affiliate(al)}")

    lines.append("---")
    lines.append("")  # empty body — all content is in the layout

    slug = re.sub(r"-+$", "", shop_id.replace("_", "-"))
    out_path = os.path.join(OUT_DIR, f"{slug}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    generated += 1

print(f"Generated {generated} shop pages in {OUT_DIR}")

# ── _group_pages/*.md の shop_count を実件数に同期 ──────────────────
import re as _re
from collections import Counter as _Counter
from pathlib import Path as _Path

_gc = _Counter()
for s in shops:
    for g in s.get('groups', []):
        _gc[g] += 1

GROUP_PAGES_DIR = _Path(ROOT) / '_group_pages'
sync_updated = 0
for md in sorted(GROUP_PAGES_DIR.glob('*.md')):
    text = md.read_text(encoding='utf-8')
    m = _re.search(r'^group_key:\s*"([^"]+)"', text, _re.MULTILINE)
    if not m:
        continue
    gkey = m.group(1)
    actual = _gc.get(gkey, 0)
    old_m = _re.search(r'^shop_count:\s*(\d+)', text, _re.MULTILINE)
    if not old_m or int(old_m.group(1)) == actual:
        continue
    old = int(old_m.group(1))
    new_text = _re.sub(r'^shop_count:\s*\d+', f'shop_count: {actual}', text, flags=_re.MULTILINE)
    new_text = _re.sub(r'(title:.*?)' + str(old) + r'(選|件)', rf'\g<1>{actual}\g<2>', new_text)
    lm = _re.search(r'^group_label:\s*"([^"]+)"', text, _re.MULTILINE)
    if lm:
        label = _re.escape(lm.group(1))
        new_text = _re.sub(r'(' + label + r'.*?グルメスポット)\d+(件)', rf'\g<1>{actual}\g<2>', new_text)
    md.write_text(new_text, encoding='utf-8')
    print(f"  group_pages sync: {gkey} {old} → {actual}")
    sync_updated += 1

if sync_updated:
    print(f"  _group_pages shop_count 同期: {sync_updated}件")
