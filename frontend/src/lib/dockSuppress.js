import { useEffect, useState } from 'react';

/**
 * Когда нижнюю панель телефона надо убрать с экрана, чтобы она не мешала (круг 11, G, U29):
 *   typing    фокус в поле, где печатают (текст, поиск, число, список, textarea): поднимается клавиатура и панель стояла бы над ней;
 *   keyboard  видимая часть окна заметно ниже окна целиком (visualViewport уменьшился больше чем на 140 px): клавиатура открыта, даже если
 *             фокус перешёл на кнопку «Готово»;
 *   dragging  палец на бегунке (input[type=range], role="slider") или на ручке диапазона: бегунок у нижнего края не должен прятаться
 *             под панелью, пока его тянут; панель возвращается через 0,6 с после отпускания.
 * Хук отдаёт одно значение: true, если мешает хоть одна причина. Все слушатели пассивные и общие для документа.
 */

const TEXT_TYPES = new Set(['text', 'search', 'email', 'url', 'tel', 'password', 'number', 'date', 'datetime-local', 'month', 'time', 'week']);
const KEYBOARD_DELTA = 140;
const RELEASE_MS = 600;
const BLUR_MS = 140;

/** В элементе печатают: текстовое поле, textarea, список-select, contenteditable. Кнопки, флажки и бегунки сюда не входят. */
export function isTextEntryElement(el) {
  if (!el || el.nodeType !== 1) return false;
  const tag = el.tagName;
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag === 'INPUT') return TEXT_TYPES.has(String(el.getAttribute('type') || 'text').toLowerCase());
  return el.isContentEditable === true || el.getAttribute?.('contenteditable') === 'true';
}

/** Элемент, который тянут пальцем: бегунок или ручка диапазона графика. */
export function isSliderElement(el) {
  if (!el || el.nodeType !== 1) return false;
  if (el.tagName === 'INPUT' && String(el.getAttribute('type') || '').toLowerCase() === 'range') return true;
  return Boolean(el.closest?.('[role="slider"], input[type="range"], [data-fe-drag-handle], .recharts-brush-traveller, .recharts-brush-slide'));
}

/** Клавиатура открыта по размерам окна: видимая область заметно ниже окна. */
export function keyboardOpenBySize(innerHeight, viewportHeight) {
  if (!Number.isFinite(innerHeight) || !Number.isFinite(viewportHeight)) return false;
  return innerHeight - viewportHeight > KEYBOARD_DELTA;
}

export function useDockSuppressed() {
  // Страница могла открыться с фокусом в поле (автофокус): учитываем сразу.
  const [typing, setTyping] = useState(() => typeof document !== 'undefined' && isTextEntryElement(document.activeElement));
  const [keyboard, setKeyboard] = useState(false);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    let blurTimer = 0;
    let releaseTimer = 0;
    const onFocusIn = (event) => {
      window.clearTimeout(blurTimer);
      if (isTextEntryElement(event.target)) setTyping(true);
    };
    const onFocusOut = () => {
      window.clearTimeout(blurTimer);
      blurTimer = window.setTimeout(() => setTyping(isTextEntryElement(document.activeElement)), BLUR_MS);
    };
    const onDown = (event) => {
      if (!isSliderElement(event.target)) return;
      window.clearTimeout(releaseTimer);
      setDragging(true);
    };
    const onUp = () => {
      window.clearTimeout(releaseTimer);
      releaseTimer = window.setTimeout(() => setDragging(false), RELEASE_MS);
    };
    const vv = window.visualViewport;
    const onResize = () => setKeyboard(keyboardOpenBySize(window.innerHeight, vv ? vv.height : window.innerHeight));

    document.addEventListener('focusin', onFocusIn);
    document.addEventListener('focusout', onFocusOut);
    document.addEventListener('pointerdown', onDown, { passive: true });
    document.addEventListener('touchstart', onDown, { passive: true });
    document.addEventListener('pointerup', onUp, { passive: true });
    document.addEventListener('pointercancel', onUp, { passive: true });
    document.addEventListener('touchend', onUp, { passive: true });
    document.addEventListener('touchcancel', onUp, { passive: true });
    vv?.addEventListener('resize', onResize);
    return () => {
      window.clearTimeout(blurTimer);
      window.clearTimeout(releaseTimer);
      document.removeEventListener('focusin', onFocusIn);
      document.removeEventListener('focusout', onFocusOut);
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('touchstart', onDown);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onUp);
      document.removeEventListener('touchend', onUp);
      document.removeEventListener('touchcancel', onUp);
      vv?.removeEventListener('resize', onResize);
    };
  }, []);

  return typing || keyboard || dragging;
}
