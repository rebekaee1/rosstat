/**
 * behavior.js — пассивный поведенческий сбор («видеокамера» сайта).
 *
 * Отличие от track.js: track.js — ручные бизнес-события (90 именованных целей,
 * дублируются в Метрику), а этот модуль собирает СЫРОЙ поведенческий поток без
 * ручной разметки, под data science:
 *
 *   - pageview      каждый переход по роутам SPA (+ первый заход);
 *   - click         КАЖДЫЙ клик: иерархический путь элемента, текст, координаты,
 *                    признаки dead (некликабельная цель) и rage (серия злых кликов);
 *   - move          траектория мыши: сэмплированная полилиния [x,y,dt] за окно
 *                    флеша (страница прореживается порогом расстояния);
 *   - dwell         уход со страницы: время на ней, максимум скролла, счётчики
 *                    кликов/дистанции мыши — «сколько жил и что делал»;
 *   - copy          что пользователь скопировал (первые 120 символов выделения).
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

export function flush() {
  drainMoves();
  if (!_queue.length) return;
  const events = _queue;
  _queue = [];
  const body = JSON.stringify({
    session_id: sessionId(),
    authed: _identity.authed ? 1 : 0,
    events,
  });
  try {
    if (navigator.sendBeacon) {
      const ok = navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
      if (ok) return;
    }
    fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
  } catch { /* телеметрия никогда не ломает UX */ }
}

function emitDwell() {
  if (!_pageLoadId || !_pageEnteredAt) return;
  push('dwell', {
    ms: Date.now() - _pageEnteredAt,
    scroll_pct: _maxScrollPct,
    clicks: _clickCount,
    move_px: Math.round(_moveDistance),
  });
}

function enterPage(url) {
  _pageLoadId = newPageLoadId();
  _pageEnteredAt = Date.now();
  _pageUrl = url;
  _maxScrollPct = 0;
  _clickCount = 0;
  _moveDistance = 0;
  push('pageview', {
    ref: document.referrer || null,
    vw: window.innerWidth,
    vh: window.innerHeight,
    dpr: Math.round((window.devicePixelRatio || 1) * 100) / 100,
    touch: 'ontouchstart' in window ? 1 : 0,
    title: (document.title || '').slice(0, 120),
  });
}

/** Вызывается роутером при смене страницы: закрывает предыдущую (dwell) и открывает новую. */
export function behaviorRouteChange(url) {
  if (!_inited || !_enabled) return;
  drainMoves();
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
  push('click', {
    path: elementPath(target),
    text: elementText(target),
    x: Math.round(x),
    y: Math.round(y),
    vx: window.innerWidth ? Math.round((e.clientX / window.innerWidth) * 100) : null,
    vy: window.innerHeight ? Math.round((e.clientY / window.innerHeight) * 100) : null,
    dead: interactive ? 0 : 1,
    rage: rage ? 1 : 0,
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
  emitDwell();
  flush();
}

/** Единственная точка входа; идемпотентна. Вызывается из App при монтировании. */
export function behaviorInit() {
  if (_inited || typeof window === 'undefined') return;
  if (/^\/embed\//.test(window.location.pathname)) return;
  _enabled = consentAllows();
  _inited = true;
  if (!_enabled) return;

  enterPage(cleanUrl());

  document.addEventListener('click', onClick, { capture: true, passive: true });
  document.addEventListener('mousemove', onMove, { passive: true });
  window.addEventListener('scroll', onScroll, { passive: true });
  document.addEventListener('copy', onCopy);
  window.addEventListener('pagehide', onLeave);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') onLeave();
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
  if (_timer) { clearInterval(_timer); _timer = null; }
}

export { elementPath as _elementPath, consentAllows as _consentAllows };
