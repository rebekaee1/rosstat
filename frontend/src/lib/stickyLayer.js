import { useSyncExternalStore } from 'react';

/**
 * Плашка «Результат» калькулятора (CalcStickyResult) и нижняя панель телефона (MobileDock) делят нижний край экрана.
 * Они не должны стоять друг над другом: пока плашка на экране, панель прячется, а плавающие кнопки страницы поднимаются
 * над плашкой. Состояние одно на документ, его читают оба компонента и CSS (круг 9, зона A).
 *
 * На корне документа:
 *   html[data-fe-sticky]   плашка на экране (CSS: прячет панель, расширяет запас прокрутки внизу)
 *   --fe-sticky-h          сколько места плашка занимает внизу сейчас (52px, пока видна; 0px, когда нет);
 *                          входит в --fe-bottom-clear (styles/z1-tokens.css)
 */
export const STICKY_HEIGHT = 52;

let active = false;
const subscribers = new Set();

/** Плашка показана (true) или убрана (false). Повторный вызов с тем же значением ничего не делает. */
export function setStickyActive(next) {
  const value = Boolean(next);
  if (value === active) return;
  active = value;
  if (typeof document !== 'undefined') {
    const root = document.documentElement;
    if (value) {
      root.dataset.feSticky = 'on';
      root.style.setProperty('--fe-sticky-h', `${STICKY_HEIGHT}px`);
    } else {
      delete root.dataset.feSticky;
      root.style.removeProperty('--fe-sticky-h');
    }
  }
  subscribers.forEach((notify) => notify());
}

function subscribe(notify) {
  subscribers.add(notify);
  return () => { subscribers.delete(notify); };
}

/** true, пока на экране плашка «Результат». */
export function useStickyActive() {
  return useSyncExternalStore(subscribe, () => active, () => false);
}
