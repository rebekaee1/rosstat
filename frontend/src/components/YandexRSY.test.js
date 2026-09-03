import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  isFloorAdShellEmpty,
  renderFloorAd,
  blockForPlatform,
  REFRESH_COOLDOWN_MS,
  __resetFloorAdState,
  __RSY_TEST,
} from '../lib/rsyFloorAd';

/** Минимальный DOM-like шелл без jsdom (vitest environment: node). */
function shell({ media = [], slots = [], text = '' } = {}) {
  return {
    querySelector(sel) {
      if (/iframe|img|video|canvas|object|embed|source|yanetag|data-videoname/i.test(sel)) {
        return media[0] || null;
      }
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '.needsclick') return slots;
      if (/iframe|img|video|canvas|object|embed|source|yanetag|data-videoname/i.test(sel)) {
        return media;
      }
      return [];
    },
    innerText: text,
  };
}

describe('isFloorAdShellEmpty', () => {
  it('считает пустым шелл без media и с пустым needsclick', () => {
    expect(
      isFloorAdShellEmpty(shell({ slots: [{ children: [], innerText: '' }] }))
    ).toBe(true);
  });

  it('не пустой при живом img', () => {
    expect(
      isFloorAdShellEmpty(
        shell({ media: [{ tagName: 'IMG', naturalWidth: 120, complete: true }] })
      )
    ).toBe(false);
  });

  it('пустой при битом img и пустом слоте', () => {
    expect(
      isFloorAdShellEmpty(
        shell({
          media: [{ tagName: 'IMG', naturalWidth: 0, complete: true }],
          slots: [{ children: [], innerText: '' }],
        })
      )
    ).toBe(true);
  });

  it('не пустой при iframe', () => {
    expect(isFloorAdShellEmpty(shell({ media: [{ tagName: 'IFRAME' }] }))).toBe(false);
  });

  it('не пустой при video', () => {
    expect(isFloorAdShellEmpty(shell({ media: [{ tagName: 'VIDEO' }] }))).toBe(false);
  });

  it('не пустой при canvas', () => {
    expect(isFloorAdShellEmpty(shell({ media: [{ tagName: 'CANVAS' }] }))).toBe(false);
  });

  it('не пустой при тексте объявления в needsclick', () => {
    expect(
      isFloorAdShellEmpty(
        shell({ slots: [{ children: [], innerText: 'Купить сталь оптом' }] })
      )
    ).toBe(false);
  });

  it('не пустой при тексте объявления вне needsclick', () => {
    expect(
      isFloorAdShellEmpty(shell({ text: 'Скидка на ипотеку до конца месяца' }))
    ).toBe(false);
  });

  it('игнорирует метку РЕКЛАМА как единственный текст', () => {
    expect(isFloorAdShellEmpty(shell({ text: 'РЕКЛАМА' }))).toBe(true);
  });

  it('игнорирует chrome РЕКЛАМА + Закрыть без креатива', () => {
    expect(isFloorAdShellEmpty(shell({ text: 'РЕКЛАМА Закрыть' }))).toBe(true);
  });

  it('пустой needsclick + текст снаружи = fill (не early-empty по слоту)', () => {
    expect(
      isFloorAdShellEmpty(
        shell({
          slots: [{ children: [], innerText: '' }],
          text: 'Специальное предложение банка',
        })
      )
    ).toBe(false);
  });
});

describe('обновление блока на SPA-навигации', () => {
  let calls;
  let destroyed;

  beforeEach(() => {
    __resetFloorAdState();
    calls = [];
    destroyed = [];
    globalThis.window = {
      Ya: {
        Context: {
          AdvManager: {
            getPlatform: () => 'desktop',
            render: (opts) => calls.push(opts),
            destroy: (opts) => destroyed.push(opts),
          },
        },
      },
      getComputedStyle: () => ({ position: 'static' }),
    };
    globalThis.document = undefined;
  });

  afterEach(() => {
    delete globalThis.window;
    delete globalThis.document;
  });

  it('первый рендер уходит в РСЯ с pageNumber=1', () => {
    expect(renderFloorAd({ now: 0 })).toBe(true);
    expect(calls).toHaveLength(1);
    expect(calls[0].pageNumber).toBe(1);
    expect(calls[0].blockId).toBe('R-A-19489903-1');
  });

  it('смена маршрута после кулдауна обновляет объявление', () => {
    renderFloorAd({ now: 0 });
    const ok = renderFloorAd({ refresh: true, now: REFRESH_COOLDOWN_MS + 1 });
    expect(ok).toBe(true);
    expect(calls).toHaveLength(2);
    // Занятый контейнер обязан быть освобождён, иначе SDK молчит.
    expect(destroyed).toHaveLength(1);
    expect(calls[1].pageNumber).toBe(2);
  });

  it('быстрые клики по меню не мигают рекламой', () => {
    renderFloorAd({ now: 0 });
    expect(renderFloorAd({ refresh: true, now: 5_000 })).toBe(false);
    expect(renderFloorAd({ refresh: true, now: 14_000 })).toBe(false);
    expect(calls).toHaveLength(1);
    expect(destroyed).toHaveLength(0);
  });

  it('кулдаун — не «раз в документ»: третий экран получает своё объявление', () => {
    renderFloorAd({ now: 0 });
    renderFloorAd({ refresh: true, now: 16_000 });
    renderFloorAd({ refresh: true, now: 32_000 });
    expect(calls.map((c) => c.pageNumber)).toEqual([1, 2, 3]);
  });

  it('без SDK (AdBlock/CSP) ничего не падает и запрос не уходит', () => {
    globalThis.window = { Ya: undefined };
    expect(renderFloorAd({ now: 0 })).toBe(false);
  });

  it('на touch выбирается мобильный блок', () => {
    const adv = { getPlatform: () => 'touch' };
    expect(blockForPlatform(adv).blockId).toBe('R-A-19489903-2');
  });

  it('кулдаун 15 с: ниже медианы живого 2-го экрана, выше проклика меню', () => {
    expect(REFRESH_COOLDOWN_MS).toBe(15_000);
  });
});

describe('empty-shell watchdog policy', () => {
  it('timer auto-destroy отключён — снос только через onError', () => {
    expect(__RSY_TEST.AUTO_DESTROY_DISABLED).toBe(true);
  });

  it('EMPTY_CHECK_MS не в опасном окне ~5–8 с (регрессия к kill-live-ads)', () => {
    expect(__RSY_TEST.EMPTY_CHECK_MS).toBeGreaterThan(60_000);
  });
});
