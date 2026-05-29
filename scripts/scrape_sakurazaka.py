"""
scrape_sakurazaka.py
zakki10.blogspot.com「そこ曲がったら、櫻坂？」掲載店舗スクレイピング

ソース: https://zakki10.blogspot.com/2022/02/sokosaku-seichi.html

HTML構造:
  <h3>【地名】店名</h3>
  <p>YYYY年M月D日に放送された...</p>
  <p>メンバー情報（Aさん、Bさん）</p>
  <div>（tabelog badge / 注文メモ）</div>
  tabelog URL: tabelog.com/area/A.../A.../XXXXX/ が埋め込まれている

使い方:
  python scripts/scrape_sakurazaka.py --output scripts/scraped_sakurazaka.json
"""

import urllib.request
import json
import re
import time
import argparse
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SOURCE_URL = 'https://zakki10.blogspot.com/2022/02/sokosaku-seichi.html'
GROUP = 'sakurazaka46'
SOURCE_VIDEO_TITLE = 'そこ曲がったら、櫻坂？'

MEMBERS = [
    '菅井友香', '小池美波', '土生瑞穂', '渡辺梨加', '守屋茜', '上村莉菜', '原田葵',
    '大園玲', '武元唯衣', '藤吉夏鈴', '森田ひかる', '増本綺良', '山﨑天', '田村保乃',
    '幸阪茉里乃', '松田里奈', '遠藤光莉', '関有美子', '松平璃子', '大沼晶保',
    '谷口愛季', '村山美羽', '向井純葉', '清水与帆', '古謝那菜佳', '中嶋優月',
    '林美澪', '小田倉麗奈', '石森璃花', '的野美青', '山下瞳月', '田鍋梨々花',
    '大園桃子',  # 元メンバー
]


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'ja,en;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read().decode('utf-8', errors='replace')


def extract_date(text: str) -> str:
    """YYYY年M月D日 → YYYY-MM-DD"""
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        return f'{y}-{mo}-{d}'
    return ''


def extract_members(text: str) -> list:
    found = []
    for name in MEMBERS:
        if name in text:
            found.append(name)
    return found


def extract_ordered_items(text: str) -> list:
    """「Xを紹介」「Xを召し上がり」などから注文品を抽出"""
    items = []
    patterns = [
        r'「([^」]{2,30})」を(?:紹介|召し上がり|希望|食べ)',
        r'「([^」]{2,30})」で(?:登場|紹介)',
        r'こちらの「([^」]{2,30})」',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            item = m.group(1).strip()
            if item and len(item) < 30:
                items.append(item)
    return list(dict.fromkeys(items))


def scrape() -> list:
    html = fetch_html(SOURCE_URL)
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.find(class_='post-body')
    if not body:
        raise RuntimeError('post-body not found')

    shops = []
    children = [c for c in body.children if hasattr(c, 'name') and c.name]

    i = 0
    while i < len(children):
        child = children[i]
        if child.name == 'h3':
            # 店名抽出: 【地名】店名
            raw_name = child.get_text(strip=True)
            name = re.sub(r'^【[^】]+】\s*', '', raw_name).strip()
            if not name:
                i += 1
                continue

            # 続くp要素を収集
            paragraphs = []
            j = i + 1
            while j < len(children) and children[j].name != 'h3':
                paragraphs.append(children[j])
                j += 1

            full_text = '\n'.join(p.get_text(strip=True) for p in paragraphs)

            # 放送日
            visited_date = extract_date(full_text)

            # メンバー
            members = extract_members(full_text)

            # 注文品
            ordered_items = extract_ordered_items(full_text)

            # tabelog URL（paragraphs内のリンクまたはHTMLから抽出）
            tabelog_url = ''
            para_html = ''.join(str(p) for p in paragraphs)
            m_tab = re.search(r'(https://tabelog\.com/[a-z]+/A\d+/A\d+/\d+/)', para_html)
            if m_tab:
                tabelog_url = m_tab.group(1)
            else:
                # badgeからrcdを取り出してURLを構築する場合もある
                m_rcd = re.search(r'tabelog\.com/badge/[^?]+\?[^"]*rcd=(\d+)', para_html)
                if m_rcd:
                    # 直接URLが隣にあるはず（上のパターンで取れているはず）
                    pass

            shop = {
                'name': name,
                'group': GROUP,
                'groups': [GROUP],
                'members': members,
                'visited_date': visited_date,
                'source_video_title': SOURCE_VIDEO_TITLE,
                'source_url': SOURCE_URL,
                'tabelog_url': tabelog_url,
                'ordered_items': ordered_items,
                'genre': '',
                'address': '',
                'lat': None,
                'lng': None,
            }
            shops.append(shop)
            i = j
        else:
            i += 1

    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_sakurazaka.json')
    args = parser.parse_args()

    print('Scraping zakki10.blogspot.com...')
    shops = scrape()
    print(f'取得: {len(shops)}件')
    for s in shops:
        tab = '✓' if s['tabelog_url'] else '✗'
        print(f'  {tab} {s["name"]} [{s["visited_date"]}] members={s["members"]}')
        if s['ordered_items']:
            print(f'      items={s["ordered_items"]}')

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'\n→ {args.output} に保存しました')


if __name__ == '__main__':
    main()
