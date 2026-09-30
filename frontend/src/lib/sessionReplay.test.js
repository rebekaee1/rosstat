// @vitest-environment jsdom
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const recorder = vi.hoisted(() => ({ emit: null, record: vi.fn(), stopped: vi.fn(), allowed: true }));
vi.mock('@rrweb/record', () => ({ record: recorder.record }));
vi.mock('./behavior', () => ({ visitorId: () => 'visitor-test', sessionId: () => 'session-test',
  consentAllows: () => recorder.allowed, isAutomationClient: () => false }));

let replay, fetchMock, listeners;
const accepted = () => ({ ok: true, status: 200, json: async () => ({ accepted: true }) });
const posts = () => fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST');

beforeEach(async () => {
  vi.resetModules();
  vi.useFakeTimers();
  recorder.allowed = true; recorder.emit = null;
  recorder.stopped.mockReset(); recorder.record.mockReset();
  recorder.record.mockImplementation((options) => { recorder.emit = options.emit; return recorder.stopped; });
  document.body.innerHTML = '';
  window.history.replaceState({}, '', '/russia/indicator/gold-price/2009');
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 339 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 500 });
  vi.spyOn(document, 'hasFocus').mockReturnValue(true);
  localStorage.clear();
  delete window.__feApplyConsent;
  fetchMock = vi.fn().mockImplementation((url) => Promise.resolve(url.endsWith('/config')
    ? { ok: true, json: async () => ({ enabled: true }) } : accepted()));
  vi.stubGlobal('fetch', fetchMock);
  listeners = [];
  const add = window.addEventListener.bind(window);
  vi.spyOn(window, 'addEventListener').mockImplementation((type, handler, opts) => {
    listeners.push([type, handler, opts]); add(type, handler, opts);
  });
  replay = await import('./sessionReplay');
});

afterEach(async () => {
  window.dispatchEvent(new CustomEvent('fe:consent:change', { detail: { analytics: false } }));
  await Promise.resolve();
  for (const [type, handler, opts] of listeners) window.removeEventListener(type, handler, opts);
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();
});

