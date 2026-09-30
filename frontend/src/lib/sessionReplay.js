/** Masked, same-origin recordings. Failed transport is a coverage gap, never a
 * complete recording. The recorder/player are separate lazy chunks. */
import { visitorId, sessionId as behaviorSessionId, consentAllows as behaviorConsentAllows, isAutomationClient } from './behavior';
import { CONSENT_CHANGE_EVENT, CONSENT_KEY } from './consent';

const PRIVATE = /^\/(admin|account|auth|login|register|reset|embed|forgot-password|verify-email)(\/|$)/;
const MAX_BUFFER = 2_000_000;
const PART_CHARS = 8000;
const MASK = '[скрыто]';
let active = null;
let initialized = false;
let explicitAnalytics = null;
let generation = 0;

export function replayPageAllowed(path) {
  try { path = decodeURIComponent(path); } catch { return false; }
  return !PRIVATE.test(path) && !document.body?.hasAttribute('data-no-analytics');
}

function captureAllowed() {
  return explicitAnalytics !== false && behaviorConsentAllows() && replayPageAllowed(location.pathname);
}

export function publicUrl(value, allowLocalReference = false) {
  // CSS/SVG paint references must retain their local ids for chart fidelity.
  // Ordinary navigation links still discard all query/hash attribution.
  if (allowLocalReference && typeof value === 'string' && /^#[a-z_][a-z0-9_.:-]{0,127}$/i.test(value)) return value;
  try {
    const u = new URL(value, window.location.origin);
    if (!['http:', 'https:'].includes(u.protocol)) return '';
    return `${u.origin}${u.pathname}`;
  } catch { return ''; }
}

export function scrubReplayEvent(event) {
  // rrweb applies text/input masks first; remove URL queries and attribute
  // values that could have been inserted by framework code afterward.
  return JSON.parse(JSON.stringify(event, (key, value) => {
    if (/^(value|placeholder|data-(user|email|token|password|phone|session|auth).*)$/i.test(key)) return MASK;
    if (['href', 'src', 'action', 'formaction', 'xlink:href'].includes(key) && typeof value === 'string') return publicUrl(value, key === 'xlink:href');
    if (key === 'srcset') return '';
    if (typeof value === 'string' && ['textContent', '_cssText', 'style', 'cssText'].includes(key)) {
      return value.replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, MASK)
        .replace(/url\(\s*(['"]?)(.*?)\1\s*\)/gi, (_match, _quote, url) => `url("${publicUrl(url, true)}")`)
        .replace(/@import\s+(['"])(.*?)\1/gi, (_match, _quote, url) => `@import "${publicUrl(url)}"`);
    }
    if (key.startsWith('on') && typeof value === 'string') return '';
    return value;
  }));
}

export function visibleState(now = Date.now()) {
  if (!captureAllowed()) return null;
  const overlay = document.querySelector('[data-analytics-overlay="cookie-consent"]');
  // Leaf text elements only: a container's innerText can include text below
  // the fold. Range geometry is checked before including each text node.
  const root = overlay || document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const boxes = [];
  let examined = 0;
  let node;
  while ((node = walker.nextNode()) && examined++ < 1000) {
    const el = node.parentElement;
    if (!el || !node.textContent.trim()) continue;
    if (el.closest('form,[data-private],.rr-block,input,textarea,[contenteditable]')) continue;
    if (el.closest('script,style,noscript')) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const r = range.getBoundingClientRect();
    // A multiline text node can intersect the viewport while most of its text
    // is below the fold. Omit clipped nodes rather than assert unseen words.
    if (r.top < 0 || r.bottom > innerHeight || r.left < 0 || r.right > innerWidth
      || r.bottom <= r.top || r.right <= r.left) continue;
    const x = Math.max(0, Math.min(innerWidth - 1, (Math.max(0, r.left) + Math.min(innerWidth, r.right)) / 2));
    const y = Math.max(0, Math.min(innerHeight - 1, (Math.max(0, r.top) + Math.min(innerHeight, r.bottom)) / 2));
    const top = document.elementFromPoint(x, y);
    if (top && top !== el && !el.contains(top)) continue;
    const content = node.textContent.trim().replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, MASK).slice(0, 500);
    if (!content) continue;
    boxes.push({ tag: el.tagName, text: content, x: Math.round(r.x), y: Math.round(r.y),
      w: Math.round(r.width), h: Math.round(r.height), block: el.getAttribute('data-block') });
    if (boxes.length >= 80) break;
  }
  return { state_id: `${now}-${Math.random().toString(36).slice(2, 8)}`, original_time_ms: now,
    page: location.pathname, viewport: { w: innerWidth, h: innerHeight }, overlay: !!overlay,
    visible_text: boxes.map(b => b.text).join('\n').slice(0, 5000), boxes,
    canvas_count: document.querySelectorAll('canvas').length };
}

export const RECORD_OPTIONS = {
  maskAllInputs: true,
  blockSelector: 'form,[data-private],.rr-block,[contenteditable]',
  maskTextSelector: '[data-private],.rr-mask',
  inlineStylesheet: true,
  recordCanvas: false,
  collectFonts: false,
  // The world-map DOM can be large. Five-minute checkpoints recover a
  // missing snapshot without duplicating its entire tree every minute.
  checkoutEveryNms: 300_000,
  sampling: { mousemove: 200, scroll: 200, input: 'last', media: 1000 },
};

export function splitReplayData(data) {
  const pieces = [];
  for (let offset = 0; offset < data.length;) {
    let end = Math.min(offset + PART_CHARS, data.length);
    // Never split a UTF-16 surrogate pair between JSON fragments.
    if (end < data.length && /[\uD800-\uDBFF]/.test(data[end - 1])) end--;
    pieces.push(data.slice(offset, end)); offset = end;
  }
  return pieces;
}

export function makeReplayTransport({ sessionId, visitor, page, recordingId, fetcher = fetch, allowed = () => true }) {
  let sequence = 0;
  let chain = Promise.resolve();
  let failed = false;
  let pending = 0;
  let reason = null;
  let controller = null;
  const cancel = (why = 'cancelled') => { failed = true; reason = why; controller?.abort(); };
  const send = (batch, ended = false) => {
    if (failed || !allowed()) return Promise.resolve();
    let data;
    try { data = JSON.stringify(batch); }
    catch { cancel('invalid_recording'); return Promise.resolve(); }
    if (typeof data !== 'string') { cancel('invalid_recording'); return Promise.resolve(); }
    if (data.length + pending > MAX_BUFFER * 2 || sequence >= 5000) {
      cancel('transport_limit'); return Promise.resolve();
    }
    const seq = sequence++;
    const fragments = splitReplayData(data);
    const parts = fragments.length;
    const payloads = fragments.map((fragment, part) => JSON.stringify({
      session_id: sessionId, visitor_id: visitor, recording_id: recordingId,
      page, sequence: seq, part, parts, ended, data: fragment,
    }));
    pending += data.length;
    chain = chain.then(async () => {
      try {
      for (const body of payloads) {
        if (failed || !allowed()) { cancel('collection_stopped'); return; }
        let accepted = false;
        for (let attempt = 0; attempt < 2 && !accepted; attempt++) {
          if (failed || !allowed()) { cancel('collection_stopped'); return; }
          controller = new AbortController();
          const timer = setTimeout(() => controller?.abort(), 7000);
          try {
            const response = await fetcher('/api/v1/analytics/replay', {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
              // Normal snapshots can span many fragments; reserving browser
              // keepalive quota for every fragment would drop initial snapshots.
              keepalive: ended && payloads.length === 1,
              signal: controller.signal,
            });
            const result = response.ok ? await response.json() : {};
            accepted = response.ok && result.accepted === true;
            if (result.reason || (response.status >= 400 && response.status < 500)) {
              cancel(result.reason || 'collector_rejected'); return;
            }
          } catch { /* Same sequence/part retry is idempotent on the server. */ }
          finally { clearTimeout(timer); controller = null; }
          if (!allowed()) { cancel('collection_stopped'); return; }
        }
        if (!accepted) { cancel('transport_failed'); return; }
      }
      } finally { pending -= data.length; }
    });
    return chain;
  };
  return { send, cancel, get failed() { return failed; }, get reason() { return reason; }, get pendingBytes() { return pending; } };
}

async function start() {
  if (active || !captureAllowed() || isAutomationClient()) return;
  const startingGeneration = generation;
  try {
    const response = await fetch('/api/v1/analytics/replay/config');
    if (!response.ok || !(await response.json()).enabled) return;
    const { record } = await import('@rrweb/record');
    if (active || !captureAllowed() || startingGeneration !== generation) return;
    const sessionId = behaviorSessionId();
    const visitor = visitorId();
    if (!sessionId || !visitor) return;
    const state = { events: [], states: [], bytes: 0, dropped: 0, stop: null, timer: null, stateTimer: null };
    const transport = makeReplayTransport({ sessionId, visitor, page: location.pathname, recordingId: crypto.randomUUID(), allowed: () => explicitAnalytics !== false && behaviorConsentAllows() });
    state.transport = transport;
    active = state;
    state.flush = (ended = false) => {
      const batch = { events: state.events, states: state.states, dropped: state.dropped, recorder_version: '2.1.6' };
      state.events = []; state.states = []; state.bytes = 0; state.dropped = 0;
      if (batch.events.length || batch.states.length || ended) return transport.send(batch, ended);
    };
    state.stop = record({ ...RECORD_OPTIONS, emit: (raw) => {
      if (!captureAllowed()) { stop(false); return; }
      if (transport.failed) { stop(false); return; }
      const event = scrubReplayEvent(raw);
      const bytes = JSON.stringify(event).length;
      if (state.bytes + bytes > MAX_BUFFER) {
        state.dropped++;
        state.flush();
        return;
      }
      state.events.push(event); state.bytes += bytes;
      if (state.bytes > 100_000) state.flush();
    } });
    const initial = visibleState();
    if (initial) state.states.push(initial);
    state.timer = setInterval(() => state.flush(), 5000);
    state.stateTimer = setInterval(() => {
      if (!captureAllowed()) { stop(false); return; }
      if (document.visibilityState !== 'hidden' && document.hasFocus()) {
        const snapshot = visibleState();
        if (snapshot) state.states.push(snapshot);
      }
      if (state.states.length > 100) { state.states.shift(); state.dropped++; }
    }, 3000);
  } catch { stop(false); }
}

function stop(ended = true) {
  const state = active;
  if (!state) return;
  active = null;
  state.stop?.();
  clearInterval(state.timer); clearInterval(state.stateTimer);
  if (ended && explicitAnalytics !== false && behaviorConsentAllows()) state.flush?.(true);
  else { state.transport?.cancel(); state.events = []; state.states = []; }
}

export function replayRouteChange() {
  generation++;
  stop();
  void start();
}

export function sessionReplayInit() {
  if (initialized) return;
  initialized = true;
  if (isAutomationClient()) return;
  window.addEventListener('pagehide', () => stop());
  window.addEventListener('pageshow', () => { void start(); });
  window.addEventListener('storage', e => { if (e.key === CONSENT_KEY) { explicitAnalytics = null; replayRouteChange(); } });
  window.addEventListener(CONSENT_CHANGE_EVENT, e => {
    explicitAnalytics = e.detail?.analytics;
    if (explicitAnalytics === false) { generation++; stop(false); }
    else replayRouteChange();
  });
  window.addEventListener('fe:analytics-overlay:change', () => {
    const snapshot = visibleState();
    if (active && snapshot) active.states.push(snapshot);
    if (!captureAllowed()) stop(false);
  });
  void start();
}
