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
    document.querySelectorAll('.group-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.group === group);
    });
  }
  if (genre) {
    const el = document.getElementById('filter-genre');
    if (el) el.value = genre;
  }

  applyFilters();
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
  ginga:        '中丸雄一 銀河チャンネル',
  kamaitachi:   'かまいたち',
  equal_love:   'イコラブ',
  notme:        '≠ME',
  neajoy:       '≒JOY',
  nogizaka46:   '乃木坂46',
  hinatazaka46: '日向坂46',
  sakurazaka46: '櫻坂46',
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
  kamaitachi:   'linear-gradient(135deg, #eab308, #fde68a)',
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

  const base = typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '';
  const groupIconUrl = group ? `${base}/assets/images/groups/${group}.jpg` : '';

  const thumbHtml = thumb
    ? `<img src="${thumb}" alt="${escHtml(shop.name)}" loading="lazy">
       <div class="shop-card__play"><div class="shop-card__play-icon">▶</div></div>
       ${badgeHtml}`
    : `<div class="shop-card__banner" style="background:${gradient}">
         ${groupIconUrl ? `<img src="${groupIconUrl}" alt="${escHtml(groupLabel)}" class="shop-card__banner-group-icon" onerror="this.style.display='none'">` : `<span class="shop-card__banner-icon">${icon}</span>`}
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

  const slug = shop.id.replace(/_+/g, '-').replace(/-{2,}/g, '-');
  const detailUrl = `${base}/shops/${slug}/`;

  return `
    <a class="shop-card" href="${detailUrl}">
      <div class="shop-card__thumb">${thumbHtml}</div>
      <div class="shop-card__body">
        <div class="shop-card__tags">${tags}</div>
        <p class="shop-card__name">${escHtml(shop.name)}</p>
        <p class="shop-card__location">📍 ${escHtml(shop.address || '')}</p>
        <p class="shop-card__desc">${escHtml(shop.description || '')}</p>
        ${members}
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
// スライドインパネル（PC専用）
// ===========================
var panelMap = null;

function openPanel(shop) {
  const panel = document.getElementById('shop-panel');
  const content = document.getElementById('shop-panel-content');
  if (!panel || !content) return;

  content.innerHTML = buildPanelContent(shop);

  // アクティブカードをハイライト
  document.querySelectorAll('.shop-card').forEach(c => c.classList.remove('active'));
  const slug = shop.id.replace(/_+/g, '-').replace(/-{2,}/g, '-');
  const activeCard = document.querySelector(`.shop-card[href*="${slug}"]`);
  if (activeCard) activeCard.classList.add('active');

  panel.classList.add('open');
  panel.setAttribute('aria-hidden', 'false');
  document.getElementById('shop-grid').classList.add('shop-grid--panel-open');

  // 地図初期化
  if (shop.lat && shop.lng) {
    setTimeout(function() {
      if (panelMap) { panelMap.remove(); panelMap = null; }
      panelMap = L.map('panel-map', { scrollWheelZoom: false }).setView([shop.lat, shop.lng], 15);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
      }).addTo(panelMap);
      L.marker([shop.lat, shop.lng]).addTo(panelMap);
    }, 50);
  }
}

function closePanel() {
  const panel = document.getElementById('shop-panel');
  if (!panel) return;
  panel.classList.remove('open');
  panel.setAttribute('aria-hidden', 'true');
  document.getElementById('shop-grid')?.classList.remove('shop-grid--panel-open');
  document.querySelectorAll('.shop-card').forEach(c => c.classList.remove('active'));
  if (panelMap) { panelMap.remove(); panelMap = null; }
}

