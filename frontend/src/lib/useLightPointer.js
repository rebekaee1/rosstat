import { useEffect } from 'react';

/**
 * Свет, который следует за курсором, и блик-проход «один раз при появлении» (раунд 3, K1.3).
 *
 * Один слушатель `pointermove` на весь документ и один IntersectionObserver, сколько бы элементов ни пользовалось
 * классами `.fe-cursor-light` и `.fe-glint` (стили в `styles/k1-scene.css`). Элементам не нужны ни ref, ни хуки:
 * достаточно класса. Хук `useLightPointer()` вызывается один раз в `LightScene` и держит эти слушатели живыми.
 *
 * Что происходит:
 *   - курсор над `.fe-cursor-light`: элементу выставляются `--mx`/`--my` (позиция внутри него, px) и атрибут
 *     `data-fe-lit`; CSS рисует радиальный свет. Работа на rAF, не чаще одного раза за кадр.
 *   - `.fe-glint` впервые попал в окно (35 % площади): получает `data-fe-glint="on"`, CSS проигрывает блик
 *     900 мс, по `animationend` атрибут становится `done` и блик больше сам не повторяется (остаётся hover).
 *   - тач и мышь без точности (`pointer: coarse`): курсорный свет не включается.
 */

const LIGHT_SEL = '.fe-cursor-light';
const GLINT_SEL = '.fe-glint';

let refCount = 0;
let teardown = null;

function canFinePointer(win) {
  try {
    return !!(win.matchMedia && win.matchMedia('(hover: hover) and (pointer: fine)').matches);
  } catch {
    return false;
  }
}

function install(win) {
  const doc = win.document;
  const cleanups = [];

  // 1. Свет за курсором.
  if (canFinePointer(win)) {
    let frame = 0;
    let lastEvent = null;
    let lit = null;

    const clear = () => {
      if (lit) {
        lit.removeAttribute('data-fe-lit');
        lit = null;
      }
    };

    const paint = () => {
      frame = 0;
      const e = lastEvent;
      lastEvent = null;
      if (!e) return;
      const target = e.target instanceof win.Element ? e.target.closest(LIGHT_SEL) : null;
      if (!target) {
        clear();
        return;
      }
      if (lit && lit !== target) lit.removeAttribute('data-fe-lit');
      const rect = target.getBoundingClientRect();
      target.style.setProperty('--mx', `${Math.round(e.clientX - rect.left)}px`);
      target.style.setProperty('--my', `${Math.round(e.clientY - rect.top)}px`);
      target.setAttribute('data-fe-lit', '');
      lit = target;
    };

    const onMove = (e) => {
      lastEvent = e;
      if (!frame) frame = win.requestAnimationFrame(paint);
    };
    const onLeave = (e) => {
      if (e.relatedTarget === null) {
        lastEvent = null;
        clear();
      }
    };
    doc.addEventListener('pointermove', onMove, { passive: true });
    doc.addEventListener('pointerout', onLeave, { passive: true });
    cleanups.push(() => {
      doc.removeEventListener('pointermove', onMove);
      doc.removeEventListener('pointerout', onLeave);
      if (frame) win.cancelAnimationFrame(frame);
      clear();
    });
  }

  // 2. Блик-проход при первом появлении.
  if (typeof win.IntersectionObserver === 'function' && typeof win.MutationObserver === 'function') {
    const io = new win.IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        io.unobserve(entry.target);
        if (!entry.target.hasAttribute('data-fe-glint')) entry.target.setAttribute('data-fe-glint', 'on');
      }
    }, { threshold: 0.35 });

    const seen = new WeakSet();
    const scan = () => {
      doc.querySelectorAll(GLINT_SEL).forEach((el) => {
        if (seen.has(el) || el.hasAttribute('data-fe-glint')) return;
        seen.add(el);
        io.observe(el);
      });
    };
    scan();

    // Новые узлы приходят вместе с маршрутами; проверка не чаще раза в 200 мс.
    let timer = 0;
    const mo = new win.MutationObserver(() => {
      if (timer) return;
      timer = win.setTimeout(() => { timer = 0; scan(); }, 200);
    });
    mo.observe(doc.body || doc.documentElement, { childList: true, subtree: true });

    const onEnd = (e) => {
      if (!e.animationName || !e.animationName.startsWith('fe-glint-once')) return;
      const el = e.target;
      if (el instanceof win.Element) {
        const host = el.closest(GLINT_SEL);
        if (host && host.getAttribute('data-fe-glint') === 'on') host.setAttribute('data-fe-glint', 'done');
      }
    };
    doc.addEventListener('animationend', onEnd, true);

    cleanups.push(() => {
      io.disconnect();
      mo.disconnect();
      if (timer) win.clearTimeout(timer);
      doc.removeEventListener('animationend', onEnd, true);
    });
  }

  return () => cleanups.forEach((fn) => fn());
}

/** Подключает слушатели (по счётчику ссылок). Возвращает отписку. Вне браузера ничего не делает. */
export function installLightPointer(win = typeof window !== 'undefined' ? window : undefined) {
  if (!win || !win.document) return () => {};
  if (refCount === 0) teardown = install(win);
  refCount += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    refCount -= 1;
    if (refCount === 0 && teardown) {
      teardown();
      teardown = null;
    }
  };
}

/** Хук: свет за курсором и блики-проходы работают, пока смонтирован хотя бы один вызов. */
export function useLightPointer() {
  useEffect(() => installLightPointer(), []);
}

export default useLightPointer;
