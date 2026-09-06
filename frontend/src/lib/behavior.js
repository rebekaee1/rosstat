/**
 * behavior.js — пассивный поведенческий сбор («видеокамера» сайта).
 *
 * Отличие от track.js: track.js — ручные бизнес-события (90 именованных целей,
 * дублируются в Метрику), а этот модуль собирает СЫРОЙ поведенческий поток без
 * ручной разметки, под data science:
 *
 *   - session_start один раз за сессию: портрет посетителя (user-agent,
 *                    экран, язык, таймзона, referrer, UTM) → behavior_sessions;
 *   - pageview      каждый переход по роутам SPA (+ первый заход);
 *   - click         КАЖДЫЙ клик: иерархический путь элемента, текст, координаты,
 *                    признаки dead (некликабельная цель) и rage (серия злых кликов);
 *   - move          траектория мыши: сэмплированная полилиния [x,y,dt] за окно
 *                    флеша (страница прореживается порогом расстояния);
 *   - dwell         уход со страницы: время на ней (по стене И активное,
 *                    visibility-aware), максимум скролла, счётчики кликов;
 *   - copy          что пользователь скопировал (первые 120 символов выделения);
 *   - vital         Web Vitals (LCP/INP/CLS/FCP/TTFB) — скорость глазами клиента;
 *   - js_error      onerror + unhandledrejection: стек, версия сборки;
 *   - api_timing    латентность /api/* глазами клиента (сэмпл 1 из 5);
 *   - block_view    блочная аналитика: время видимости [data-block]-секций;
 *   - form          воронка форм без снятия текста (фокус → submit).
 *
 * Идентичность: постоянный visitor_id (localStorage, живёт годами — аналог
 * clientID Метрики) уходит в каждом батче; _ym_uid из куки Метрики в
 * session_start даёт ретро-мост к повизитной истории raw_metrika_visits.
 *
 * Транспорт: буфер в памяти → sendBeacon на /api/v1/analytics/behavior батчами
 * (интервал 10 с / 60 событий / pagehide). При 100k посетителей/день это даёт
 * порядка сотен вставок в секунду в пике — держится bulk-insert'ом на бэке.
 *
 * Приватность (152-ФЗ): не перехватываем ввод в поля (keystroke-логирования
 * нет), текст не снимается с input/textarea/[contenteditable], явный отказ от
 * аналитики в актуальной редакции политики (fe:consent:v1) отключает сбор.
 * Не работает на /embed/* (iframe на чужих сайтах).
 */

const ENDPOINT = '/api/v1/analytics/behavior';
const SESSION_KEY = 'fe:analytics:session';
const SESSION_META_KEY = 'fe:analytics:session:meta';
const VISITOR_KEY = 'fe:analytics:visitor';
const CONSENT_KEY = 'fe:consent:v1';
const CONSENT_V = '2026-06-16';

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_AT_QUEUE = 60;
const MOVE_SAMPLE_MS = 120;      // не чаще одной точки в 120 мс
const MOVE_MIN_DIST = 12;        // и только если сдвиг > 12px
const MOVE_MAX_POINTS = 240;     // жёсткий потолок точек на один move-батч
const RAGE_WINDOW_MS = 700;
const RAGE_RADIUS = 28;
const RAGE_COUNT = 3;

const INTERACTIVE = 'a,button,input,select,textarea,label,summary,[role="button"],[role="link"],[role="tab"],[role="menuitem"],[role="option"],[role="switch"],[onclick]';
const NO_TEXT_CAPTURE = 'input,textarea,[contenteditable="true"]';

const ACTIVE_GAP_MS = 15_000;    // разрыв активности больше — время не «активное»
const ERRORS_MAX_PER_PAGE = 10;  // потолок js_error с одной страницы
const API_TIMING_SAMPLE = 5;     // латентность API — каждый 5-й запрос
const BLOCK_RESCAN_MS = 3_000;   // как часто искать новые [data-block] в DOM

