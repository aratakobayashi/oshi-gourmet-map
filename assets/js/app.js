/* 推しグルメ巡礼MAP 共通スクリプト（保存・動画・地図・共有）。全ページで defer 読み込み */
(function () {
  'use strict';
  var BASE = window.BASE || '';

  // ---------- 保存（localStorage 'fav_shops' に店舗IDの配列） ----------
  function favs() {
    try { return JSON.parse(localStorage.getItem('fav_shops') || '[]'); } catch (e) { return []; }
  }
  function setFavs(list) {
    try { localStorage.setItem('fav_shops', JSON.stringify(list)); } catch (e) {}
  }
  function paintFav(btn, on) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    var t = btn.querySelector('[data-fav-text]') || btn.querySelector('span');
    if (t) t.textContent = on ? (btn.dataset.onText || '保存済') : (btn.dataset.offText || '保存');
  }
  window.paintFavs = function (root) {
    var saved = favs();
    (root || document).querySelectorAll('[data-fav]').forEach(function (b) {
      paintFav(b, saved.indexOf(b.dataset.fav) > -1);
    });
  };
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-fav]');
    if (!b) return;
    e.preventDefault();
    var id = b.dataset.fav, saved = favs(), i = saved.indexOf(id);
    if (i > -1) saved.splice(i, 1); else saved.push(id);
    setFavs(saved);
    document.querySelectorAll('[data-fav="' + id + '"]').forEach(function (x) { paintFav(x, i < 0); });
  });

  // ---------- 店舗の行（_includes/row.html と同じ形。data/explore.json の1件から作る） ----------
  var I = { id: 0, n: 1, u: 2, g: 3, gr: 4, p: 5, c: 6, st: 7, w: 8, la: 9, ln: 10, v: 11, t: 12, r: 13, m: 14, src: 15, d: 16, x: 17 };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var GIX = function () { return window.GIX || {}; }, GEN = function () { return window.GENRES || {}; };
  function genreLabel(g) { return GEN()[g] ? GEN()[g].label : g; }
  function thumb(r) {
    var gi = GIX()[r[I.gr][0]] || {};
    if (r[I.v]) return '<div class="thumb"><img src="https://i.ytimg.com/vi_webp/' + r[I.v] + '/mqdefault.webp" alt="" width="320" height="180" loading="lazy" decoding="async"></div>';
    if (r[I.t]) return '<div class="thumb"><img src="' + esc(r[I.t]) + '" alt="" width="300" height="200" loading="lazy" decoding="async"></div>';
    return '<div class="thumb thumb--noimg" style="--g:' + (gi.c || '#9a8f80') + '"><span class="stamp stamp--tilt" aria-hidden="true">' + (GEN()[r[I.g]] ? GEN()[r[I.g]].mark : '食') + '</span></div>';
  }
  function meta(r) {
    var gi = GIX()[r[I.gr][0]] || {};
    return '<p class="card__meta"><span class="dot"></span>' + esc(gi.l || r[I.gr][0]) + '・' + esc(genreLabel(r[I.g])) + '</p>';
  }
  function row(r) {
    var gi = GIX()[r[I.gr][0]] || {};
    var mem = r[I.m].slice(0, 2).join('・');
    return '<div class="row" style="--g:' + (gi.c || '#9a8f80') + '">' + thumb(r) +
      '<div class="row__body">' + meta(r) +
      '<a class="row__name" href="' + BASE + '/shops/' + r[I.u] + '/">' + esc(r[I.n]) + '</a>' +
      '<p class="card__st">' + esc(r[I.st] || r[I.p]) + (mem ? '・' + esc(mem) : '') + '</p>' +
      '<p class="row__tags">' + (r[I.x] ? '<span class="badge badge--closed">閉店</span>' : '') + (r[I.r] ? '<span class="badge--ok badge">予約可</span>' : '') + (r[I.src] ? '<span class="row__src">' + esc(r[I.src]) + '</span>' : '') + '</p>' +
      '</div><button type="button" class="fav-btn" data-fav="' + esc(r[I.id]) + '" aria-pressed="false" aria-label="' + esc(r[I.n]) + 'を保存"><span>保存</span></button></div>';
  }
  // 並び替え（閉店は最後）。how: new / video / book / name
  function sortRows(rows, how) {
    var cmpNew = function (a, b) { return (b[I.d] > a[I.d]) - (b[I.d] < a[I.d]) || (!!b[I.v]) - (!!a[I.v]); };
    var f = {
      new: cmpNew,
      video: function (a, b) { return (!!b[I.v]) - (!!a[I.v]) || cmpNew(a, b); },
      book: function (a, b) { return b[I.r] - a[I.r] || cmpNew(a, b); },
      name: function (a, b) { return a[I.n].localeCompare(b[I.n], 'ja'); }
    }[how] || cmpNew;
    return rows.sort(function (a, b) { return a[I.x] - b[I.x] || f(a, b); });
  }
  var dataReady = null;
  function loadData() {
    if (!dataReady) dataReady = fetch(BASE + '/data/explore.json').then(function (r) { return r.json(); });
    return dataReady;
  }
  window.shopUI = { I: I, esc: esc, thumb: thumb, meta: meta, row: row, favs: favs, sort: sortRows, load: loadData };

  // ---------- YouTube（タップしたときに埋め込みを読み込む） ----------
  document.addEventListener('click', function (e) {
    var b = e.target.closest('button.yt[data-yt]');
    if (!b || b.querySelector('iframe')) return;
    var f = document.createElement('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + b.dataset.yt + '?autoplay=1&rel=0';
    f.title = b.getAttribute('aria-label') || 'YouTube';
    f.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
    f.allowFullscreen = true;
    b.appendChild(f);
    b.removeAttribute('aria-label');
  });

  // ---------- 地図（ボタンを押したとき / PCは画面に近づいたときに読み込む） ----------
  var leafletReady = null;
  window.loadLeaflet = function () {
    if (window.L) return Promise.resolve();
    if (leafletReady) return leafletReady;
    var dir = BASE + '/assets/vendor/leaflet/';
    leafletReady = new Promise(function (ok) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = dir + 'leaflet.css';
      document.head.appendChild(css);
      var js = document.createElement('script');
      js.src = dir + 'leaflet.js'; js.onload = ok;
      document.body.appendChild(js);
    });
    return leafletReady;
  };
  function showMap(box) {
    if (box.dataset.loaded) return;
    box.dataset.loaded = '1';
    window.loadLeaflet().then(function () {
      var lat = +box.dataset.lat, lng = +box.dataset.lng;
      var el = document.createElement('div');
      box.innerHTML = '';
      box.appendChild(el);
      var map = L.map(el, { scrollWheelZoom: false }).setView([lat, lng], 16);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors', maxZoom: 19
      }).addTo(map);
      L.marker([lat, lng]).addTo(map).bindPopup(box.dataset.name || '');
    });
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-map-load]');
    if (b) showMap(b.closest('[data-map]'));
  });
  var boxes = document.querySelectorAll('[data-map]');
  if (boxes.length && 'IntersectionObserver' in window && matchMedia('(min-width: 1024px)').matches) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (x) { if (x.isIntersecting) { io.unobserve(x.target); showMap(x.target); } });
    }, { rootMargin: '200px' });
    boxes.forEach(function (b) { io.observe(b); });
  }

  // ---------- 共有 ----------
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-share]');
    if (!b) return;
    var data = { title: document.title, url: location.href };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(function () {
      var t = b.textContent; b.textContent = 'URLをコピーしました';
      setTimeout(function () { b.textContent = t; }, 1600);
    });
  });

  // ---------- 目次（記事本文の h2 / h3 から作る。スマホは本文上の開閉式、PCは左の列） ----------
  var heads = [].filter.call(document.querySelectorAll('.prose h2, .prose h3'), function (h) { return !h.closest('.ecard, .faq'); });
  var toc = document.querySelector('[data-toc]'), side = document.querySelector('[data-toc-list]');
  heads.forEach(function (h, i) { if (!h.id) h.id = 'h-' + i; });
  function fill(ol, withH3) {
    heads.forEach(function (h) {
      if (h.tagName === 'H3' && !withH3) return;
      var li = document.createElement('li'), a = document.createElement('a');
      if (h.tagName === 'H3') li.className = 'h3';
      a.href = '#' + h.id; a.textContent = h.textContent.trim();
      li.appendChild(a); ol.appendChild(li);
    });
  }
  if (toc) { fill(toc.querySelector('ol'), true); if (!heads.length) toc.hidden = true; }
  if (side) {
    fill(side, false);
    if (!side.children.length) side.parentNode.hidden = true;
    else if ('IntersectionObserver' in window) {
      var links = {};
      side.querySelectorAll('a').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
      var io2 = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (!e.isIntersecting || !links[e.target.id]) return;
          side.querySelectorAll('a[aria-current]').forEach(function (x) { x.removeAttribute('aria-current'); });
          links[e.target.id].setAttribute('aria-current', 'true');
        });
      }, { rootMargin: '0px 0px -70% 0px' });
      heads.forEach(function (h) { if (h.tagName === 'H2') io2.observe(h); });
    }
  }

  window.paintFavs();
})();
