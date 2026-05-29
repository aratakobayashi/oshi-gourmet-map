/**
 * filter.js
 * 統合フィルターモーダル（推し・エリア・人気 3タブ）
 * main.js の globals: selectedGroups, selectedPrefs, GROUP_LABELS, GROUP_SOLID_COLORS,
 *   GROUP_INITIALS, REGION_MAP, allShops, applyFilters, updateFilterBar, updateFilterChips, escHtml
 */

// ===========================
// ローカル定数
// ===========================
const GROUP_READINGS = {
  yonino:           'よにのちゃんねる',
  snowman:          'すのーまん',
  sixtones:         'すとーんず',
  equal_love:       'いこらぶ',
  notme:            'のっといこーるみー',
  neajoy:           'にあじょい',
  naniwa:           'なにわだんし',
  kamenashi:        'かめなしかずや',
  ginga:            'なかまるゆういち',
  kamaitachi:       'かまいたち',
  kodoku_no_gurume: 'こどくのぐるめ',
  heysayjump:       'へいせいじゃんぷ',
  nogizaka46:       'のぎざか',
  hinatazaka46:     'ひなたざか',
  sakurazaka46:     'さくらざか',
  timelesz:         'たいむれす',
  shiori:           'しおり',
  kingprince:       'きんぐあんどぷりんす',
  arashi:           'あらし',
  kimura:           'きむらたくや',
  kpop_enhypen:     'えんはいぷん',
  kpop_seventeen:   'せぶんてぃーん',
  kpop_riize:       'らいず',
  kpop_nct:         'えぬしーてぃー',
};

const GROUP_MEMBERS = {
  snowman:    ['岩本照','深澤辰哉','ラウール','渡辺翔太','向井康二','阿部亮平','目黒蓮','宮舘涼太','佐久間大介'],
  sixtones:   ['ジェシー','京本大我','松村北斗','髙地優吾','森本慎太郎','田中樹'],
  yonino:     ['二宮和也','山田涼介','菊池風磨','中丸雄一'],
  equal_love: ['音嶋莉沙','齊藤なぎさ','髙松瞳','大谷映美里','山本杏奈','野口衣織','瀧脇笙古','佐々木舞香'],
  notme:      ['櫻井もも','蟹沢萌子','鈴木瞳美','尾木波菜','永田詩央里'],
  naniwa:     ['西畑大吾','大橋和也','道枝駿佑','大西流星','高橋恭平','藤原丈一郎','長尾謙杜'],
  arashi:     ['大野智','櫻井翔','相葉雅紀','二宮和也','松本潤'],
  kimura:     ['木村拓哉'],
};

const MAJOR_CITIES = {
  '東京都':  ['渋谷区','新宿区','中央区','港区','千代田区','台東区','世田谷区','目黒区'],
  '大阪府':  ['大阪市','梅田','心斎橋','難波','天王寺'],
  '神奈川県':['横浜市','川崎市','鎌倉市'],
  '京都府':  ['京都市','祇園','嵐山'],
  '愛知県':  ['名古屋市','栄','金山'],
  '福岡県':  ['福岡市','博多','天神'],
};

const KANA_ROWS = ['あ','か','さ','た','な','は','ま','や','ら','わ'];

// 各かな文字 → 行の先頭文字
const CHAR_TO_ROW = (function() {
  const map = {};
  const rows = {
    'あ': 'あいうえお',
    'か': 'かきくけこがぎぐげご',
    'さ': 'さしすせそざじずぜぞ',
    'た': 'たちつてとだぢづでど',
    'な': 'なにぬねの',
    'は': 'はひふへほばびぶべぼぱぴぷぺぽ',
    'ま': 'まみむめも',
    'や': 'やゆよ',
    'ら': 'らりるれろ',
    'わ': 'わをんー',
  };
  Object.entries(rows).forEach(([row, chars]) => {
    for (const ch of chars) map[ch] = row;
  });
  // Latin / numeric → special bucket
  for (let c = 'a'.charCodeAt(0); c <= 'z'.charCodeAt(0); c++) {
    map[String.fromCharCode(c)] = 'わ'; // fallback; handled separately
  }
  return map;
})();

