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
    if (y > lastY && y > 80) nav.classList.add('bottom-nav--hidden');
    else nav.classList.remove('bottom-nav--hidden');
    lastY = y;
  }, { passive: true });
})();

const SHOPS_URL = (typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '') + '/data/shops.json';

let allShops = [];
let filteredShops = [];
let selectedGroups     = new Set();
let selectedPrefs      = new Set();
let tempSelectedGroups = new Set();
let tempSelectedPrefs  = new Set();
let activeRegion       = null;

// ===========================
// データ読み込み
// ===========================
async function loadShops() {
  const res = await fetch(SHOPS_URL);
  allShops = await res.json();
  filteredShops = [...allShops];

  populateFilters();
  initFromUrlParams();

  if (typeof renderMapMarkers === 'function') renderMapMarkers(filteredShops);
}

// ===========================
// URLパラメーターで初期フィルターをセット
// ===========================
function initFromUrlParams() {
  const params = new URLSearchParams(window.location.search);
  const group = params.get('group');
  const genre = params.get('genre');
  const pref  = params.get('pref');

  if (group && GROUP_LABELS[group]) selectedGroups.add(group);
  if (pref) selectedPrefs.add(pref);
  if (genre) {
    const el = document.getElementById('filter-genre');
    if (el) el.value = genre;
  }

  applyFilters();
  updateFilterBar();
  updateFilterChips();
}

