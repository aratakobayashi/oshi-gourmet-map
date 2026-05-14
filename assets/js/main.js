/**
 * main.js
 * お店データの読み込み・フィルター・グリッド表示・モーダル制御
 */

// ===========================
// ボトムナビ スクロール自動非表示（SP）
// ===========================
(function() {
  var nav = document.querySelector('.bottom-nav');
  if (!nav) return;
  var lastY = 0;
  window.addEventListener('scroll', function() {
    var y = window.scrollY;
    if (y > lastY && y > 80) {
      nav.classList.add('bottom-nav--hidden');
    } else {
      nav.classList.remove('bottom-nav--hidden');
    }
    lastY = y;
  }, { passive: true });
})();

const SHOPS_URL = (typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '') + '/data/shops.json';

let allShops = [];
let filteredShops = [];
let selectedGroups = new Set();

// ===========================
// データ読み込み
// ===========================
async function loadShops() {
  const res = await fetch(SHOPS_URL);
  allShops = await res.json();
  filteredShops = [...allShops];

  populateFilters();
  initFromUrlParams();

  // 地図が初期化済みなら更新
  if (typeof renderMapMarkers === 'function') renderMapMarkers(filteredShops);
}

// ===========================
// URLパラメーターで初期フィルターをセット
// ===========================
function initFromUrlParams() {
  const params = new URLSearchParams(window.location.search);
  const group = params.get('group');
  const genre = params.get('genre');

  if (group && GROUP_LABELS[group]) {
    selectedGroups.add(group);
    document.querySelectorAll('.group-chip').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.group === group);
    });
  }
  if (genre) {
    const el = document.getElementById('filter-genre');
    if (el) el.value = genre;
  }

  applyFilters();
  updateFilterSummary();
  updateFilterChips();
}

// ===========================
// フィルター選択肢を生成
// ===========================
function populateFilters() {
  const genres = [...new Set(allShops.map(s => s.genre).filter(Boolean))].sort();
  const prefs  = [...new Set(allShops.map(s => s.prefecture).filter(Boolean))].sort();

  fillSelect('filter-genre', genres);
  fillSelect('filter-prefecture', prefs);
  renderGroupButtons();
}

function fillSelect(id, options) {
  const el = document.getElementById(id);
  if (!el) return;
  options.forEach(val => {
    const opt = document.createElement('option');
    opt.value = val;
    opt.textContent = val;
    el.appendChild(opt);
  });
}

// ===========================
// グループチップ描画（新デザイン）
// ===========================
const GROUP_INITIALS = {
  yonino:'よ', snowman:'S', sixtones:'Si', naniwa:'な', kamenashi:'亀',
  kamaitachi:'か', equal_love:'=', notme:'≠', neajoy:'≒',
  nogizaka46:'乃', hinatazaka46:'日', sakurazaka46:'櫻',
  heysayjump:'H', ginga:'中', kodoku_no_gurume:'孤', timelesz:'T',
};

function renderGroupButtons() {
  const row = document.getElementById('group-filter-row');
  if (!row) return;

  const groups = [...new Set(allShops.flatMap(s => s.groups || []))];
  groups.sort((a, b) => {
    const ca = allShops.filter(s => (s.groups || []).includes(a)).length;
    const cb = allShops.filter(s => (s.groups || []).includes(b)).length;
    return cb - ca;
  });

  row.innerHTML = groups.map(g => {
    const label   = GROUP_LABELS[g] || g;
    const color   = GROUP_SOLID_COLORS[g] || '#b72a65';
    const initial = GROUP_INITIALS[g] || label.charAt(0);
    return `<button class="group-chip" data-group="${escHtml(g)}"
      style="--chip-color:${color}" title="${escHtml(label)}">
      <span class="group-chip__initial">${escHtml(initial)}</span>
      <span class="group-chip__label">${escHtml(label)}</span>
    </button>`;
  }).join('');

  row.querySelectorAll('.group-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const g = btn.dataset.group;
      if (selectedGroups.has(g)) {
        selectedGroups.delete(g);
        btn.classList.remove('active');
      } else {
        selectedGroups.add(g);
        btn.classList.add('active');
      }
      applyFilters();
      updateFilterSummary();
      updateFilterChips();
    });
  });
}