// ===========================
// モジュール状態
// ===========================
let _tempGroups    = new Set();
let _tempPrefs     = new Set();
let _filterTab     = 'popular';
let _kanaRow       = null;       // null = QUICK/人気 表示
let _activeRegion  = null;
let _filterGroups  = [];         // [{id,label,color,initial,reading,count,kanaRow,members}]
let _filterPrefs   = {};         // { region: [{name, count}] }
let _filterOpen    = false;
let _expandedGroup = null;
let _searchQuery   = '';

// ===========================
// 公開 API
// ===========================

/**
 * initFilterModal(shops)
 * data/shops.json ロード完了後に main.js から呼ぶ。
 */
function initFilterModal(shops) {
  // グループ一覧を構築
  const countMap = {};
  shops.forEach(s => {
    (s.groups || []).forEach(g => { countMap[g] = (countMap[g] || 0) + 1; });
  });

  _filterGroups = Object.keys(GROUP_LABELS).map(id => {
    const reading = GROUP_READINGS[id] || '';
    const firstChar = reading.charAt(0);
    const kanaRow = CHAR_TO_ROW[firstChar] || null;
    return {
      id,
      label:   GROUP_LABELS[id] || id,
      color:   GROUP_SOLID_COLORS[id] || '#b72a65',
      initial: GROUP_INITIALS[id] || (GROUP_LABELS[id] || id).charAt(0),
      reading,
      count:   countMap[id] || 0,
      kanaRow,
      members: GROUP_MEMBERS[id] || [],
    };
  }).filter(g => g.count > 0);

  _filterGroups.sort((a, b) => b.count - a.count);

  // 都道府県 → リージョン
  const prefCountMap = {};
  shops.forEach(s => {
    if (s.prefecture) prefCountMap[s.prefecture] = (prefCountMap[s.prefecture] || 0) + 1;
  });

  _filterPrefs = {};
  Object.entries(REGION_MAP).forEach(([region, prefs]) => {
    const available = prefs
      .filter(p => prefCountMap[p] > 0)
      .map(p => ({ name: p, count: prefCountMap[p] || 0 }));
    if (available.length) _filterPrefs[region] = available;
  });

  // 最初のリージョンをデフォルトに
  const firstRegion = Object.keys(_filterPrefs)[0] || null;
  _activeRegion = firstRegion;

  _registerEvents();
}

/**
 * openFilterModal(tab)
 * tab: 'popular' | 'talent' | 'pref'
 */
function openFilterModal(tab) {
  _tempGroups = new Set(selectedGroups);
  _tempPrefs  = new Set(selectedPrefs);
  _searchQuery = '';
  _expandedGroup = null;
  _kanaRow = null;

  const overlay = document.getElementById('filter-modal-overlay');
  if (!overlay) return;
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  _filterOpen = true;

  // 検索フィールドをリセット
  const searchEl = document.getElementById('filter-modal-search');
  if (searchEl) searchEl.value = '';

  _switchTab(tab || 'popular');

  // PC のみ自動フォーカス（SP はキーボードが即開くのを防ぐ）
  if (window.innerWidth > 768) {
    requestAnimationFrame(() => { if (searchEl) searchEl.focus(); });
  }
}

// ===========================
// 内部関数
// ===========================

function _registerEvents() {
  // フィルターバーの「推し」「エリア」ボタンを乗っ取る
  document.getElementById('group-modal-open')?.addEventListener('click', () => openFilterModal('talent'));
  document.getElementById('area-modal-open')?.addEventListener('click', () => openFilterModal('pref'));

  // 閉じる
  document.getElementById('filter-modal-close')?.addEventListener('click', _close);
  document.getElementById('filter-modal-overlay')?.addEventListener('click', function(e) {
    if (e.target === this) _close();
  });
  // Escapeキーは main.js 側で一元管理

  // タブ切り替え
  document.querySelectorAll('.fmodal__filter-tab').forEach(btn => {
    btn.addEventListener('click', () => _switchTab(btn.dataset.tab));
  });

  // 検索
  document.getElementById('filter-modal-search')?.addEventListener('input', function() {
    _searchQuery = this.value.trim().toLowerCase();
    if (_filterTab === 'talent') _renderTalent();
    else if (_filterTab === 'popular') _renderPopular();
    else if (_filterTab === 'pref') _renderPref();
  });

  // 適用 / リセット
  document.getElementById('filter-apply-btn')?.addEventListener('click', _apply);
  document.getElementById('filter-reset-all')?.addEventListener('click', _resetAll);
}