// ===========================
// フィルター選択肢を生成
// ===========================
function populateFilters() {
  const genres = [...new Set(allShops.map(s => s.genre).filter(Boolean))].sort();
  fillSelect('filter-genre', genres);
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
// 定数
// ===========================
const GROUP_INITIALS = {
  yonino:'よ', snowman:'S', sixtones:'Si', naniwa:'な', kamenashi:'亀',
  kamaitachi:'か', equal_love:'=', notme:'≠', neajoy:'≒',
  nogizaka46:'乃', hinatazaka46:'日', sakurazaka46:'櫻',
  heysayjump:'H', ginga:'中', kodoku_no_gurume:'孤', timelesz:'T',
};

const GROUP_LABELS = {
  yonino:           'よにのちゃんねる',
  snowman:          'Snow Man',
  sixtones:         'SixTONES',
  naniwa:           'なにわ男子',
  kamenashi:        '亀梨和也',
  ginga:            '中丸雄一 銀河チャンネル',
  kamaitachi:       'かまいたち',
  kodoku_no_gurume: '孤独のグルメ',
  heysayjump:       'Hey! Say! JUMP',
  timelesz:         'timelesz',
  equal_love:       'イコラブ',
  notme:            '≠ME',
  neajoy:           '≒JOY',
  nogizaka46:       '乃木坂46',
  hinatazaka46:     '日向坂46',
  sakurazaka46:     '櫻坂46',
};

const GROUP_SOLID_COLORS = {
  yonino:'#e8537a', snowman:'#3b82f6', sixtones:'#7c3aed', naniwa:'#f97316',
  kamenashi:'#059669', kamaitachi:'#8b5cf6', kodoku_no_gurume:'#92400e',
  heysayjump:'#ef4444', equal_love:'#f43f5e', notme:'#0d9488',
  timelesz:'#1d4ed8', neajoy:'#d946ef', nogizaka46:'#0ea5e9',
  sakurazaka46:'#e11d48', hinatazaka46:'#f59e0b', ginga:'#6366f1',
};

const GROUP_COLORS = {
  yonino:           'linear-gradient(135deg, #e8537a, #f7a1b5)',
  snowman:          'linear-gradient(135deg, #3b82f6, #93c5fd)',
  sixtones:         'linear-gradient(135deg, #7c3aed, #a78bfa)',
  equal_love:       'linear-gradient(135deg, #f43f5e, #fb923c)',
  notme:            'linear-gradient(135deg, #0d9488, #5eead4)',
  neajoy:           'linear-gradient(135deg, #d946ef, #f0abfc)',
  sakurazaka46:     'linear-gradient(135deg, #e11d48, #fda4af)',
  nogizaka46:       'linear-gradient(135deg, #0ea5e9, #7dd3fc)',
  hinatazaka46:     'linear-gradient(135deg, #f59e0b, #fde68a)',
  naniwa:           'linear-gradient(135deg, #f97316, #fbbf24)',
  kamenashi:        'linear-gradient(135deg, #059669, #6ee7b7)',
  ginga:            'linear-gradient(135deg, #6366f1, #a5b4fc)',
  kamaitachi:       'linear-gradient(135deg, #8b5cf6, #c4b5fd)',
  kodoku_no_gurume: 'linear-gradient(135deg, #92400e, #d97706)',
  heysayjump:       'linear-gradient(135deg, #ef4444, #fbbf24)',
  timelesz:         'linear-gradient(135deg, #1d4ed8, #60a5fa)',
};

const GENRE_ICONS = {
  'カフェ':'☕','ラーメン':'🍜','焼肉':'🥩','食事':'🍽️','スイーツ':'🍰','寿司':'🍣',
  'もんじゃ':'🍳','居酒屋':'🍺','和食':'🍱','中華':'🥟','カレー':'🍛','その他':'🍴',
};

const REGION_MAP = {
  '関東':         ['東京都','神奈川県','埼玉県','千葉県','茨城県','栃木県','群馬県'],
  '近畿':         ['大阪府','兵庫県','京都府','奈良県','滋賀県','和歌山県','三重県'],
  '東海':         ['愛知県','静岡県','岐阜県'],
  '九州・沖縄':   ['福岡県','佐賀県','長崎県','熊本県','大分県','宮崎県','鹿児島県','沖縄県'],
  '北海道・東北': ['北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県'],
  '中国・四国':   ['広島県','岡山県','山口県','鳥取県','島根県','徳島県','香川県','愛媛県','高知県'],
  '甲信越・北陸': ['新潟県','富山県','石川県','福井県','長野県','山梨県'],
  '海外・その他': ['シンガポール','韓国','台湾','タイ','アメリカ','フランス','その他海外'],
};

// ===========================
// フィルターバー更新
// ===========================
function updateFilterBar() {
  renderGroupDots();
  const el = document.getElementById('fbar-summary');
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

function renderGroupDots() {
  const container = document.getElementById('fbar-group-dots');
  if (!container) return;
  if (selectedGroups.size === 0) { container.innerHTML = ''; return; }

  const MAX_DOTS = 3;
  const dotList = [...selectedGroups];
  const shown   = dotList.slice(0, MAX_DOTS);
  const extra   = dotList.length - MAX_DOTS;

  let html = shown.map(g => {
    const color   = GROUP_SOLID_COLORS[g] || '#b72a65';
    const initial = GROUP_INITIALS[g] || (GROUP_LABELS[g] || g).charAt(0);
    return `<span class="fbar__group-dot" style="background:${color}" title="${escHtml(GROUP_LABELS[g] || g)}">${escHtml(initial)}</span>`;
  }).join('');

  if (extra > 0) {
    html += `<span class="fbar__group-dot fbar__group-dot--more">+${extra}</span>`;
  }

  container.innerHTML = html;
}

// ===========================
// 選択中チップ更新
// ===========================
function updateFilterChips() {
  const container = document.getElementById('fbar-chips');
  const row       = document.getElementById('fbar-chips-row');
  if (!container) return;

  const hasGroups = selectedGroups.size > 0;
  const hasPrefs  = selectedPrefs.size > 0;

  if (!hasGroups && !hasPrefs) {
    if (row) row.style.display = 'none';
    container.innerHTML = '';
    return;
  }
  if (row) row.style.display = '';

  const groupChips = [...selectedGroups].map(g => {
    const label = GROUP_LABELS[g] || g;
    const color = GROUP_SOLID_COLORS[g] || '#b72a65';
    const count = filteredShops.filter(s => (s.groups || []).includes(g)).length;
    return `<span class="fbar__chip" style="color:${color};background:${color}18;border:1px solid ${color}40">
      ${escHtml(label)}<span class="fbar__chip__count"> ${count}</span>
      <button class="fbar__chip__remove" data-remove-group="${escHtml(g)}" aria-label="${escHtml(label)}を外す">×</button>
    </span>`;
  });

  const prefChips = [...selectedPrefs].map(p =>
    `<span class="fbar__chip fbar__chip--pref">
      ${escHtml(p)}
      <button class="fbar__chip__remove" data-remove-pref="${escHtml(p)}" aria-label="${escHtml(p)}を外す">×</button>
    </span>`
  );

  container.innerHTML = groupChips.concat(prefChips).join('');

  container.querySelectorAll('.fbar__chip__remove[data-remove-group]').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedGroups.delete(btn.dataset.removeGroup);
      applyFilters(); updateFilterBar(); updateFilterChips();
    });
  });
  container.querySelectorAll('.fbar__chip__remove[data-remove-pref]').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedPrefs.delete(btn.dataset.removePref);
      applyFilters(); updateFilterChips();
    });
  });
}

