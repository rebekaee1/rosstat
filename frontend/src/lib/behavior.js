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
 * Транспорт: буфер в памяти → подтверждаемый fetch; на уходе best-effort beacon
 * (интервал 10 с / 60 событий / pagehide). При 100k посетителей/день это даёт
 * порядка сотен вставок в секунду в пике — держится bulk-insert'ом на бэке.
 *
 * Приватность (152-ФЗ): не перехватываем ввод в поля (keystroke-логирования
 * нет), текст не снимается с input/textarea/[contenteditable], явный отказ от
 * аналитики в актуальной редакции политики (fe:consent:v1) отключает сбор.
 * Не работает на /embed/* (iframe на чужих сайтах).
 */

import { EVIDENCE_VERSION, SCROLL_SETTLE_MS, createBlockClock, createScrollProgress, evidenceToken, inpEvidence, interactionTarget, unobscuredRatio } from './behaviorEvidence';
import { CONSENT_CHANGE_EVENT } from './consent';

const ENDPOINT = '/api/v1/analytics/behavior';
const SESSION_KEY = 'fe:analytics:session';
const SESSION_META_KEY = 'fe:analytics:session:meta';
const VISITOR_KEY = 'fe:analytics:visitor';
const CONSENT_KEY = 'fe:consent:v1';
const CONSENT_V = '2026-06-16';

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_AT_QUEUE = 60;
const DELIVERY_RETRY_MS = [1000, 3000, 10_000];
const DELIVERY_LIFETIME_MS = 60_000;
const DELIVERY_MAX_BATCHES = 4;
const DELIVERY_MAX_PENDING_BYTES = 128 * 1024;
// keepalive has a shared 64KiB browser budget, also used by other collectors.
const DELIVERY_BODY_BYTES = 48 * 1024;
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
const MAX_BLOCK_ELEMENTS = 64;
const MAX_INTERACTIONS_PER_PAGE = 160;
const GEOMETRY_REFRESH_MS = 200;
const INPUT_CAPTURE_TYPES = new Set(['pointerdown', 'pointerup', 'pointercancel', 'touchstart', 'touchend', 'touchcancel', 'click', 'keydown', 'keyup', 'keypress']);

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
let _pendingBatches = [];
let _deliveryActive = null;
let _deliveryTimer = null;
let _leavingBytes = 0;
let _flushing = false;
let _identity = { authed: false, userId: null };
let _pageLoadId = null;
let _pageEnteredAt = 0;
let _pageUrl = null;
let _scrollProgress = createScrollProgress();
let _scrollTimer = null;
let _pageSuspended = false;
let _windowFocused = true;
let _routeTimer = null;
let _pageHistory = [];
let _inputTargets = [];
let _generation = 0;
let _listeners = [];
let _restoreFetch = null;
let _interactionCount = 0;
let _interactionSequence = 0;
let _pointers = new Map();
let _overlayState = null;
let _geometryAt = 0;
let _geometryTimer = null;
let _clickCount = 0;
let _moveDistance = 0;
let _movePoints = [];
let _lastMove = { x: 0, y: 0, t: 0 };
let _recentClicks = [];
let _timer = null;
let _inited = false;
let _enabled = true;
let _collectorsStarted = false;
let _explicitAnalytics = null;
let _captureStartedAt = 0;
const _attention = createAttentionClock();
let _errorCount = 0;
let _apiCallCounter = 0;
// One clock per semantic block; duplicate DOM nodes never multiply its time.
let _blocks = new Map();
let _blockElements = new Map();
let _blockObserver = null;
let _blockTimer = null;
let _formsSeen = new Set();