function _close() {
  const overlay = document.getElementById('filter-modal-overlay');
  if (overlay) {
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
  }
  document.body.style.overflow = '';
  _filterOpen = false;
}

function closeFilterModal() { _close(); }

function _apply() {
  selectedGroups = new Set(_tempGroups);
  selectedPrefs  = new Set(_tempPrefs);
  _close();
  applyFilters();
  updateFilterBar();
  updateFilterChips();
}

function _resetAll() {
  _tempGroups.clear();
  _tempPrefs.clear();
  _expandedGroup = null;
  _renderSelectedStack();
  _updateApplyBtn();
  if (_filterTab === 'popular') _renderPopular();
  else if (_filterTab === 'talent') _renderTalent();
  else if (_filterTab === 'pref') _renderPref();
}

function _switchTab(tab) {
  _filterTab = tab;

  // タブボタンのアクティブ状態
  document.querySelectorAll('.fmodal__filter-tab').forEach(btn => {
    btn.classList.toggle('fmodal__filter-tab--active', btn.dataset.tab === tab);
  });

  // ペインの表示切り替え
  ['popular','talent','pref'].forEach(t => {
    const pane = document.getElementById('pane-' + t);
    if (pane) pane.hidden = (t !== tab);
  });

  // 検索をクリア（タブをまたいで検索クエリが引き継がれるのを防ぐ）
  _searchQuery = '';
  const searchEl = document.getElementById('filter-modal-search');
  if (searchEl) {
    searchEl.value = '';
    if (tab === 'talent') searchEl.placeholder = 'グループ・タレント名で検索...';
    else if (tab === 'pref') searchEl.placeholder = '都道府県名で検索...';
    else searchEl.placeholder = 'グループ・エリア名で検索...';
  }

  if (tab === 'popular') _renderPopular();
  else if (tab === 'talent') _renderTalent();
  else if (tab === 'pref') _renderPref();

  _renderSelectedStack();
  _updateApplyBtn();
}

// ===========================
// Popular タブ
// ===========================
function _renderPopular() {
  _renderPopularTrending();
  _renderPopularTop10();
  _renderPopularAreas();
  _renderPopularRecent();
}

function _renderPopularTrending() {
  const el = document.getElementById('pane-popular-trending');
  if (!el) return;

  const q = _searchQuery;
  let groups = _filterGroups;
  if (q) groups = groups.filter(g => g.label.toLowerCase().includes(q) || g.reading.includes(q));

  // TOP3 をショートカットカードとして表示
  const top3 = groups.slice(0, 3);
  el.innerHTML = top3.map(g => {
    const sel = _tempGroups.has(g.id);
    return `<button class="fmodal-trend-card${sel ? ' fmodal-trend-card--sel' : ''}" data-gid="${escHtml(g.id)}"
      style="--gc:${escHtml(g.color)}">
      <span class="fmodal-trend-card__dot" style="background:${escHtml(g.color)}">${escHtml(g.initial)}</span>
      <span class="fmodal-trend-card__name">${escHtml(g.label)}</span>
      <span class="fmodal-trend-card__count">${g.count}件</span>
    </button>`;
  }).join('');

  el.querySelectorAll('.fmodal-trend-card').forEach(btn => {
    btn.addEventListener('click', () => {
      _toggleGroup(btn.dataset.gid);
      _renderPopularTrending();
      _renderPopularTop10();
    });
  });
}