/** Headless-ферма и вкладка Cursor не должны писать behavior/events. */
export function isAutomationUa(ua, webdriver = false) {
  if (webdriver) return true;
  return /HeadlessChrome|Cursor\//i.test(ua || '');
}

export function isAutomationClient() {
  if (typeof navigator === 'undefined') return false;
  return isAutomationUa(navigator.userAgent, navigator.webdriver === true);
}

let _queue = [];
let _identity = { authed: false, userId: null };
let _pageLoadId = null;
let _pageEnteredAt = 0;
let _pageUrl = null;
let _maxScrollPct = 0;
let _clickCount = 0;
let _moveDistance = 0;
let _movePoints = [];
let _lastMove = { x: 0, y: 0, t: 0 };
let _recentClicks = [];
let _timer = null;
let _inited = false;
let _enabled = true;
// активное время: суммируем разрывы между действиями, если разрыв < ACTIVE_GAP_MS
let _activeMs = 0;
let _lastActivityTs = 0;
let _errorCount = 0;
let _apiCallCounter = 0;
// блочная аналитика: имя блока → { enter: ts|null, ms: суммарно видим }
let _blocks = new Map();
let _blockObserver = null;
let _blockTimer = null;
let _formsSeen = new Set();

function sessionId() {
  try {
    let v = window.sessionStorage.getItem(SESSION_KEY);
    if (!v) {
      v = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      window.sessionStorage.setItem(SESSION_KEY, v);
    }
    return v;
  } catch {
    return null;
  }
}

/** Постоянный идентификатор посетителя (аналог clientID Метрики): UUID в
 * localStorage, живёт годами, склеивает сессии одного человека. */
export function visitorId() {
  try {
    let v = window.localStorage.getItem(VISITOR_KEY);
    if (!v) {
      v = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
      window.localStorage.setItem(VISITOR_KEY, v);
    }
    return v;
  } catch {
    return null;
  }
}

/** _ym_uid из first-party куки Метрики — ретро-мост к её повизитной истории. */
function ymUid() {
  try {
    const m = document.cookie.match(/(?:^|;\s*)_ym_uid=([^;]+)/);
    return m ? decodeURIComponent(m[1]).slice(0, 40) : null;
  } catch {
    return null;
  }
}

function markActivity() {
  const now = Date.now();
  if (_lastActivityTs && now - _lastActivityTs < ACTIVE_GAP_MS) {
    _activeMs += now - _lastActivityTs;
  }
  _lastActivityTs = now;
}

function consentAllows() {
  // Подразумеваемое согласие; уважаем только явный отказ текущей редакции.
  try {
    const raw = window.localStorage.getItem(CONSENT_KEY);
    if (!raw) return true;
    const rec = JSON.parse(raw);
    if (rec && rec.v === CONSENT_V && rec.analytics === false) return false;
  } catch { /* ignore */ }
  return true;
}

function newPageLoadId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Иерархический путь элемента: страница → блок → элемент. Идентификаторы в
 * приоритете: id > data-track > aria-label > короткие классы > nth-of-type.
 * Tailwind-утилиты (px-6, hover:...) отбрасываются как шум.
 */
