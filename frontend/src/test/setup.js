// Общий setup vitest. Для node-тестов no-op; для jsdom (component-тесты,
// Т-13) — полифилы браузерных API, которых нет в jsdom, но которые требуют
// recharts (ResizeObserver), gsap/анимации (matchMedia) и трекинг.
if (typeof window !== 'undefined') {
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