function _renderPopularTop10() {
  const el = document.getElementById('pane-popular-top10');
  if (!el) return;

  const q = _searchQuery;
  let groups = _filterGroups;
  if (q) groups = groups.filter(g => g.label.toLowerCase().includes(q) || g.reading.includes(q));

  // 4位以降を表示（上位3件はトレンドカードと重複するため）
  const rest = q ? groups : groups.slice(3);
  el.innerHTML = rest.map((g, i) => {
    const rank = q ? i + 1 : i + 4;
    const sel = _tempGroups.has(g.id);
    return `<button class="fmodal-top10-item${sel ? ' fmodal-top10-item--sel' : ''}" data-gid="${escHtml(g.id)}">
      <span class="fmodal-top10-item__rank">${rank}</span>
      <span class="fmodal-top10-item__dot" style="background:${escHtml(g.color)}">${escHtml(g.initial)}</span>
      <span class="fmodal-top10-item__name">${escHtml(g.label)}</span>
      <span class="fmodal-top10-item__count">${g.count}件</span>
      <span class="fmodal-top10-item__check">${sel ? '✓' : ''}</span>
    </button>`;
  }).join('');

  el.querySelectorAll('.fmodal-top10-item').forEach(btn => {
    btn.addEventListener('click', () => {
      _toggleGroup(btn.dataset.gid);
      _renderPopularTrending();
      _renderPopularTop10();
    });
  });
}

function _renderPopularAreas() {
  const el = document.getElementById('pane-popular-areas');
  if (!el) return;

  const q = _searchQuery;

  // 都道府県をカウント順に並べ上位5件
  const allPrefs = Object.values(_filterPrefs).flat();
  allPrefs.sort((a, b) => b.count - a.count);
  let top5 = allPrefs.slice(0, 5);
  if (q) top5 = top5.filter(p => p.name.includes(q));

  el.innerHTML = top5.map(p => {
    const sel = _tempPrefs.has(p.name);
    return `<button class="fmodal-area-chip${sel ? ' fmodal-area-chip--sel' : ''}" data-pref="${escHtml(p.name)}">
      ${escHtml(p.name)}<span class="fmodal-area-chip__count"> ${p.count}</span>
    </button>`;
  }).join('');

  el.querySelectorAll('.fmodal-area-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      _togglePref(btn.dataset.pref);
      _renderPopularAreas();
    });
  });
}

function _renderPopularRecent() {
  const section = document.getElementById('pane-popular-recent-section');
  if (!section) return;

  let recent = [];
  try {
    recent = JSON.parse(localStorage.getItem('recent_oshi') || '[]');
  } catch(e) { recent = []; }

  const validRecent = recent.filter(id => _filterGroups.some(g => g.id === id)).slice(0, 4);
  if (!validRecent.length) { section.hidden = true; return; }
  section.hidden = false;

  const listEl = document.getElementById('pane-popular-recent');
  if (!listEl) return;

  listEl.innerHTML = validRecent.map(id => {
    const g = _filterGroups.find(x => x.id === id);
    if (!g) return '';
    const sel = _tempGroups.has(g.id);
    return `<button class="fmodal-top10-item${sel ? ' fmodal-top10-item--sel' : ''}" data-gid="${escHtml(g.id)}">
      <span class="fmodal-top10-item__dot" style="background:${escHtml(g.color)}">${escHtml(g.initial)}</span>
      <span class="fmodal-top10-item__name">${escHtml(g.label)}</span>
      <span class="fmodal-top10-item__count">${g.count}件</span>
      <span class="fmodal-top10-item__check">${sel ? '✓' : ''}</span>
    </button>`;
  }).join('');

  listEl.querySelectorAll('.fmodal-top10-item').forEach(btn => {
    btn.addEventListener('click', () => {
      _toggleGroup(btn.dataset.gid);
      _renderPopularRecent();
      _renderPopularTop10();
      _renderPopularTrending();
    });
  });
}

// ===========================
// Talent タブ
// ===========================
function _renderTalent() {
  _renderTalentKanaPane();
  _renderTalentList();
}

