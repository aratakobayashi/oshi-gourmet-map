/**
 * main.js
 * お店データの読み込み・フィルター・グリッド表示・モーダル制御
 */

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
  renderGrid(filteredShops);
  updateCount(filteredShops.length);
  updateHero();
  updateGroupShowcase();

  // 地図が初期化済みなら更新
  if (typeof renderMapMarkers === 'function') renderMapMarkers(filteredShops);
}

// ===========================
// ヒーロー統計更新
// ===========================
function updateHero() {
  const groups = new Set(allShops.flatMap(s => s.groups || []));
  const prefs  = new Set(allShops.map(s => s.prefecture).filter(Boolean));

  const sub = document.getElementById('hero-sub');
  if (sub) {
    const names = [...groups].slice(0, 3).map(g => GROUP_LABELS[g] || g).join('・');
    sub.textContent = `${names}など${groups.size}グループ、${allShops.length}件のグルメスポットを収録`;
  }

  const statsEl = document.getElementById('hero-stats');
  if (statsEl) {
    const items = [
      { num: allShops.length, label: '件のお店' },
      { num: groups.size,     label: 'グループ'  },
      { num: prefs.size,      label: '都道府県'  },
    ];
    statsEl.innerHTML = items.map(({ num, label }) => `
      <div class="hero__stat">
        <span class="hero__stat-num">${num}</span>
        <span class="hero__stat-label">${label}</span>
      </div>`).join('');
  }
}

function scrollToFilter() {
  document.querySelector('.filter-bar')?.scrollIntoView({ behavior: 'smooth' });
}

// ===========================
// グループショーケース
// ===========================
function updateGroupShowcase() {
  const showcase = document.getElementById('group-showcase');
  if (!showcase) return;

  const groups = [...new Set(allShops.flatMap(s => s.groups || []))];
  groups.sort((a, b) => {
    const ca = allShops.filter(s => (s.groups || []).includes(a)).length;
    const cb = allShops.filter(s => (s.groups || []).includes(b)).length;
    return cb - ca;
  });

  showcase.innerHTML = groups.map(g => {
    const label = GROUP_LABELS[g] || g;
    const grad  = GROUP_COLORS[g] || 'linear-gradient(135deg,#aaa,#ccc)';
    const count = allShops.filter(s => (s.groups || []).includes(g)).length;
    return `<button class="group-showcase__card" data-group="${escHtml(g)}"
      style="--group-grad:${grad}" onclick="activateGroup('${escHtml(g)}')">
      <span class="group-showcase__name">${escHtml(label)}</span>
      <span class="group-showcase__count">${count}</span>
      <span class="group-showcase__count-label">件のお店</span>
    </button>`;
  }).join('');
}

