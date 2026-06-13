#!/usr/bin/env python3
"""推しグルメ巡礼MAP 品質チェックスクリプト"""

import json
import re
import collections
from pathlib import Path

SHOPS_PATH = Path(__file__).parent.parent / "data" / "shops.json"

GROUP_LABELS = {
    "kingprince": "King&Prince",
    "arashi": "嵐",
    "nogizaka46": "乃木坂46",
    "kodoku_no_gurume": "孤独のグルメ",
    "naniwa": "なにわ男子",
    "sixtones": "SixTONES",
    "equal_love": "=LOVE系",
    "snowman": "Snow Man",
    "yonino": "よにのちゃんねる",
    "timelesz": "timelesz",
    "heysayjump": "Hey!Say!JUMP",
    "notme": "≠ME",
    "neajoy": "≒JOY",
    "agroup": "Aぇ!group",
    "kamenashi": "亀梨和也",
    "shiori": "しおりん",
    "smap": "SMAP",
    "sakurazaka46": "桜坂46",
    "hinatazaka46": "日向坂46",
    "ginga": "銀河テレビ",
    "kattun": "KAT-TUN",
    "kamaitachi": "かまいたち",
    "kpop_enhypen": "ENHYPEN",
    "kimura": "木村拓哉",
    "kpop_seventeen": "SEVENTEEN",
    "kpop_riize": "RIIZE",
    "numberi": "Number_i",
    "kpop_nct": "NCT",
    "travisjapan": "Travis Japan",
    "kinkikids": "KinKi Kids",
    "west": "WEST.",
    "kpop_twice": "TWICE",
    "kismai": "Kis-My-Ft2",
    "v6": "V6",
}

# 非食スポット疑いパターン（店名全体として怪しいもの）
NON_FOOD_PATTERNS = [
    r"駅\s*前?$",                   # 「〇〇駅」「〇〇駅前」で終わる
    r"駅\s+[^店舗]",                # 「〇〇駅 バス乗り場」など駅+スペース+非店舗
    r"商店街$",                      # 商店街
    r"エントランス前",               # ホテルエントランス前
    r"ロビー",                       # ホテルロビー
    r"(公園|広場|砂浜|ビーチ|海岸)$",  # 公園・ビーチ
    r"^大涌谷",                      # 観光地
    r"(コインランドリー|サウナ施設|書店|楽器店)$",
]

SUSPICIOUS_GENRES = {"観光", "スポット", "ロケ地", "施設", "建物", "その他"}


def bar(ratio, width=12):
    """割合をブロックバーで表現"""
    filled = round(ratio * width)
    empty = width - filled
    color = "\033[92m" if ratio >= 0.9 else "\033[93m" if ratio >= 0.7 else "\033[91m"
    return f"{color}{'█' * filled}{'░' * empty}\033[0m"


def pct(num, den):
    return num / den if den > 0 else 0


def check_non_food(name, genre):
    for p in NON_FOOD_PATTERNS:
        if re.search(p, name):
            return True
    if genre in SUSPICIOUS_GENRES and re.search(r"駅|公園|橋|神社|寺|城|展望|旅館|ホテル", name):
        return True
    return False


def analyze(shops):
    total = len(shops)
    issues_by_shop = []
    group_stats = collections.defaultdict(lambda: {
        "total": 0,
        "no_coords": 0,
        "no_genre": 0,
        "no_address": 0,
        "no_tabelog": 0,
        "no_thumbnail": 0,
        "no_description": 0,
        "suspicious": 0,
    })

    # 重複チェック（グループ内）
    group_names = collections.Counter()
    for s in shops:
        group_names[(s.get("group", ""), s.get("name", "").strip())] += 1
    within_group_dups = {k for k, v in group_names.items() if v > 1}

    # 全グループ横断の重複
    all_names = collections.Counter(s.get("name", "").strip() for s in shops)
    cross_group_dups = {n for n, c in all_names.items() if c > 1 and n}

    for s in shops:
        g = s.get("group", "unknown")
        name = s.get("name", "")
        genre = s.get("genre", "")
        issues = []

        group_stats[g]["total"] += 1

        # 完全性チェック
        if not s.get("lat") or not s.get("lng"):
            group_stats[g]["no_coords"] += 1
            issues.append("座標なし")
        if not genre:
            group_stats[g]["no_genre"] += 1
            issues.append("ジャンルなし")
        if not s.get("address"):
            group_stats[g]["no_address"] += 1
            issues.append("住所なし")
        has_tabelog = s.get("tabelog_url") or any(
            "tabelog" in (lnk.get("url", "")) for lnk in s.get("affiliate_links", [])
        )
        if not has_tabelog:
            group_stats[g]["no_tabelog"] += 1
            issues.append("tabelog URLなし")

        # サムネイル
        if not s.get("thumbnail_url"):
            group_stats[g]["no_thumbnail"] += 1
            issues.append("サムネイルなし")

        # 説明文
        if not s.get("description"):
            group_stats[g]["no_description"] += 1
            issues.append("説明文なし")

        # 適切性
        if check_non_food(name, genre):
            group_stats[g]["suspicious"] += 1
            issues.append(f"非食の疑い")

        if issues:
            issues_by_shop.append({
                "group": g,
                "name": name,
                "id": s.get("id", ""),
                "issues": issues,
            })

    return group_stats, issues_by_shop, within_group_dups, cross_group_dups