// ===========================
// フィルター適用
// ===========================
function applyFilters() {
  const query = document.getElementById('search-input')?.value.trim().toLowerCase() || '';
  const genre = document.getElementById('filter-genre')?.value || '';

  filteredShops = allShops.filter(s => {
    if (genre && s.genre !== genre) return false;
    if (selectedPrefs.size  > 0 && !selectedPrefs.has(s.prefecture)) return false;
    if (selectedGroups.size > 0 && !(s.groups || []).some(g => selectedGroups.has(g))) return false;
    if (query) {
      const hay = [s.name, s.description, s.address, ...(s.tags || []), ...(s.members || [])].join(' ').toLowerCase();
      if (!hay.includes(query)) return false;
    }
    return true;
  });

  renderGrid(filteredShops);
  updateCount(filteredShops.length);
  if (typeof renderMapMarkers === 'function') renderMapMarkers(filteredShops);
}

// ===========================
// グループ選択モーダル
// ===========================
function openGroupModal() {
  tempSelectedGroups = new Set(selectedGroups);
  renderGroupCheckList('');
  updateGroupModalApplyBtn();
  const overlay = document.getElementById('group-modal-overlay');
  if (overlay) { overlay.classList.add('open'); overlay.setAttribute('aria-hidden', 'false'); }
  document.body.style.overflow = 'hidden';
}

function closeGroupModal() {
  const overlay = document.getElementById('group-modal-overlay');
  if (overlay) { overlay.classList.remove('open'); overlay.setAttribute('aria-hidden', 'true'); }
  document.body.style.overflow = '';
}

function renderGroupCheckList(query) {
  const list = document.getElementById('group-check-list');
  if (!list) return;

  const q = (query || '').toLowerCase();
  const groups = [...new Set(allShops.flatMap(s => s.groups || []))];
  groups.sort((a, b) => {
    const ca = allShops.filter(s => (s.groups || []).includes(a)).length;
    const cb = allShops.filter(s => (s.groups || []).includes(b)).length;
    return cb - ca;
  });

  const visible = q ? groups.filter(g => (GROUP_LABELS[g] || g).toLowerCase().includes(q)) : groups;

  list.innerHTML = visible.map(g => {
    const label   = GROUP_LABELS[g] || g;
    const color   = GROUP_SOLID_COLORS[g] || '#b72a65';
    const initial = GROUP_INITIALS[g] || label.charAt(0);
    const count   = allShops.filter(s => (s.groups || []).includes(g)).length;
    const sel     = tempSelectedGroups.has(g);
    return `<li class="group-check-item${sel ? ' selected' : ''}" data-group="${escHtml(g)}">
      <span class="group-check-item__dot" style="background:${color}">${escHtml(initial)}</span>
      <span class="group-check-item__name">${escHtml(label)}</span>
      <span class="group-check-item__count">${count}件</span>
      ${sel ? '<span class="group-check-item__star">★</span>' : ''}
      <span class="group-check-item__check">${sel ? '✓' : ''}</span>
    </li>`;
  }).join('');

  list.querySelectorAll('.group-check-item').forEach(item => {
    item.addEventListener('click', () => {
      const g = item.dataset.group;
      if (tempSelectedGroups.has(g)) tempSelectedGroups.delete(g);
      else tempSelectedGroups.add(g);
      renderGroupCheckList(document.getElementById('group-search-input')?.value || '');
      updateGroupModalApplyBtn();
    });
  });
}