function _renderTalentKanaPane() {
  // PC: 左ペイン / SP: 水平スクロールタブ
  const pcPane = document.getElementById('talent-kana-pane');
  const spTabs = document.getElementById('talent-kana-sp-tabs');

  if (pcPane) {
    pcPane.innerHTML = _buildKanaPaneHTML();
    _attachKanaPaneEvents(pcPane);
  }
  if (spTabs) {
    spTabs.innerHTML = _buildKanaTabsHTML();
    _attachKanaPaneEvents(spTabs);
  }
}

function _buildKanaPaneHTML() {
  const quickButtons = [
    { key: null, label: '人気順', icon: '🔥' },
  ];
  const quickHtml = quickButtons.map(({ key, label, icon }) => {
    const active = _kanaRow === key;
    return `<button class="fmodal-kana-quick${active ? ' fmodal-kana-quick--active' : ''}" data-kana="${key === null ? '' : key}">${icon} ${label}</button>`;
  }).join('');

  const kanaHtml = KANA_ROWS.map(row => {
    const hasGroups = _filterGroups.some(g => g.kanaRow === row);
    const active = _kanaRow === row;
    return `<button class="fmodal-kana-btn${active ? ' fmodal-kana-btn--active' : ''}${!hasGroups ? ' fmodal-kana-btn--empty' : ''}"
      data-kana="${row}" ${!hasGroups ? 'disabled' : ''}>${row}</button>`;
  }).join('');

  return `<div class="fmodal-kana-quick-row">${quickHtml}</div><div class="fmodal-kana-grid">${kanaHtml}</div>`;
}

function _buildKanaTabsHTML() {
  const allBtn = `<button class="fmodal-kana-sp-tab${_kanaRow === null ? ' fmodal-kana-sp-tab--active' : ''}" data-kana="">すべて</button>`;
  const kanaBtns = KANA_ROWS.map(row => {
    const hasGroups = _filterGroups.some(g => g.kanaRow === row);
    const active = _kanaRow === row;
    return `<button class="fmodal-kana-sp-tab${active ? ' fmodal-kana-sp-tab--active' : ''}${!hasGroups ? ' fmodal-kana-sp-tab--empty' : ''}"
      data-kana="${row}" ${!hasGroups ? 'disabled' : ''}>${row}</button>`;
  }).join('');
  return allBtn + kanaBtns;
}

function _attachKanaPaneEvents(container) {
  container.querySelectorAll('[data-kana]').forEach(btn => {
    btn.addEventListener('click', () => {
      const val = btn.dataset.kana;
      _kanaRow = val === '' ? null : val;
      _renderTalent();
    });
  });
}

