import { useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import '../styles/k3-shell.css';

/**
 * Шторка снизу (мобильное меню, выбор вида графика и т.п.): стеклянный лист с ручкой-каплей, затемнением фона,
 * закрытием свайпом вниз за ручку, по Esc и по нажатию на фон.
 *
 * Лист рисуется порталом в body: у шапки и панелей с `backdrop-filter` потомок с `position: fixed` привязался бы
 * к ним, а не к окну. Состояние открытия держит вызывающий (`open`, `onClose`); пока `open` ложь, ничего не рисуется.
 *
 * `children` — прокручиваемое тело (по умолчанию класс `fe-bsheet__body`, `bodyClassName` добавляет свои),
 * `header` — закреплённая полоса между ручкой и телом (заголовок и «Готово» у выбора раздела),
 * `footer` — закреплённая нижняя полоса (кнопки «Войти» / «Регистрация» и т.п.),
 * `ariaLabel` или `labelledBy` (id заголовка) — имя диалога.
 */
const CLOSE_DISTANCE = 96; // px: дальше этого отпущенная шторка закрывается
const CLOSE_VELOCITY = 0.6; // px/мс: быстрый щелчок вниз закрывает и на коротком пути

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function BottomSheet({
  open,
  onClose,
  id,
  ariaLabel,
  labelledBy,
  className,
  header = null,
  bodyClassName,
  footerClassName,
  footer = null,
  children,
}) {
  const t = useT();
  const sheetRef = useRef(null);
  const drag = useRef(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  // Фокус внутрь листа при открытии и обратно к тому, что было в фокусе, при закрытии.
  useEffect(() => {
    if (!open) return undefined;
    const before = document.activeElement;
    sheetRef.current?.focus({ preventScroll: true });
    return () => {
      if (before instanceof HTMLElement && document.contains(before)) before.focus({ preventScroll: true });
    };
  }, [open]);

  // Esc закрывает; Tab не уходит за лист (фокус ходит по кругу внутри).
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') {
        onCloseRef.current?.();
        return;
      }
      if (event.key !== 'Tab' || !sheetRef.current) return;
      const items = [...sheetRef.current.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === sheetRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const setOffset = (dy, animated) => {
    const el = sheetRef.current;
    if (!el) return;
    el.style.transition = animated ? 'transform 0.22s cubic-bezier(0.22, 0.7, 0.2, 1)' : 'none';
    el.style.transform = dy ? `translateY(${dy}px)` : '';
  };

  const onPointerDown = useCallback((event) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    drag.current = { startY: event.clientY, lastY: event.clientY, lastT: event.timeStamp, velocity: 0, dy: 0 };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }, []);

  const onPointerMove = useCallback((event) => {
    const d = drag.current;
    if (!d) return;
    const dy = Math.max(0, event.clientY - d.startY);
    const dt = Math.max(1, event.timeStamp - d.lastT);
    d.velocity = (event.clientY - d.lastY) / dt;
    d.lastY = event.clientY;
    d.lastT = event.timeStamp;
    d.dy = dy;
    setOffset(dy, false);
  }, []);

  const finishDrag = useCallback(() => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.dy > CLOSE_DISTANCE || (d.dy > 24 && d.velocity > CLOSE_VELOCITY)) {
      setOffset(sheetRef.current ? sheetRef.current.offsetHeight : 600, true);
      onCloseRef.current?.();
    } else {
      setOffset(0, true);
    }
  }, []);

  if (!open || typeof document === 'undefined') return null;

  return createPortal(
    <>
      <div className="fe-bsheet-scrim" aria-hidden="true" data-testid="sheet-scrim" onClick={() => onCloseRef.current?.()} />
      <div
        ref={sheetRef}
        id={id}
        role="dialog"
        aria-modal="true"
        aria-label={labelledBy ? undefined : ariaLabel}
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={cn('fe-bsheet', className)}
      >
        <div
          className="fe-bsheet__grab"
          data-testid="sheet-grab"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          <span className="fe-bsheet__handle" aria-hidden="true" />
          <span className="sr-only">{t('k3.sheet.dragHint')}</span>
        </div>
        {header}
        <div className={cn('fe-bsheet__body', bodyClassName)}>{children}</div>
        {footer ? <div className={cn('fe-bsheet__foot', footerClassName)}>{footer}</div> : null}
      </div>
    </>,
    document.body,
  );
}
