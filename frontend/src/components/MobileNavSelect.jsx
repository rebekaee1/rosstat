import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';

function optionText(opt) {
  return opt.count != null ? `${opt.label} (${opt.count})` : opt.label;
}

/**
 * Мобильный выбор раздела (темы / округа / срез): кнопка + bottom sheet.
 * Нативный &lt;select&gt; не используем — на телефоне он выглядит чужеродно
 * и неочевидно, что это выпадающий список.
 * На lg+ скрыт — там остаётся боковой список или чипы.
 */
export default function MobileNavSelect({
  label = 'Раздел',
  value,
  options,
  onChange,
  className = '',
}) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const closeBtnRef = useRef(null);
  const selected = useMemo(
    () => options?.find((opt) => String(opt.value) === String(value)) || options?.[0],
    [options, value],
  );

  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    // Фокус в шапку листа — сразу ясно, что это модальный выбор.
    queueMicrotask(() => closeBtnRef.current?.focus());
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!options?.length) return null;

  const sheet = open && typeof document !== 'undefined'
    ? createPortal(
      <div
        className="fixed inset-0 z-[90] flex flex-col justify-end lg:hidden"
        role="presentation"
      >
        <button
          type="button"
          aria-label="Закрыть"
          className="absolute inset-0 bg-text-primary/35 backdrop-blur-[2px]"
          onClick={() => setOpen(false)}
        />
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className="relative z-10 flex max-h-[min(78dvh,560px)] flex-col rounded-t-[1.5rem] border border-border-subtle bg-surface shadow-[0_-18px_50px_rgba(35,30,16,0.18)]"
        >
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border-subtle px-4 pb-3 pt-3.5">
            <div className="min-w-0">
              <div className="mx-auto mb-2.5 h-1 w-9 rounded-full bg-border-subtle sm:mx-0" aria-hidden />
              <p
                id={titleId}
                className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary"
              >
                {label}
              </p>
              <p className="mt-0.5 truncate text-sm font-medium text-text-primary">
                Выберите раздел
              </p>
            </div>
            <button
              ref={closeBtnRef}
              type="button"
              onClick={() => setOpen(false)}
              className={cn(
                FOCUS_RING_SURFACE,
                'shrink-0 rounded-xl px-3 py-2 text-sm font-medium text-champagne bg-champagne/10 hover:bg-champagne/15',
              )}
            >
              Готово
            </button>
          </div>
          <ul className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 py-2 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {options.map((opt) => {
              const active = String(opt.value) === String(value);
              return (
                <li key={String(opt.value)}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(opt.value);
                      setOpen(false);
                    }}
                    className={cn(
                      FOCUS_RING_SURFACE,
                      'flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-left transition-colors',
                      active
                        ? 'bg-champagne/15 text-champagne'
                        : 'text-text-primary hover:bg-obsidian-lighter',
                    )}
                  >
                    <span className="min-w-0 flex-1 text-[15px] font-medium leading-snug">
                      {optionText(opt)}
                    </span>
                    {active ? (
                      <Check className="h-4 w-4 shrink-0" strokeWidth={2.5} />
                    ) : (
                      <span className="h-4 w-4 shrink-0" aria-hidden />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>,
      document.body,
    )
    : null;

  return (
    <div className={cn('mb-4 block lg:hidden', className)}>
      <p className="mb-2 block px-0.5 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
        {label}
      </p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          FOCUS_RING_SURFACE,
          'flex h-12 w-full items-center gap-3 rounded-xl border border-border-subtle bg-surface px-3.5 text-left shadow-sm',
          'active:border-border-champagne',
        )}
      >
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">
          {selected ? optionText(selected) : 'Выбрать…'}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-obsidian-lighter px-2 py-1 text-[11px] font-medium text-text-secondary">
          Сменить
          <ChevronDown className="h-3.5 w-3.5" />
        </span>
      </button>
      {sheet}
    </div>
  );
}