function activateGroup(groupId) {
  selectedGroups.clear();
  selectedGroups.add(groupId);

  document.querySelectorAll('.group-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.group === groupId);
  });

  applyFilters();
  document.querySelector('.filter-bar')?.scrollIntoView({ behavior: 'smooth' });
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
// グループボタン描画
// ===========================
function renderGroupButtons() {
  const row = document.getElementById('group-filter-row');
  if (!row) return;

  const groups = [...new Set(allShops.flatMap(s => s.groups || []))];
  // データ件数順に並べる
  groups.sort((a, b) => {
    const ca = allShops.filter(s => (s.groups || []).includes(a)).length;
    const cb = allShops.filter(s => (s.groups || []).includes(b)).length;
    return cb - ca;
  });

  row.innerHTML = groups.map(g => {
    const label = GROUP_LABELS[g] || g;
    const grad  = GROUP_COLORS[g] || 'linear-gradient(135deg,#aaa,#ccc)';
    return `<button class="group-btn" data-group="${escHtml(g)}"
      style="--group-grad:${grad}">${escHtml(label)}</button>`;
  }).join('');

  row.querySelectorAll('.group-btn').forEach(btn => {
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
// ソート（サムネあり優先）
// ===========================
function sortShops(shops) {
  return [...shops].sort((a, b) => (b.youtube_id ? 1 : 0) - (a.youtube_id ? 1 : 0));
}

// ===========================
// グリッド描画
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
}

const GROUP_LABELS = {
  yonino:       'よにのちゃんねる',
  snowman:      'Snow Man',
  sixtones:     'SixTONES',
  naniwa:       'なにわ男子',
  kamenashi:    '亀梨和也',
  equal_love:   'イコラブ',
  nogizaka46:   '乃木坂46',
  hinatazaka46: '日向坂46',
  sakurazaka46: '櫻坂46',
};

const GROUP_COLORS = {
  yonino:       'linear-gradient(135deg, #e8537a, #f7a1b5)',
  snowman:      'linear-gradient(135deg, #3b82f6, #93c5fd)',
  sixtones:     'linear-gradient(135deg, #7c3aed, #a78bfa)',
  equal_love:   'linear-gradient(135deg, #f43f5e, #fb923c)',
  sakurazaka46: 'linear-gradient(135deg, #e11d48, #fda4af)',
  nogizaka46:   'linear-gradient(135deg, #0ea5e9, #7dd3fc)',
  hinatazaka46: 'linear-gradient(135deg, #f59e0b, #fde68a)',
  naniwa:       'linear-gradient(135deg, #f97316, #fbbf24)',
  kamenashi:    'linear-gradient(135deg, #059669, #6ee7b7)',
};
const GENRE_ICONS = {
  'カフェ':'☕','ラーメン':'🍜','焼肉':'🥩','食事':'🍽️','スイーツ':'🍰','寿司':'🍣',
  'もんじゃ':'🍳','居酒屋':'🍺','和食':'🍱','その他':'🍴',
};

function buildShopCard(shop) {
  const thumb = shop.youtube_id
    ? `https://img.youtube.com/vi/${shop.youtube_id}/mqdefault.jpg`
    : null;

  const group = (shop.groups || [])[0] || shop.group || '';
  const gradient = GROUP_COLORS[group] || 'linear-gradient(135deg, #e8537a, #7c3aed)';
  const icon = GENRE_ICONS[shop.genre] || '🍽️';

  const groupLabel = GROUP_LABELS[group] || group;
  const badgeHtml = `<span class="shop-card__group-badge" style="background:${gradient}">${escHtml(groupLabel)}</span>`;

  const thumbHtml = thumb
    ? `<img src="${thumb}" alt="${escHtml(shop.name)}" loading="lazy">
       <div class="shop-card__play"><div class="shop-card__play-icon">▶</div></div>
       ${badgeHtml}`
    : `<div class="shop-card__banner" style="background:${gradient}">
         <span class="shop-card__banner-icon">${icon}</span>
         <span class="shop-card__banner-genre">${escHtml(shop.genre||'')}</span>
       </div>
       ${badgeHtml}`;

  const tags = [
    shop.genre    ? `<span class="badge badge--genre">${escHtml(shop.genre)}</span>` : '',
    shop.prefecture ? `<span class="badge badge--pref">${escHtml(shop.prefecture)}</span>` : '',
  ].join('');

  const members = (shop.members || []).length
    ? `<p class="shop-card__members">👤 ${shop.members.map(escHtml).join(' / ')}</p>`
    : '';

  return `
    <div class="shop-card" onclick="openModal('${escHtml(shop.id)}')" role="button" tabindex="0"
         onkeydown="if(event.key==='Enter')openModal('${escHtml(shop.id)}')">
      <div class="shop-card__thumb">${thumbHtml}</div>
      <div class="shop-card__body">
        <div class="shop-card__tags">${tags}</div>
        <p class="shop-card__name">${escHtml(shop.name)}</p>
        <p class="shop-card__location">📍 ${escHtml(shop.address || '')}</p>
        <p class="shop-card__desc">${escHtml(shop.description || '')}</p>
        ${members}
      </div>
    </div>`;
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
  document.getElementById('view-grid').style.display = view === 'grid' ? '' : 'none';
  document.getElementById('view-map').style.display  = view === 'map'  ? '' : 'none';

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
// イベントリスナー
// ===========================
document.addEventListener('DOMContentLoaded', () => {
  // フィルター
  ['search-input','filter-genre','filter-prefecture'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', applyFilters);
  });

  document.getElementById('reset-filters')?.addEventListener('click', () => {
    ['search-input','filter-genre','filter-prefecture'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    selectedGroups.clear();
    document.querySelectorAll('.group-btn').forEach(b => b.classList.remove('active'));
    applyFilters();
  });

  // タブ
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  // モーダルを閉じる
  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  document.getElementById('modal-overlay')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  // データ読み込み
  if (document.getElementById('shop-grid')) {
    loadShops();
  }
});
