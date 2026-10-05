/**
 * Бюджет и выключатели «сцены света» (раунд 3, K1).
 *
 * Сцена (фон-небо, грани по бокам, герой, блики) красива, но стоит кадров. Здесь решается, сколько из неё
 * показывать на конкретном устройстве. Итог пишется на <html> двумя атрибутами, их читает `styles/k1-scene.css`:
 *   data-fe-motion="off"  нет плавания, параллакса, бликов-проходов (reduced-motion, reduced-transparency,
 *                         Save-Data, слабый процессор);
 *   data-fe-lite="on"     нет картинок и полупрозрачных наложений (Save-Data, reduced-transparency): остаётся
 *                         только цветной фон.
 *
 * Бюджет размытия, который соблюдают все зоны: не больше 12 слоёв `backdrop-filter` в кадре на компьютере
 * и 6 на телефоне. Сама сцена размытия не использует вовсе.
 */

export const BLUR_BUDGET = Object.freeze({ desktop: 12, phone: 6 });

/** Не больше этого числа логических ядер считается слабым устройством: параллакс и плавание выключаются. */
export const LOW_CORE_LIMIT = 4;

const MQ_REDUCED_MOTION = '(prefers-reduced-motion: reduce)';
const MQ_REDUCED_TRANSPARENCY = '(prefers-reduced-transparency: reduce)';

function matches(win, query) {
  try {
    return !!(win && typeof win.matchMedia === 'function' && win.matchMedia(query).matches);
  } catch {
    return false;
  }
}

/**
 * Что можно показывать на этом устройстве прямо сейчас.
 * @param {Window} [win]
 * @returns {{ motion: boolean, lite: boolean, reason: string[] }}
 */
export function readSceneMode(win = typeof window !== 'undefined' ? window : undefined) {
  const reason = [];
  if (!win) return { motion: false, lite: true, reason: ['no-window'] };
  const nav = win.navigator || {};
  const reducedMotion = matches(win, MQ_REDUCED_MOTION);
  const reducedTransparency = matches(win, MQ_REDUCED_TRANSPARENCY);
  const conn = nav.connection || nav.mozConnection || nav.webkitConnection;
  const saveData = !!(conn && conn.saveData);
  const cores = Number(nav.hardwareConcurrency);
  const lowCpu = Number.isFinite(cores) && cores > 0 && cores <= LOW_CORE_LIMIT;

  if (reducedMotion) reason.push('reduced-motion');
  if (reducedTransparency) reason.push('reduced-transparency');
  if (saveData) reason.push('save-data');
  if (lowCpu) reason.push('low-cpu');

  return {
    motion: !(reducedMotion || reducedTransparency || saveData || lowCpu),
    lite: reducedTransparency || saveData,
    reason,
  };
}

/**
 * Пишет режим на <html> и следит за изменениями системных настроек.
 * @returns {() => void} отписка
 */
export function applySceneMode(win = typeof window !== 'undefined' ? window : undefined) {
  if (!win || !win.document) return () => {};
  const root = win.document.documentElement;
  const apply = () => {
    const mode = readSceneMode(win);
    root.setAttribute('data-fe-motion', mode.motion ? 'on' : 'off');
    root.setAttribute('data-fe-lite', mode.lite ? 'on' : 'off');
    root.classList.add('fe-scene-on');
    return mode;
  };
  apply();
  const lists = [MQ_REDUCED_MOTION, MQ_REDUCED_TRANSPARENCY]
    .map((q) => {
      try { return win.matchMedia ? win.matchMedia(q) : null; } catch { return null; }
    })
    .filter(Boolean);
  const onChange = () => apply();
  lists.forEach((l) => (l.addEventListener ? l.addEventListener('change', onChange) : l.addListener?.(onChange)));
  return () => {
    lists.forEach((l) => (l.removeEventListener ? l.removeEventListener('change', onChange) : l.removeListener?.(onChange)));
    root.classList.remove('fe-scene-on');
    root.removeAttribute('data-fe-motion');
    root.removeAttribute('data-fe-lite');
  };
}

/**
 * Какой герой рисовать за первым экраном: главная и карточка страны. Остальные страницы получают только небо.
 * Карточка страны это один сегмент пути, не занятый служебными разделами (`/germany`, `/russia`).
 * @param {string} pathname
 * @param {(segment: string) => boolean} isReserved
 * @returns {'home' | 'country' | null}
 */
export function heroKindForPath(pathname, isReserved) {
  const path = String(pathname || '/').replace(/\/+$/, '') || '/';
  if (path === '/') return 'home';
  const parts = path.split('/').filter(Boolean);
  if (parts.length !== 1) return null;
  if (parts[0].toLowerCase() === 'russia') return 'country';
  return isReserved && isReserved(parts[0]) ? null : 'country';
}

/**
 * Смещение слоя при прокрутке с затуханием: начинается со скорости `depth` от прокрутки (0,15 или 0,3),
 * но не уходит дальше `cap` пикселей, чтобы слой не покинул экран на длинной странице.
 */
export function parallaxOffset(scrollY, depth, cap) {
  const y = Math.max(0, Number(scrollY) || 0);
  const d = Number(depth) || 0;
  const c = Math.max(1, Number(cap) || 1);
  return -c * (1 - Math.exp(-(y * d) / c));
}

/**
 * Переход между страницами «преломление» (K1.6). Оборачивает обновление в View Transition, если браузер умеет
 * и движение разрешено; иначе просто выполняет обновление. Стили переходов в `styles/k1-scene.css`.
 * Для ссылок React Router достаточно prop `viewTransition`; эта функция нужна для программных переходов.
 * @param {() => void} update
 */
export function runWithSceneTransition(update, win = typeof window !== 'undefined' ? window : undefined) {
  const doc = win && win.document;
  const canAnimate = doc && typeof doc.startViewTransition === 'function'
    && doc.documentElement.getAttribute('data-fe-motion') === 'on';
  if (!canAnimate) {
    update();
    return null;
  }
  return doc.startViewTransition(() => {
    update();
  });
}
