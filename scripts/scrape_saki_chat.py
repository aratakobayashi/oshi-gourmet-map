#!/usr/bin/env python3
"""
saki-chat.com のなにわ男子東京ロケ地記事から店舗情報をスクレイピング
対象: https://saki-chat.com/naniwa-tokyo/

出力: scripts/scraped_saki_chat_naniwa.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
from bs4 import BeautifulSoup

GROUP = 'naniwa'
MEMBERS = ['大西流星', '道枝駿佑', '高橋恭平', '長尾謙杜', '西畑大吾', '藤原丈一郎', '大橋和也']
SOURCE_TITLE = 'なにわ男子のなんでやねん'

GENRE_MAP = [
    (['ラーメン', '冷麺', 'そば', 'うどん', 'SOBA', 'わんこそば'], 'ラーメン'),
    (['焼肉', '焼き肉', 'カルビ', 'Meat'], '焼肉'),
    (['寿司', '鮨', '回転寿司', '立ち寿司'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン', 'BAKERY'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'ピザ', 'pizza', 'Pizza', 'PST'], 'カフェ'),
    (['バーガー', 'Burger', 'burger', 'チキン', 'フライドチキン'], '食事'),
    (['餃子', 'ギョーザ', '中華', '小吃'], '中華'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['牡蠣', '海鮮', '魚', 'seafood'], '海鮮'),
    (['牛タン', '焼肉'], '焼肉'),
    (['大衆食堂', '食堂'], '食事'),
    (['居酒屋', 'バー', '横丁'], '居酒屋'),
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def extract_member_from_h3(h3_text):
    """h3 text 'XXXの東京ロケ地ご飯編' からメンバー名を抽出"""
    for m in MEMBERS:
        if m in h3_text:
            return m
    if 'なにわ男子メンバー全員' in h3_text or h3_text == 'なにわ男子の東京ロケ地ご飯編':
        return ''  # 全員
    return ''


def parse_date_shop_map(section_paras):
    """
    h3セクションの段落から {shop_name_fragment: (date, episode_title)} を構築
    例: "2021年7月9日に放送された、「XXX」より紹介された店舗は、そうめん そそそ 研究室の1店舗です。"
    """
    date_shop_map = {}
    all_member_date = None  # 全員コーナー用

    for para in section_paras:
        # 日付抽出
        date_m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', para)
        if not date_m:
            # 全員コーナーの場合 "2024年1月25に" と不完全な場合もある
            date_m2 = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})', para)
            if date_m2:
                y, mo, d = date_m2.groups()
                all_member_date = f'{y}-{int(mo):02d}-{int(d):02d}'
            continue

        y, mo, d = date_m.groups()
        date_str = f'{y}-{int(mo):02d}-{int(d):02d}'

        # エピソードタイトル
        ep_m = re.search(r'「(.+?)」', para)
        ep_title = ep_m.group(1) if ep_m else ''

        # 店名リスト抽出: "店名は、..." or "店舗は、..." の後
        shops_m = re.search(r'店(?:名|舗)は[、,]\s*(.+?)(?:の\d+店舗|です|。)', para)
        if not shops_m:
            continue

        shops_str = shops_m.group(1)
        # "店名1と、店名2" or "店名1、店名2" で分割
        raw_names = re.split(r'と[、,]|[、,]', shops_str)
        for raw_name in raw_names:
            name_clean = raw_name.strip()
            if name_clean:
                date_shop_map[name_clean] = (date_str, ep_title)

    return date_shop_map, all_member_date


def find_date_for_shop(h4_name, date_shop_map, all_member_date):
    """h4 店名を date_shop_map から部分一致で検索"""
    # 完全一致
    if h4_name in date_shop_map:
        return date_shop_map[h4_name]
    # 前方一致 (h4 は「挽肉と米　吉祥寺店」、map は「挽肉と米」)
    for key, val in date_shop_map.items():
        if h4_name.startswith(key) or key in h4_name:
            return val
    # 全員コーナー
    if all_member_date:
        return (all_member_date, '')
    return ('', '')


def extract_address(paras):
    """段落テキストから住所を抽出 '住所は、...'"""
    for para in paras:
        m = re.search(r'住所は[、,]\s*(.+?)(?:で[、,]|です[。]?|$)', para)
        if m:
            addr = m.group(1).strip()
            # 最寄駅・アクセス情報を除去
            addr = re.sub(r'[、,]?\s*(最寄[駅]|徒歩|から徒歩|より徒歩).*$', '', addr).strip()
            # 末尾の "で" や "でXX駅" パターンを除去
            addr = re.sub(r'で(?:[^、。\n]*)$', '', addr).strip()
            addr = re.sub(r'で$', '', addr).strip()
            return addr
    return ''


def extract_description(h4_name, paras):
    """最初の1-2文を説明文に"""
    desc_parts = []
    for para in paras:
        if re.search(r'^住所は[、,]', para):
            break
        if para and len(para) > 5:
            desc_parts.append(para)
        if len(desc_parts) >= 2:
            break
    desc = ' '.join(desc_parts)
    return desc[:120] if desc else ''


def scrape(url):
    print(f'取得中: {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    content = soup.find('div', class_='entry-content') or soup.find('article')
    if not content:
        raise RuntimeError('Content not found')

    shops = []
    current_member = ''
    current_date_map = {}
    current_all_date = None

    elements = list(content.find_all(['h2', 'h3', 'h4']))

    # h3: member section → build date map from following paras (before first h4)
    # h4: shop name → extract info from following paras (before next h4/h3)
    # We process content tags in order

    all_tags = list(content.children)

    i = 0
    while i < len(all_tags):
        tag = all_tags[i]
        if not hasattr(tag, 'name') or not tag.name:
            i += 1
            continue

        if tag.name == 'h3':
            h3_text = tag.get_text(strip=True)
            if '閉店' in h3_text:
                current_member = ''
                current_date_map = {}
                current_all_date = None
                i += 1
                continue

            current_member = extract_member_from_h3(h3_text)

            # collect paragraphs until first h4 or h3
            section_paras = []
            j = i + 1
            while j < len(all_tags):
                sib = all_tags[j]
                if not hasattr(sib, 'name') or not sib.name:
                    j += 1
                    continue
                if sib.name in ['h2', 'h3', 'h4']:
                    break
                if sib.name == 'p':
                    t = sib.get_text(separator=' ', strip=True)
                    if t:
                        section_paras.append(t)
                j += 1

            current_date_map, current_all_date = parse_date_shop_map(section_paras)

        elif tag.name == 'h4':
            shop_name = tag.get_text(strip=True)

            # collect paragraphs until next h4/h3/h2
            shop_paras = []
            j = i + 1
            while j < len(all_tags):
                sib = all_tags[j]
                if not hasattr(sib, 'name') or not sib.name:
                    j += 1
                    continue
                if sib.name in ['h2', 'h3', 'h4']:
                    break
                if sib.name == 'p':
                    t = sib.get_text(separator=' ', strip=True)
                    if t:
                        shop_paras.append(t)
                j += 1

            address = extract_address(shop_paras)
            desc = extract_description(shop_name, shop_paras)
            date_str, ep_title = find_date_for_shop(shop_name, current_date_map, current_all_date)
            genre = detect_genre(shop_name + desc)

            tabelog_url = 'https://tabelog.com/rstLst/?vs=1&sk=' + urllib.parse.quote(shop_name)

            shops.append({
                'name': shop_name,
                'visited_date': date_str,
                'description': desc,
                'genre': genre,
                'group': GROUP,
                'groups': [GROUP],
                'members': [current_member] if current_member else [],
                'address': address,
                'lat': None,
                'lng': None,
                'youtube_id': '',
                'source_video_title': ep_title if ep_title else SOURCE_TITLE,
                'source_video_url': '',
                'source_type': 'tv',
                'tabelog_url': tabelog_url,
                'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}],
            })
            print(f'  {shop_name} ({date_str}) {current_member} addr={address[:30] if address else "なし"}')

        i += 1

    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://saki-chat.com/naniwa-tokyo/')
    parser.add_argument('--output', default='scripts/scraped_saki_chat_naniwa.json')
    args = parser.parse_args()

    shops = scrape(args.url)

    # 重複除去（同名）
    seen = set()
    unique = []
    for s in shops:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(unique)}件')
    print(f'→ {args.output}')


if __name__ == '__main__':
    main()