// ===========================
// フィルターサマリー更新
// ===========================
function updateFilterSummary() {
  const el = document.getElementById('filter-summary-text');
  if (!el) return;
  if (selectedGroups.size === 0) {
    el.textContent = '全グループ表示中';
  } else {
    const labels = [...selectedGroups].map(g => GROUP_LABELS[g] || g);
    if (labels.length <= 2) {
      el.textContent = labels.join('・') + ' で絞り込み中';
    } else {
      el.textContent = `推し${labels.length}組で絞り込み中`;
    }
  }
}

// ===========================
// 選択中チップ更新（PC用）
// ===========================
function updateFilterChips() {
  const container = document.getElementById('shops-filter-chips');
  if (!container) return;
  if (selectedGroups.size === 0) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = [...selectedGroups].map(g => {
    const label = GROUP_LABELS[g] || g;
    const color = GROUP_SOLID_COLORS[g] || '#b72a65';
    return `<span class="filter-chip" style="color:${color};background:${color}18;border-color:${color}40">
      ${escHtml(label)}
      <button class="filter-chip__remove" data-group="${escHtml(g)}" aria-label="${escHtml(label)}を外す">×</button>
    </span>`;
  }).join('');

  container.querySelectorAll('.filter-chip__remove').forEach(btn => {
    btn.addEventListener('click', () => {
      const g = btn.dataset.group;
      selectedGroups.delete(g);
      document.querySelector(`.group-chip[data-group="${g}"]`)?.classList.remove('active');
      applyFilters();
      updateFilterSummary();
      updateFilterChips();
    });
  });
}

// ===========================
// フィルター適用
// ===========================
function applyFilters() {
  const query = document.getElementById('search-input')?.value.trim().toLowerCase() || '';
  const genre = document.getElementById('filter-genre')?.value || '';
  const pref  = document.getElementById('filter-prefecture')?.value || '';

  filteredShops = allShops.filter(s => {
    if (genre && s.genre !== genre) return false;
    if (pref  && s.prefecture !== pref) return false;
    if (selectedGroups.size > 0 && !(s.groups || []).some(g => selectedGroups.has(g))) return false;
    if (query) {
      const hay = [s.name, s.description, s.address, ...(s.tags || [])].join(' ').toLowerCase();
      if (!hay.includes(query)) return false;
    }
    return true;
  });

  renderGrid(filteredShops);
  updateCount(filteredShops.length);
  if (typeof renderMapMarkers === 'function') renderMapMarkers(filteredShops);
}

// ===========================
// ソート
// ===========================
function getSortMode() {
  return document.getElementById('sort-select')?.value || 'recent';
}

function sortShops(shops) {
  const mode = getSortMode();
  if (mode === 'video') {
    return [...shops].sort((a, b) => (b.youtube_id ? 1 : 0) - (a.youtube_id ? 1 : 0));
  }
  // recent: visited_date降順 → youtube_idあり優先
  return [...shops].sort((a, b) => {
    const da = a.visited_date || '';
    const db = b.visited_date || '';
    if (db !== da) return db.localeCompare(da);
    return (b.youtube_id ? 1 : 0) - (a.youtube_id ? 1 : 0);
  });
}

// ===========================
// カードグリッド描画
// ===========================
function renderGrid(shops) {
  shops = sortShops(shops);
  const grid = document.getElementById('shop-grid');
  if (!grid) return;

  if (shops.length === 0) {
    grid.innerHTML = '<p class="no-results">該当するお店が見つかりませんでした。</p>';
    return;
  }
  grid.innerHTML = shops.map(s => buildShopCard(s)).join('');
  restoreFavButtons();
}

