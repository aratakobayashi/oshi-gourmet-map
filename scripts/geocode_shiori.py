"""
geocode_shiori.py
しおりショップデータ専用ジオコーダー

tabelog URL のある店舗はページの JSON-LD から座標取得（正確）。
ない店舗は建物名除去 + Nominatim でフォールバック。
"""

import json, re, time, urllib.request, urllib.parse

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
INPUT  = "scripts/shiori_shops_raw.json"
OUTPUT = "scripts/shiori_shops_geocoded.json"


def normalize(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif ch == "　":
            result.append(" ")
        elif ch in ("−", "－"):
            result.append("-")
        else:
            result.append(ch)
    return "".join(result)


def strip_building(address: str) -> str:
    """番地は残し、その後ろの建物名・フロア情報を除去する"""
    address = normalize(address)
    # "数字-数字-数字 建物名" → "数字-数字-数字"
    address = re.sub(r"(\d+[-]\d+(?:[-]\d+)?)\s+.*$", r"\1", address).strip()
    # 〒xxx-xxxx から始まる郵便番号を除去
    address = re.sub(r"^〒?\d{3}-?\d{4}\s*", "", address).strip()
    return address


def geocode_query(query: str) -> tuple:
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "jp",
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": "oshi-gourmet-map/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
        if results:
            lat, lng = float(results[0]["lat"]), float(results[0]["lon"])
            # 日本範囲チェック
            if 24 <= lat <= 46 and 122 <= lng <= 154:
                return lat, lng
    except Exception as e:
        print(f"    API エラー: {e}")
    return None, None


def geocode_from_tabelog(url: str) -> tuple:
    """tabelog ページの JSON-LD から座標を取得する"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        m = re.search(r'"latitude"\s*:\s*([\d.]+)[^}]*"longitude"\s*:\s*([\d.]+)', html)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if 24 <= lat <= 46 and 122 <= lng <= 154:
                return lat, lng
    except Exception as e:
        print(f"    tabelog取得エラー: {e}")
    return None, None


def geocode(shop: dict) -> tuple:
    name  = shop.get("name", "")
    addr  = normalize(shop.get("address", "").strip())
    pref  = shop.get("prefecture", "")
    city  = shop.get("city", "")

    # tabelog URL があれば先に試みる（最も正確）
    tabelog_url = shop.get("tabelog_url", "")
    if tabelog_url:
        print(f"    [tabelog] {tabelog_url}")
        lat, lng = geocode_from_tabelog(tabelog_url)
        time.sleep(1)
        if lat and lng:
            return lat, lng

    strategies = []

    if addr:
        strategies.append(("フル住所", addr))
        stripped = strip_building(addr)
        if stripped != addr:
            strategies.append(("建物名除去", stripped))
        # 丁目形式: "1-30-8" → "1丁目30番8号" / "1丁目"
        base = re.sub(r"\d+[-]\d+.*$", "", stripped).strip()
        m = re.search(r"(\d+)[-](\d+)(?:[-](\d+))?", stripped)
        if m and base:
            chome, ban, go = m.group(1), m.group(2), m.group(3)
            addr_chome = f"{base}{chome}丁目{ban}番" + (f"{go}号" if go else "")
            strategies.append(("丁目形式", addr_chome))
            strategies.append(("丁目のみ", f"{base}{chome}丁目"))
        # 町名+県市だけでも試す
        if base:
            strategies.append(("町名", base))

    if pref or city:
        strategies.append(("エリア+店名", f"{pref}{city} {name}"))

    strategies.append(("店名のみ", name))

    for label, query in strategies:
        print(f"    [{label}] {query}")
        lat, lng = geocode_query(query)
        time.sleep(1)
        if lat and lng:
            return lat, lng

    return None, None


def main():
    with open(INPUT, encoding="utf-8") as f:
        shops = json.load(f)

    success = 0
    for i, shop in enumerate(shops):
        print(f"\n[{i+1}/{len(shops)}] {shop['name']}")
        lat, lng = geocode(shop)
        if lat and lng:
            shop["lat"] = lat
            shop["lng"] = lng
            print(f"    → ✓ lat={lat:.6f}, lng={lng:.6f}")
            success += 1
        else:
            shop.pop("lat", None)
            shop.pop("lng", None)
            print(f"    → ✗ 取得失敗")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {success}/{len(shops)} 件成功 → {OUTPUT}")


if __name__ == "__main__":
    main()
