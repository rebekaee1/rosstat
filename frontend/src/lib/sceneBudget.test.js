// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import {
  BLUR_BUDGET,
  applySceneMode,
  heroKindForPath,
  parallaxOffset,
  readSceneMode,
  runWithSceneTransition,
} from './sceneBudget';
import { isReservedFirstSegment } from './sitePaths';

function fakeWin({ reducedMotion = false, reducedTransparency = false, saveData = false, cores = 12 } = {}) {
  return {
    navigator: { hardwareConcurrency: cores, connection: { saveData } },
    matchMedia: (q) => ({
      matches: q.includes('reduced-motion') ? reducedMotion : q.includes('reduced-transparency') ? reducedTransparency : false,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
  };
}

describe('sceneBudget: режим сцены', () => {
  it('на обычном компьютере движение и картинки включены', () => {
    expect(readSceneMode(fakeWin())).toEqual({ motion: true, lite: false, reason: [] });
  });

  it('prefers-reduced-motion выключает движение, но не картинки', () => {
    const m = readSceneMode(fakeWin({ reducedMotion: true }));
    expect(m.motion).toBe(false);
    expect(m.lite).toBe(false);
    expect(m.reason).toContain('reduced-motion');
  });

  it('prefers-reduced-transparency и Save-Data выключают и движение, и картинки', () => {
    for (const opts of [{ reducedTransparency: true }, { saveData: true }]) {
      const m = readSceneMode(fakeWin(opts));
      expect(m.motion).toBe(false);
      expect(m.lite).toBe(true);
    }
  });

  it('четыре ядра и меньше: без движения, картинки остаются', () => {
    const m = readSceneMode(fakeWin({ cores: 4 }));
    expect(m.motion).toBe(false);
    expect(m.lite).toBe(false);
    expect(m.reason).toContain('low-cpu');
    expect(readSceneMode(fakeWin({ cores: 5 })).motion).toBe(true);
  });

  it('неизвестное число ядер не считается слабым устройством', () => {
    const w = fakeWin();
    w.navigator.hardwareConcurrency = undefined;
    expect(readSceneMode(w).motion).toBe(true);
  });

  it('бюджет размытия: 12 на компьютере, 6 на телефоне', () => {
    expect(BLUR_BUDGET).toEqual({ desktop: 12, phone: 6 });
  });

  it('applySceneMode пишет атрибуты на html и снимает их при отписке', () => {
    const off = applySceneMode(window);
    const root = document.documentElement;
    expect(root.getAttribute('data-fe-motion')).toMatch(/^(on|off)$/);
    expect(root.getAttribute('data-fe-lite')).toMatch(/^(on|off)$/);
    expect(root.classList.contains('fe-scene-on')).toBe(true);
    off();
    expect(root.hasAttribute('data-fe-motion')).toBe(false);
    expect(root.classList.contains('fe-scene-on')).toBe(false);
  });
});

describe('sceneBudget: герой по адресу', () => {
  it('главная и карточка страны получают героя', () => {
    expect(heroKindForPath('/', isReservedFirstSegment)).toBe('home');
    expect(heroKindForPath('/germany', isReservedFirstSegment)).toBe('country');
    expect(heroKindForPath('/germany/', isReservedFirstSegment)).toBe('country');
    expect(heroKindForPath('/russia', isReservedFirstSegment)).toBe('country');
  });

  it('служебные разделы и вложенные страницы без героя', () => {
    for (const p of ['/about', '/calculator', '/compare', '/currencies', '/forecasts', '/germany/indicator/x', '/russia/regions']) {
      expect(heroKindForPath(p, isReservedFirstSegment)).toBeNull();
    }
  });
});

describe('sceneBudget: параллакс', () => {
  it('начинается со скорости depth и не уходит дальше cap', () => {
    expect(parallaxOffset(0, 0.15, 160)).toBe(-0);
    expect(parallaxOffset(100, 0.15, 160)).toBeCloseTo(-14.3, 0);
    expect(parallaxOffset(100000, 0.15, 160)).toBeGreaterThan(-160.001);
    expect(parallaxOffset(100000, 0.3, 320)).toBeGreaterThan(-320.001);
  });

  it('смещение монотонно растёт по модулю', () => {
    let prev = 0;
    for (let y = 0; y <= 4000; y += 200) {
      const v = Math.abs(parallaxOffset(y, 0.3, 320));
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });
});

describe('sceneBudget: переход между страницами', () => {
  it('без View Transitions или при выключенном движении просто выполняет обновление', () => {
    const update = vi.fn();
    expect(runWithSceneTransition(update, { document: { documentElement: { getAttribute: () => 'on' } } })).toBeNull();
    expect(update).toHaveBeenCalledTimes(1);

    const update2 = vi.fn();
    const startViewTransition = vi.fn();
    runWithSceneTransition(update2, { document: { startViewTransition, documentElement: { getAttribute: () => 'off' } } });
    expect(startViewTransition).not.toHaveBeenCalled();
    expect(update2).toHaveBeenCalledTimes(1);
  });

  it('при поддержке оборачивает обновление в startViewTransition', () => {
    const update = vi.fn();
    const startViewTransition = vi.fn((cb) => { cb(); return { finished: Promise.resolve() }; });
    runWithSceneTransition(update, { document: { startViewTransition, documentElement: { getAttribute: () => 'on' } } });
    expect(startViewTransition).toHaveBeenCalledTimes(1);
    expect(update).toHaveBeenCalledTimes(1);
  });
});