function updateGroupModalApplyBtn() {
  const btn = document.getElementById('group-modal-apply');
  if (!btn) return;
  if (tempSelectedGroups.size === 0) {
    btn.textContent = '全グループ表示 →';
  } else {
    const count = allShops.filter(s => (s.groups || []).some(g => tempSelectedGroups.has(g))).length;
    btn.textContent = `${tempSelectedGroups.size}組で絞り込む（${count}件） →`;
  }
}

function applyGroupFilter() {
  selectedGroups = new Set(tempSelectedGroups);
  closeGroupModal();
  applyFilters();
  updateFilterBar();
  updateFilterChips();
}

// ===========================
// エリア選択モーダル
// ===========================
function openAreaModal() {
  tempSelectedPrefs = new Set(selectedPrefs);
  activeRegion = null;
  renderAreaModalPC();
  renderAreaModalSP();
  updateAreaModalApplyBtn();
  const overlay = document.getElementById('area-modal-overlay');
  if (overlay) { overlay.classList.add('open'); overlay.setAttribute('aria-hidden', 'false'); }
  document.body.style.overflow = 'hidden';
}

function closeAreaModal() {
  const overlay = document.getElementById('area-modal-overlay');
  if (overlay) { overlay.classList.remove('open'); overlay.setAttribute('aria-hidden', 'true'); }
  document.body.style.overflow = '';
}

function getAvailablePrefs() {
  return [...new Set(allShops.map(s => s.prefecture).filter(Boolean))];
}

function renderAreaModalPC() {
  const container = document.getElementById('area-modal-pc');
  if (!container) return;
  const avail = getAvailablePrefs();

  container.innerHTML = Object.entries(REGION_MAP).map(([region, prefs]) => {
    const available = prefs.filter(p => avail.includes(p));
    if (!available.length) return '';
    return `<div class="area-region">
      <p class="area-region__title">${escHtml(region)}</p>
      <div class="area-pills">
        ${available.map(p => `<button class="area-pill${tempSelectedPrefs.has(p) ? ' selected' : ''}" data-pref="${escHtml(p)}">${escHtml(p)}</button>`).join('')}
      </div>
    </div>`;
  }).join('');

  container.querySelectorAll('.area-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = btn.dataset.pref;
      if (tempSelectedPrefs.has(p)) tempSelectedPrefs.delete(p);
      else tempSelectedPrefs.add(p);
      btn.classList.toggle('selected', tempSelectedPrefs.has(p));
      updateAreaModalApplyBtn();
    });
  });
}

function renderAreaModalSP() {
  const sidebar = document.getElementById('area-sidebar');
  const prefsEl = document.getElementById('area-prefs');
  if (!sidebar || !prefsEl) return;
  const avail = getAvailablePrefs();

  const availRegions = Object.entries(REGION_MAP).filter(([, prefs]) => prefs.some(p => avail.includes(p)));
  if (!activeRegion && availRegions.length) activeRegion = availRegions[0][0];

  sidebar.innerHTML = availRegions.map(([region]) =>
    `<div class="area-sidebar__item${activeRegion === region ? ' active' : ''}" data-region="${escHtml(region)}">${escHtml(region)}</div>`
  ).join('');

  sidebar.querySelectorAll('.area-sidebar__item').forEach(item => {
    item.addEventListener('click', () => {
      activeRegion = item.dataset.region;
      sidebar.querySelectorAll('.area-sidebar__item').forEach(i =>
        i.classList.toggle('active', i.dataset.region === activeRegion)
      );
      showRegionPrefs(avail);
    });
  });

  showRegionPrefs(avail);
}

