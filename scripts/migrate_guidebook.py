#!/usr/bin/env python3
"""
migrate_guidebook.py
推し活ガイドブック（oshikatsu-guide.com / WordPress・SWELL）の記事を、
グルメMAPの _guides コレクション（/guide/<slug>/）へ移す。

- 公開ページ（post-sitemap.xml の各URL）の HTML から本文（div.post_content）を取り出す
  ※ WP REST API はサーバー側で 403 になるため使わない
- 記事内の画像（wp-content/uploads）は assets/img/guide/ にダウンロードして参照を差し替える
- 記事間リンクを新URLに張り替え、移さない記事（ライブレポート）へのリンクは文字だけ残す
- ASP リンクに rel="sponsored noopener" を付け、ASP リンクがある記事は pr: true にする
- 旧URL → 新URL の対応表を redirects/guidebook_redirects.csv に出力（301設定用）

使い方:
  python scripts/migrate_guidebook.py            # 取得して _guides/ を生成
  python scripts/migrate_guidebook.py --no-images  # 画像のダウンロードを省略
"""
import argparse
import csv
import hashlib
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup, Comment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, '_guides')
IMG_DIR = os.path.join(ROOT, 'assets', 'img', 'guide')
REDIRECT_CSV = os.path.join(ROOT, 'redirects', 'guidebook_redirects.csv')
SITEMAP = 'https://oshikatsu-guide.com/post-sitemap.xml'
OLD_HOST = 'oshikatsu-guide.com'
UA = 'oshi-gourmet-map-migration/1.0 (+https://gourmet.oshikatsu-guide.com)'

# タイトルのキーワード → (新しいslug, カテゴリ, 会場名[ジオコーディング用])
# カテゴリ: venue（会場ガイド）/ travel（遠征準備）/ basics（推し活の基本）/ profile（グループ・メンバー紹介）
# None は移さない記事（ライブレポート：時期が過ぎて検索需要が低いため）
SLUGS = [
    ('さいたまスーパーアリーナ', 'saitama-super-arena', 'venue', 'さいたまスーパーアリーナ'),
    ('キューアンドエースタジアムみやぎ', 'qa-stadium-miyagi', 'venue', 'キューアンドエースタジアムみやぎ'),
    ('マリンメッセ福岡', 'marine-messe-fukuoka', 'venue', 'マリンメッセ福岡'),
    ('大阪城ホール', 'osaka-jo-hall', 'venue', '大阪城ホール'),
    ('日本ガイシホール', 'nippon-gaishi-hall', 'venue', '日本ガイシホール'),
    ('日産スタジアム', 'nissan-stadium', 'venue', '日産スタジアム'),
    ('札幌ドーム', 'sapporo-dome', 'venue', '札幌ドーム'),
    ('横浜アリーナ', 'yokohama-arena', 'venue', '横浜アリーナ'),
    ('ゼビオアリーナ仙台', 'xebio-arena-sendai', 'venue', 'ゼビオアリーナ仙台'),
    ('武蔵野の森総合スポーツプラザ', 'musashino-forest-sport-plaza', 'venue', '武蔵野の森総合スポーツプラザ'),
    ('Aichi Sky Expo', 'aichi-sky-expo', 'venue', 'Aichi Sky Expo'),
    ('Asueアリーナ大阪', 'asue-arena-osaka', 'venue', 'Asueアリーナ大阪'),
    ('ぴあアリーナMM', 'pia-arena-mm', 'venue', 'ぴあアリーナMM'),
    ('代々木第一体育館', 'yoyogi-national-gymnasium', 'venue', '国立代々木競技場第一体育館'),
    ('北海きたえーる', 'hokkai-kitaeru', 'venue', '北海きたえーる'),
    ('有明アリーナ', 'ariake-arena', 'venue', '有明アリーナ'),
    ('神戸ワールド記念ホール', 'kobe-world-kinen-hall', 'venue', '神戸ワールド記念ホール'),
    ('静岡エコパアリーナ', 'shizuoka-ecopa-arena', 'venue', 'エコパアリーナ'),
    ('ライブ遠征の準備', 'live-ensei-checklist', 'travel', None),
    ('遠征Wi-Fi', 'ensei-wifi', 'travel', None),
    ('ライブ遠征の交通手段', 'live-ensei-transport', 'travel', None),
    ('timeleszアリーナツアー完全ガイド', 'timelesz-arena-tour-guide', 'travel', None),
    ('推し活とは？', 'what-is-oshikatsu', 'basics', None),
    ('SNSで推し活', 'sns-oshikatsu-tips', 'basics', None),
    ('ぼっち推し活', 'solo-oshikatsu', 'basics', None),
    ('推し活に必要な持ち物', 'oshikatsu-items-checklist', 'basics', None),
    ('推しができたら最初に', 'first-steps-new-oshi', 'basics', None),
    ('男が推し活して何が悪い', 'oshikatsu-for-men', 'basics', None),
    ('社会人男子の推し活', 'working-men-oshikatsu', 'basics', None),
    ('痛バの作り方', 'itabag-guide', 'basics', None),
    ('推し活費用を賢く節約', 'oshikatsu-saving-tips', 'basics', None),
    ('推しバレ', 'oshibare-episodes', 'basics', None),
    ('ACEesとは', 'acees-profile', 'profile', None),
    ('B&amp;ZAI', 'bandzai-profile', 'profile', None),
    ('B&ZAI', 'bandzai-profile', 'profile', None),
    ('KEY TO LIT', 'key-to-lit-profile', 'profile', None),
    ('少年忍者', 'shonen-ninja-profile', 'profile', None),
    ('Star Song Special', 'star-song-special', 'profile', None),
    ('寺西拓人', 'teranishi-takuto', 'profile', None),
    ('篠塚大輝', 'shinozuka-taiki', 'profile', None),
    ('猪俣周杜', 'inomata-shuto', 'profile', None),
    ('橋本将生', 'hashimoto-shosei', 'profile', None),
    # ライブレポート（移さない）
    ('YOUNG OLD」東京ドームレポ', None, None, None),
    ('YOUNG OLD」福岡公演レポ', None, None, None),
    ('N / bias” 福岡公演レポ', None, None, None),
    ('N / bias」名古屋公演レポ', None, None, None),
    ('ACEes 2025 PROLOGUE 福岡公演レポ', None, None, None),
    ('timelesz FAM 千葉公演レポ', None, None, None),
]

