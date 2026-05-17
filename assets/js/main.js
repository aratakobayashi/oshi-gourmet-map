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
let activeRegion       = null;
let userLat            = null;
let userLng            = null;
let displayCount       = 120;
let currentSortedShops = [];
const PAGE_SIZE        = 120;

// ===========================
// データ読み込み
// ===========================
async function loadShops() {
  const res = await fetch(SHOPS_URL);
  allShops = await res.json();
  filteredShops = [...allShops];

  populateFilters();
  initFromUrlParams();
  initPlaceholderRotation(allShops);

  if (typeof initFilterModal === 'function') initFilterModal(allShops);

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
  renderGenrePills(genres);
}

function renderGenrePills(genres) {
  const container = document.getElementById('genre-pills');
  if (!container) return;
  const currentGenre = document.getElementById('filter-genre')?.value || '';
  const pills = [{ value: '', label: 'すべて' }].concat(
    genres.map(g => ({ value: g, label: (GENRE_ICONS[g] ? GENRE_ICONS[g] + ' ' : '') + g }))
  );
  container.innerHTML = pills.map(({ value, label }) =>
    `<button class="genre-pill${value === currentGenre ? ' active' : ''}" data-genre="${escHtml(value)}">${escHtml(label)}</button>`
  ).join('');
  container.querySelectorAll('.genre-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('filter-genre').value = btn.dataset.genre;
      container.querySelectorAll('.genre-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyFilters();
      updateFilterChips();
    });
  });
}