def print_report(shops):
    total = len(shops)
    group_stats, issues_by_shop, within_dups, cross_dups = analyze(shops)

    # --- 全体サマリー ---
    all_no_coords = sum(v["no_coords"] for v in group_stats.values())
    all_no_genre = sum(v["no_genre"] for v in group_stats.values())
    all_no_address = sum(v["no_address"] for v in group_stats.values())
    all_no_tabelog = sum(v["no_tabelog"] for v in group_stats.values())
    all_no_thumb = sum(v["no_thumbnail"] for v in group_stats.values())
    all_no_desc = sum(v["no_description"] for v in group_stats.values())
    all_suspicious = sum(v["suspicious"] for v in group_stats.values())

    print("\n" + "=" * 60)
    print("  推しグルメ巡礼MAP 品質レポート")
    print("=" * 60)
    print(f"  総店舗数: {total:,}件 / グループ数: {len(group_stats)}")
    print()

    print("【項目別スコア（全体）】")
    dims = [
        ("座標あり    ", total - all_no_coords, total),
        ("ジャンルあり", total - all_no_genre, total),
        ("住所あり    ", total - all_no_address, total),
        ("tabelog URL ", total - all_no_tabelog, total),
        ("サムネイル  ", total - all_no_thumb, total),
        ("説明文あり  ", total - all_no_desc, total),
        ("適切性      ", total - all_suspicious, total),
    ]
    for label, ok, den in dims:
        r = pct(ok, den)
        print(f"  {label}  {bar(r)}  {r*100:5.1f}%  ({ok:,}/{den:,})")

    # --- グループ別テーブル ---
    print()
    print("【グループ別スコア】")
    header = f"  {'グループ':<16} {'件数':>4}  {'座標':>5}  {'tabelog':>7}  {'サムネ':>6}  {'説明文':>6}  {'適切性':>6}  {'総合':>5}"
    print(header)
    print("  " + "-" * 62)

    # 件数降順でソート
    sorted_groups = sorted(group_stats.items(), key=lambda x: -x[1]["total"])

    for g, st in sorted_groups:
        label = GROUP_LABELS.get(g, g)
        n = st["total"]
        coord_r  = pct(n - st["no_coords"], n)
        tabel_r  = pct(n - st["no_tabelog"], n)
        thumb_r  = pct(n - st["no_thumbnail"], n)
        desc_r   = pct(n - st["no_description"], n)
        relev_r  = pct(n - st["suspicious"], n)
        overall  = (coord_r + tabel_r + thumb_r + desc_r + relev_r) / 5

        def c(r):
            if r >= 0.9: return f"\033[92m{r*100:5.1f}%\033[0m"
            if r >= 0.7: return f"\033[93m{r*100:5.1f}%\033[0m"
            return f"\033[91m{r*100:5.1f}%\033[0m"

        print(f"  {label:<16} {n:>4}   {c(coord_r)}   {c(tabel_r)}    {c(thumb_r)}   {c(desc_r)}   {c(relev_r)}  {c(overall)}")

    # --- 重複チェック ---
    print()
    print("【一意性チェック】")
    if within_dups:
        print(f"  グループ内重複: {len(within_dups)}件")
        for g, name in list(within_dups)[:10]:
            print(f"    [{GROUP_LABELS.get(g,g)}] {name}")
    else:
        print("  グループ内重複: \033[92mなし ✓\033[0m")

    cross_list = [(n, [s.get("group") for s in shops if s.get("name","").strip()==n]) for n in cross_dups]
    if cross_list:
        print(f"  グループ横断同名: {len(cross_list)}件（同一店舗が複数グループに登録）")
        for name, gs in cross_list[:10]:
            labels = [GROUP_LABELS.get(g, g) for g in gs]
            print(f"    {name} → {', '.join(labels)}")
    else:
        print("  グループ横断重複: \033[92mなし ✓\033[0m")

    # --- 要修正リスト ---
    print()
    print("【要確認リスト（問題数 多い順）】")
    sorted_issues = sorted(issues_by_shop, key=lambda x: -len(x["issues"]))

    # 非食疑い優先で表示
    suspicious = [i for i in sorted_issues if "非食の疑い" in i["issues"]]
    if suspicious:
        print(f"\n  ▼ 非食の疑いあり ({len(suspicious)}件)")
        for item in suspicious[:20]:
            g = GROUP_LABELS.get(item["group"], item["group"])
            others = [x for x in item["issues"] if x != "非食の疑い"]
            extra = f" + {', '.join(others)}" if others else ""
            print(f"    [{g}] {item['name']}{extra}")

    # 欠損多い順
    print(f"\n  ▼ 完全性が低い (3項目以上欠損)")
    multi_issues = [i for i in sorted_issues if len(i["issues"]) >= 3 and "非食の疑い" not in i["issues"]]
    if multi_issues:
        for item in multi_issues[:20]:
            g = GROUP_LABELS.get(item["group"], item["group"])
            print(f"    [{g}] {item['name']}  →  {', '.join(item['issues'])}")
    else:
        print("    なし ✓")

    # サムネなし
    no_thumb_shops = [i for i in issues_by_shop if "サムネイルなし" in i["issues"]]
    print(f"\n  ▼ サムネイルなし ({len(no_thumb_shops)}件) — 上位10件")
    for item in no_thumb_shops[:10]:
        g = GROUP_LABELS.get(item["group"], item["group"])
        print(f"    [{g}] {item['name']}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    shops = json.loads(SHOPS_PATH.read_text())
    print_report(shops)