function elementPath(el, maxDepth = 6) {
  const parts = [];
  let node = el;
  while (node && node.nodeType === 1 && parts.length < maxDepth && node.tagName !== 'HTML') {
    let part = node.tagName.toLowerCase();
    if (node.id) {
      part += `#${node.id}`;
      parts.unshift(part);
      break; // id уникален — выше подниматься незачем
    }
    const track = node.getAttribute('data-track') || node.getAttribute('aria-label');
    if (track) {
      part += `[${track.slice(0, 32)}]`;
    } else {
      const cls = Array.from(node.classList)
        .filter((c) => c.length <= 24 && !/[:[]/.test(c) && !/^(px|py|pt|pb|pl|pr|mx|my|mt|mb|ml|mr|w|h|gap|text|bg|border|rounded|flex|grid|items|justify|hover|focus|transition|duration|font|leading|tracking|shadow|opacity|z|top|left|right|bottom|absolute|relative|inline|block|hidden|overflow|max|min|space|divide|cursor|select|whitespace|break|order|col|row|self|place|content|sr)-/.test(c) && !['flex', 'grid', 'block', 'hidden', 'relative', 'absolute', 'container', 'group', 'peer', 'truncate', 'uppercase', 'lowercase', 'capitalize', 'italic', 'underline', 'antialiased'].includes(c))
        .slice(0, 2);
      if (cls.length) {
        part += `.${cls.join('.')}`;
      } else if (node.parentElement) {
        const same = Array.from(node.parentElement.children).filter((s) => s.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
    }
    parts.unshift(part);
    node = node.parentElement;
  }
  return parts.join(' > ').slice(0, 380);
}

function elementText(el) {
  if (el.closest(NO_TEXT_CAPTURE)) return null; // не снимаем пользовательский ввод
  const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
  return t ? t.slice(0, 100) : null;
}

function cleanUrl() {
  return window.location.pathname + window.location.search;
}

function push(type, fields) {
  if (!_enabled) return;
  _queue.push({
    t: type,
    ts: Date.now(),
    url: _pageUrl || cleanUrl(),
    pl: _pageLoadId,
    ...fields,
  });
  if (_queue.length >= FLUSH_AT_QUEUE) flush();
}

function drainMoves() {
  if (_movePoints.length < 2) { _movePoints = []; return; }
  const pts = _movePoints;
  _movePoints = [];
  push('move', { pts, n: pts.length });
}

function batchId() {
  return (window.crypto && window.crypto.randomUUID)
    ? window.crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function flush() {
  drainMoves();
  if (!_queue.length) return;
  const events = _queue;
  _queue = [];
  // batch_id — идемпотентность на инжесте: sendBeacon умеет ретраить,
  // сервер дедуплицирует повторную доставку того же батча (Redis SETNX).
  const hasPortrait = events.some((e) => e.t === 'session_start');
  const body = JSON.stringify({
    session_id: sessionId(),
    visitor_id: visitorId(),
    authed: _identity.authed ? 1 : 0,
    batch_id: batchId(),
    events,
  });
  try {
    // Батч с портретом шлём через fetch: только подтверждённая доставка
    // (resp.ok) помечает session_start отправленным — иначе портрет
    // переотправится на следующем pageview (сервер идемпотентен).
    if (!hasPortrait && navigator.sendBeacon) {
      const ok = navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
      if (ok) return;
    }
    fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true })
      .then((resp) => {
        if (hasPortrait && resp && resp.ok) {
          try { window.sessionStorage.setItem(SESSION_META_KEY, '1'); } catch { /* ignore */ }
        }
      })
      .catch(() => {});
  } catch { /* телеметрия никогда не ломает UX */ }
}

const DWELL_MAX_MS = 4 * 3600 * 1000; // страховка от вкладок, забытых на ночь

function emitDwell() {
  if (!_pageLoadId || !_pageEnteredAt) return;
  markActivity();
  const now = Date.now();
  const ms = Math.min(now - _pageEnteredAt, DWELL_MAX_MS);
  push('dwell', {
    ms,
    active_ms: Math.min(_activeMs, ms),
    scroll_pct: _maxScrollPct,
    clicks: _clickCount,
    move_px: Math.round(_moveDistance),
  });
  // Сегментация: dwell закрывает отрезок и обнуляет счётчики — повторный
  // visibilitychange не дублирует уже отправленное время (лечит dwell > 4ч).
  _pageEnteredAt = now;
  _activeMs = 0;
  _clickCount = 0;
  _moveDistance = 0;
}

/** Блочная аналитика: закрыть учёт видимости и отправить по событию на блок. */
function emitBlockViews() {
  const now = Date.now();
  for (const [name, rec] of _blocks) {
    if (rec.enter) { rec.ms += now - rec.enter; rec.enter = null; }
    if (rec.ms >= 500) push('block_view', { block: name, ms: Math.round(rec.ms) });
  }
  _blocks = new Map();
}

function observeBlocksNow() {
  if (!_blockObserver) return;
  document.querySelectorAll('[data-block]').forEach((el) => {
    if (el.__feBlockObserved) return;
    el.__feBlockObserved = true;
    _blockObserver.observe(el);
  });
}

function setupBlockObserver() {
  if (typeof IntersectionObserver === 'undefined') return;
  _blockObserver = new IntersectionObserver((entries) => {
    const now = Date.now();
    for (const entry of entries) {
      const name = entry.target.getAttribute('data-block');
      if (!name) continue;
      let rec = _blocks.get(name);
      if (!rec) { rec = { enter: null, ms: 0 }; _blocks.set(name, rec); }
      if (entry.isIntersecting && !rec.enter) rec.enter = now;
      else if (!entry.isIntersecting && rec.enter) { rec.ms += now - rec.enter; rec.enter = null; }
    }
  }, { threshold: 0.5 });
  observeBlocksNow();
  _blockTimer = setInterval(observeBlocksNow, BLOCK_RESCAN_MS);
}

/**
 * Портрет сессии (session_start) — один раз за сессию: user-agent, экран,
 * язык, таймзона, referrer и UTM точки входа. Серверная сторона разбирает UA
 * в браузер/ОС/устройство (behavior_sessions) — собственный аналог визита
 * Метрики, чтобы знать аудиторию своими данными и сверять с Метрикой.
 */
function emitSessionStart() {
  // Флаг ставит flush() ТОЛЬКО после подтверждённой доставки (resp.ok) —
  // при потере батча портрет переотправится со следующей страницы
  // (сервер идемпотентен по session_id_hash). Лечит «сессии без портрета».
  try {
    if (window.sessionStorage.getItem(SESSION_META_KEY)) return;
  } catch { return; }
  let tz = null;
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch { /* ignore */ }
  const q = new URLSearchParams(window.location.search);
  const ATTR_KEYS = ['ysclid', 'yclid', 'gclid', 'fbclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_referrer', 'etext'];
  try {
    const fromRef = new URL(document.referrer).searchParams;
    for (const key of ATTR_KEYS) {
      if (!q.get(key) && fromRef.get(key)) q.set(key, fromRef.get(key));
    }
  } catch { /* referrer пуст или чужой origin без query */ }
  try {
    const fromWin = window.__feAttr || {};
    for (const key of ATTR_KEYS) {
      if (!q.get(key) && fromWin[key]) q.set(key, fromWin[key]);
    }
  } catch { /* нет моста от consent.js */ }
  try {
    const cm = document.cookie.match(/(?:^|; )fe_attr=([^;]*)/);
    if (cm) {
      const fromCk = new URLSearchParams(decodeURIComponent(cm[1].replace(/\+/g, ' ')));
      for (const key of ATTR_KEYS) {
        if (!q.get(key) && fromCk.get(key)) q.set(key, fromCk.get(key));
      }
    }
  } catch { /* нет куки */ }
  const conn = navigator.connection || null;
  let theme = null;
  try { theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; } catch { /* ignore */ }
  let orient = null;
  try { orient = (window.screen.orientation && window.screen.orientation.type) ? (window.screen.orientation.type.startsWith('portrait') ? 'portrait' : 'landscape') : null; } catch { /* ignore */ }
  push('session_start', {
    ua: (navigator.userAgent || '').slice(0, 500),
    ref: (function () {
      const stamped = q.get('utm_referrer') || '';
      const raw = document.referrer || '';
      try {
        if (!raw) return stamped || null;
        const rh = new URL(raw).hostname.replace(/^www\./, '');
        const host = (location.hostname || '').replace(/^www\./, '');
        const apex = host.replace(/^ru\./, '');
        if (rh === host || rh === apex || rh === `ru.${apex}`) return stamped || raw;
      } catch { /* чужой referrer */ }
      return raw || stamped || null;
    })(),
    sw: (window.screen && window.screen.width) || null,
    sh: (window.screen && window.screen.height) || null,
    vw: window.innerWidth,
    vh: window.innerHeight,
    dpr: Math.round((window.devicePixelRatio || 1) * 100) / 100,
    lang: (navigator.language || '').slice(0, 16) || null,
    tz,
    touch: 'ontouchstart' in window ? 1 : 0,
    us: q.get('utm_source'),
    um: q.get('utm_medium'),
    uc: q.get('utm_campaign'),
    ut: q.get('utm_term'),
    uco: q.get('utm_content'),
    yclid: q.get('yclid'),
    ysclid: q.get('ysclid'),
    ur: q.get('utm_referrer'),
    etext: q.get('etext'),
    ymuid: ymUid(),
    conn: conn && conn.effectiveType ? String(conn.effectiveType).slice(0, 16) : null,
    dl: conn && typeof conn.downlink === 'number' ? conn.downlink : null,
    dm: typeof navigator.deviceMemory === 'number' ? navigator.deviceMemory : null,
    hc: typeof navigator.hardwareConcurrency === 'number' ? navigator.hardwareConcurrency : null,
    theme,
    orient,
    wd: navigator.webdriver ? 1 : 0,
  });
}

/** Web Vitals глазами клиента: LCP/INP/CLS/FCP/TTFB с рейтингом. Динамический
 * импорт — библиотека не попадает в критический путь загрузки. */
function setupVitals() {
  import('web-vitals').then(({ onLCP, onINP, onCLS, onFCP, onTTFB }) => {
    const report = (m) => push('vital', {
      m: m.name,
      v: Math.round(m.value * (m.name === 'CLS' ? 1000 : 1)) / (m.name === 'CLS' ? 1000 : 1),
      rating: m.rating,
    });
    onLCP(report); onINP(report); onCLS(report); onFCP(report); onTTFB(report);
  }).catch(() => { /* vitals опциональны */ });
}

/** JS-ошибки: onerror + unhandledrejection + упавшие ресурсы. Версия сборки
 * (__BUILD_ID__ подставляет Vite) привязывает регрессии к деплоям. */
function setupErrorCapture() {
  const build = (typeof __BUILD_ID__ !== 'undefined' && __BUILD_ID__) || null;
  window.addEventListener('error', (e) => {
    if (_errorCount >= ERRORS_MAX_PER_PAGE) return;
    _errorCount += 1;
    if (e.target && e.target !== window && (e.target.src || e.target.href)) {
      push('js_error', { kind: 'resource', src: String(e.target.src || e.target.href).slice(0, 300), tag: e.target.tagName, build });
      return;
    }
    push('js_error', {
      kind: 'error',
      msg: String(e.message || '').slice(0, 300),
      src: String(e.filename || '').slice(0, 300),
      line: e.lineno || null,
      stack: e.error && e.error.stack ? String(e.error.stack).slice(0, 500) : null,
      build,
    });
  }, { capture: true });
  window.addEventListener('unhandledrejection', (e) => {
    if (_errorCount >= ERRORS_MAX_PER_PAGE) return;
    _errorCount += 1;
    const r = e.reason;
    push('js_error', {
      kind: 'rejection',
      msg: String((r && (r.message || r)) || '').slice(0, 300),
      stack: r && r.stack ? String(r.stack).slice(0, 500) : null,
      build,
    });
  });
}

/** Латентность API глазами клиента: обёртка fetch, сэмпл 1 из N, только /api/. */
function setupApiTiming() {
  const orig = window.fetch;
  if (typeof orig !== 'function') return;
  // Сигнатура (input, init) сохраняется через arguments — init не читаем.
  window.fetch = function feFetch(input) {
    let url = null;
    try { url = typeof input === 'string' ? input : (input && input.url) || null; } catch { /* ignore */ }
    const isApi = url && url.indexOf('/api/') !== -1 && url.indexOf('/analytics/') === -1;
    if (!isApi) return orig.apply(this, arguments);
    _apiCallCounter += 1;
    if (_apiCallCounter % API_TIMING_SAMPLE !== 0) return orig.apply(this, arguments);
    const t0 = performance.now();
    return orig.apply(this, arguments).then((resp) => {
      push('api_timing', {
        u: String(url).replace(/^https?:\/\/[^/]+/, '').split('?')[0].slice(0, 200),
        ms: Math.round(performance.now() - t0),
        st: resp.status,
        ok: resp.ok ? 1 : 0,
      });
      return resp;
    }, (err) => {
      push('api_timing', {
        u: String(url).replace(/^https?:\/\/[^/]+/, '').split('?')[0].slice(0, 200),
        ms: Math.round(performance.now() - t0),
        st: 0,
        ok: 0,
      });
      throw err;
    });
  };
}

/** Воронка форм без снятия текста: первый фокус в форме и submit. */
function formName(form) {
  return (form.getAttribute('id') || form.getAttribute('name') || form.getAttribute('data-track') || form.getAttribute('aria-label') || elementPath(form)).slice(0, 120);
}

function onFormFocus(e) {
  const el = e.target instanceof Element ? e.target : null;
  const form = el && el.closest && el.closest('form');
  if (!form) return;
  const name = formName(form);
  const key = `${_pageLoadId}:${name}`;
  if (_formsSeen.has(key)) return;
  _formsSeen.add(key);
  push('form', { f: name, step: 'focus' });
}

function onFormSubmit(e) {
  const form = e.target instanceof Element ? e.target.closest('form') : null;
  if (!form) return;
  push('form', { f: formName(form), step: 'submit' });
}

function enterPage(url) {
  _pageLoadId = newPageLoadId();
  _pageEnteredAt = Date.now();
  _pageUrl = url;
  _maxScrollPct = 0;
  _clickCount = 0;
  _moveDistance = 0;
  _activeMs = 0;
  _lastActivityTs = Date.now();
  _errorCount = 0;
  _formsSeen = new Set();
  push('pageview', {
    ref: document.referrer || null,
    vw: window.innerWidth,
    vh: window.innerHeight,
    dpr: Math.round((window.devicePixelRatio || 1) * 100) / 100,
    touch: 'ontouchstart' in window ? 1 : 0,
    title: (document.title || '').slice(0, 120),
  });
  emitSessionStart(); // ретрай портрета, пока доставка не подтверждена
}

/** Вызывается роутером при смене страницы: закрывает предыдущую (dwell) и открывает новую. */
export function behaviorRouteChange(url) {
  if (!_inited || !_enabled) return;
  drainMoves();
  emitBlockViews();
  emitDwell();
  // отложить на тик, чтобы document.title успел обновиться через useMeta
  setTimeout(() => enterPage(url), 60);
}

/** Идентичность из AuthProvider (через track.js) — уходит в каждый батч. */
export function behaviorSetIdentity({ authed, userId } = {}) {
  _identity = { authed: !!authed, userId: userId || null };
}

function onClick(e) {
  const el = e.target instanceof Element ? e.target : null;
  if (!el) return;
  _clickCount += 1;
  const now = Date.now();
  const x = e.pageX, y = e.pageY;

  // rage: N кликов в маленьком радиусе за короткое окно
  _recentClicks = _recentClicks.filter((c) => now - c.t < RAGE_WINDOW_MS);
  _recentClicks.push({ x: e.clientX, y: e.clientY, t: now });
  const rage = _recentClicks.length >= RAGE_COUNT
    && _recentClicks.every((c) => Math.hypot(c.x - e.clientX, c.y - e.clientY) < RAGE_RADIUS);

  const interactive = el.closest(INTERACTIVE);
  const target = interactive || el;
  // авто-outbound: клик по внешней ссылке несёт целевой хост+путь
  let out = null;
  const anchor = el.closest && el.closest('a[href]');
  if (anchor) {
    try {
      const href = new URL(anchor.href, window.location.href);
      if (href.host && href.host !== window.location.host) {
        out = (href.host + href.pathname).slice(0, 200);
      }
    } catch { /* ignore */ }
  }
  push('click', {
    path: elementPath(target),
    text: elementText(target),
    x: Math.round(x),
    y: Math.round(y),
    vx: window.innerWidth ? Math.round((e.clientX / window.innerWidth) * 100) : null,
    vy: window.innerHeight ? Math.round((e.clientY / window.innerHeight) * 100) : null,
    dead: interactive ? 0 : 1,
    rage: rage ? 1 : 0,
    // isTrusted=false — синтетический клик (скрипт/бот, не устройство ввода);
    // антибот-скоринг сервера читает этот флаг (BI 2.1, этап 3).
    ...(e.isTrusted ? {} : { synthetic: 1 }),
    ...(out ? { out } : {}),
  });
}

function onMove(e) {
  const now = Date.now();
  if (now - _lastMove.t < MOVE_SAMPLE_MS) return;
  const dx = e.pageX - _lastMove.x;
  const dy = e.pageY - _lastMove.y;
  const dist = Math.hypot(dx, dy);
  if (dist < MOVE_MIN_DIST) return;
  _moveDistance += dist;
  if (_movePoints.length < MOVE_MAX_POINTS) {
    _movePoints.push([Math.round(e.pageX), Math.round(e.pageY), now - (_lastMove.t || now)]);
  }
  _lastMove = { x: e.pageX, y: e.pageY, t: now };
}

function onScroll() {
  const doc = document.documentElement;
  const total = doc.scrollHeight - window.innerHeight;
  if (total <= 0) { _maxScrollPct = 100; return; }
  const pct = Math.min(100, Math.round((window.scrollY / total) * 100));
  if (pct > _maxScrollPct) _maxScrollPct = pct;
}

function onCopy() {
  let text = null;
  try {
    const sel = window.getSelection();
    text = sel ? String(sel).trim().replace(/\s+/g, ' ').slice(0, 120) : null;
  } catch { /* ignore */ }
  if (text) push('copy', { text });
}

function onLeave() {
  drainMoves();
  emitBlockViews();
  emitDwell();
  flush();
}

/** Единственная точка входа; идемпотентна. Вызывается из App при монтировании
 * (SPA) и из standalone-бандла на чистых SSR-страницах — один исходник,
 * полный паритет сбора. */
export function behaviorInit() {
  if (_inited || typeof window === 'undefined') return;
  if (isAutomationClient()) return;
  if (/^\/embed\//.test(window.location.pathname)) return;
  _enabled = consentAllows();
  _inited = true;
  if (!_enabled) return;

  visitorId(); // создать постоянный идентификатор при первом заходе
  setupErrorCapture();
  setupApiTiming();
  enterPage(cleanUrl()); // pageview + портрет (session_start с ретраем)
  setupVitals();
  setupBlockObserver();

  document.addEventListener('click', (e) => { markActivity(); onClick(e); }, { capture: true, passive: true });
  document.addEventListener('mousemove', (e) => { markActivity(); onMove(e); }, { passive: true });
  window.addEventListener('scroll', () => { markActivity(); onScroll(); }, { passive: true });
  document.addEventListener('keydown', markActivity, { passive: true });
  document.addEventListener('copy', onCopy);
  document.addEventListener('focusin', onFormFocus, { passive: true });
  document.addEventListener('submit', onFormSubmit, { capture: true });
  window.addEventListener('pagehide', onLeave);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') onLeave();
    else markActivity();
  });

  _timer = setInterval(flush, FLUSH_INTERVAL_MS);
}

/** Для тестов: сброс состояния модуля. */
export function _resetForTests() {
  _queue = [];
  _movePoints = [];
  _recentClicks = [];
  _inited = false;
  _enabled = true;
  _pageLoadId = null;
  _pageEnteredAt = 0;
  _pageUrl = null;
  _maxScrollPct = 0;
  _clickCount = 0;
  _moveDistance = 0;
  _lastMove = { x: 0, y: 0, t: 0 };
  _activeMs = 0;
  _lastActivityTs = 0;
  _errorCount = 0;
  _apiCallCounter = 0;
  _blocks = new Map();
  _formsSeen = new Set();
  if (_timer) { clearInterval(_timer); _timer = null; }
  if (_blockTimer) { clearInterval(_blockTimer); _blockTimer = null; }
  if (_blockObserver) { _blockObserver.disconnect(); _blockObserver = null; }
}

export { elementPath as _elementPath, consentAllows as _consentAllows };