export function sessionId() {
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

/** Input-backed attention and passive visible time are separate observations.
 * Neither proves a human; browser automation can produce trusted input too. */
export function createAttentionClock() {
  let visible = false;
  let tick = 0;
  let inputAt = null;
  let active = 0;
  let seen = 0;
  function advance(now) {
    now = Math.max(tick, now);
    if (visible) {
      seen += Math.max(0, now - tick);
      if (inputAt !== null) active += Math.max(0, Math.min(now, inputAt + ACTIVE_GAP_MS) - tick);
    }
    tick = now;
  }
  return {
    reset(now, isVisible) { tick = now; visible = isVisible; inputAt = null; active = 0; seen = 0; },
    visibility(now, isVisible) {
      advance(now); visible = isVisible;
      if (!visible) inputAt = null;
    },
    input(now, trusted, isVisible) {
      advance(now);
      visible = isVisible;
      if (trusted && visible) inputAt = Math.max(tick, now);
      if (!visible) inputAt = null;
    },
    snapshot(now) {
      advance(now);
      const result = { active_ms: active, visible_ms: seen };
      active = 0; seen = 0;
      return result;
    },
    activeUntil() { return visible && inputAt !== null ? inputAt + ACTIVE_GAP_MS : null; },
  };
}

function attentionVisible() {
  return _windowFocused && document.visibilityState !== 'hidden' && document.hasFocus();
}

function markActivity(event) {
  if (!_enabled) return;
  captureInputTarget(event);
  const now = Date.now();
  _attention.input(now, event?.isTrusted === true, attentionVisible());
  // Close preceding block intervals before extending their input-backed window.
  refreshBlocks(false, now);
}

function captureInputTarget(event) {
  if (event?.isTrusted !== true || !INPUT_CAPTURE_TYPES.has(event.type) || !(event.target instanceof Element)) return;
  let start = event.timeStamp;
  if (!Number.isFinite(start)) return;
  // Legacy Safari timestamps can be epoch-based rather than performance-relative.
  if (start > 1e12) start -= performance.timeOrigin;
  if (start < 0 || start > performance.now() + 8) return;
  const url = cleanUrl();
  _inputTargets.push({ start, type: event.type, family: event.type.startsWith('key') ? 'keyboard' : 'pointer',
    target: interactionTarget(event.target), url, pl: url === _pageUrl ? _pageLoadId : null });
  if (_inputTargets.length > 400) _inputTargets.shift();
}

function originalInpTarget(metric, evidence) {
  if (evidence.inp_start_ms === null) return null;
  const entryType = metric.entries?.[0]?.name;
  const exactType = INPUT_CAPTURE_TYPES.has(entryType) ? entryType : null;
  const matches = _inputTargets.filter((input) => input.family === evidence.inp_type
    && (!exactType || input.type === exactType) && Math.abs(input.start - evidence.inp_start_ms) <= 8)
    .sort((a, b) => Math.abs(a.start - evidence.inp_start_ms) - Math.abs(b.start - evidence.inp_start_ms));
  if (!matches.length) return null;
  // Equal-time inputs with different targets are ambiguous, never a guessed target.
  if (matches[1] && Math.abs(matches[0].start - evidence.inp_start_ms) === Math.abs(matches[1].start - evidence.inp_start_ms)
    && matches[0].target !== matches[1].target) return null;
  return matches[0];
}

export function consentAllows() {
  if (_explicitAnalytics === false) return false;
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

function listen(target, type, handler, options) {
  target.addEventListener(type, handler, options);
  _listeners.push(() => target.removeEventListener(type, handler, options));
}

function relativeTime() {
  return Math.max(0, Math.round(performance.now()));
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

function deliveryCurrent(batch) {
  return _enabled && consentAllows() && batch.generation === _generation && _pendingBatches.includes(batch)
    && Date.now() < batch.createdAt + DELIVERY_LIFETIME_MS;
}

function removeBatch(batch) {
  _pendingBatches = _pendingBatches.filter((item) => item !== batch);
  if (_deliveryActive === batch) _deliveryActive = null;
  for (const controller of batch.controllers) {
    try { controller.abort(); } catch { /* ignore */ }
  }
}

function clearDelivery() {
  if (_deliveryTimer) clearTimeout(_deliveryTimer);
  _deliveryTimer = null;
  for (const batch of _pendingBatches) removeBatch(batch);
  _pendingBatches = [];
  _deliveryActive = null;
  _leavingBytes = 0;
}

function retryAfterMs(resp) {
  let value;
  try { value = resp?.headers?.get('Retry-After'); } catch { return null; }
  if (!value) return null;
  if (/^\d+(?:\.\d+)?$/.test(value.trim())) return Number(value) * 1000;
  const when = Date.parse(value);
  return Number.isFinite(when) ? Math.max(0, when - Date.now()) : null;
}

async function deliveryResponse(resp) {
  if (!resp?.ok) return resp;
  try {
    const result = await resp.json();
    if (result?.accepted === true) return resp;
    if (result?.accepted === false) return { rejected: true };
  } catch { /* an unreadable response is not an acknowledgement */ }
  return null;
}

function acknowledge(batch) {
  if (!deliveryCurrent(batch)) return;
  if (batch.hasPortrait) {
    try { window.sessionStorage.setItem(SESSION_META_KEY, '1'); } catch { /* ignore */ }
  }
  removeBatch(batch);
}

function applyDeliveryResult(batch, resp) {
  if (!deliveryCurrent(batch)) return;
  if (resp?.ok) acknowledge(batch);
  else if ((!resp || resp.status >= 500 || resp.status === 429) && batch.attempts <= DELIVERY_RETRY_MS.length) {
    const backoff = DELIVERY_RETRY_MS[batch.attempts - 1];
    const delay = Math.max(backoff, retryAfterMs(resp) ?? 0);
    batch.nextAt = Math.max(batch.nextAt, Date.now() + delay);
    // A long Retry-After must never be truncated into an earlier retry.
    if (batch.nextAt >= batch.createdAt + DELIVERY_LIFETIME_MS) removeBatch(batch);
  } else removeBatch(batch);
}

function finishDelivery(batch, attempt, resp) {
  if (!deliveryCurrent(batch) || batch.attempt !== attempt) return;
  if (_deliveryActive === batch) _deliveryActive = null;
  applyDeliveryResult(batch, resp);
  pumpDelivery();
}

function scheduleDelivery() {
  if (_deliveryTimer) clearTimeout(_deliveryTimer);
  _deliveryTimer = null;
  if (!_pendingBatches.length) return;
  let next = Math.min(..._pendingBatches.map((batch) => batch.createdAt + DELIVERY_LIFETIME_MS));
  if (!_deliveryActive && !_pageSuspended) next = Math.min(next,
    ..._pendingBatches.filter((batch) => batch.attempts <= DELIVERY_RETRY_MS.length).map((batch) => batch.nextAt));
  _deliveryTimer = setTimeout(() => { _deliveryTimer = null; pumpDelivery(); }, Math.max(0, next - Date.now()));
}

function pumpDelivery() {
  if (!_enabled || !consentAllows()) { clearDelivery(); return; }
  for (const batch of _pendingBatches) if (!deliveryCurrent(batch)) removeBatch(batch);
  if (!_deliveryActive && !_pageSuspended) {
    const batch = _pendingBatches.find((item) => item.nextAt <= Date.now() && item.attempts <= DELIVERY_RETRY_MS.length);
    if (batch) {
      const attempt = {};
      batch.attempt = attempt;
      batch.attempts += 1;
      _deliveryActive = batch;
      try {
        const controller = typeof AbortController === 'function' ? new AbortController() : null;
        if (controller) batch.controllers.push(controller);
        // Regular delivery has a response and does not consume shared keepalive quota.
        Promise.resolve(fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: batch.body, keepalive: false, ...(controller ? { signal: controller.signal } : {}) }))
          .then(deliveryResponse)
          .then((resp) => finishDelivery(batch, attempt, resp), () => finishDelivery(batch, attempt, null));
      } catch { finishDelivery(batch, attempt, null); }
    }
  }
  scheduleDelivery();
}

function sendLeavingBatches() {
  for (const batch of _pendingBatches) {
    if (!deliveryCurrent(batch) || batch.leftAttempted || batch.nextAt > Date.now() || batch.attempts > DELIVERY_RETRY_MS.length
      || _leavingBytes + batch.bytes > DELIVERY_BODY_BYTES) continue;
    batch.leftAttempted = true;
    _leavingBytes += batch.bytes;
    batch.attempts += 1;
    try {
      if (navigator.sendBeacon?.(ENDPOINT, new Blob([batch.body], { type: 'application/json' }))) {
        // Queue acceptance is not a server response. Retain until ack/expiry.
        continue;
      }
    } catch { /* fall back to the same first-party endpoint */ }
    try {
      const controller = typeof AbortController === 'function' ? new AbortController() : null;
      if (controller) batch.controllers.push(controller);
      Promise.resolve(fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: batch.body, keepalive: true, ...(controller ? { signal: controller.signal } : {}) }))
        .then(deliveryResponse)
        .then((resp) => { applyDeliveryResult(batch, resp); pumpDelivery(); }, () => { applyDeliveryResult(batch, null); pumpDelivery(); });
    } catch { /* leaving delivery is best effort */ }
  }
  scheduleDelivery();
}

