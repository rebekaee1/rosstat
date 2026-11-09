// Общий setup vitest. Для node-тестов no-op; для jsdom (component-тесты,
// Т-13) — полифилы браузерных API, которых нет в jsdom, но которые требуют
// recharts (ResizeObserver), gsap/анимации (matchMedia) и трекинг.
import { afterEach } from 'vitest';
import { cleanup, configure } from '@testing-library/react';

if (typeof window !== 'undefined') {
  // Vitest globals выключены, поэтому auto-cleanup testing-library не видит
  // глобальный afterEach. Явно размонтируем React-дерево до teardown jsdom.
  afterEach(cleanup);

  // R8-E: при полном прогоне десятки страниц с lazy-импортами конкурируют за процессор, и стандартная секунда
  // ожидания waitFor/findBy истекает раньше, чем догрузится страница (R7PricesBlock, CurrencyPages, ComparePage,
  // WorldRatingPage, HomeContinue по отдельности зелёные). Ждём дольше: зелёный тест от этого не медленнее.
  configure({ asyncUtilTimeout: 6000 });
  // Хранилище не переходит из теста в тест внутри одного файла (последние страницы, выбранный регион, кэши).
  afterEach(() => {
    try { window.localStorage.clear(); window.sessionStorage.clear(); } catch { /* хранилище недоступно */ }
  });

  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver = window.ResizeObserver || RO;
  window.IntersectionObserver = window.IntersectionObserver
    || class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  window.matchMedia = window.matchMedia
    || ((q) => ({
      matches: false,
      media: q,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
    }));
  window.scrollTo = window.scrollTo || (() => {});
  // sendBeacon дергается behavior.js/track.js на pageview.
  if (!navigator.sendBeacon) navigator.sendBeacon = () => true;
}