# 旧記事内に手書きされていた、実在しない短縮URL（旧サイトでもリンク切れ）→ 新slug
# None は該当記事がない（ライブレポート等）ため、リンクを外して文字だけ残す
ALIASES = {
    'yokohama-arena': 'yokohama-arena',
    'marinemesse-fukuoka': 'marine-messe-fukuoka',
    'marine-messe-fukuoka-hotel': 'marine-messe-fukuoka',
    'ariake-arena': 'ariake-arena',
    'itabag-storage': 'itabag-guide',
    'pain-bag-storage': 'itabag-guide',
    'itabag-layout-tips': 'itabag-guide',
    'oshikatsu-budget-saving': 'oshikatsu-saving-tips',
    'saving': 'oshikatsu-saving-tips',
    'start-beginner-mens': 'oshikatsu-for-men',
    'men-pushikatsu-tips': 'oshikatsu-for-men',
    'oshikatsu-for-men': 'oshikatsu-for-men',
    'oshibare-mens': 'oshibare-episodes',
    'oshibare-mens-guide': 'oshibare-episodes',
    '猪俣周杜の魅力を徹底解剖': 'inomata-shuto',
    'live-prepare-guide': 'live-ensei-checklist',
    'acees-member-profile': 'acees-profile',
}


def alias_target(href):
    seg = urllib.parse.unquote(urllib.parse.urlparse(href).path).rstrip('/').split('/')[-1]
    for key, slug in ALIASES.items():
        if seg == key or (not key.isascii() and seg.startswith(key)):
            return f'/guide/{slug}/'
    return None


# 旧記事で他の会場ガイドが使っている、じゃらんのバリューコマース紹介リンク（運営者のID）
JALAN_VC_URL = 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3750604&pid=892542269'

ASP_HOSTS = ('valuecommerce.com', 'a8.net', 'amazon.co.jp', 'amzn.to', 'rakuten.co.jp',
             'moshimo.com', 'afi-b.com', 'accesstrade.net', 'dmm.co.jp')

_ctx = ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt') \
    if os.path.exists('/root/.ccr/ca-bundle.crt') else ssl.create_default_context()


def fetch(url, binary=False):
    url = urllib.parse.quote(url, safe=':/?=&%#@')
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(req, context=_ctx, timeout=60).read()
            return data if binary else data.decode('utf-8', 'replace')
        except urllib.error.HTTPError:
            raise
        except (TimeoutError, urllib.error.URLError, ConnectionError):
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


def lookup(title):
    for key, slug, cat, venue in SLUGS:
        if key in title:
            return slug, cat, venue
    raise SystemExit(f'SLUGS に対応がありません: {title}')


def norm_old_url(u):
    """旧サイトの記事URLを比較用に正規化（デコード・末尾スラッシュ）"""
    p = urllib.parse.urlparse(urllib.parse.unquote(u))
    return p.netloc.replace('www.', '') + p.path.rstrip('/') + '/'


MISSING_IMAGES = []