export function flush({ leaving = false } = {}) {
  if (_flushing || !_enabled || !consentAllows()) return;
  _flushing = true;
  try {
    drainMoves();
    for (const batch of _pendingBatches) if (!deliveryCurrent(batch)) removeBatch(batch);
    while (_queue.length) {
      const envelope = { session_id: sessionId(), visitor_id: visitorId(), authed: _identity.authed ? 1 : 0, batch_id: batchId() };
      let count = Math.min(_queue.length, FLUSH_AT_QUEUE);
      let body, bytes;
      do {
        body = JSON.stringify({ ...envelope, events: _queue.slice(0, count) });
        bytes = new Blob([body]).size;
        if (bytes <= DELIVERY_BODY_BYTES || count === 1) break;
        count = Math.max(1, Math.floor(count / 2));
      } while (count);
      const events = _queue.splice(0, count);
      const pendingBytes = _pendingBatches.reduce((total, batch) => total + batch.bytes, 0);
      if (bytes > DELIVERY_BODY_BYTES || _pendingBatches.length >= DELIVERY_MAX_BATCHES
        || pendingBytes + bytes > DELIVERY_MAX_PENDING_BYTES) continue;
      _pendingBatches.push({ body, bytes, hasPortrait: events.some((event) => event.t === 'session_start'),
        createdAt: Date.now(), nextAt: Date.now(), generation: _generation, attempts: 0, controllers: [], leftAttempted: false });
    }
    pumpDelivery();
    if (leaving) sendLeavingBatches();
  } catch { /* телеметрия никогда не ломает UX */ }
  finally { _flushing = false; }
}

