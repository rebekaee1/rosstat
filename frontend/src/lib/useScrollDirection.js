import { useSyncExternalStore } from 'react';

/**
 * Куда и насколько прокручена страница: один общий слушатель на весь документ (шапка, лента курсов, док-панель
 * и cookie-значок читают одно и то же состояние, а не вешают по своему обработчику).
 *
 * Снимок меняется только при смене одного из полей, поэтому компоненты не перерисовываются на каждый кадр прокрутки:
 *   scrolled  страница сдвинута больше чем на 24 px (шапка становится плотнее)
 *   deep      сдвиг больше 96 px (есть смысл сжимать шапку, прятать ленту, показывать док-панель)
 *   dir       'down' | 'up': последнее заметное направление (порог 6 px, чтобы дрожь пальца не считалась)
 *   idle      прокрутка остановилась (700 мс без событий)
 *   rest      человек остановился надолго (2,5 с без событий): док-панель возвращается и без движения вверх (круг 9, S1)
 */
const SCROLLED_AT = 24;
const DEEP_AT = 96;
const MIN_DELTA = 6;
const IDLE_MS = 700;
const REST_MS = 2500;

let state = { scrolled: false, deep: false, dir: 'up', idle: true, rest: true };
let lastY = 0;
let frame = 0;
let idleTimer = 0;
let restTimer = 0;
let listening = false;
const subscribers = new Set();

const readY = () => (typeof window === 'undefined' ? 0 : Math.max(0, window.scrollY || window.pageYOffset || 0));

function commit(next) {
  if (
    next.scrolled === state.scrolled
    && next.deep === state.deep
    && next.dir === state.dir
    && next.idle === state.idle
    && next.rest === state.rest
  ) return;
  state = next;
  subscribers.forEach((notify) => notify());
}

function measure(idle) {
  const y = readY();
  let { dir } = state;
  if (y <= 0) {
    dir = 'up';
    lastY = 0;
  } else if (Math.abs(y - lastY) >= MIN_DELTA) {
    dir = y > lastY ? 'down' : 'up';
    lastY = y;
  }
  commit({ scrolled: y > SCROLLED_AT, deep: y > DEEP_AT, dir, idle, rest: idle ? state.rest : false });
}

function onScroll() {
  if (frame) return;
  frame = window.requestAnimationFrame(() => {
    frame = 0;
    measure(false);
    window.clearTimeout(idleTimer);
    window.clearTimeout(restTimer);
    idleTimer = window.setTimeout(() => commit({ ...state, idle: true }), IDLE_MS);
    restTimer = window.setTimeout(() => commit({ ...state, idle: true, rest: true }), REST_MS);
  });
}

function subscribe(notify) {
  subscribers.add(notify);
  if (!listening && typeof window !== 'undefined') {
    listening = true;
    lastY = readY();
    state = { scrolled: false, deep: false, dir: 'up', idle: true, rest: true };
    measure(true);
    window.addEventListener('scroll', onScroll, { passive: true });
  }
  return () => {
    subscribers.delete(notify);
    if (subscribers.size === 0 && listening) {
      listening = false;
      window.removeEventListener('scroll', onScroll);
      window.cancelAnimationFrame(frame);
      window.clearTimeout(idleTimer);
      window.clearTimeout(restTimer);
      frame = 0;
    }
  };
}

const getSnapshot = () => state;
const getServerSnapshot = () => state;

export function useScrollDirection() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