const GROUP_LABELS = {
  yonino:       'よにのちゃんねる',
  snowman:      'Snow Man',
  sixtones:     'SixTONES',
  naniwa:       'なにわ男子',
  kamenashi:    '亀梨和也',
  ginga:        '中丸雄一 銀河チャンネル',
  kamaitachi:   'かまいたち',
  kodoku_no_gurume: '孤独のグルメ',
  heysayjump:   'Hey! Say! JUMP',
  timelesz:     'timelesz',
  equal_love:   'イコラブ',
  notme:        '≠ME',
  neajoy:       '≒JOY',
  nogizaka46:   '乃木坂46',
  hinatazaka46: '日向坂46',
  sakurazaka46: '櫻坂46',
};

const GROUP_SOLID_COLORS = {
  yonino:'#e8537a', snowman:'#3b82f6', sixtones:'#7c3aed', naniwa:'#f97316',
  kamenashi:'#059669', kamaitachi:'#8b5cf6', kodoku_no_gurume:'#92400e', heysayjump:'#ef4444', equal_love:'#f43f5e', notme:'#0d9488',
  timelesz:'#1d4ed8',
  neajoy:'#d946ef', nogizaka46:'#0ea5e9', sakurazaka46:'#e11d48',
  hinatazaka46:'#f59e0b', ginga:'#6366f1',
};

const GROUP_COLORS = {
  yonino:       'linear-gradient(135deg, #e8537a, #f7a1b5)',
  snowman:      'linear-gradient(135deg, #3b82f6, #93c5fd)',
  sixtones:     'linear-gradient(135deg, #7c3aed, #a78bfa)',
  equal_love:   'linear-gradient(135deg, #f43f5e, #fb923c)',
  notme:        'linear-gradient(135deg, #0d9488, #5eead4)',
  neajoy:       'linear-gradient(135deg, #d946ef, #f0abfc)',
  sakurazaka46: 'linear-gradient(135deg, #e11d48, #fda4af)',
  nogizaka46:   'linear-gradient(135deg, #0ea5e9, #7dd3fc)',
  hinatazaka46: 'linear-gradient(135deg, #f59e0b, #fde68a)',
  naniwa:       'linear-gradient(135deg, #f97316, #fbbf24)',
  kamenashi:    'linear-gradient(135deg, #059669, #6ee7b7)',
  ginga:        'linear-gradient(135deg, #6366f1, #a5b4fc)',
  kamaitachi:       'linear-gradient(135deg, #eab308, #fde68a)',
  kodoku_no_gurume: 'linear-gradient(135deg, #92400e, #d97706)',
  heysayjump:       'linear-gradient(135deg, #ef4444, #fbbf24)',
  timelesz:         'linear-gradient(135deg, #1d4ed8, #60a5fa)',
};
const GENRE_ICONS = {
  'カフェ':'☕','ラーメン':'🍜','焼肉':'🥩','食事':'🍽️','スイーツ':'🍰','寿司':'🍣',
  'もんじゃ':'🍳','居酒屋':'🍺','和食':'🍱','中華':'🥟','カレー':'🍛','その他':'🍴',
};