const DWELL_MAX_MS = 4 * 3600 * 1000; // страховка от вкладок, забытых на ночь

function emitDwell() {
  if (!_pageLoadId || !_pageEnteredAt || _pageSuspended) return;
  const now = Date.now();
  const attention = _attention.snapshot(now);
  const ms = Math.max(0, Math.min(now - _pageEnteredAt, DWELL_MAX_MS));
  const scroll = observeScroll(false);
  push('dwell', {
    ms,
    active_ms: Math.min(attention.active_ms, ms),
    visible_ms: Math.min(attention.visible_ms, ms),
    attention_version: 2,
    scroll_pct: scroll.pct,
    scroll_valid: scroll.valid ? 1 : 0,
    scroll_height: Math.round(scroll.height),
    scroll_viewport: Math.round(scroll.viewport),
    scroll_max_y: scroll.max_y,
    scroll_version: EVIDENCE_VERSION,
    clicks: _clickCount,
    move_px: Math.round(_moveDistance),
  });
  // Сегментация: dwell закрывает отрезок и обнуляет счётчики — повторный
  // visibilitychange не дублирует уже отправленное время (лечит dwell > 4ч).
  _pageEnteredAt = now;
  _clickCount = 0;
  _moveDistance = 0;
}

/** Блочная аналитика: закрыть учёт видимости и отправить по событию на блок. */
function emitBlockViews() {
  const now = Date.now();
  refreshBlocks(true, now);
  for (const [name, rec] of _blocks) {
    const observed = rec.clock.snapshot(now);
    if (observed.visible_ms >= 500) push('block_view', {
      block: name,
      ms: Math.round(observed.visible_ms),
      visible_ms: Math.round(observed.visible_ms),
      active_ms: Math.round(observed.active_ms),
      visibility_version: EVIDENCE_VERSION,
    });
  }
}

function observeBlocksNow() {
  if (!_blockObserver || !_enabled) return;
  for (const [el] of _blockElements) {
    if (!el.isConnected) { _blockObserver.unobserve(el); _blockElements.delete(el); }
  }
  for (const el of document.querySelectorAll('[data-block]')) {
    if (_blockElements.has(el)) continue;
    if (_blockElements.size >= MAX_BLOCK_ELEMENTS) break;
    const name = evidenceToken(el.getAttribute('data-block'));
    if (!name) continue;
    if (!_blocks.has(name) && _blocks.size >= MAX_BLOCK_ELEMENTS) continue;
    _blockElements.set(el, { name, intersecting: false, ratio: 0 });
    if (!_blocks.has(name)) _blocks.set(name, { clock: createBlockClock(Date.now()), visible: false });
    _blockObserver.observe(el);
  }
  refreshBlocks();
  observeScroll(false);
}

function overlayRects() {
  const rects = [];
  for (const el of document.querySelectorAll('[data-analytics-overlay]')) {
    if (rects.length >= 8) break;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
    const rect = el.getBoundingClientRect();
    if (rect.right > rect.left && rect.bottom > rect.top) rects.push(rect);
  }
  return rects;
}