function initPlaceholderRotation(shops) {
  const input = document.getElementById('search-input');
  if (!input) return;

  const members = [...new Set(shops.flatMap(s => s.members || []))].filter(Boolean);
  const shuffle = arr => {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };
  const samples = shuffle([
    ...members.slice(0, 12).map(m => `「${m}」で検索`),
    '「渋谷」で検索',
    '「ラーメン」で検索',
    '「Snow Man」で検索',
    '「浅草」で検索',
  ]);

  let idx = 0;
  const rotate = () => {
    if (document.activeElement === input || input.value) return;
    input.placeholder = samples[idx % samples.length] + '...';
    idx++;
  };
  rotate();
  setInterval(rotate, 3000);
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

  const currentGenre = document.getElementById('filter-genre')?.value || '';
  const hasGroups = selectedGroups.size > 0;
  const hasPrefs  = selectedPrefs.size > 0;
  const hasGenre  = !!currentGenre;

  if (!hasGroups && !hasPrefs && !hasGenre) {
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

  const genreChips = hasGenre ? [
    `<span class="fbar__chip fbar__chip--genre">
      ${escHtml((GENRE_ICONS[currentGenre] || '') + ' ' + currentGenre)}
      <button class="fbar__chip__remove" id="genre-chip-remove" aria-label="${escHtml(currentGenre)}を外す">×</button>
    </span>`
  ] : [];

  container.innerHTML = groupChips.concat(prefChips).concat(genreChips).join('');

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

  document.getElementById('genre-chip-remove')?.addEventListener('click', () => {
    document.getElementById('filter-genre').value = '';
    document.querySelectorAll('.genre-pill').forEach(b => b.classList.toggle('active', b.dataset.genre === ''));
    applyFilters();
    updateFilterChips();
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
// ソート
// ===========================
function getSortMode() {
  return document.getElementById('sort-select')?.value || 'recent';
}

function sortShops(shops) {
  const mode = getSortMode();
  if (mode === 'nearby' && userLat !== null) {
    return [...shops].sort((a, b) => {
      const da = (a.lat && a.lng) ? haversineDistance(userLat, userLng, a.lat, a.lng) : Infinity;
      const db = (b.lat && b.lng) ? haversineDistance(userLat, userLng, b.lat, b.lng) : Infinity;
      return da - db;
    });
  }
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
  currentSortedShops = sortShops(shops);
  displayCount = PAGE_SIZE;
  window.scrollTo(0, 0);

  const grid = document.getElementById('shop-grid');
  if (!grid) return;

  if (currentSortedShops.length === 0) {
    renderMoreButton();
    const query = document.getElementById('search-input')?.value.trim() || '';
    const hasFilter = selectedGroups.size > 0 || selectedPrefs.size > 0
      || !!document.getElementById('filter-genre')?.value;

    const groupSuggestions = query
      ? Object.entries(GROUP_LABELS).filter(([k, v]) =>
          v.includes(query) || k.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 3)
      : [];

    const suggestHtml = groupSuggestions.length
      ? `<p class="no-results__suggest-label">もしかして:</p>
         <div class="no-results__suggest-btns">
           ${groupSuggestions.map(([k, v]) =>
             `<button class="no-results__suggest-btn" data-group="${escHtml(k)}">${escHtml(v)}</button>`
           ).join('')}
         </div>`
      : '';

    grid.innerHTML = `
      <div class="no-results">
        <p class="no-results__icon">🔍</p>
        <p class="no-results__text">「${escHtml(query || 'この条件')}」に一致するお店が見つかりませんでした。</p>
        ${suggestHtml}
        ${hasFilter
          ? `<button class="no-results__reset" id="no-results-reset">フィルターをすべてリセット →</button>`
          : ''}
      </div>`;

    grid.querySelectorAll('.no-results__suggest-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const input = document.getElementById('search-input');
        if (input) { input.value = ''; document.getElementById('search-clear').hidden = true; }
        document.getElementById('filter-genre').value = '';
        document.querySelectorAll('.genre-pill').forEach(b => b.classList.toggle('active', b.dataset.genre === ''));
        selectedGroups.clear();
        selectedGroups.add(btn.dataset.group);
        selectedPrefs.clear();
        applyFilters(); updateFilterBar(); updateFilterChips();
      });
    });

    document.getElementById('no-results-reset')?.addEventListener('click', () => {
      const input = document.getElementById('search-input');
      if (input) { input.value = ''; }
      const clearBtn = document.getElementById('search-clear');
      if (clearBtn) clearBtn.hidden = true;
      document.getElementById('filter-genre').value = '';
      document.querySelectorAll('.genre-pill').forEach(b => b.classList.toggle('active', b.dataset.genre === ''));
      selectedGroups.clear();
      selectedPrefs.clear();
      applyFilters(); updateFilterBar(); updateFilterChips();
    });
    return;
  }

  grid.innerHTML = currentSortedShops.slice(0, displayCount).map(s => buildShopCard(s)).join('');
  restoreFavButtons();
  renderMoreButton();
}

function renderMoreButton() {
  const btnWrap = document.getElementById('more-btn-wrap');
  if (!btnWrap) return;

  if (!currentSortedShops.length || displayCount >= currentSortedShops.length) {
    btnWrap.innerHTML = '';
    return;
  }

  const remaining = currentSortedShops.length - displayCount;
  btnWrap.innerHTML = `<button class="more-btn" id="more-btn">もっと見る（残り${remaining}件）</button>`;

  document.getElementById('more-btn').addEventListener('click', () => {
    const btn = document.getElementById('more-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="more-btn__spinner"></span>';

    const newItems = currentSortedShops.slice(displayCount, displayCount + PAGE_SIZE);
    displayCount += PAGE_SIZE;

    const grid = document.getElementById('shop-grid');
    const tpl = document.createElement('template');
    tpl.innerHTML = newItems.map(s => buildShopCard(s)).join('');
    grid.append(tpl.content);
    restoreFavButtons();
    renderMoreButton();
  });
}

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

  const thumbHtml = thumb
    ? `<img src="${thumb}" alt="${escHtml(shop.name)}" loading="lazy">
       <div class="shop-card__play"><div class="shop-card__play-icon">▶</div></div>`
    : `<div class="shop-card__banner" style="background:${gradient}">
         <span class="shop-card__banner-icon">${icon}</span>
         <span class="shop-card__banner-genre">${escHtml(shop.genre || '')}</span>
       </div>`;

  const locationParts = [shop.prefecture, shop.city].filter(Boolean);
  const location = locationParts.length
    ? locationParts.join(' ')
    : (shop.nearest_station ? shop.nearest_station + '付近' : '');

  const metaRow = group || shop.genre
    ? `<div class="shop-card__meta-row">
        ${group ? `<span class="shop-card__group-label" style="color:${solidColor}">${escHtml(groupLabel)}</span>` : ''}
        ${group && shop.genre ? `<span class="shop-card__sep">·</span>` : ''}
        ${shop.genre ? `<span class="shop-card__genre">${escHtml(shop.genre)}</span>` : ''}
      </div>` : '';

  const memberFirst = (shop.members || [])[0] || '';
  const memberHtml  = memberFirst ? `<p class="shop-card__member">👤 ${escHtml(memberFirst)}</p>` : '';

  const visitedHtml = shop.visited_date
    ? `<p class="shop-card__visited">📅 ${formatVisited(shop.visited_date)}</p>` : '';

  const videoIcon = shop.source_type ? '📺' : '🎬';
  const videoHtml = shop.source_video_title
    ? `<p class="shop-card__video">${videoIcon} ${escHtml(shop.source_video_title)}</p>` : '';

  const distHtml = (userLat !== null && getSortMode() === 'nearby' && shop.lat && shop.lng)
    ? `<p class="shop-card__distance">🧭 ${haversineDistance(userLat, userLng, shop.lat, shop.lng).toFixed(1)} km</p>`
    : '';

  const shopSlug = shop.id.replace(/_/g, '-').replace(/-{2,}/g, '-').replace(/-+$/g, '');
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
        ${distHtml}
        ${memberHtml}
        ${visitedHtml}
        ${videoHtml}
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
function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function showToast(message) {
  const existing = document.getElementById('shop-toast');
  if (existing) existing.remove();
  const el = document.createElement('div');
  el.id = 'shop-toast';
  el.className = 'shop-toast';
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('shop-toast--show'));
  setTimeout(() => {
    el.classList.remove('shop-toast--show');
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

function requestGeolocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) { reject(new Error('unsupported')); return; }
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      err => reject(err),
      { timeout: 8000 }
    );
  });
}