function showRegionPrefs(avail) {
  const prefsEl = document.getElementById('area-prefs');
  if (!prefsEl || !activeRegion) return;
  const prefs = (REGION_MAP[activeRegion] || []).filter(p => avail.includes(p));

  prefsEl.innerHTML = prefs.map(p => {
    const sel = tempSelectedPrefs.has(p);
    return `<div class="area-pref-check${sel ? ' selected' : ''}" data-pref="${escHtml(p)}">
      <span class="area-pref-check__box">${sel ? '✓' : ''}</span>
      <span class="area-pref-check__name">${escHtml(p)}</span>
    </div>`;
  }).join('');

  prefsEl.querySelectorAll('.area-pref-check').forEach(item => {
    item.addEventListener('click', () => {
      const p = item.dataset.pref;
      if (tempSelectedPrefs.has(p)) tempSelectedPrefs.delete(p);
      else tempSelectedPrefs.add(p);
      item.classList.toggle('selected', tempSelectedPrefs.has(p));
      const box = item.querySelector('.area-pref-check__box');
      if (box) box.textContent = tempSelectedPrefs.has(p) ? '✓' : '';
      updateAreaModalApplyBtn();
    });
  });
}

function updateAreaModalApplyBtn() {
  const btn = document.getElementById('area-modal-apply');
  if (!btn) return;
  if (tempSelectedPrefs.size === 0) {
    btn.textContent = '全エリア表示 →';
  } else {
    const count = allShops.filter(s => tempSelectedPrefs.has(s.prefecture)).length;
    btn.textContent = `${tempSelectedPrefs.size}エリアで絞り込む（${count}件） →`;
  }
}

