// @vitest-environment jsdom
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { behaviorInit, behaviorRouteChange, consentAllows, flush, _resetForTests } from './behavior';
import { saveConsent } from './consent';

const callbacks = vi.hoisted(() => ({ inp: null, opts: null }));
vi.mock('web-vitals', () => ({ onLCP: vi.fn(), onCLS: vi.fn(), onFCP: vi.fn(), onTTFB: vi.fn() }));
vi.mock('web-vitals/attribution', () => ({ onINP: (fn, opts) => { callbacks.inp = fn; callbacks.opts = opts; } }));

let fetchMock, handlers, observer, height, y, focused, visibility;
const baseTime = Date.UTC(2026, 8, 30, 13, 44, 20);
const box = (top, bottom) => ({ left: 0, right: 339, top, bottom });
const events = () => fetchMock.mock.calls.flatMap(([, init]) => JSON.parse(init.body).events);
const matching = (type) => events().filter((event) => event.t === type);
const settleDelivery = async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); };
const pointer = (type, target, trusted = true) => handlers.get(type)({ type, target, isTrusted: trusted,
  timeStamp: Date.now() - baseTime, pointerId: 1, pointerType: 'touch', changedTouches: [{ identifier: 1 }] });
const capturedClick = (target) => handlers.get('click')({ type: 'click', target, isTrusted: true,
  timeStamp: Date.now() - baseTime, pageX: 1, pageY: 1, clientX: 1, clientY: 1 });

beforeEach(() => {
  _resetForTests();
  vi.useFakeTimers();
  vi.setSystemTime(baseTime);
  vi.spyOn(performance, 'now').mockImplementation(() => Date.now() - baseTime);
  focused = true; visibility = 'visible'; height = 2000; y = 0;
  vi.spyOn(document, 'hasFocus').mockImplementation(() => focused);
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
  Object.defineProperty(document.documentElement, 'scrollHeight', { configurable: true, get: () => height });
  Object.defineProperty(document.body, 'scrollHeight', { configurable: true, get: () => height });
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 339 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 500 });
  Object.defineProperty(window, 'scrollY', { configurable: true, get: () => y });
  // Test the touch fallback, which also runs on standalone pages without PointerEvent.
  vi.stubGlobal('PointerEvent', undefined);
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback) { this.callback = callback; observer = this; }
    observe() {} unobserve() {} disconnect() {}
  });
  fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ accepted: true }) });
  vi.stubGlobal('fetch', fetchMock);
  vi.spyOn(navigator, 'sendBeacon', 'get').mockReturnValue(undefined);
  handlers = new Map();
  const add = document.addEventListener.bind(document);
  vi.spyOn(document, 'addEventListener').mockImplementation((type, handler, opts) => {
    handlers.set(type, handler); add(type, handler, opts);
  });
  localStorage.clear(); sessionStorage.clear();
  sessionStorage.setItem('fe:analytics:session:meta', '1');
  document.body.innerHTML = '';
  delete window.__feApplyConsent;
  window.history.replaceState({}, '', '/russia/indicator/gold-price/2009');
  callbacks.inp = null; callbacks.opts = null;
});

afterEach(() => {
  _resetForTests();
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();
});