function buildShopCard(shop) {
  const thumb = shop.youtube_id
    ? `https://img.youtube.com/vi/${shop.youtube_id}/mqdefault.jpg`
    : shop.thumbnail_url || null;

  const group      = (shop.groups || [])[0] || shop.group || '';
  const gradient   = GROUP_COLORS[group] || 'linear-gradient(135deg, #e8537a, #7c3aed)';
  const solidColor = GROUP_SOLID_COLORS[group] || '#b72a65';
  const groupLabel = GROUP_LABELS[group] || group;
  const icon       = GENRE_ICONS[shop.genre] || '🍽️';
  const base       = typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '';
  const groupIconUrl = group ? `${base}/assets/images/groups/${group}.jpg` : '';

  const thumbHtml = thumb
    ? `<img src="${thumb}" alt="${escHtml(shop.name)}" loading="lazy">
       <div class="shop-card__play"><div class="shop-card__play-icon">▶</div></div>`
    : `<div class="shop-card__banner" style="background:${gradient}">
         ${groupIconUrl ? `<img src="${groupIconUrl}" alt="${escHtml(groupLabel)}" class="shop-card__banner-group-icon" onerror="this.style.display='none'">` : `<span class="shop-card__banner-icon">${icon}</span>`}
         <span class="shop-card__banner-genre">${escHtml(shop.genre||'')}</span>
       </div>`;

  // 表示エリア: 都道府県 · 最寄り駅 (住所は長すぎるので使わない)
  const locationParts = [shop.prefecture, shop.nearest_station].filter(Boolean);
  const location = locationParts.length ? locationParts.join(' · ') : (shop.city || '');

  const metaRow = group || shop.genre
    ? `<div class="shop-card__meta-row">
        ${group ? `<span class="shop-card__group-label" style="color:${solidColor}">${escHtml(groupLabel)}</span>` : ''}
        ${group && shop.genre ? `<span class="shop-card__sep">·</span>` : ''}
        ${shop.genre ? `<span class="shop-card__genre">${escHtml(shop.genre)}</span>` : ''}
      </div>` : '';

  const memberFirst = (shop.members || [])[0] || '';
  const memberHtml = memberFirst
    ? `<p class="shop-card__member">👤 ${escHtml(memberFirst)}</p>` : '';

  const shopSlug = shop.id.replace(/_/g, '-').replace(/-+$/g, '');
  const detailUrl = `${base}/shops/${shopSlug}/`;

  return `
    <a class="shop-card" href="${detailUrl}">
      <div class="shop-card__thumb">
        ${thumbHtml}
        <button class="shop-card__fav" aria-label="保存" onclick="toggleFav(event,'${escHtml(shop.id)}',this)">♡</button>
      </div>
      <div class="shop-card__body">
        ${metaRow}
        <p class="shop-card__name">${escHtml(shop.name)}</p>
        ${location ? `<p class="shop-card__location">📍 ${escHtml(location)}</p>` : ''}
        ${memberHtml}
      </div>
    </a>`;
}

// ===========================
// モーダル
// ===========================
function openModal(shopId) {
  const shop = allShops.find(s => s.id === shopId);
  if (!shop) return;

  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');

  const youtubeHtml = shop.youtube_id ? `
    <div class="modal-youtube">
      <iframe src="https://www.youtube.com/embed/${shop.youtube_id}"
        title="YouTube video player" allow="autoplay; encrypted-media; picture-in-picture"
        allowfullscreen loading="lazy"></iframe>
    </div>` : '';

  const linksHtml = (shop.affiliate_links || []).map(l =>
    `<a href="${escHtml(l.url)}" class="modal-link" target="_blank" rel="noopener">${escHtml(l.label)}</a>`
  ).join('');

  const tags = [
    shop.genre      ? `<span class="badge badge--genre">${escHtml(shop.genre)}</span>` : '',
    shop.prefecture ? `<span class="badge badge--pref">${escHtml(shop.prefecture)}</span>` : '',
    ...(shop.tags || []).map(t => `<span class="badge">${escHtml(t)}</span>`),
  ].join('');

  const members = (shop.members || []).length
    ? `<p class="modal-members">👤 ${shop.members.map(escHtml).join(' / ')}</p>` : '';

  const visitedHtml = shop.visited_date
    ? `<p class="modal-visited-date">📅 ${formatDate(shop.visited_date)}訪問</p>` : '';
  const videoTitleHtml = shop.source_video_title
    ? `<p class="modal-video-title">🎬 ${escHtml(shop.source_video_title)}</p>` : '';

  content.innerHTML = `
    <div class="modal-body">
      ${youtubeHtml}
      ${visitedHtml}
      ${videoTitleHtml}
      <div class="modal-meta">${tags}</div>
      <h2 class="modal-title">${escHtml(shop.name)}</h2>
      <p class="modal-address">📍 ${escHtml(shop.address || '')}</p>
      <p class="modal-desc">${escHtml(shop.description || '')}</p>
      ${members}
      <div class="modal-links">${linksHtml}</div>
    </div>`;

  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  // YouTube の再生を止める
  const iframe = overlay.querySelector('iframe');
  if (iframe) iframe.src = iframe.src;
}


