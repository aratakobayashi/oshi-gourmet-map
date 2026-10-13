"""
post_course.py
特集記事の front matter の courses から、手描き風の巡礼コース図（assets/img/posts/<slug>/course-<n>.svg）を作る。
  courses:
    - title: "押上から両国へ"            # 図の題
      stops: [店のID, 店のID, ...]        # 回る順
      labels: ["ソラマチ", ...]           # 点の横の短い名前（省略時は店名）
      legs: ["半蔵門線で1駅", ...]        # 点と点のあいだの移動（事実だけ。省略可）
点の位置は店の座標から（向きと距離の比は実際どおり、大きさは図に合わせる）。直線距離を km で添える。
使い方: python scripts/post_course.py <記事のslug> [--color '#7c3aed']
"""
import json
import math
import os
import random
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post_figures import ROOT, FONT, SERIF, INK, INK2, esc, find_post  # noqa: E402

W = 420


def km(a, b):
    dy = (a[0] - b[0]) * 111.0
    dx = (a[1] - b[1]) * 111.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def wobble(p, q, rnd, n=14, amp=3.2):
    """p→q を手で引いたような線（少し揺らす）"""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = p[0] + (q[0] - p[0]) * t
        y = p[1] + (q[1] - p[1]) * t
        if 0 < i < n:
            nx, ny = -(q[1] - p[1]), q[0] - p[0]
            L = math.hypot(nx, ny) or 1
            off = math.sin(t * math.pi) * amp * 2.2 + rnd.uniform(-amp, amp) * .5
            x += nx / L * off
            y += ny / L * off
        pts.append((x, y))
    return 'M' + ' L'.join('%.1f,%.1f' % p for p in pts)


def draw(course, shops, color):
    rnd = random.Random(7)
    stops = [shops[i] for i in course['stops'] if i in shops]
    labels = course.get('labels') or [s['name'] for s in stops]
    legs = course.get('legs') or []
    lat = [s['lat'] for s in stops]
    lng = [s['lng'] for s in stops]
    c = math.cos(math.radians(sum(lat) / len(lat)))
    xs = [(g - min(lng)) * c for g in lng]
    ys = [(max(lat) - a) for a in lat]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-4)
    box_w, box_h = W - 150, 300
    k = min(box_w / max(max(xs) - min(xs), 1e-4), box_h / max(max(ys) - min(ys), 1e-4), box_w / span)
    ox = 70 + (box_w - (max(xs) - min(xs)) * k) / 2
    oy = 96 + (box_h - (max(ys) - min(ys)) * k) / 2
    P = [(ox + x * k, oy + y * k) for x, y in zip(xs, ys)]
    H = 96 + box_h + 56 + 24 * (2 * len(stops) - 1)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" rx="14" fill="#fbf6ea"/>',
         # 方眼のノート
         '<g stroke="#eadfca" stroke-width="1">' + ''.join(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}"/>' for y in range(20, H, 20)) + '</g>',
         f'<text x="22" y="44" font-size="20" font-weight="800" fill="{INK}" font-family="{SERIF}">{esc(course["title"])}</text>',
         f'<text x="22" y="68" font-size="12.5" fill="{INK2}">点の位置は実際の向き・距離の比のとおり（手描き風の図）</text>']
    total = 0.0
    dists = []
    for i in range(len(P) - 1):
        d = km((stops[i]['lat'], stops[i]['lng']), (stops[i + 1]['lat'], stops[i + 1]['lng']))
        dists.append(d)
        total += d
        o.append(f'<path d="{wobble(P[i], P[i + 1], rnd)}" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="2 7" stroke-linecap="round"/>')
    for i, (x, y) in enumerate(P):
        rot = rnd.uniform(-12, 12)
        o.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate({rot:.1f})"><circle r="17" fill="#fffdf6" stroke="{color}" stroke-width="2.5"/><circle r="13" fill="none" stroke="{color}" stroke-width="1"/>'
                 f'<text y="6" text-anchor="middle" font-size="16" font-weight="800" fill="{color}" font-family="{SERIF}">{i + 1}</text></g>')
    # 点の横の名前: 重ならず、図からはみ出さない位置を選ぶ
    boxes = [(x - 18, y - 18, x + 18, y + 18) for x, y in P]
    def tw(s):
        return sum(13.5 if ord(ch) > 255 else 7.5 for ch in s)
    for i, (x, y) in enumerate(P):
        w = tw(labels[i])
        best = None
        for dx, dy, anchor in [(24, -8, 'start'), (24, 22, 'start'), (-24, -8, 'end'), (-24, 22, 'end'), (-w / 2, -26, 'start'), (-w / 2, 40, 'start')]:
            lx = x + dx
            x0 = lx if anchor == 'start' else lx - w
            box = (x0, y + dy - 14, x0 + w, y + dy + 4)
            if box[0] < 8 or box[2] > W - 8 or box[1] < 80:
                continue
            hit = any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in boxes)
            if not hit:
                best = (lx, y + dy, anchor, box)
                break
        if not best:
            lx = min(max(x + 24, 8), W - 8 - w)
            best = (lx, y - 8, 'start', (lx, y - 22, lx + w, y - 4))
        boxes.append(best[3])
        o.append(f'<text x="{best[0]:.1f}" y="{best[1]:.1f}" font-size="13.5" font-weight="700" text-anchor="{best[2]}" fill="{INK}" stroke="#fbf6ea" stroke-width="4" paint-order="stroke">{esc(labels[i])}</text>')
    y = 96 + box_h + 40
    o.append(f'<text x="22" y="{y}" font-size="13" font-weight="800" fill="{INK}">回る順（直線で合わせて約{total:.1f}km）</text>')
    row = 0
    for i, s in enumerate(stops):
        row += 1
        o.append(f'<text x="22" y="{y + 24 * row}" font-size="13" fill="{INK}"><tspan font-weight="800" fill="{color}">{i + 1}</tspan>　{esc(s["name"][:26])}</text>')
        if i < len(dists):
            row += 1
            leg = (legs[i] + '・' if i < len(legs) and legs[i] else '') + f'直線で約{dists[i]:.1f}km'
            o.append(f'<text x="40" y="{y + 24 * row}" font-size="12" fill="{INK2}">↓ {esc(leg)}</text>')
    o.append('</svg>')
    return '\n'.join(o), W, H


def main():
    slug = sys.argv[1]
    color = sys.argv[sys.argv.index('--color') + 1] if '--color' in sys.argv else '#e2553f'
    path = find_post(slug)
    fm = yaml.safe_load(open(path, encoding='utf-8').read().split('---', 2)[1]) or {}
    shops = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8')) if s.get('lat')}
    out = os.path.join(ROOT, 'assets', 'img', 'posts', slug)
    os.makedirs(out, exist_ok=True)
    for n, course in enumerate(fm.get('courses') or [], 1):
        svg, w, h = draw(course, shops, color)
        open(os.path.join(out, f'course-{n}.svg'), 'w', encoding='utf-8').write(svg)
        print(slug, f'course-{n}.svg', w, h)


if __name__ == '__main__':
    main()