function refreshBlocks(measure = true, now = Date.now()) {
  const focused = attentionVisible() && !_pageSuspended;
  if (measure) {
    const visibleNames = new Set();
    const viewport = { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight };
    const overlays = focused ? overlayRects() : [];
    if (focused) {
      for (const [el, rec] of _blockElements) {
        if (el.isConnected && rec.intersecting && rec.ratio >= 0.5
          && unobscuredRatio(el.getBoundingClientRect(), viewport, overlays) >= 0.5) visibleNames.add(rec.name);
      }
    }
    for (const [name, rec] of _blocks) rec.visible = visibleNames.has(name);
    _geometryAt = now;
  }
  for (const rec of _blocks.values()) rec.clock.update(now, focused && rec.visible, _attention.activeUntil());
}

function scheduleGeometry() {
  if (Date.now() - _geometryAt >= GEOMETRY_REFRESH_MS) { refreshBlocks(); return; }
  if (!_geometryTimer) _geometryTimer = setTimeout(() => {
    _geometryTimer = null;
    refreshBlocks();
  }, GEOMETRY_REFRESH_MS);
}

function resetBlocks() {
  if (_blockObserver) _blockObserver.disconnect();
  _blockElements = new Map();
  _blocks = new Map();
}

function setupBlockObserver() {
  if (typeof IntersectionObserver === 'undefined') return;
  _blockObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const rec = _blockElements.get(entry.target);
      if (!rec) continue;
      rec.intersecting = entry.isIntersecting;
      rec.ratio = entry.intersectionRatio;
    }
    refreshBlocks();
  }, { threshold: [0, 0.5, 1] });
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
  const generation = _generation;
  const report = (m) => {
    if (generation !== _generation) return;
    const evidence = m.name === 'INP' ? inpEvidence(m, performance.timeOrigin) : {};
    if (m.name === 'INP' && evidence.inp_start_ms !== null && evidence.inp_start_ms < _captureStartedAt) return;
    const originalInput = m.name === 'INP' ? originalInpTarget(m, evidence) : null;
    if (m.name === 'INP') {
      // The library sees entry.target after handlers/React have mutated it.
      evidence.inp_reported_target = evidence.inp_target;
      evidence.inp_target = originalInput?.target ?? null;
      evidence.inp_target_source = originalInput ? 'capture_event' : 'unmatched_library';
    }
    // A delayed INP report can describe an interaction on the preceding SPA route.
    const page = originalInput || (m.name === 'INP' && evidence.inp_start_ms !== null
      ? [..._pageHistory].reverse().find((p) => p.start <= evidence.inp_start_ms) : null);
    push('vital', {
      m: m.name,
      v: Math.round(m.value * (m.name === 'CLS' ? 1000 : 1)) / (m.name === 'CLS' ? 1000 : 1),
      rating: m.rating,
      ...evidence,
      ...(page ? { url: page.url, pl: page.pl } : {}),
    });
  };
  import('web-vitals').then(({ onLCP, onCLS, onFCP, onTTFB }) => {
    if (generation !== _generation) return;
    onLCP(report); onCLS(report); onFCP(report); onTTFB(report);
  }).catch(() => { /* vitals опциональны */ });
  import('web-vitals/attribution').then(({ onINP }) => {
    if (generation !== _generation) return;
    onINP(report, { generateTarget: interactionTarget, includeProcessedEventEntries: false });
  }).catch(() => { /* vitals опциональны */ });
}

/** JS-ошибки: onerror + unhandledrejection + упавшие ресурсы. Версия сборки
 * (__BUILD_ID__ подставляет Vite) привязывает регрессии к деплоям. */
