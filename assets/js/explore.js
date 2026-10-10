/* お店を探す（/shops/）: 絞り込み・並び替え・地図。データは data/explore.json を表示後に読み込む */
(function () {
  'use strict';
  var BASE = window.BASE || '';
  var GIX = window.GIX || {}, GENRES = window.GENRES || {}, GMETA = window.GMETA || [], LISTS = window.LISTS || [];
  var PAGE = 20;
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var isPC = matchMedia('(min-width: 1024px)');

  var I = window.shopUI.I;
  var BYID = {}, DATA = null, loading = null, shown = PAGE, current = [];

  function emptyState() { return { groups: [], members: [], prefs: [], stations: [], genres: [], q: '', sort: 'new', view: 'list', near: null, nl: '' }; }
  var state = emptyState(), draft = null;

  // ---------- URL ⇄ 状態 ----------
  function readURL() {
    var p = new URLSearchParams(location.search), list = function (k) { return (p.get(k) || '').split(',').filter(Boolean); };
    state.groups = list('g').concat(list('group'));
    state.members = list('m');
    state.prefs = list('pref');
    state.stations = list('st');
    state.genres = list('genre');
    state.q = p.get('q') || '';
    state.sort = p.get('sort') || 'new';
    state.view = p.get('view') === 'map' ? 'map' : 'list';
    // ?near=緯度,経度&nl=会場名 … 会場ガイドなどから「この場所の近く順」で開く
    var nr = (p.get('near') || '').split(',').map(Number);
    state.near = nr.length === 2 && !isNaN(nr[0]) && !isNaN(nr[1]) ? nr : null;
    state.nl = state.near ? (p.get('nl') || '') : '';
  }
  function writeURL() {
    var p = new URLSearchParams();
    if (state.groups.length) p.set('g', state.groups.join(','));
    if (state.members.length) p.set('m', state.members.join(','));
    if (state.prefs.length) p.set('pref', state.prefs.join(','));
    if (state.stations.length) p.set('st', state.stations.join(','));
    if (state.genres.length) p.set('genre', state.genres.join(','));
    if (state.q) p.set('q', state.q);
    if (state.sort !== 'new') p.set('sort', state.sort);
    if (state.view === 'map') p.set('view', 'map');
    if (state.near) { p.set('near', state.near.join(',')); if (state.nl) p.set('nl', state.nl); }
    if (openShop) p.set('shop', openShop);
    var s = p.toString();
    history.replaceState(history.state, '', location.pathname + (s ? '?' + s.replace(/%2C/g, ',') : ''));
  }
  function hasFilter(s) { return s.groups.length || s.prefs.length || s.stations.length || s.genres.length || s.q; }
  function dist(r) {  // near からの距離（km）。座標のない店は後ろへ
    if (!state.near || !r[I.la]) return 1e9;
    var dy = (r[I.la] - state.near[0]) * 111, dx = (r[I.ln] - state.near[1]) * 111 * Math.cos(state.near[0] * Math.PI / 180);
    return Math.sqrt(dx * dx + dy * dy);
  }

  // ---------- データ ----------
  function load() {
    if (loading) return loading;
    loading = fetch(BASE + '/data/explore.json').then(function (r) { return r.json(); }).then(function (rows) {
      DATA = rows;
      rows.forEach(function (r) {
        BYID[r[I.id]] = r;
        var labels = r[I.gr].map(function (g) { return GIX[g] ? GIX[g].l : g; }).join(' ');
        r.hay = [r[I.n], r[I.m].join(' '), r[I.st], r[I.c], r[I.p], labels, r[I.src]].join(' ').toLowerCase();
      });
    });
    return loading;
  }

  // ---------- 絞り込み ----------
  function match(r, s) {
    if (s.groups.length) {
      var ok = s.groups.some(function (g) {
        if (r[I.gr].indexOf(g) < 0) return false;
        var mem = s.members.filter(function (m) { return m.indexOf(g + ':') === 0; });
        if (!mem.length) return true;
        return mem.some(function (m) { return r[I.m].indexOf(m.slice(g.length + 1)) > -1; });
      });
      if (!ok) return false;
    }
    if (s.prefs.length || s.stations.length) {
      if (s.prefs.indexOf(r[I.p]) < 0 && s.stations.indexOf(r[I.st]) < 0) return false;
    }
    if (s.genres.length && s.genres.indexOf(r[I.g]) < 0) return false;
    if (s.q) {
      var words = s.q.toLowerCase().split(/[\s　]+/).filter(Boolean);
      for (var i = 0; i < words.length; i++) if (r.hay.indexOf(words[i]) < 0) return false;
    }
    return true;
  }
  function filtered(s) { return DATA.filter(function (r) { return match(r, s); }); }
  function sortRows(rows, how) {
    var cmpNew = function (a, b) { return (b[I.d] > a[I.d]) - (b[I.d] < a[I.d]) || (!!b[I.v]) - (!!a[I.v]); };
    var f = {
      new: cmpNew,
      video: function (a, b) { return (!!b[I.v]) - (!!a[I.v]) || cmpNew(a, b); },
      book: function (a, b) { return b[I.r] - a[I.r] || cmpNew(a, b); },
      name: function (a, b) { return a[I.n].localeCompare(b[I.n], 'ja'); }
    }[how] || cmpNew;
    if (state.near) return rows.sort(function (a, b) { return a[I.x] - b[I.x] || dist(a) - dist(b); });
    return rows.sort(function (a, b) { return a[I.x] - b[I.x] || f(a, b); });
  }

  // ---------- 表示（assets/js/app.js の shopUI） ----------
  var thumb = function (r) { return window.shopUI.thumb(r); };
  var meta = function (r) { return window.shopUI.meta(r); };
  var rowHTML = function (r) { return window.shopUI.row(r); };
  var genreLabel = function (g) { return GENRES[g] ? GENRES[g].label : g; };

  function render() {
    current = sortRows(filtered(state), state.sort);
    $('sort').hidden = !!state.near;
    shown = PAGE;
    $('count').textContent = current.length.toLocaleString();
    drawRows();
    drawChips();
    drawSummary();
    if (mapOn()) drawMap();
    writeURL();
  }
  function drawRows() {
    var list = current.slice(0, shown);
    $('rows').innerHTML = list.length ? list.map(rowHTML).join('') :
      '<p class="empty">条件に合うお店がありません。条件を減らしてみてください。</p>';
    var more = $('more');
    more.hidden = current.length <= shown;
    more.textContent = 'さらに' + Math.min(PAGE, current.length - shown) + '軒を表示（' + shown + ' / ' + current.length + '）';
    if (window.paintFavs) window.paintFavs($('rows'));
    if (typeof markRow === 'function') markRow();
  }
  function drawChips() {
    var box = $('selchips'), h = [];
    state.groups.forEach(function (g) {
      var gi = GIX[g] || {};
      h.push('<button type="button" class="selchip" style="--g:' + gi.c + '" data-rm="groups" data-v="' + esc(g) + '"><span class="dot"></span>' + esc(gi.l || g) + ' ×</button>');
    });
    state.members.forEach(function (m) { h.push('<button type="button" class="selchip" data-rm="members" data-v="' + esc(m) + '">' + esc(m.split(':')[1]) + ' ×</button>'); });
    state.prefs.forEach(function (p) { h.push('<button type="button" class="selchip" data-rm="prefs" data-v="' + esc(p) + '">' + esc(p) + ' ×</button>'); });
    state.stations.forEach(function (p) { h.push('<button type="button" class="selchip" data-rm="stations" data-v="' + esc(p) + '">' + esc(p) + ' ×</button>'); });
    state.genres.forEach(function (g) { h.push('<button type="button" class="selchip" data-rm="genres" data-v="' + esc(g) + '">' + esc(genreLabel(g)) + ' ×</button>'); });
    if (state.near) h.push('<button type="button" class="selchip" data-rm-near>' + esc((state.nl || 'この場所') + 'の近く順') + ' ×</button>');
    if (h.length) h.push('<button type="button" class="linkbtn" data-clear>クリア</button>');
    box.innerHTML = h.join('');
    box.hidden = !h.length;
    var n = function (k) { return state[k].length; };
    setBtn('btn-oshi', '推し', n('groups'));
    setBtn('btn-area', 'エリア・駅', n('prefs') + n('stations'));
    setBtn('btn-genre', 'ジャンル', n('genres'));
  }
  function setBtn(id, label, n) {
    var b = $(id);
    b.textContent = label + (n ? '・' + n : '');
    b.setAttribute('aria-pressed', n ? 'true' : 'false');
  }
  function drawSummary() {
    var box = $('summary');
    if (state.groups.length !== 1) { box.hidden = true; return; }
    var g = state.groups[0], gi = GIX[g] || {}, counts = {};
    DATA.forEach(function (r) { if (r[I.gr].indexOf(g) > -1) counts[r[I.g]] = (counts[r[I.g]] || 0) + 1; });
    var items = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).map(function (k) {
      var slug = g.replace(/_/g, '-') + '-' + k;
      var label = esc(genreLabel(k)) + ' ' + counts[k];
      return LISTS.indexOf(slug) > -1 ? '<a href="' + BASE + '/list/' + slug + '/">' + label + '</a>' : '<span>' + label + '</span>';
    });
    box.innerHTML = '<p class="meta">' + esc(gi.l) + ' × ジャンルのまとめ</p><p class="summary__items">' + items.join('<span aria-hidden="true">・</span>') + '</p>' +
      '<p class="meta" style="margin-top:8px"><a href="' + BASE + (gi.u || '/groups/') + '">' + esc(gi.l) + 'のページを見る →</a></p>';
    box.hidden = false;
  }

  // ---------- 絞り込みシート ----------
  var tab = 'oshi', kana = '人気', gsearch = '', openG = {};
  var KANA = ['人気', 'あ', 'か', 'さ', 'た', 'な', 'は', 'ま', 'や', 'ら', 'わ'];
  var ROWS = { 'あ': 'あいうえおぁぃぅぇぉゔ', 'か': 'かきくけこがぎぐげご', 'さ': 'さしすせそざじずぜぞ', 'た': 'たちつてとだぢづでどっ', 'な': 'なにぬねの', 'は': 'はひふへほばびぶべぼぱぴぷぺぽ', 'ま': 'まみむめも', 'や': 'やゆよゃゅょ', 'ら': 'らりるれろ', 'わ': 'わをん' };
  function clone(s) { return JSON.parse(JSON.stringify(s)); }
  function toggle(arr, v) { var i = arr.indexOf(v); if (i > -1) arr.splice(i, 1); else arr.push(v); }

  var opener = null;
  function openSheet(t) {
    opener = document.activeElement;
    load().then(function () {
      draft = clone(state);
      tab = t || 'oshi';
      $('sheet').hidden = false; $('sheet-bg').hidden = false;
      document.body.style.overflow = 'hidden';
      drawSheet();
      $('sheet-close').focus();
    });
  }
  function closeSheet() {
    $('sheet').hidden = true; $('sheet-bg').hidden = true;
    document.body.style.overflow = '';
    if (opener && opener.focus) opener.focus();
  }
  function drawSheet() {
    document.querySelectorAll('#sheet [data-tab]').forEach(function (b) { b.setAttribute('aria-selected', b.dataset.tab === tab ? 'true' : 'false'); });
    var body = $('sheet-body');
    if (tab === 'oshi') body.innerHTML = oshiPane();
    else if (tab === 'area') body.innerHTML = areaPane();
    else body.innerHTML = genrePane();
    if (tab === 'oshi') {
      var inp = $('gsearch');
      inp.value = gsearch;
      inp.addEventListener('input', function () { gsearch = inp.value; var l = $('glist'); l.innerHTML = groupItems(); });
    }
    $('sheet-apply').textContent = filtered(draft).length.toLocaleString() + '軒を見る';
  }
  function refreshSheet() {
    if (tab === 'oshi') $('glist').innerHTML = groupItems();
    else drawSheet();
    $('sheet-apply').textContent = filtered(draft).length.toLocaleString() + '軒を見る';
  }
  function oshiPane() {
    return '<label class="searchbox searchbox--sm" style="width:100%"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><input type="search" id="gsearch" placeholder="グループ・メンバー名" aria-label="グループ・メンバー名で探す"></label>' +
      '<div class="kana" role="group" aria-label="五十音">' + KANA.map(function (k) { return '<button type="button" data-kana="' + k + '" aria-pressed="' + (k === kana) + '"' + (k === '人気' ? ' style="width:auto;padding:0 10px;border-radius:19px"' : '') + '>' + k + '</button>'; }).join('') + '</div>' +
      '<ul class="glist" id="glist">' + groupItems() + '</ul>';
  }
  function groupItems() {
    var q = gsearch.trim().toLowerCase();
    var list = GMETA.filter(function (g) {
      if (q) return (g.label + ' ' + g.kana + ' ' + g.members.map(function (m) { return m.name; }).join(' ')).toLowerCase().indexOf(q) > -1;
      if (kana === '人気') return true;
      return (ROWS[kana] || '').indexOf((g.kana || '').charAt(0)) > -1;
    });
    if (!list.length) return '<li class="empty">見つかりませんでした</li>';
    return list.map(function (g) {
      var on = draft.groups.indexOf(g.id) > -1, open = openG[g.id] || (on && draft.members.some(function (m) { return m.indexOf(g.id + ':') === 0; }));
      var mem = '';
      if (open && g.members.length) {
        var anyMem = draft.members.some(function (m) { return m.indexOf(g.id + ':') === 0; });
        mem = '<div class="members"><button type="button" class="chip' + (on && !anyMem ? ' chip--on' : '') + '" data-allmem="' + g.id + '">すべて</button>' +
          g.members.map(function (m) { var k = g.id + ':' + m.name; return '<button type="button" class="chip' + (draft.members.indexOf(k) > -1 ? ' chip--on' : '') + '" data-mem="' + esc(k) + '">' + esc(m.name) + '</button>'; }).join('') + '</div>';
      }
      return '<li><div class="grow"><input type="checkbox" id="g-' + g.id + '" data-g="' + g.id + '"' + (on ? ' checked' : '') + '>' +
        '<label for="g-' + g.id + '" style="--g:' + g.color + '"><span class="dot"></span><span><b>' + esc(g.label) + '</b><small>' + esc(g.kana) + '</small></span></label>' +
        '<span class="cnt">' + g.count + '軒</span>' +
        (g.members.length ? '<button type="button" class="more" data-open-g="' + g.id + '" aria-expanded="' + !!open + '" aria-label="' + esc(g.label) + 'のメンバーで絞る">' + (open ? '▴' : '▾') + '</button>' : '<span></span>') +
        '</div>' + mem + '</li>';
    }).join('');
  }
  function countBy(idx) {
    var c = {};
    DATA.forEach(function (r) { var v = r[idx]; if (v) c[v] = (c[v] || 0) + 1; });
    return Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).map(function (k) { return [k, c[k]]; });
  }
  function areaPane() {
    var prefs = countBy(I.p), sts = countBy(I.st).slice(0, 40);
    var chip = function (kind, kv) { var on = draft[kind].indexOf(kv[0]) > -1; return '<button type="button" class="chip chip--area' + (on ? ' chip--on' : '') + '" data-' + kind + '="' + esc(kv[0]) + '">' + esc(kv[0]) + ' <span class="cnt">' + kv[1] + '</span></button>'; };
    return '<p class="action__label">駅（お店の多い順）</p><div class="chips" style="margin:8px 0 24px">' + sts.map(function (kv) { return chip('stations', kv); }).join('') + '</div>' +
      '<p class="action__label">都道府県・地域</p><div class="chips" style="margin-top:8px">' + prefs.map(function (kv) { return chip('prefs', kv); }).join('') + '</div>';
  }
  function genrePane() {
    var c = {}; DATA.forEach(function (r) { c[r[I.g]] = (c[r[I.g]] || 0) + 1; });
    return '<div class="genre-grid">' + Object.keys(GENRES).filter(function (g) { return c[g]; }).map(function (g) {
      var on = draft.genres.indexOf(g) > -1;
      return '<button type="button" class="genre-pick" data-genres="' + g + '" aria-pressed="' + on + '"><span class="stamp">' + GENRES[g].mark + '</span>' + esc(GENRES[g].label) + ' <span class="cnt">' + c[g] + '</span></button>';
    }).join('') + '</div>';
  }

  document.addEventListener('click', function (e) {
    var t = e.target, b;
    if ((b = t.closest('[data-open]'))) { openSheet(b.dataset.open); return; }
    if ((b = t.closest('[data-rm]'))) { var a = state[b.dataset.rm]; a.splice(a.indexOf(b.dataset.v), 1); if (b.dataset.rm === 'groups') state.members = state.members.filter(function (m) { return m.indexOf(b.dataset.v + ':') !== 0; }); render(); return; }
    if (t.closest('[data-rm-near]')) { state.near = null; state.nl = ''; render(); return; }
    if (t.closest('[data-clear]')) { var v = state.view, so = state.sort; state = emptyState(); state.view = v; state.sort = so; $('q').value = ''; render(); return; }
    if ((b = t.closest('[data-view]'))) { state.view = b.dataset.view; applyView(); writeURL(); return; }
    if (t.closest('[data-view-fab]')) { state.view = state.view === 'map' ? 'list' : 'map'; applyView(); writeURL(); window.scrollTo(0, 0); return; }
    if (!draft || $('sheet').hidden) return;
    if ((b = t.closest('#sheet [data-tab]'))) { tab = b.dataset.tab; drawSheet(); return; }
    if ((b = t.closest('[data-kana]'))) { kana = b.dataset.kana; gsearch = ''; drawSheet(); return; }
    if ((b = t.closest('[data-open-g]'))) { openG[b.dataset.openG] = !openG[b.dataset.openG]; refreshSheet(); return; }
    if ((b = t.closest('[data-allmem]'))) { var g = b.dataset.allmem; draft.members = draft.members.filter(function (m) { return m.indexOf(g + ':') !== 0; }); if (draft.groups.indexOf(g) < 0) draft.groups.push(g); refreshSheet(); return; }
    if ((b = t.closest('[data-mem]'))) { var k = b.dataset.mem, gg = k.split(':')[0]; toggle(draft.members, k); if (draft.groups.indexOf(gg) < 0) draft.groups.push(gg); refreshSheet(); return; }
    if ((b = t.closest('[data-stations]'))) { toggle(draft.stations, b.dataset.stations); refreshSheet(); return; }
    if ((b = t.closest('[data-prefs]'))) { toggle(draft.prefs, b.dataset.prefs); refreshSheet(); return; }
    if ((b = t.closest('[data-genres]'))) { toggle(draft.genres, b.dataset.genres); refreshSheet(); return; }
  });
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (t.matches && t.matches('[data-g]') && draft) {
      var g = t.dataset.g;
      toggle(draft.groups, g);
      if (!t.checked) draft.members = draft.members.filter(function (m) { return m.indexOf(g + ':') !== 0; });
      $('sheet-apply').textContent = filtered(draft).length.toLocaleString() + '軒を見る';
    }
  });
  $('sheet-close').addEventListener('click', closeSheet);
  $('sheet-bg').addEventListener('click', closeSheet);
  document.addEventListener('keydown', function (e) {
    if ($('sheet').hidden) return;
    if (e.key === 'Escape') { closeSheet(); return; }
    if (e.key !== 'Tab') return;
    // シートが開いている間は、Tab で移る先をシートの中だけにする
    var f = [].filter.call($('sheet').querySelectorAll('button, input, a[href]'), function (x) { return x.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (!$('sheet').contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  $('sheet-reset').addEventListener('click', function () { var q = draft.q, so = draft.sort, v = draft.view; draft = emptyState(); draft.q = q; draft.sort = so; draft.view = v; refreshSheet(); if (tab === 'oshi') drawSheet(); });
  $('sheet-apply').addEventListener('click', function () { state = draft; draft = null; closeSheet(); render(); });

  // ---------- 検索・並び替え・もっと見る ----------
  var timer;
  $('q').addEventListener('input', function () {
    var v = this.value;
    clearTimeout(timer);
    timer = setTimeout(function () { load().then(function () { state.q = v.trim(); render(); }); }, 200);
  });
  $('q').addEventListener('focus', load, { once: true });
  // スマホで「検索」を押したらキーボードを閉じて結果を見せる
  $('q').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); this.blur(); } });
  $('sort').addEventListener('change', function () { var v = this.value; load().then(function () { state.sort = v; render(); }); });
  $('more').addEventListener('click', function () {
    load().then(function () {
      if (!current.length) current = sortRows(filtered(state), state.sort);
      shown += PAGE; drawRows();
    });
  });

  // お店ページから「戻る」で帰ってきたとき、広げた件数と見ていた位置を戻す
  var KEY = 'explore:' + location.pathname;
  function remember() {
    try { sessionStorage.setItem(KEY, JSON.stringify({ q: location.search, shown: shown, y: scrollY })); } catch (e) {}
  }
  function restore() {
    var saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(KEY) || 'null'); sessionStorage.removeItem(KEY); } catch (e) {}
    var nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
    if (!saved || saved.q !== location.search || (nav && nav.type !== 'back_forward')) return;
    if (saved.shown > shown) { shown = saved.shown; drawRows(); }
    requestAnimationFrame(function () { window.scrollTo(0, saved.y); });
  }
  $('rows').addEventListener('click', function (e) { if (e.target.closest('a')) remember(); });
  window.addEventListener('pagehide', remember);

  // ---------- 地図 ----------
  var map, cluster, nearMark;
  function mapOn() { return state.view === 'map' || isPC.matches; }
  function applyView() {
    var split = isPC.matches;
    $('explore').classList.toggle('explore--split', split);
    $('mapview').hidden = !mapOn();
    document.querySelector('.explore__list').hidden = !split && state.view === 'map';
    document.querySelectorAll('[data-view]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.view === state.view ? 'true' : 'false'); });
    $('fab').textContent = state.view === 'map' ? '一覧で見る' : '地図で見る';
    if (mapOn()) load().then(drawMap);
  }
  function loadCluster() {
    return window.loadLeaflet().then(function () {
      if (L.markerClusterGroup) return;
      return new Promise(function (ok) {
        var dir = BASE + '/assets/vendor/leaflet/';
        ['MarkerCluster.css'].forEach(function (f) { var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = dir + f; document.head.appendChild(l); });
        var s = document.createElement('script'); s.src = dir + 'leaflet.markercluster.js'; s.onload = ok; document.body.appendChild(s);
      });
    });
  }
  function drawMap() {
    if (!DATA) return;
    loadCluster().then(function () {
      if (!map) {
        map = L.map('map', { zoomControl: true }).setView([35.68, 139.76], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }).addTo(map);
        map.on('click', function () { $('mapcard').hidden = true; });
      }
      setTimeout(function () { map.invalidateSize(); }, 50);
      if (cluster) map.removeLayer(cluster);
      cluster = L.markerClusterGroup({
        showCoverageOnHover: false, maxClusterRadius: 50,
        iconCreateFunction: function (c) { return L.divIcon({ html: '<div class="cluster">' + c.getChildCount() + '</div>', className: '', iconSize: [44, 44] }); }
      });
      var pts = [];
      current.forEach(function (r) {
        if (!r[I.la]) return;
        var gi = GIX[r[I.gr][0]] || {};
        var m = L.marker([r[I.la], r[I.ln]], { icon: L.divIcon({ html: '<div class="pin" style="--g:' + (gi.c || '#9a8f80') + '"></div>', className: '', iconSize: [30, 30] }), title: r[I.n] });
        m.on('click', function () { showCard(r); });
        cluster.addLayer(m); pts.push([r[I.la], r[I.ln]]);
      });
      map.addLayer(cluster);
      if (state.near) {
        map.setView(state.near, 15);
        if (nearMark) map.removeLayer(nearMark);
        nearMark = L.circleMarker(state.near, { radius: 10, color: '#241F1A', weight: 3, fillColor: '#fff', fillOpacity: 1 }).addTo(map);
        if (state.nl) nearMark.bindTooltip(state.nl, { permanent: true, direction: 'top', offset: [0, -10] });
      } else if (pts.length && hasFilter(state)) map.fitBounds(pts, { padding: [30, 30], maxZoom: 15 });
    });
  }
  function showCard(r) {
    var c = $('mapcard'), gi = GIX[r[I.gr][0]] || {};
    c.href = BASE + '/shops/' + r[I.u] + '/';
    c.removeAttribute('aria-label');
    c.style.setProperty('--g', gi.c || '#9a8f80');
    c.innerHTML = thumb(r) + '<div>' + meta(r) + '<p class="card__name">' + esc(r[I.n]) + '</p><p class="card__st">' + esc(r[I.st] || r[I.p]) + '</p><p class="link-more" style="margin-top:4px">詳しく見る →</p></div>';
    c.hidden = false;
  }
  // 一覧の店にマウスを乗せると、地図上の位置を強調する（まとまっていても見えるよう別のピンを重ねる）
  var hl = null;
  function highlight(id) {
    if (hl) { map.removeLayer(hl); hl = null; }
    var r = BYID[id];
    if (!map || !r || !r[I.la]) return;
    var gi = GIX[r[I.gr][0]] || {};
    hl = L.marker([r[I.la], r[I.ln]], { icon: L.divIcon({ html: '<div class="pin pin--hl" style="--g:' + (gi.c || '#9a8f80') + '"></div>', className: '', iconSize: [40, 40] }), zIndexOffset: 1000, interactive: false }).addTo(map);
  }
  $('rows').addEventListener('mouseover', function (e) {
    var row = e.target.closest('.row'), b = row && row.querySelector('[data-fav]');
    if (b && b.dataset.fav !== $('rows').dataset.hl) { $('rows').dataset.hl = b.dataset.fav; load().then(function () { highlight(b.dataset.fav); }); }
  });
  $('rows').addEventListener('mouseleave', function () { $('rows').dataset.hl = ''; if (hl && map) { map.removeLayer(hl); hl = null; } });

  // ---------- PC: 一覧の店を押すと右側に詳細を開く（店ごとのページ /shops/<slug>/ はそのまま残す） ----------
  var openShop = new URLSearchParams(location.search).get('shop') || '';
  var detailCache = {}, lastRow = null;
  function shopURL(slug) { return BASE + '/shops/' + slug + '/'; }
  function slugOf(a) { var m = a && (a.getAttribute('href') || '').match(/\/shops\/([^/]+)\/$/); return m ? m[1] : ''; }
  function fetchDetail(slug) {
    if (!detailCache[slug]) {
      detailCache[slug] = fetch(shopURL(slug)).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); }).then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        return { shop: doc.querySelector('.shop'), cta: doc.querySelector('.sticky-actions .btn--accent'), title: doc.title };
      });
      detailCache[slug].catch(function () { delete detailCache[slug]; });
    }
    return detailCache[slug];
  }
  function markRow() {
    document.querySelectorAll('#rows .row').forEach(function (r) {
      if (openShop && slugOf(r.querySelector('.row__name')) === openShop) r.setAttribute('aria-current', 'true');
      else r.removeAttribute('aria-current');
    });
  }
  function setShopURL(push) {
    var u = new URL(location.href);
    if (openShop) u.searchParams.set('shop', openShop); else u.searchParams.delete('shop');
    history[push ? 'pushState' : 'replaceState']({ shop: openShop }, '', u.pathname + u.search.replace(/%2C/g, ','));
  }
  function openDetail(slug, push) {
    var box = $('detail');
    openShop = slug;
    box.hidden = false;
    box.setAttribute('aria-busy', 'true');
    $('detail-open').href = shopURL(slug);
    $('detail-body').innerHTML = '<p class="detail__loading">読み込み中…</p>';
    markRow();
    setShopURL(push);
    fetchDetail(slug).then(function (d) {
      if (openShop !== slug) return;
      $('detail-body').innerHTML = '';
      if (d.shop) $('detail-body').appendChild(document.importNode(d.shop, true));
      // 上のバーに、店舗ページ（スマホ）の下部固定バーと同じメインボタンを出す
      var slot = $('detail-cta');
      slot.innerHTML = '';
      if (d.cta) {
        var c = document.importNode(d.cta, true);
        var href = c.getAttribute('href') || '';
        if (href.charAt(0) === '#') {
          var btn = document.createElement('button');
          btn.type = 'button'; btn.className = c.className + ' btn--sm'; btn.textContent = c.textContent;
          btn.addEventListener('click', function () { var t = box.querySelector(href); if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
          slot.appendChild(btn);
        } else { c.classList.add('btn--sm'); slot.appendChild(c); }
      }
      box.removeAttribute('aria-busy');
      box.scrollTop = 0;
      if (window.paintFavs) window.paintFavs(box);
      var h = box.querySelector('h1');
      if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
      // アクセス解析: 詳細を開いたら店舗ページを見たものとして記録する
      if (window.gtag) window.gtag('event', 'page_view', { page_location: location.origin + shopURL(slug), page_title: d.title });
    }).catch(function () { location.href = shopURL(slug); });
  }
  function hideDetail() {
    openShop = '';
    $('detail').hidden = true;
    $('detail-body').innerHTML = '';
    markRow();
    if (lastRow && document.contains(lastRow)) { var a = lastRow.querySelector('.row__name'); if (a) a.focus({ preventScroll: true }); }
    if (map) setTimeout(function () { map.invalidateSize(); }, 50);
  }
  function closeDetail() {
    if (history.state && history.state.shop) history.back();   // 開いたときの履歴を戻す（ブラウザの「戻る」と同じ）
    else { hideDetail(); setShopURL(false); }
  }
  function onShopClick(e, a, row) {
    if (!isPC.matches || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var slug = slugOf(a);
    if (!slug) return;
    e.preventDefault();
    lastRow = row || null;
    if (slug !== openShop) openDetail(slug, true);
  }
  $('rows').addEventListener('click', function (e) {
    if (e.target.closest('[data-fav]')) return;
    var row = e.target.closest('.row');
    if (row) onShopClick(e, row.querySelector('.row__name'), row);
  });
  $('mapcard').addEventListener('click', function (e) { onShopClick(e, $('mapcard'), null); });
  // マウスを乗せたら先に読み込んでおく（押したときすぐ開くように）
  var pre;
  $('rows').addEventListener('mouseover', function (e) {
    if (!isPC.matches) return;
    var row = e.target.closest('.row'), slug = row && slugOf(row.querySelector('.row__name'));
    clearTimeout(pre);
    if (slug) pre = setTimeout(function () { fetchDetail(slug).catch(function () {}); }, 120);
  });
  $('detail-close').addEventListener('click', closeDetail);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && openShop && $('sheet').hidden) closeDetail(); });
  window.addEventListener('popstate', function () {
    var slug = new URLSearchParams(location.search).get('shop');
    if (slug && isPC.matches) { if (slug !== openShop) openDetail(slug, false); }
    else if (openShop) hideDetail();
  });

  isPC.addEventListener && isPC.addEventListener('change', applyView);

  // ---------- 初期化 ----------
  readURL();
  if (openShop) {
    // 共有された「詳細を開いた状態」のURL。スマホでは店舗ページへ移る
    if (isPC.matches) openDetail(openShop, false); else location.replace(shopURL(openShop));
  }
  $('q').value = state.q;
  $('sort').value = state.sort;
  if (location.hash === '#q') $('q').focus();
  var needNow = hasFilter(state) || state.sort !== 'new' || state.view === 'map' || state.near;
  if (needNow) load().then(function () { render(); restore(); });
  applyView();
  if (!needNow) {
    // 最初の20軒はHTMLにある。データは表示が落ち着いてから読む
    var later = function () { (window.requestIdleCallback || setTimeout)(function () { load().then(function () { current = sortRows(filtered(state), state.sort); $('count').textContent = current.length.toLocaleString(); drawRows(); restore(); if (mapOn()) drawMap(); }); }); };
    if (document.readyState === 'complete') later(); else window.addEventListener('load', later);
  }
})();
