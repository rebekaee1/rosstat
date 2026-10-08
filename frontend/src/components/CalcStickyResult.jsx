// Результат калькулятора, который «липнет» снизу на телефоне и планшете (раунд 3, K8.3; круг 9, S1).
// Пока человек двигает ползунки и поля, сам блок результата остаётся ниже экрана; плашка показывает то же число
// одной строкой 44 px и по нажатию прокручивает к блоку. Плашка показывается, только когда блок результата ЛЕЖИТ НИЖЕ окна
// (ушедший вверх результат человек уже видел) и пока ни одно поле ввода или бегунок не в руках: так она не закрывает то, что двигают.
// Пока она на экране, нижняя панель телефона спрятана (lib/stickyLayer.js: html[data-fe-sticky]), у футера плашки нет.
// Плашка живёт в document.body: backdrop-filter у родителей сделал бы fixed относительным к ним, а не к окну.
// На широком экране (от 1024 px) результат стоит рядом с формой, плашка скрыта стилями (styles/k8-tools.css).
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowDown } from 'lucide-react';
import { useT } from '../i18n';
import { setStickyActive } from '../lib/stickyLayer';
import { useFooterTone } from '../lib/useFooterTone';
import '../styles/k8-tools.css';

const FIELD_SKIP_TYPES = new Set(['button', 'submit', 'reset', 'checkbox', 'radio', 'image', 'file']);

/** Поле, в которое человек вводит или которое двигает: поле, список, текстовая область, бегунок. */
function isFieldTarget(node) {
  if (!node || typeof node.tagName !== 'string') return false;
  const tag = node.tagName.toUpperCase();
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag === 'INPUT') return !FIELD_SKIP_TYPES.has(String(node.type || '').toLowerCase());
  return node.isContentEditable === true;
}

/** Ложь, пока в фокусе поле ввода или палец ведёт бегунок (и ещё секунду после отпускания). */
function useFieldIdle() {
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let release = 0;
    const focusIn = (event) => { if (isFieldTarget(event.target)) setBusy(true); };
    const focusOut = (event) => { if (isFieldTarget(event.target)) setBusy(false); };
    const down = (event) => {
      if (!isFieldTarget(event.target) || event.target.type !== 'range') return;
      window.clearTimeout(release);
      setBusy(true);
    };
    const up = () => {
      window.clearTimeout(release);
      // Бегунок на iOS не получает фокус: после отпускания плашка возвращается не сразу, чтобы не мигать между касаниями.
      release = window.setTimeout(() => setBusy(isFieldTarget(document.activeElement)), 900);
    };
    document.addEventListener('focusin', focusIn);
    document.addEventListener('focusout', focusOut);
    document.addEventListener('pointerdown', down, true);
    document.addEventListener('pointerup', up, true);
    document.addEventListener('pointercancel', up, true);
    return () => {
      window.clearTimeout(release);
      document.removeEventListener('focusin', focusIn);
      document.removeEventListener('focusout', focusOut);
      document.removeEventListener('pointerdown', down, true);
      document.removeEventListener('pointerup', up, true);
      document.removeEventListener('pointercancel', up, true);
    };
  }, []);
  return busy;
}

/** Блок результата лежит ниже нижнего края окна (а не выше верхнего). Без данных о положении считаем, что ниже. */
function isBelowViewport(entry) {
  const rect = entry?.boundingClientRect;
  if (!rect || typeof rect.top !== 'number') return true;
  const bottom = entry.rootBounds && typeof entry.rootBounds.bottom === 'number'
    ? entry.rootBounds.bottom
    : (typeof window === 'undefined' ? 0 : window.innerHeight);
  return rect.top > bottom;
}

/**
 * targetRef: ref блока результата; value: готовая строка («57 991 ₽»); active: результат есть и не грузится;
 * label: короткая подпись над числом (по умолчанию «Результат»).
 */
export default function CalcStickyResult({ targetRef, value, active = true, label }) {
  const t = useT();
  const [below, setBelow] = useState(false);
  const fieldBusy = useFieldIdle();
  const overFooter = useFooterTone().dock;

  useEffect(() => {
    const node = targetRef?.current;
    // Без наблюдателя плашка не показывается (below остаётся false); при смене active IO отдаёт актуальное значение сразу.
    if (!active || !node || typeof IntersectionObserver !== 'function') return undefined;
    const io = new IntersectionObserver(([entry]) => setBelow(!entry.isIntersecting && isBelowViewport(entry)), { threshold: 0.05 });
    io.observe(node);
    return () => io.disconnect();
  }, [targetRef, active]);

  const shown = Boolean(active && below && value && !fieldBusy && !overFooter && typeof document !== 'undefined');
  // Пока плашка на экране, нижняя панель телефона спрятана, а плавающие кнопки поднимаются над плашкой (lib/stickyLayer.js).
  useEffect(() => {
    // От 1024 px плашки нет (результат стоит рядом с формой, CSS её скрывает): запас и панель не трогаем.
    const narrow = typeof window.matchMedia !== 'function' || window.matchMedia('(max-width: 1023px)').matches;
    setStickyActive(shown && narrow);
    return () => setStickyActive(false);
  }, [shown]);

  if (!shown) return null;

  const shownLabel = label || t('k8.sticky.label');
  const goToResult = () => {
    const node = targetRef?.current;
    if (!node || typeof node.scrollIntoView !== 'function') return;
    const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    node.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' });
  };

  return createPortal(
    <button
      type="button"
      className="fe-k8-sticky"
      data-testid="calc-sticky-result"
      aria-label={t('k8.sticky.aria', { value })}
      onClick={goToResult}
    >
      <span className="fe-k8-sticky__row">
        <span className="fe-k8-sticky__label">{shownLabel}</span>
        <span className="fe-k8-sticky__value fe-k8-engraved">{value}</span>
      </span>
      <span className="fe-k8-sticky__go" aria-hidden="true">
        <span className="fe-k8-sticky__go-label">{t('c9a.sticky.go')}</span>
        <ArrowDown size={18} />
      </span>
    </button>,
    document.body,
  );
}