function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const [y, m, d] = dateStr.split('-');
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

function formatVisited(dateStr) {
  if (!dateStr) return '';
  const [y, m] = dateStr.split('-');
  return `${y}年${parseInt(m)}月`;
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
  // 検索入力 + クリアボタン
  document.getElementById('search-input')?.addEventListener('input', function() {
    const btn = document.getElementById('search-clear');
    if (btn) btn.hidden = !this.value;
    applyFilters();
  });
  document.getElementById('search-clear')?.addEventListener('click', () => {
    const input = document.getElementById('search-input');
    if (input) { input.value = ''; input.focus(); }
    const btn = document.getElementById('search-clear');
    if (btn) btn.hidden = true;
    applyFilters();
  });

  // ジャンル（hidden）
  document.getElementById('filter-genre')?.addEventListener('change', applyFilters);

  // Escapeキーでモーダルを閉じる
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Escape') return;
    if (typeof closeFilterModal === 'function') closeFilterModal();
  });

  // ソート（近い順はGeolocation取得を待つ）
  document.getElementById('sort-select')?.addEventListener('change', async function() {
    if (this.value === 'nearby') {
      if (userLat !== null) {
        renderGrid(filteredShops);
        return;
      }
      this.disabled = true;
      try {
        const { lat, lng } = await requestGeolocation();
        userLat = lat;
        userLng = lng;
        renderGrid(filteredShops);
      } catch {
        this.value = 'recent';
        showToast('現在地を取得できませんでした。位置情報の許可を確認してください。');
        renderGrid(filteredShops);
      } finally {
        this.disabled = false;
      }
    } else {
      renderGrid(filteredShops);
    }
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
