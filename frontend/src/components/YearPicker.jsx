import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '../lib/format';
import '../styles/world.css';

/**
 * Выбор года: фирменная кнопка с «шторкой» из пилюль-годов вместо системного колёсика.
 * Новые годы — первыми; выбранный подсвечен и при открытии оказывается в видимой части списка.
 * Закрывается по выбору, Escape и касанию вне; фокус возвращается на кнопку.
 */
export default function YearPicker({
  years = [], value = null, onChange, label, disabled = false, align = 'end', className,
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const listRef = useRef(null);
  const id = useId().replaceAll(':', '');
  const ordered = [...years].reverse();

  const close = useCallback((restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) buttonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const outside = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const key = (event) => {
      if (event.key === 'Escape') { event.stopPropagation(); close(true); }
    };
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', key, true);
    return () => {
      document.removeEventListener('pointerdown', outside, true);
      document.removeEventListener('keydown', key, true);
    };
  }, [open, close]);

  // Выбранный год — в видимой части списка: без scrollIntoView, чтобы страница не прыгала.
  useEffect(() => {
    if (!open) return;
    const list = listRef.current;
    const current = list?.querySelector('[aria-selected="true"]');
    if (list && current) list.scrollTop = Math.max(0, current.offsetTop - list.clientHeight / 2 + current.offsetHeight / 2);
  }, [open]);

  if (!years.length || value == null) return null;
  const choose = (year) => {
    close(true);
    if (year !== value) onChange?.(year);
  };

  return (
    <div ref={rootRef} className={cn('fe-year', className)}>
      <button
        ref={buttonRef}
        type="button"
        className="fe-year-button fe-press"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `year-${id}` : undefined}
        aria-label={label ? `${label}: ${value}` : String(value)}
        disabled={disabled}
        onClick={() => setOpen((previous) => !previous)}
      >
        <span>{value}</span>
        <ChevronDown size={16} aria-hidden="true" className="fe-year-chevron" />
      </button>
      {open && (
        <div
          ref={listRef}
          id={`year-${id}`}
          role="listbox"
          aria-label={label}
          className={cn('fe-year-pop', align === 'start' && 'fe-year-pop--start')}
        >
          {ordered.map((year) => (
            <button
              key={year}
              type="button"
              role="option"
              aria-selected={year === value}
              className="fe-year-option fe-press"
              onClick={() => choose(year)}
            >
              {year === value && <Check size={13} aria-hidden="true" />}
              {year}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