function _renderTalentList() {
  const listEl = document.getElementById('talent-group-list');
  if (!listEl) return;

  const q = _searchQuery;
  let groups = _filterGroups;

  if (q) {
    groups = groups.filter(g =>
      g.label.toLowerCase().includes(q) ||
      g.reading.includes(q) ||
      (g.members || []).some(m => m.includes(q))
    );
  } else if (_kanaRow !== null) {
    groups = groups.filter(g => g.kanaRow === _kanaRow);
  }

  if (!groups.length) {
    listEl.innerHTML = '<p class="fmodal-empty">該当するグループがありません</p>';
    return;
  }

  listEl.innerHTML = groups.map(g => {
    const sel = _tempGroups.has(g.id);
    const expanded = _expandedGroup === g.id;
    const hasMembers = g.members && g.members.length > 0;
    const memberHtml = hasMembers && expanded
      ? `<div class="fmodal-member-chips">
          ${g.members.map(m => `<button class="fmodal-member-chip" data-gid="${escHtml(g.id)}">${escHtml(m)}</button>`).join('')}
        </div>` : '';
    const expandBtn = hasMembers
      ? `<button class="fmodal-group-expand" data-gid="${escHtml(g.id)}" aria-expanded="${expanded}" aria-label="メンバー展開">${expanded ? '▲' : '▼'}</button>`
      : '';
    const hotBadge = g.count >= 50 ? `<span class="fmodal-hot-badge">HOT</span>` : '';
    return `<div class="fmodal-group-row${sel ? ' fmodal-group-row--sel' : ''}" data-gid="${escHtml(g.id)}">
      <div class="fmodal-group-row__main">
        <span class="fmodal-group-row__check fmodal-group-check" data-gid="${escHtml(g.id)}">
          <span class="fmodal-check-box${sel ? ' fmodal-check-box--on' : ''}">${sel ? '✓' : ''}</span>
        </span>
        <span class="fmodal-group-row__dot" style="background:${escHtml(g.color)}">${escHtml(g.initial)}</span>
        <span class="fmodal-group-row__info">
          <span class="fmodal-group-row__name">${escHtml(g.label)}</span>
          <span class="fmodal-group-row__reading">${escHtml(g.reading)}</span>
        </span>
        ${hotBadge}
        <span class="fmodal-group-row__count">${g.count}件</span>
        ${expandBtn}
      </div>
      ${memberHtml}
    </div>`;
  }).join('');

  // チェック（行クリック）
  listEl.querySelectorAll('.fmodal-group-check').forEach(el => {
    el.addEventListener('click', e => {
      e.stopPropagation();
      _toggleGroup(el.dataset.gid);
      _renderTalent();
      _saveRecentOshi(el.dataset.gid);
    });
  });

  // 行クリック（チェックと同じ）
  listEl.querySelectorAll('.fmodal-group-row__main').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.closest('.fmodal-group-expand') || e.target.closest('.fmodal-group-check')) return;
      const gid = el.closest('[data-gid]').dataset.gid;
      _toggleGroup(gid);
      _renderTalent();
      _saveRecentOshi(gid);
    });
  });

  // 展開ボタン
  listEl.querySelectorAll('.fmodal-group-expand').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const gid = btn.dataset.gid;
      _expandedGroup = (_expandedGroup === gid) ? null : gid;
      _renderTalentList();
    });
  });

  // メンバーチップ（グループ選択と同義）
  listEl.querySelectorAll('.fmodal-member-chip').forEach(chip => {
    chip.addEventListener('click', e => {
      e.stopPropagation();
      _toggleGroup(chip.dataset.gid);
      _saveRecentOshi(chip.dataset.gid);
      _renderTalent();
    });
  });
}

// ===========================
// Pref タブ
// ===========================
function _renderPref() {
  _renderPrefRegions();
  _renderPrefList();
}

function _renderPrefRegions() {
  const pcPane   = document.getElementById('pref-region-pane');
  const spScroll = document.getElementById('pref-region-sp-scroll');

  const regions = Object.keys(_filterPrefs);

  const makeItems = (wrapClass) => regions.map(r => {
    const active = _activeRegion === r;
    return `<button class="${wrapClass}${active ? ' ' + wrapClass + '--active' : ''}" data-region="${escHtml(r)}">${escHtml(r)}</button>`;
  }).join('');

  if (pcPane) {
    pcPane.innerHTML = makeItems('fmodal-region-item');
    pcPane.querySelectorAll('[data-region]').forEach(btn => {
      btn.addEventListener('click', () => { _activeRegion = btn.dataset.region; _renderPref(); });
    });
  }
  if (spScroll) {
    spScroll.innerHTML = makeItems('fmodal-region-sp-tab');
    spScroll.querySelectorAll('[data-region]').forEach(btn => {
      btn.addEventListener('click', () => { _activeRegion = btn.dataset.region; _renderPref(); });
    });
  }
}

