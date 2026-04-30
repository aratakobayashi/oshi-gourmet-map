"""
scrape_yonino.py
よにのちゃんねるのロケ地まとめサイトから店舗情報をスクレイピングするスクリプト
※サイト運営者の許可を得て使用しています

使い方:
  python scripts/scrape_yonino.py --output scripts/scraped_yonino.json
"""

import urllib.request
import json
import re
import argparse
from bs4 import BeautifulSoup

URL = 'https://8888-info.hatenablog.com/entry/%E6%9C%9D%E3%81%94%E3%81%AF%E3%82%93'


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    with urllib.request.urlopen(req) as r:
        return r.read().decode('utf-8')


def parse_address_phone(text: str):
    """「〒106-0047東京都港区...03-3440-1166」→ 住所と電話番号に分離"""
    text = re.sub(r'^〒\d{3}-\d{4}', '', text).strip()
    # 電話番号は半角数字のみで検索（全角数字を除外するため [0-9] を使用）
    phone_m = re.search(r'(☎\s*|)([0-9]{2,4}-[0-9]{2,4}-[0-9]{4})', text)
    if phone_m:
        phone = phone_m.group(2)
        address = text[:phone_m.start()].replace('☎', '').strip()
    else:
        phone = ''
        address = text.strip()
    return address, phone


def scrape(url: str) -> list:
    print('HTMLを取得中...')
    html = fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    entry = soup.find('div', class_='entry-content')
    if not entry:
        raise RuntimeError('記事本文が見つかりません')

    elements = entry.find_all(['h3', 'h4', 'h5', 'p'])

    shops = []
    current_year = 2026
    current_date = None
    current_episode = None
    current_station = None

    i = 0
    while i < len(elements):
        el = elements[i]
        text = el.get_text(strip=True)

        # 年の切り替えを検出（h3）
        if el.name == 'h3' and '年' in text:
            m = re.search(r'(\d{4})年', text)
            if m:
                current_year = int(m.group(1))

        # 配信日・動画番号を検出（h4）
        elif el.name == 'h4' and '配信' in text and '月' in text:
            m = re.search(r'(\d+)月(\d+)日', text)
            ep_m = re.search(r'#(\d+)', text)
            if m:
                month, day = int(m.group(1)), int(m.group(2))
                current_date = f'{current_year}-{month:02d}-{day:02d}'
                current_episode = ep_m.group(1) if ep_m else ''
                current_station = None

        # 最寄り駅を検出（h4）
        elif el.name == 'h4' and ('駅' in text or '徒歩' in text) and '配信' not in text:
            current_station = text

        # 店名を検出（h5、絵文字で始まる）
        elif el.name == 'h5' and current_date:
            # スキップするパターン
            if (text.startswith('✅') or text.startswith('【')
                    or text.startswith('(') or text.startswith('（')):
                i += 1
                continue

            # 絵文字・記号・【】を除いた店名を取得
            shop_name = re.sub(r'^[^\w\u3040-\u9FFF【]+', '', text).strip()
            shop_name = shop_name.strip('【】').strip()
            if not shop_name:
                i += 1
                continue

            # お店ではないエントリをスキップ
            skip_words = ['テイクアウト', 'ゲスト：', 'ランチビュッフェ', 'チョコ', 'アワード', 'BEST']
            if any(w in shop_name for w in skip_words):
                i += 1
                continue

            # 以降の要素から住所を探す
            address = ''
            phone = ''
            j = i + 1
            while j < len(elements):
                next_el = elements[j]
                next_text = next_el.get_text(strip=True)

                # 次の店名や日付が来たら終了
                if next_el.name in ('h3', 'h4'):
                    break
                # 読み仮名（括弧始まり）はスキップして続ける
                if next_el.name == 'h5' and (next_text.startswith('(') or next_text.startswith('（')):
                    j += 1
                    continue
                if next_el.name == 'h5' and not next_text.startswith('✅') and not next_text.startswith('【'):
                    break

                # パターン1: <h5>✅住所</h5><p>住所テキスト</p>
                if next_el.name == 'h5' and '住所' in next_text:
                    if j + 1 < len(elements) and elements[j + 1].name == 'p':
                        addr_text = elements[j + 1].get_text(strip=True)
                        if '〒' in addr_text or '都' in addr_text or '県' in addr_text:
                            address, phone = parse_address_phone(addr_text)
                    break

                # パターン2: <p>【住所】</p><p>住所テキスト</p>
                if next_el.name == 'p' and next_text == '【住所】':
                    if j + 1 < len(elements) and elements[j + 1].name == 'p':
                        addr_text = elements[j + 1].get_text(strip=True)
                        if '〒' in addr_text or '都' in addr_text or '県' in addr_text:
                            address, phone = parse_address_phone(addr_text)
                    break

                # パターン3: <p>【住所】住所テキスト</p>（同じpに入っている）
                if next_el.name == 'p' and '【住所】' in next_text and len(next_text) > 5:
                    addr_text = next_text.replace('【住所】', '').strip()
                    if addr_text:
                        address, phone = parse_address_phone(addr_text)
                    break

                j += 1

            shops.append({
                'name': shop_name,
                'visited_date': current_date,
                'episode': current_episode,
                'nearest_station': current_station or '',
                'address': address,
                'phone': phone,
                'group': 'yonino',
                'groups': ['yonino'],
            })

        i += 1

    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_yonino.json')
    args = parser.parse_args()

    shops = scrape(URL)

    # 住所なしの件数を集計
    with_addr = sum(1 for s in shops if s['address'])
    without_addr = len(shops) - with_addr

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(shops)}件（住所あり: {with_addr}件 / 住所なし: {without_addr}件）')
    print(f'→ {args.output} に保存しました')
    print('\n=== 最初の5件 ===')
    for s in shops[:5]:
        print(f'[{s["visited_date"]}] {s["name"]}')
        print(f'  住所: {s["address"]}')
        print(f'  電話: {s["phone"]}')
        print(f'  最寄り: {s["nearest_station"]}')


if __name__ == '__main__':
    main()