function applyAreaFilter() {
  selectedPrefs = new Set(tempSelectedPrefs);
  closeAreaModal();
  applyFilters();
  updateFilterChips();
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

function buildShopCard(shop) {
  const thumb = shop.youtube_id
    ? `https://img.youtube.com/vi/${shop.youtube_id}/mqdefault.jpg`
    : shop.thumbnail_url || null;

  const group      = (shop.groups || [])[0] || shop.group || '';
  const solidColor = GROUP_SOLID_COLORS[group] || '#b72a65';
  const groupLabel = GROUP_LABELS[group] || group;
  const base       = typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '';

  const groupPillHtml = group
    ? `<div class="shop-card__group-pill" style="background:${solidColor}">${escHtml(groupLabel)}</div>`
    : '';

  const thumbHtml = thumb
    ? `<img src="${thumb}" alt="${escHtml(shop.name)}" loading="lazy">
       <div class="shop-card__play"><div class="shop-card__play-icon">▶</div></div>`
    : `<div class="shop-card__placeholder">
         <span class="shop-card__placeholder-name">${escHtml(shop.name)}</span>
       </div>`;

  const memberFirst = (shop.members || [])[0] || '';
  const memberHtml  = memberFirst ? `<p class="shop-card__member">👤 ${escHtml(memberFirst)}</p>` : '';

  // 住所は都道府県+市区町村までを表示（長い住所を短縮）
  const locationParts = [shop.prefecture, shop.city].filter(Boolean);
  const location = locationParts.length
    ? locationParts.join(' ')
    : (shop.nearest_station ? shop.nearest_station + '付近' : '');

  const shopSlug = shop.id.replace(/_/g, '-').replace(/-{2,}/g, '-').replace(/-+$/g, '');
  const detailUrl = `${base}/shops/${shopSlug}/`;

  return `
    <a class="shop-card" href="${detailUrl}">
      ${groupPillHtml}
      <div class="shop-card__thumb">
        ${thumbHtml}
        <button class="shop-card__fav" aria-label="保存" onclick="toggleFav(event,'${escHtml(shop.id)}',this)">♡</button>
      </div>
      <div class="shop-card__body">
        <p class="shop-card__name">${escHtml(shop.name)}</p>
        ${location ? `<p class="shop-card__location">📍 ${escHtml(location)}</p>` : ''}
        ${shop.description ? `<p class="shop-card__desc">${escHtml(shop.description)}</p>` : ''}
        ${memberHtml}
      </div>
    </a>`;
}

// ===========================
// 店舗詳細モーダル（layout/default.html用）
// ===========================
function openModal(shopId) {
  const shop = allShops.find(s => s.id === shopId);
  if (!shop) return;

  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');
  if (!overlay || !content) return;

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

  const visitedHtml    = shop.visited_date      ? `<p class="modal-visited-date">📅 ${formatDate(shop.visited_date)}訪問</p>` : '';
  const videoTitleHtml = shop.source_video_title ? `<p class="modal-video-title">🎬 ${escHtml(shop.source_video_title)}</p>` : '';

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
  if (!overlay) return;
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
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
    const id   = href.split('/shops/')[1]?.replace(/\//g,'').replace(/-/g,'_') || '';
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
  // 検索トグル
  const searchToggle = document.getElementById('search-toggle');
  if (searchToggle) {
    searchToggle.addEventListener('click', function() {
      const panel = document.getElementById('fbar-search-panel');
      if (!panel) return;
      const showing = panel.style.display !== 'none';
      panel.style.display = showing ? 'none' : '';
      this.classList.toggle('fbar__btn--active', !showing);
      if (!showing) document.getElementById('search-input')?.focus();
    });
  }

  // 検索入力
  document.getElementById('search-input')?.addEventListener('input', applyFilters);

  // ジャンル（hidden）
  document.getElementById('filter-genre')?.addEventListener('change', applyFilters);

  // グループモーダル
  document.getElementById('group-modal-open')?.addEventListener('click', openGroupModal);
  document.getElementById('group-modal-close')?.addEventListener('click', closeGroupModal);
  document.getElementById('group-modal-apply')?.addEventListener('click', applyGroupFilter);
  document.getElementById('group-modal-reset')?.addEventListener('click', () => {
    tempSelectedGroups.clear();
    renderGroupCheckList(document.getElementById('group-search-input')?.value || '');
    updateGroupModalApplyBtn();
  });
  document.getElementById('group-search-input')?.addEventListener('input', function() {
    renderGroupCheckList(this.value);
  });

  // エリアモーダル
  document.getElementById('area-modal-open')?.addEventListener('click', openAreaModal);
  document.getElementById('area-modal-close')?.addEventListener('click', closeAreaModal);
  document.getElementById('area-modal-apply')?.addEventListener('click', applyAreaFilter);
  document.getElementById('area-modal-reset')?.addEventListener('click', () => {
    tempSelectedPrefs.clear();
    renderAreaModalPC();
    renderAreaModalSP();
    updateAreaModalApplyBtn();
  });

  // オーバーレイクリックで閉じる
  document.getElementById('group-modal-overlay')?.addEventListener('click', function(e) {
    if (e.target === this) closeGroupModal();
  });
  document.getElementById('area-modal-overlay')?.addEventListener('click', function(e) {
    if (e.target === this) closeAreaModal();
  });

  // Escapeキーでモーダルを閉じる
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Escape') return;
    if (document.getElementById('group-modal-overlay')?.classList.contains('open')) closeGroupModal();
    else if (document.getElementById('area-modal-overlay')?.classList.contains('open')) closeAreaModal();
  });

  // ソート
  document.getElementById('sort-select')?.addEventListener('change', () => renderGrid(filteredShops));

  // タブ
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  // データ読み込み
  if (document.getElementById('shop-grid')) {
    loadShops();
  }
});