function _renderPrefList() {
  const listEl = document.getElementById('pref-list');
  if (!listEl || !_activeRegion) return;

  const q = _searchQuery;
  let prefs = _filterPrefs[_activeRegion] || [];
  if (q) prefs = prefs.filter(p => p.name.includes(q));

  if (!prefs.length) {
    listEl.innerHTML = '<p class="fmodal-empty">該当するエリアがありません</p>';
    return;
  }

  const pillsHtml = prefs.map(p => {
    const sel = _tempPrefs.has(p.name);
    return `<button class="fmodal-pref-pill${sel ? ' fmodal-pref-pill--sel' : ''}" data-pref="${escHtml(p.name)}">
      ${escHtml(p.name)}<span class="fmodal-pref-pill__count">${p.count}</span>
    </button>`;
  }).join('');

  // 選択中の都道府県の主要エリアを表示
  const selectedInRegion = prefs.filter(p => _tempPrefs.has(p.name));
  let cityDrillHtml = '';
  selectedInRegion.forEach(p => {
    const cities = MAJOR_CITIES[p.name];
    if (cities && cities.length) {
      cityDrillHtml += `<div class="fmodal-city-drill">
        <p class="fmodal-city-drill__label">${escHtml(p.name)}の主要エリア（参考）</p>
        <div class="fmodal-city-chips">
          ${cities.map(c => `<span class="fmodal-city-chip">${escHtml(c)}</span>`).join('')}
        </div>
      </div>`;
    }
  });

  listEl.innerHTML = `<div class="fmodal-pref-pills">${pillsHtml}</div>${cityDrillHtml}`;

  listEl.querySelectorAll('.fmodal-pref-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      _togglePref(btn.dataset.pref);
      _renderPrefList();
    });
  });
}

// ===========================
// 選択スタック + 適用ボタン
// ===========================
function _renderSelectedStack() {
  const el = document.getElementById('filter-selected');
  if (!el) return;

  const groupChips = [..._tempGroups].map(id => {
    const g = _filterGroups.find(x => x.id === id);
    if (!g) return '';
    return `<span class="fmodal-sel-chip" style="background:${escHtml(g.color)}20;border:1px solid ${escHtml(g.color)}50;color:${escHtml(g.color)}">
      ${escHtml(g.label)}
      <button class="fmodal-sel-chip__remove" data-type="group" data-val="${escHtml(id)}" aria-label="外す">×</button>
    </span>`;
  });

  const prefChips = [..._tempPrefs].map(p =>
    `<span class="fmodal-sel-chip fmodal-sel-chip--pref">
      ${escHtml(p)}
      <button class="fmodal-sel-chip__remove" data-type="pref" data-val="${escHtml(p)}" aria-label="外す">×</button>
    </span>`
  );

  const all = groupChips.concat(prefChips).filter(Boolean);
  if (!all.length) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = all.join('');

  el.querySelectorAll('.fmodal-sel-chip__remove').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.type === 'group') _tempGroups.delete(btn.dataset.val);
      else _tempPrefs.delete(btn.dataset.val);
      _renderSelectedStack();
      _updateApplyBtn();
      if (_filterTab === 'popular') _renderPopular();
      else if (_filterTab === 'talent') _renderTalent();
      else if (_filterTab === 'pref') _renderPref();
    });
  });
}

function _updateApplyBtn() {
  const btn = document.getElementById('filter-apply-btn');
  if (!btn) return;
  if (!allShops || !allShops.length) return;

  const total = allShops.length;

  if (_tempGroups.size === 0 && _tempPrefs.size === 0) {
    btn.textContent = `${total}件のお店を見る →`;
    return;
  }

  const count = allShops.filter(s => {
    const groupOk = _tempGroups.size === 0 || (s.groups || []).some(g => _tempGroups.has(g));
    const prefOk  = _tempPrefs.size === 0  || _tempPrefs.has(s.prefecture);
    return groupOk && prefOk;
  }).length;

  btn.textContent = `${count}件を見る →`;
}

// ===========================
// ヘルパー
// ===========================
function _toggleGroup(id) {
  if (_tempGroups.has(id)) _tempGroups.delete(id);
  else _tempGroups.add(id);
  _renderSelectedStack();
  _updateApplyBtn();
}

function _togglePref(name) {
  if (_tempPrefs.has(name)) _tempPrefs.delete(name);
  else _tempPrefs.add(name);
  _renderSelectedStack();
  _updateApplyBtn();
}

function _saveRecentOshi(id) {
  try {
    let recent = JSON.parse(localStorage.getItem('recent_oshi') || '[]');
    recent = [id, ...recent.filter(x => x !== id)].slice(0, 6);
    localStorage.setItem('recent_oshi', JSON.stringify(recent));
  } catch(e) {}
}