describe('browser evidence integration', () => {
  it('attributes delayed INP to its original SPA page with a sanitized locator', async () => {
    behaviorInit();
    await vi.dynamicImportSettled();
    expect(callbacks.opts.includeProcessedEventEntries).toBe(false);
    vi.advanceTimersByTime(800);
    document.body.innerHTML = '<button data-fe-interaction-action="accept">Хорошо</button>';
    capturedClick(document.querySelector('button'));
    vi.advanceTimersByTime(200);
    behaviorRouteChange('/');
    vi.advanceTimersByTime(60);
    callbacks.inp({ name: 'INP', value: 3744, rating: 'poor', entries: [{ name: 'click' }], attribution: {
      interactionTime: 800, interactionType: 'pointer', interactionTarget: 'button[data-fe-interaction-action=accept]',
      inputDelay: 3700, processingDuration: 20, presentationDelay: 24, loadState: 'complete',
    } });
    flush();
    const vital = matching('vital')[0];
    expect(vital).toMatchObject({ url: '/russia/indicator/gold-price/2009', inp_start_ms: 800,
      inp_target: 'body > button[data-fe-interaction-action=accept]', input_delay_ms: 3700, processing_ms: 20, presentation_ms: 24 });
    expect(vital.pl).toBe(matching('pageview')[0].pl);
    expect(vital.pl).not.toBe(matching('pageview')[1].pl);
  });

  it('retains original INP action when React reuses and renames the target node', async () => {
    document.body.innerHTML = '<button data-fe-interaction-action="customize">Настроить</button>';
    behaviorInit();
    await vi.dynamicImportSettled();
    vi.advanceTimersByTime(1000);
    const button = document.querySelector('button');
    capturedClick(button); // document capture runs before the app's onClick.
    button.setAttribute('data-fe-interaction-action', 'accept-all');
    button.textContent = 'Принять всё';
    vi.advanceTimersByTime(1000);
    callbacks.inp({ name: 'INP', value: 80, rating: 'good', entries: [{ name: 'click' }], attribution: {
      interactionTime: 1000, interactionType: 'pointer', interactionTarget: callbacks.opts.generateTarget(button),
      inputDelay: 20, processingDuration: 40, presentationDelay: 20, loadState: 'complete',
    } });
    flush();
    expect(matching('vital')[0]).toMatchObject({ inp_start_ms: 1000, inp_target_source: 'capture_event' });
    expect(matching('vital')[0].inp_target).toContain('data-fe-interaction-action=customize');
    expect(matching('vital')[0].inp_reported_target).toContain('data-fe-interaction-action=accept-all');
  });

  it('does not turn a post-dispatch library locator into an original target without matching input', async () => {
    behaviorInit();
    await vi.dynamicImportSettled();
    vi.advanceTimersByTime(1000);
    callbacks.inp({ name: 'INP', value: 80, rating: 'good', attribution: {
      interactionTime: 500, interactionType: 'pointer', interactionTarget: 'button[data-fe-interaction-action=accept-all]',
      inputDelay: 20, processingDuration: 40, presentationDelay: 20, loadState: 'complete',
    } });
    flush();
    expect(matching('vital')[0]).toMatchObject({ inp_target: null, inp_target_source: 'unmatched_library',
      inp_reported_target: 'button[data-fe-interaction-action=accept-all]' });
  });

  it('excludes cookie occlusion and focus loss, while retaining one clock across flushes', async () => {
    document.body.innerHTML = '<section data-block="chart"></section><aside data-analytics-overlay="cookie-consent"><button data-fe-interaction-action="accept">Хорошо</button></aside>';
    const block = document.querySelector('section');
    const overlay = document.querySelector('aside');
    block.getBoundingClientRect = () => box(0, 400);
    overlay.getBoundingClientRect = () => box(50, 500);
    behaviorInit();
    observer.callback([{ target: block, isIntersecting: true, intersectionRatio: 1 }]);
    pointer('touchstart', document.querySelector('button'));
    vi.advanceTimersByTime(1000);
    overlay.remove();
    window.dispatchEvent(new CustomEvent('fe:analytics-overlay:change', { detail: { id: 'cookie-consent', visible: false, expanded: false } }));
    vi.advanceTimersByTime(1000);
    focused = false;
    window.dispatchEvent(new Event('blur'));
    vi.advanceTimersByTime(1000);
    focused = true;
    window.dispatchEvent(new Event('focus'));
    vi.advanceTimersByTime(1000);
    visibility = 'hidden';
    document.dispatchEvent(new Event('visibilitychange'));
    const first = matching('block_view')[0];
    expect(first).toMatchObject({ block: 'chart', ms: 2000, visible_ms: 2000, active_ms: 1000, visibility_version: 3 });
    await settleDelivery();
    visibility = 'visible';
    document.dispatchEvent(new Event('visibilitychange'));
    pointer('touchstart', block);
    vi.advanceTimersByTime(1000);
    window.dispatchEvent(new Event('pagehide'));
    expect(matching('block_view')[1]).toMatchObject({ ms: 1000, active_ms: 1000 });
    expect(matching('ui_state').map((event) => event.visible)).toEqual([1, 0]);
  });

  it('never promotes an intersection below 50% to attention', () => {
    document.body.innerHTML = '<section data-block="chart"></section>';
    const block = document.querySelector('section');
    block.getBoundingClientRect = () => box(0, 400);
    behaviorInit();
    observer.callback([{ target: block, isIntersecting: true, intersectionRatio: 0.49 }]);
    pointer('touchstart', block);
    vi.advanceTimersByTime(1000);
    window.dispatchEvent(new Event('pagehide'));
    expect(matching('block_view')).toHaveLength(0);
  });

  it('records repeated touches even when no click/consent handler is dispatched', () => {
    document.body.innerHTML = '<aside data-analytics-overlay="cookie-consent"><button data-fe-interaction-action="accept">Хорошо</button></aside>';
    behaviorInit();
    const button = document.querySelector('button');
    pointer('touchstart', button); vi.advanceTimersByTime(40); pointer('touchend', button);
    vi.advanceTimersByTime(50);
    pointer('touchstart', button); vi.advanceTimersByTime(60); pointer('touchcancel', button);
    flush();
    expect(matching('interaction').map((event) => [event.phase, event.action, event.duration_ms])).toEqual([
      ['start', 'accept', null], ['end', 'accept', 40], ['start', 'accept', null], ['cancel', 'accept', 60],
    ]);
    expect(matching('click')).toHaveLength(0);
    expect(matching('ui_state')).toHaveLength(1);
  });

  it('does not double emit dwell on visibilitychange followed by pagehide', () => {
    behaviorInit();
    vi.advanceTimersByTime(1000);
    visibility = 'hidden';
    document.dispatchEvent(new Event('visibilitychange'));
    vi.advanceTimersByTime(5);
    window.dispatchEvent(new Event('pagehide'));
    expect(matching('dwell')).toHaveLength(1);
    expect(matching('dwell')[0]).toMatchObject({ ms: 1000, scroll_pct: 0, scroll_valid: 0 });
  });

  it('keeps short → tall loading from creating 100% and excludes script-only scroll', () => {
    height = 500;
    behaviorInit();
    window.dispatchEvent(new Event('scroll'));
    height = 2000;
    vi.advanceTimersByTime(300);
    y = 1500;
    window.dispatchEvent(new Event('scroll'));
    vi.advanceTimersByTime(300);
    window.dispatchEvent(new Event('pagehide'));
    expect(matching('dwell')[0]).toMatchObject({ scroll_pct: 0, scroll_valid: 0, scroll_height: 2000 });
  });

  it('revokes immediately even if persistence and applying consent both fail', () => {
    document.body.innerHTML = '<button data-fe-interaction-action="accept">Хорошо</button>';
    behaviorInit();
    pointer('touchstart', document.querySelector('button'));
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('storage blocked'); });
    window.__feApplyConsent = () => { throw new Error('tracker failed'); };
    expect(() => saveConsent({ analytics: false, ads: false })).toThrow('tracker failed');
    expect(consentAllows()).toBe(false);
    pointer('touchend', document.querySelector('button'));
    flush();
    window.dispatchEvent(new Event('pagehide'));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('limits lifecycle volume and keeps untrusted input out of active time', async () => {
    document.body.innerHTML = '<button data-fe-interaction-action="accept">Хорошо</button>';
    behaviorInit();
    const button = document.querySelector('button');
    for (let i = 0; i < 100; i++) { pointer('touchstart', button, false); pointer('touchend', button, false); }
    await settleDelivery();
    vi.advanceTimersByTime(1000);
    window.dispatchEvent(new Event('pagehide'));
    expect(matching('interaction')).toHaveLength(160);
    expect(matching('dwell')[0].active_ms).toBe(0);
  });
});