function setupErrorCapture() {
  const build = (typeof __BUILD_ID__ !== 'undefined' && __BUILD_ID__) || null;
  listen(window, 'error', (e) => {
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
  listen(window, 'unhandledrejection', (e) => {
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

function apiTimingUrl(url) {
  return String(url).replace(/^https?:\/\/[^/]+/, '').split('?')[0].slice(0, 200);
}

function isApiTimingUrl(url) {
  return Boolean(url) && url.indexOf('/api/') !== -1 && url.indexOf('/analytics/') === -1;
}

/** Латентность API глазами клиента: обёртки fetch и XMLHttpRequest (Axios ходит через XHR),
 *  сэмпл 1 из N, только /api/. Измерение пассивно: ответ и ошибки не меняются. */
function setupApiTiming() {
  const orig = window.fetch;
  const restores = [];
  if (typeof orig === 'function') {
    // Сигнатура (input, init) сохраняется через arguments — init не читаем.
    window.fetch = function feFetch(input) {
      let url = null;
      try { url = typeof input === 'string' ? input : (input && input.url) || null; } catch { /* ignore */ }
      if (!isApiTimingUrl(url)) return orig.apply(this, arguments);
      _apiCallCounter += 1;
      if (_apiCallCounter % API_TIMING_SAMPLE !== 0) return orig.apply(this, arguments);
      const t0 = performance.now();
      return orig.apply(this, arguments).then((resp) => {
        push('api_timing', { u: apiTimingUrl(url), ms: Math.round(performance.now() - t0), st: resp.status, ok: resp.ok ? 1 : 0 });
        return resp;
      }, (err) => {
        push('api_timing', { u: apiTimingUrl(url), ms: Math.round(performance.now() - t0), st: 0, ok: 0 });
        throw err;
      });
    };
    const wrapper = window.fetch;
    restores.push(() => { if (window.fetch === wrapper) window.fetch = orig; });
  }

  const XHR = typeof window.XMLHttpRequest === 'function' ? window.XMLHttpRequest : null;
  const proto = XHR && XHR.prototype;
  if (proto && typeof proto.open === 'function' && typeof proto.send === 'function') {
    const origOpen = proto.open;
    const origSend = proto.send;
    proto.open = function feXhrOpen(method, url) {
      try { this.__feTimingUrl = typeof url === 'string' ? url : (url && String(url)) || null; } catch { /* ignore */ }
      return origOpen.apply(this, arguments);
    };
    proto.send = function feXhrSend() {
      try {
        const url = this.__feTimingUrl;
        if (isApiTimingUrl(url)) {
          _apiCallCounter += 1;
          if (_apiCallCounter % API_TIMING_SAMPLE === 0) {
            const t0 = performance.now();
            // loadend срабатывает и при успехе, и при ошибке/таймауте/abort.
            this.addEventListener('loadend', () => {
              const st = this.status || 0;
              push('api_timing', { u: apiTimingUrl(url), ms: Math.round(performance.now() - t0), st, ok: st >= 200 && st < 300 ? 1 : 0 });
            }, { once: true });
          }
        }
      } catch { /* телеметрия никогда не ломает UX */ }
      return origSend.apply(this, arguments);
    };
    const openWrapper = proto.open;
    const sendWrapper = proto.send;
    restores.push(() => {
      if (proto.open === openWrapper) proto.open = origOpen;
      if (proto.send === sendWrapper) proto.send = origSend;
    });
  }
  if (restores.length) _restoreFetch = () => { for (const restore of restores) restore(); };
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
  _scrollProgress = createScrollProgress();
  _pageSuspended = false;
  _pointers = new Map();
  _interactionCount = 0;
  _interactionSequence = 0;
  _overlayState = null;
  resetBlocks();
  _clickCount = 0;
  _moveDistance = 0;
  _attention.reset(Date.now(), attentionVisible());
  _errorCount = 0;
  _formsSeen = new Set();
  _pageHistory.push({ start: relativeTime(), url, pl: _pageLoadId });
  _pageHistory = _pageHistory.slice(-40);
  push('pageview', {
    ref: document.referrer || null,
    vw: window.innerWidth,
    vh: window.innerHeight,
    dpr: Math.round((window.devicePixelRatio || 1) * 100) / 100,
    touch: 'ontouchstart' in window ? 1 : 0,
    title: (document.title || '').slice(0, 120),
  });
  emitSessionStart(); // ретрай портрета, пока доставка не подтверждена
  observeScroll(false);
  observeBlocksNow();
  recordOverlayState();
}

/** Вызывается роутером при смене страницы: закрывает предыдущую (dwell) и открывает новую. */
export function behaviorRouteChange(url) {
  if (!_inited || !_enabled) return;
  if (_routeTimer) clearTimeout(_routeTimer);
  drainMoves();
  emitBlockViews();
  emitDwell();
  _pageSuspended = true;
  _attention.visibility(Date.now(), false);
  refreshBlocks(false);
  // отложить на тик, чтобы document.title успел обновиться через useMeta
  _routeTimer = setTimeout(() => { _routeTimer = null; enterPage(url); }, 60);
}

/** Идентичность из AuthProvider (через track.js) — уходит в каждый батч. */
export function behaviorSetIdentity({ authed, userId } = {}) {
  _identity = { authed: !!authed, userId: userId || null };
}

function onClick(e) {
  if (!_enabled) return;
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
    interaction_target: interactionTarget(target),
    action: interactionAction(target),
    relative_ms: relativeTime(),
    evidence_version: EVIDENCE_VERSION,
  });
}

function interactionAction(target) {
  return evidenceToken(target?.closest?.('[data-fe-interaction-action]')?.getAttribute('data-fe-interaction-action'));
}

/** Pointer lifecycle is evidence of input delivery, not proof of a dispatched click. */
function onPointer(event) {
  if (!_enabled) return;
  markActivity(event);
  if (_interactionCount >= MAX_INTERACTIONS_PER_PAGE) return;
  const touch = event.type.startsWith('touch') ? event.changedTouches?.[0] : null;
  const pointer = touch ? `t${touch.identifier}` : `p${event.pointerId ?? 0}`;
  const phase = /(?:down|start)$/.test(event.type) ? 'start' : /cancel$/.test(event.type) ? 'cancel' : 'end';
  const el = event.target instanceof Element ? event.target : null;
  if (!el) return;
  const now = relativeTime();
  let rec = _pointers.get(pointer);
  if (phase === 'start') {
    if (_pointers.size >= 8) return;
    rec = { id: ++_interactionSequence, started: now };
    _pointers.set(pointer, rec);
  }
  _interactionCount += 1;
  push('interaction', {
    interaction_type: event.type,
    input_type: touch ? 'touch' : (['mouse', 'pen', 'touch'].includes(event.pointerType) ? event.pointerType : 'unknown'),
    phase,
    interaction_id: rec?.id ?? null,
    target: interactionTarget(el),
    action: interactionAction(el),
    trusted: event.isTrusted === true ? 1 : 0,
    relative_ms: now,
    duration_ms: phase !== 'start' && rec ? Math.min(60_000, Math.max(0, now - rec.started)) : null,
    evidence_version: EVIDENCE_VERSION,
  });
  if (phase !== 'start') _pointers.delete(pointer);
}

function recordOverlayState(event) {
  const detail = event?.detail;
  if (detail && detail.id !== 'cookie-consent') return;
  const panel = document.querySelector('[data-analytics-overlay="cookie-consent"]');
  const style = panel && window.getComputedStyle(panel);
  const visible = detail ? detail.visible === true
    : !!panel && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  const expanded = detail?.expanded === true;
  const key = `${visible}:${expanded}`;
  if (key !== _overlayState) {
    _overlayState = key;
    push('ui_state', {
      component: 'cookie-consent', visible: visible ? 1 : 0, expanded: expanded ? 1 : 0,
      config_version: CONSENT_V, evidence_version: EVIDENCE_VERSION,
      relative_ms: relativeTime(), source: detail ? 'component' : 'dom',
    });
  }
  refreshBlocks();
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

function observeScroll(input = false) {
  const doc = document.documentElement;
  return _scrollProgress.observe({
    height: Math.max(doc.scrollHeight, document.body?.scrollHeight || 0), viewport: window.innerHeight,
    y: window.scrollY, time: Date.now(), input, visible: attentionVisible() && !_pageSuspended,
  });
}

function onScroll(event) {
  // Browser-generated scroll can also follow script scrollTo; require recent
  // trusted pointer/wheel/key input before treating it as visitor progress.
  const until = _attention.activeUntil();
  observeScroll(event?.isTrusted === true && until !== null && Date.now() <= until);
  scheduleGeometry();
  if (_scrollTimer) clearTimeout(_scrollTimer);
  _scrollTimer = setTimeout(() => { _scrollTimer = null; observeScroll(false); }, SCROLL_SETTLE_MS);
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
  if (!_pageSuspended) {
    drainMoves();
    emitBlockViews();
    emitDwell();
    _pageSuspended = true;
    _attention.visibility(Date.now(), false);
    refreshBlocks(false);
  }
  flush({ leaving: true });
}

function onVisibility() {
  const visible = attentionVisible();
  if (document.visibilityState !== 'hidden' && _pageSuspended) {
    _pageSuspended = false;
    _pageEnteredAt = Date.now();
    _leavingBytes = 0;
    for (const batch of _pendingBatches) batch.leftAttempted = false;
    pumpDelivery();
  }
  _attention.visibility(Date.now(), visible);
  refreshBlocks();
  if (document.visibilityState === 'hidden') onLeave();
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
  listen(window, CONSENT_CHANGE_EVENT, onConsentChange);
  listen(window, 'storage', (event) => { if (event.key === CONSENT_KEY) onConsentChange(); });
  if (!_enabled) return;

  startCollectors();
}

function startCollectors() {
  _collectorsStarted = true;
  _captureStartedAt = relativeTime();
  visitorId(); // создать постоянный идентификатор при первом заходе
  setupErrorCapture();
  setupApiTiming();
  enterPage(cleanUrl()); // pageview + портрет (session_start с ретраем)
  setupVitals();
  setupBlockObserver();

  listen(document, 'click', (e) => { markActivity(e); onClick(e); }, { capture: true, passive: true });
  listen(document, 'mousemove', (e) => { markActivity(e); onMove(e); }, { passive: true });
  listen(window, 'scroll', onScroll, { passive: true });
  listen(document, 'wheel', markActivity, { passive: true });
  for (const type of ['keydown', 'keyup', 'keypress']) listen(document, type, markActivity, { capture: true, passive: true });
  const pointerTypes = typeof window.PointerEvent === 'function'
    ? ['pointerdown', 'pointerup', 'pointercancel'] : ['touchstart', 'touchend', 'touchcancel'];
  for (const type of pointerTypes) listen(document, type, onPointer, { capture: true, passive: true });
  listen(document, 'copy', onCopy);
  listen(document, 'focusin', onFormFocus, { passive: true });
  listen(document, 'submit', onFormSubmit, { capture: true });
  listen(window, 'pagehide', onLeave);
  listen(document, 'visibilitychange', onVisibility);
  listen(window, 'pageshow', onVisibility);
  listen(window, 'fe:analytics-overlay:change', recordOverlayState);
  listen(window, 'resize', () => { observeScroll(false); refreshBlocks(); });

  listen(window, 'blur', () => { _windowFocused = false; _attention.visibility(Date.now(), false); refreshBlocks(false); });
  listen(window, 'focus', () => { _windowFocused = true; onVisibility(); });

  _timer = setInterval(flush, FLUSH_INTERVAL_MS);
}

function onConsentChange(event) {
  _explicitAnalytics = event?.detail?.v === CONSENT_V && typeof event.detail.analytics === 'boolean'
    ? event.detail.analytics : null;
  const allowed = consentAllows();
  if (allowed === _enabled) return;
  _generation += 1;
  _enabled = allowed;
  if (!allowed) {
    // Revocation applies immediately even if localStorage or a tracker failed.
    clearDelivery();
    _queue = []; _movePoints = []; _pointers = new Map(); _pageHistory = []; _inputTargets = [];
    _pageSuspended = true;
    _attention.reset(Date.now(), false);
    resetBlocks();
  } else if (!_collectorsStarted) startCollectors();
  else {
    _captureStartedAt = relativeTime();
    enterPage(cleanUrl());
    setupVitals();
  }
}

/** Для тестов: сброс состояния модуля. */
export function _resetForTests() {
  _generation += 1;
  clearDelivery();
  _flushing = false;
  for (const remove of _listeners) remove();
  _listeners = [];
  if (_restoreFetch) { _restoreFetch(); _restoreFetch = null; }
  _queue = [];
  _movePoints = [];
  _recentClicks = [];
  _inited = false;
  _enabled = true;
  _collectorsStarted = false;
  _explicitAnalytics = null;
  _captureStartedAt = 0;
  _pageLoadId = null;
  _pageEnteredAt = 0;
  _pageUrl = null;
  _scrollProgress = createScrollProgress();
  _pageSuspended = false;
  _windowFocused = true;
  _pageHistory = [];
  _inputTargets = [];
  _interactionCount = 0;
  _interactionSequence = 0;
  _pointers = new Map();
  _overlayState = null;
  _geometryAt = 0;
  _clickCount = 0;
  _moveDistance = 0;
  _lastMove = { x: 0, y: 0, t: 0 };
  _attention.reset(0, false);
  _errorCount = 0;
  _apiCallCounter = 0;
  _blocks = new Map();
  _blockElements = new Map();
  _formsSeen = new Set();
  if (_timer) { clearInterval(_timer); _timer = null; }
  if (_blockTimer) { clearInterval(_blockTimer); _blockTimer = null; }
  if (_blockObserver) { _blockObserver.disconnect(); _blockObserver = null; }
  if (_scrollTimer) { clearTimeout(_scrollTimer); _scrollTimer = null; }
  if (_geometryTimer) { clearTimeout(_geometryTimer); _geometryTimer = null; }
  if (_routeTimer) { clearTimeout(_routeTimer); _routeTimer = null; }
}

export { elementPath as _elementPath, consentAllows as _consentAllows };