function buildPanelContent(shop) {
  const base = typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '';
  const slug = shop.id.replace(/_+/g, '-').replace(/-{2,}/g, '-');
  const detailUrl = base + '/shops/' + slug + '/';

  const thumb = shop.youtube_id
    ? `<div class="shop-panel__thumb"><img src="https://img.youtube.com/vi/${shop.youtube_id}/maxresdefault.jpg" alt="${escHtml(shop.name)}" loading="lazy"></div>`
    : '';

  const meta = [
    shop.address        ? `<li>📍 ${escHtml(shop.address)}</li>` : '',
    shop.nearest_station? `<li>🚃 ${escHtml(shop.nearest_station)}</li>` : '',
    shop.price_range    ? `<li>💰 ${escHtml(shop.price_range)}</li>` : '',
    shop.visited_date   ? `<li>📅 ${escHtml(formatDate(shop.visited_date))}訪問</li>` : '',
    (shop.members||[]).length ? `<li>👤 ${shop.members.map(escHtml).join('・')}</li>` : '',
  ].filter(Boolean).join('');

  const btnHP = shop.hotpepper_url ? `<a href="${escHtml(shop.hotpepper_url)}" class="shop-panel__btn shop-panel__btn--primary" target="_blank" rel="noopener">ホットペッパーで予約</a>` : '';
  const btnTL = shop.tabelog_url   ? `<a href="${escHtml(shop.tabelog_url)}" class="shop-panel__btn shop-panel__btn--outline" target="_blank" rel="noopener">食べログで見る</a>` : '';
  const mapsUrl = shop.google_maps_url || (shop.address ? 'https://maps.google.com/?q=' + encodeURIComponent(shop.address) : '');
  const btnGM = mapsUrl ? `<a href="${escHtml(mapsUrl)}" class="shop-panel__btn shop-panel__btn--maps" target="_blank" rel="noopener">Googleマップ</a>` : '';

  const videoHtml = shop.youtube_id ? `
    <div class="shop-panel__video">
      <a href="https://www.youtube.com/watch?v=${shop.youtube_id}" class="shop-panel__video-link" target="_blank" rel="noopener">
        <img src="https://img.youtube.com/vi/${shop.youtube_id}/mqdefault.jpg" alt="${escHtml(shop.name)}">
        <div class="shop-panel__video-play"><span>▶</span></div>
      </a>
      ${shop.source_video_title ? `<p class="shop-panel__video-title">${escHtml(shop.source_video_title)}</p>` : ''}
    </div>` : '';

  const mapHtml = (shop.lat && shop.lng) ? `<div id="panel-map" class="shop-panel__map"></div>` : '';

  return `
    ${thumb}
    <div class="shop-panel__body">
      <div class="shop-panel__badges">
        ${shop.genre      ? `<span class="badge badge--genre">${escHtml(shop.genre)}</span>` : ''}
        ${shop.prefecture ? `<span class="badge badge--pref">${escHtml(shop.prefecture)}</span>` : ''}
      </div>
      <h2 class="shop-panel__name">${escHtml(shop.name)}</h2>
      ${shop.description ? `<p class="shop-panel__desc">${escHtml(shop.description)}</p>` : ''}
      ${meta ? `<ul class="shop-panel__meta">${meta}</ul>` : ''}
      <div class="shop-panel__actions">${btnHP}${btnTL}${btnGM}</div>
      ${videoHtml}
      ${mapHtml}
      <a href="${detailUrl}" class="shop-panel__detail-link">詳細ページを見る →</a>
    </div>`;
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

  // パネルを閉じる
  document.getElementById('shop-panel-close')?.addEventListener('click', closePanel);

  // グリッドのクリック：PC はパネル、SP はページ遷移
  document.getElementById('shop-grid')?.addEventListener('click', function(e) {
    if (window.innerWidth < 1024) return;
    const card = e.target.closest('.shop-card');
    if (!card) return;
    e.preventDefault();
    const href = card.getAttribute('href') || '';
    const slug = href.replace(/.*\/shops\//, '').replace(/\/$/, '');
    const shop = allShops.find(s => s.id.replace(/_+/g, '-').replace(/-{2,}/g, '-') === slug);
    if (shop) openPanel(shop);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closePanel(); }
  });

  // データ読み込み
  if (document.getElementById('shop-grid')) {
    loadShops();
  }
});
