import { useSyncExternalStore } from 'react';

/**
 * Светлое стекло шапки, ленты и дока над тёмным подвалом становится грязно-серым. Этот хук говорит, какие из закреплённых
 * элементов сейчас лежат над подвалом (`footer.fe-footer`): им ставится `data-tone="dark"` (сапфировое стекло, светлый текст).
 *
 * Один слушатель прокрутки на документ, расчёт по кадру. Снимок меняется только при смене флагов.
 *   ticker  верхний край экрана (лента курсов, 0–36 px)
 *   nav     шапка (центр ≈ 76 px от верха)
 *   dock    док-панель (центр ≈ 44 px от низа окна)
 */
const NAV_Y = 76;
const TICKER_Y = 18;
const DOCK_FROM_BOTTOM = 44;

let state = { ticker: false, nav: false, dock: false };
let frame = 0;
let listening = false;
const subscribers = new Set();

function measure() {
  if (typeof document === 'undefined') return;
  const footer = document.querySelector('footer.fe-footer');
  let next = { ticker: false, nav: false, dock: false };
  if (footer) {
    const { top, bottom } = footer.getBoundingClientRect();
    const h = window.innerHeight || 0;
    const covers = (y) => top <= y && bottom >= y;
    next = { ticker: covers(TICKER_Y), nav: covers(NAV_Y), dock: covers(h - DOCK_FROM_BOTTOM) };
  }
  if (next.ticker !== state.ticker || next.nav !== state.nav || next.dock !== state.dock) {
    state = next;
    subscribers.forEach((notify) => notify());
  }
}

function schedule() {
  if (frame) return;
  frame = window.requestAnimationFrame(() => {
    frame = 0;
    measure();
  });
}

function subscribe(notify) {
  subscribers.add(notify);
  if (!listening && typeof window !== 'undefined') {
    listening = true;
    state = { ticker: false, nav: false, dock: false };
    measure();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
  }
  return () => {
    subscribers.delete(notify);
    if (subscribers.size === 0 && listening) {
      listening = false;
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      window.cancelAnimationFrame(frame);
      frame = 0;
    }
  };
}

export function useFooterTone() {
  return useSyncExternalStore(subscribe, () => state, () => state);
}