// ===========================
// タブ切り替え
// ===========================
function switchView(view) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });
  const masterDetail = document.getElementById('shop-list-wrap');
  const mapSection   = document.getElementById('view-map');
  if (masterDetail) masterDetail.style.display = view === 'grid' ? '' : 'none';
  if (mapSection)   mapSection.style.display   = view === 'map'  ? '' : 'none';

  if (view === 'map' && typeof initMap === 'function') {
    initMap();
    renderMapMarkers(filteredShops);
  }
}

// ===========================
// ユーティリティ
// ===========================
function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const [y, m, d] = dateStr.split('-');
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

function updateCount(n) {
  const el = document.getElementById('result-count');
  if (el) el.textContent = `${n} 件のお店`;
}

// ===========================
// ♡ お気に入りトグル（localStorage）
// ===========================
function toggleFav(event, shopId, btn) {
  event.preventDefault();
  event.stopPropagation();
  const saved = JSON.parse(localStorage.getItem('fav_shops') || '[]');
  const idx = saved.indexOf(shopId);
  if (idx >= 0) {
    saved.splice(idx, 1);
    btn.classList.remove('saved');
    btn.textContent = '♡';
  } else {
    saved.push(shopId);
    btn.classList.add('saved');
    btn.textContent = '♥';
  }
  localStorage.setItem('fav_shops', JSON.stringify(saved));
}

function restoreFavButtons() {
  const saved = JSON.parse(localStorage.getItem('fav_shops') || '[]');
  if (!saved.length) return;
  document.querySelectorAll('.shop-card__fav[aria-label="保存"]').forEach(btn => {
    const card = btn.closest('.shop-card');
    if (!card) return;
    const href = card.getAttribute('href') || '';
    const id = href.split('/shops/')[1]?.replace(/\//g,'').replace(/-/g,'_') || '';
    if (saved.includes(id) || saved.some(s => href.includes(s.replace(/_/g,'-')))) {
      btn.classList.add('saved');
      btn.textContent = '♥';
    }
  });
}

// ===========================
// イベントリスナー
// ===========================
document.addEventListener('DOMContentLoaded', () => {
  // フィルター入力
  ['search-input','filter-genre','filter-prefecture'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', applyFilters);
  });

  // ソート
  document.getElementById('sort-select')?.addEventListener('change', () => {
    renderGrid(filteredShops);
  });

  // リセット
  document.getElementById('reset-filters')?.addEventListener('click', () => {
    ['search-input','filter-genre','filter-prefecture'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    selectedGroups.clear();
    document.querySelectorAll('.group-chip').forEach(b => b.classList.remove('active'));
    applyFilters();
    updateFilterSummary();
    updateFilterChips();
  });

  // フィルターパネルトグル（SP用）
  document.getElementById('filter-toggle-btn')?.addEventListener('click', function() {
    const panel = document.getElementById('shops-filter-panel');
    if (!panel) return;
    const isCollapsed = panel.classList.toggle('collapsed');
    this.setAttribute('aria-expanded', String(!isCollapsed));
    this.textContent = isCollapsed ? '変更 ▾' : '閉じる ▴';
  });

  // タブ
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  // データ読み込み
  if (document.getElementById('shop-grid')) {
    loadShops();
  }
});