def local_image(url, args):
    """wp-content/uploads の画像をダウンロードし、WebP（最大幅1200px）に変換してサイト内パスを返す。
    旧サイトでも404の画像は None を返し（呼び出し側で削除）、MISSING_IMAGES に記録する"""
    url = urllib.parse.urljoin('https://' + OLD_HOST + '/', url)
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    keep = ext == '.gif'  # アニメーションの可能性があるGIFは変換しない
    name = hashlib.sha1(urllib.parse.unquote(url).encode()).hexdigest()[:16] + (ext if keep else '.webp')
    path = os.path.join(IMG_DIR, name)
    if not args.no_images and not os.path.exists(path):
        os.makedirs(IMG_DIR, exist_ok=True)
        try:
            data = fetch(url, binary=True)
        except urllib.error.HTTPError:
            MISSING_IMAGES.append(urllib.parse.unquote(url))
            return None, urllib.parse.unquote(url)
        if keep:
            open(path, 'wb').write(data)
        else:
            from io import BytesIO
            from PIL import Image
            im = Image.open(BytesIO(data))
            im = im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB')
            if im.width > 1200:
                im = im.resize((1200, round(im.height * 1200 / im.width)), Image.LANCZOS)
            im.save(path, 'WEBP', quality=80, method=6)
        time.sleep(0.3)
    return '/assets/img/guide/' + name, urllib.parse.unquote(url)


def is_asp(href):
    host = urllib.parse.urlparse(href if '//' in href else 'https:' + href).netloc
    return any(host.endswith(h) for h in ASP_HOSTS)


def convert(html, url_map, image_log, args):
    soup = BeautifulSoup(html, 'html.parser')
    pc = [d for d in soup.find_all('div', class_='post_content') if d.get('class') == ['post_content']][0]

    # 不要要素: コメント・タイトル重複のh1・SWELLの目次・スクリプト・noscript
    for c in pc.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in pc.find_all(['h1', 'script', 'noscript']):
        t.decompose()
    for t in pc.select('.p-toc'):
        t.decompose()
    # 執筆時のメモ（「※ここに〇〇の画像」等）が公開されていたため削除
    for t in pc.find_all(string=re.compile(r'^\s*※ここに')):
        block = t.find_parent(['div', 'p', 'figure']) or t.parent
        block.decompose()
    for p in pc.find_all('p'):
        if not p.get_text(strip=True) and not p.find(['img', 'iframe', 'a']):
            p.decompose()

    # 画像: 遅延読み込み属性を戻し、旧サイトの画像はローカルへ
    for img in pc.find_all('img'):
        src = img.get('data-src') or img.get('src') or ''
        if '【' in src:  # 未設定のまま公開されていた画像（例: 【3章画像URL】）
            img.decompose()
            continue
        for a in ['data-src', 'data-srcset', 'srcset', 'sizes', 'data-aspectratio']:
            img.attrs.pop(a, None)
        cls = [c for c in (img.get('class') or []) if c != 'lazyload']
        if cls:
            img['class'] = cls
        else:
            img.attrs.pop('class', None)
        if OLD_HOST in src and '/wp-content/uploads/' in src:
            new, orig = local_image(src, args)
            if new is None:  # 旧サイトでも表示されていない画像は削除
                parent = img.parent
                img.decompose()
                if parent.name in ('figure', 'p') and not parent.get_text(strip=True) and not parent.find(['img', 'iframe']):
                    parent.decompose()
                continue
            image_log[new] = orig
            src = new
        img['src'] = src
        if 'width' in img.attrs and img['width'] in ('1', '0'):
            continue  # ASPの計測用ピクセルはそのまま
        img['loading'] = 'lazy'

    for f in pc.find_all('iframe'):
        if f.get('data-src'):
            f['src'] = f['data-src']
            del f['data-src']
        f.attrs.pop('class', None)
        f['loading'] = 'lazy'

    # リンク
    has_asp = False
    for a in pc.find_all('a'):
        href = (a.get('href') or '').strip()
        if 'XXXXXX' in href or '【' in href:
            if 'じゃらん' in href:  # 【あなたのじゃらんVCリンク】→ 他の会場ガイドと同じじゃらんリンク
                a['href'] = JALAN_VC_URL
                href = JALAN_VC_URL
            else:
                a.unwrap()  # 未設定のまま公開されていたリンク
                continue
        if OLD_HOST in urllib.parse.urlparse(href).netloc.replace('www.', '') and \
                not urllib.parse.urlparse(href).netloc.startswith('collection.'):
            key = norm_old_url(href)
            if key in url_map:
                if url_map[key]:
                    a['href'] = url_map[key]
                    a.attrs.pop('target', None)
                    a.attrs.pop('rel', None)
                else:
                    a.unwrap()  # 移さない記事へのリンクは文字だけ残す
                continue
            if '/wp-content/uploads/' in href:
                new, orig = local_image(href, args)
                if new is None:
                    a.unwrap()
                else:
                    image_log[new] = orig
                    a['href'] = new
                continue
            target = alias_target(href)
            if target:
                a['href'] = target
                a.attrs.pop('target', None)
                a.attrs.pop('rel', None)
            else:
                a.unwrap()  # 旧サイトでも存在しないページ・管理画面などへのリンク
            continue
        if is_asp(href):
            has_asp = True
            a['rel'] = 'sponsored noopener'
            a['target'] = '_blank'
        elif href.startswith('http'):
            a['rel'] = 'noopener'
            a['target'] = '_blank'

    embeds = []
    if pc.select('blockquote.twitter-tweet'):
        embeds.append('twitter')
    if pc.select('blockquote.instagram-media'):
        embeds.append('instagram')
    if pc.select('blockquote.tiktok-embed'):
        embeds.append('tiktok')

    body = pc.decode_contents().strip()
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body, has_asp, embeds


