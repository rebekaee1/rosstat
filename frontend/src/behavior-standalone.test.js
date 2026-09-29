import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const renderFloorAd = vi.fn();
const behaviorInit = vi.fn();
vi.mock('./lib/rsyFloorAd', () => ({ renderFloorAd }));
vi.mock('./lib/behavior', () => ({ behaviorInit }));

/** Минимальный document/window без jsdom (vitest environment: node). */
function stubDom({ noAds = false } = {}) {
  vi.stubGlobal('window', {});
  vi.stubGlobal('document', {
    readyState: 'complete',
    body: { hasAttribute: (name) => noAds && name === 'data-no-ads' },
    addEventListener: vi.fn(),
  });
}

describe('behavior-standalone: реклама на быстрых ссылках', () => {
  beforeEach(() => {
    vi.resetModules();
    renderFloorAd.mockClear();
    behaviorInit.mockClear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it('ставит floorAd в очередь yaContextCb и рендерит его при исполнении', async () => {
    stubDom();
    await import('./behavior-standalone');
    expect(behaviorInit).toHaveBeenCalledTimes(1);
    expect(window.yaContextCb).toHaveLength(1);
    // Рендер только когда context.js (после сигнала человека) разберёт очередь.
    expect(renderFloorAd).not.toHaveBeenCalled();
    window.yaContextCb[0]();
    expect(renderFloorAd).toHaveBeenCalledTimes(1);
  });

  it('не просит рекламу на странице с data-no-ads (404)', async () => {
    stubDom({ noAds: true });
    await import('./behavior-standalone');
    expect(behaviorInit).toHaveBeenCalledTimes(1);
    expect(window.yaContextCb).toBeUndefined();
  });

  it('ошибка SDK не роняет страницу', async () => {
    stubDom();
    renderFloorAd.mockImplementationOnce(() => { throw new Error('adblock'); });
    await import('./behavior-standalone');
    expect(() => window.yaContextCb[0]()).not.toThrow();
  });
});