describe('recording transport', () => {
  it('joins multibyte text and emoji without splitting UTF-16 surrogate pairs', () => {
    const original = `${'я'.repeat(7999)}😀金${'😀'.repeat(9000)}`;
    const parts = replay.splitReplayData(original);
    expect(parts.join('')).toBe(original);
    for (const part of parts) {
      expect(part.length).toBeLessThanOrEqual(8000);
      expect(part.at(-1)).not.toMatch(/[\uD800-\uDBFF]/);
      expect(part[0]).not.toMatch(/[\uDC00-\uDFFF]/);
      expect(new TextDecoder().decode(new TextEncoder().encode(part))).toBe(part);
    }
  });

  it('cancels an inflight request without retrying it or sending queued fragments', async () => {
    const fetcher = vi.fn((_url, opts) => new Promise((_resolve, reject) => {
      opts.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    const transport = replay.makeReplayTransport({ sessionId: 's', visitor: 'v', page: '/', recordingId: 'r', fetcher });
    const sent = transport.send({ events: ['x'.repeat(16000)] });
    transport.send({ events: ['later'] });
    await Promise.resolve();
    expect(fetcher).toHaveBeenCalledTimes(1);
    transport.cancel('consent_revoked');
    await sent;
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(transport.failed).toBe(true);
    expect(transport.pendingBytes).toBe(0);
  });

  it('fails closed after bounded request timeouts', async () => {
    const fetcher = vi.fn((_url, opts) => new Promise((_resolve, reject) => {
      opts.signal.addEventListener('abort', () => reject(new DOMException('timeout', 'AbortError')));
    }));
    const transport = replay.makeReplayTransport({ sessionId: 's', visitor: 'v', page: '/', recordingId: 'r', fetcher });
    const sent = transport.send({ events: [1] });
    await vi.advanceTimersByTimeAsync(14_000);
    await sent;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(transport.reason).toBe('transport_failed');
    expect(transport.pendingBytes).toBe(0);
  });

  it('bounds pending payloads and rejects malformed data without throwing or sending', async () => {
    const fetcher = vi.fn().mockResolvedValue(accepted());
    const options = { sessionId: 's', visitor: 'v', page: '/', recordingId: 'r', fetcher };
    const transport = replay.makeReplayTransport(options);
    await transport.send({ events: ['x'.repeat(4_000_000)] });
    expect(transport.reason).toBe('transport_limit');
    expect(fetcher).not.toHaveBeenCalled();
    const invalid = replay.makeReplayTransport(options);
    const circular = {}; circular.self = circular;
    await expect(invalid.send(circular)).resolves.toBeUndefined();
    expect(invalid.reason).toBe('invalid_recording');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('respects server rejection instead of reporting a complete recording', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200,
      json: async () => ({ accepted: false, reason: 'visitor_quota' }) });
    const transport = replay.makeReplayTransport({ sessionId: 's', visitor: 'v', page: '/', recordingId: 'r', fetcher });
    await transport.send({ events: [1] });
    await transport.send({ events: [2] });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(transport.reason).toBe('visitor_quota');
  });
});

describe('privacy and visible evidence', () => {
  it.each(['/forgot-password', '/verify-email', '/verify-email/code', '/account', '/login', '/register'])('excludes private route %s before collection', (path) => {
    expect(replay.replayPageAllowed(path)).toBe(false);
  });
  it('scrubs sensitive attributes, URL queries, srcset, inline handlers and CSS URLs', () => {
    const result = replay.scrubReplayEvent({ node: { attributes: {
      value: 'my-password', placeholder: 'my-email@example.com', 'data-auth-token': 'secret-token',
      href: 'https://example.com/path?token=secret#account', src: '/image.png?email=user@example.com',
      srcset: '/one.png?token=a 1x,/two.png?token=b 2x', onclick: 'secret()',
      style: 'background:url("/asset.png?token=secret");content:"user@example.com"',
    }, _cssText: '@import "/styles.css?token=secret";a{background:url(https://cdn.test/img?secret=1)}' } });
    const serialized = JSON.stringify(result);
    expect(serialized).not.toMatch(/secret|my-password|my-email|user@example/);
    expect(result.node.attributes.srcset).toBe('');
    expect(result.node.attributes.href).toBe('https://example.com/path');
    expect(replay.RECORD_OPTIONS).toMatchObject({ maskAllInputs: true, recordCanvas: false });
  });

  it('retains safe local CSS/SVG paint references while scrubbing external SVG URLs', () => {
    const result = replay.scrubReplayEvent({ attributes: {
      style: 'clip-path:url(#recharts-clip-1);fill:url("#gradient:2")',
      'xlink:href': '#marker-1', href: '/link?token=secret#private',
    }, node: { attributes: { 'xlink:href': 'https://cdn.test/icon.svg?token=secret#person' } } });
    expect(result.attributes.style).toBe('clip-path:url("#recharts-clip-1");fill:url("#gradient:2")');
    expect(result.attributes['xlink:href']).toBe('#marker-1');
    expect(result.node.attributes['xlink:href']).toBe('https://cdn.test/icon.svg');
    expect(result.attributes.href).not.toContain('private');
  });

  it('does not describe below-fold, private or obscured text as visible', () => {
    document.body.innerHTML = '<p id="visible">Видимый график</p><p id="below">Ниже экрана</p><p id="partial">Начало видно, продолжение ниже экрана</p><form><p>Частный ввод</p></form><p id="covered">Перекрыто</p>';
    const ranges = { 'Видимый график': { x: 0, y: 10, left: 0, right: 200, top: 10, bottom: 30, width: 200, height: 20 },
      'Ниже экрана': { x: 0, y: 600, left: 0, right: 200, top: 600, bottom: 620, width: 200, height: 20 },
      'Начало видно, продолжение ниже экрана': { x: 0, y: 400, left: 0, right: 200, top: 400, bottom: 900, width: 200, height: 500 },
      'Перекрыто': { x: 0, y: 40, left: 0, right: 200, top: 40, bottom: 60, width: 200, height: 20 } };
    Object.defineProperty(Range.prototype, 'getBoundingClientRect', { configurable: true,
      value() { return ranges[this.startContainer.textContent]; } });
    Object.defineProperty(document, 'elementFromPoint', { configurable: true,
      value: () => document.querySelector('#visible') });
    const state = replay.visibleState(123);
    expect(state.visible_text).toBe('Видимый график');
    expect(state.boxes).toHaveLength(1);
  });

  it('stops on a private route before recording private DOM changes', async () => {
    replay.sessionReplayInit();
    await vi.dynamicImportSettled();
    expect(recorder.record).toHaveBeenCalledTimes(1);
    window.history.replaceState({}, '', '/account');
    recorder.emit({ type: 3, data: { textContent: 'private-account-secret' } });
    replay.replayRouteChange();
    await vi.dynamicImportSettled();
    expect(recorder.stopped).toHaveBeenCalled();
    expect(recorder.record).toHaveBeenCalledTimes(1);
    expect(posts()).toHaveLength(0);
    expect(replay.visibleState()).toBeNull();
  });

  it('revokes queued recordings through the real consent event despite storage/apply failure', async () => {
    replay.sessionReplayInit();
    await vi.dynamicImportSettled();
    recorder.emit({ type: 3, data: { textContent: 'public-event-not-yet-sent' } });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('storage blocked'); });
    window.__feApplyConsent = () => { throw new Error('tracker failed'); };
    const { saveConsent } = await import('./consent');
    expect(() => saveConsent({ analytics: false, ads: false })).toThrow('tracker failed');
    await vi.advanceTimersByTimeAsync(10_000);
    window.dispatchEvent(new Event('pagehide'));
    expect(recorder.stopped).toHaveBeenCalledTimes(1);
    expect(posts()).toHaveLength(0);
    expect(replay.visibleState()).toBeNull();
  });
});