def meta(soup, **attrs):
    m = soup.find('meta', attrs=attrs)
    return m['content'].strip() if m and m.get('content') else ''


def yaml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-images', action='store_true')
    args = ap.parse_args()

    urls = [u for u in re.findall(r'<loc>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</loc>', fetch(SITEMAP))]
    pages = []
    for u in urls:
        html = fetch(u)
        soup = BeautifulSoup(html, 'html.parser')
        title = re.sub(r'\s*-\s*推し活ガイドブック\s*$', '', soup.title.get_text(strip=True))
        slug, cat, venue = lookup(title)
        pages.append(dict(url=u, html=html, soup=soup, title=title, slug=slug, cat=cat, venue=venue))
        time.sleep(0.5)

    url_map = {norm_old_url(p['url']): (f"/guide/{p['slug']}/" if p['slug'] else None) for p in pages}

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(REDIRECT_CSV), exist_ok=True)
    image_log = {}
    rows = []
    for p in pages:
        if not p['slug']:
            rows.append([urllib.parse.unquote(p['url']), '/guide/', p['title'], '移さない（ライブレポート）'])
            continue
        soup = p['soup']
        body, has_asp, embeds = convert(p['html'], url_map, image_log, args)
        ld = ' '.join(s.get_text() for s in soup.find_all('script', type='application/ld+json'))
        published = (re.search(r'"datePublished":"([^"]+)"', ld) or [None, ''])[1]
        modified = (re.search(r'"dateModified":"([^"]+)"', ld) or [None, ''])[1]
        thumb = soup.select_one('.p-articleThumb img')
        thumb_src = (thumb.get('data-src') or thumb.get('src')) if thumb else ''
        if thumb_src and OLD_HOST in thumb_src:
            thumb_src, orig = local_image(thumb_src, args)
            if thumb_src:
                image_log[thumb_src] = orig

        fm = ['---',
              f'title: {yaml_str(p["title"])}',
              f'description: {yaml_str(meta(soup, name="description") or meta(soup, property="og:description"))}',
              f'date: {published[:10]}',
              f'last_modified_at: {modified[:10] or published[:10]}',
              f'guide_category: {p["cat"]}',
              f'original_url: {yaml_str(urllib.parse.unquote(p["url"]))}']
        if thumb_src:
            fm.append(f'thumbnail: {thumb_src}')
        if p['venue']:
            fm.append(f'venue_name: {yaml_str(p["venue"])}')
        if has_asp:
            fm.append('pr: true')
        if embeds:
            fm.append('embeds: [' + ', '.join(embeds) + ']')
        fm.append('---')
        out = '\n'.join(fm) + '\n{% raw %}\n' + body + '\n{% endraw %}\n'
        with open(os.path.join(OUT_DIR, p['slug'] + '.html'), 'w', encoding='utf-8') as f:
            f.write(out)
        rows.append([urllib.parse.unquote(p['url']), f'/guide/{p["slug"]}/', p['title'], ''])

    with open(REDIRECT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['旧URL', '新URL（gourmet.oshikatsu-guide.com）', 'タイトル', '備考'])
        w.writerows(rows)
    with open(os.path.join(OUT_DIR, '..', 'redirects', 'guidebook_images.json'), 'w', encoding='utf-8') as f:
        json.dump(image_log, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f'記事 {len(pages)}件 → 移行 {sum(1 for p in pages if p["slug"])}件 / 画像 {len(image_log)}件')
    for u in MISSING_IMAGES:
        print('  旧サイトでも見つからない画像（元URLのまま）:', u)


if __name__ == '__main__':
    main()
