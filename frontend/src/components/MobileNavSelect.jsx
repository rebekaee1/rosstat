import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { cn, formatCount } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { useT } from '../i18n';
import BottomSheet from './BottomSheet';
import '../styles/platform-pages.css';

/** Число показателей — аккуратной «таблеткой» справа, а не скобками в названии. */
function CountPill({ count }) {
  if (count == null) return null;
  return (
    <span className="fe-num ml-2 shrink-0 rounded-full bg-obsidian-lighter px-2 py-0.5 text-xs font-medium text-text-secondary">
      {typeof count === 'number' ? formatCount(count) : count}
    </span>
  );
}

/**
 * Мобильный выбор раздела (темы / округа / срез): кнопка + bottom sheet.
 * Нативный &lt;select&gt; не используем — на телефоне он выглядит чужеродно
 * и неочевидно, что это выпадающий список.
 * На lg+ скрыт — там остаётся боковой список или чипы.
 */
export default function MobileNavSelect({
  label,
  value,
  options,
  onChange,
  className = '',
  pickTitle = '',
}) {
  const t = useT();
  const sectionLabel = label || t('mobile.section');
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
    // Фокус в шапку листа — сразу ясно, что это модальный выбор (лист BottomSheet сам берёт фокус, кнопка «Готово» следующая).
    queueMicrotask(() => closeBtnRef.current?.focus());
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!options?.length) return null;

  // Лист выбора: общая стеклянная шторка (BottomSheet): ручка-капля, свайп вниз, фон тонируется, рисуется порталом.
  const sheet = (
    <BottomSheet
      open={open}
      onClose={() => setOpen(false)}
      labelledBy={titleId}
      bodyClassName="px-2 py-2 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
      header={(
        <div className="flex shrink-0 items-center justify-between gap-3 px-4 pb-3">
          <div className="min-w-0">
            <p id={titleId} className="text-sm font-medium text-text-secondary">
              {sectionLabel}
            </p>
            <p className="mt-0.5 truncate text-sm font-medium text-text-primary">
              {pickTitle || t('mobile.pickSection')}
            </p>
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={() => setOpen(false)}
            className={cn(
              FOCUS_RING_SURFACE,
              'fe-tap fe-press min-h-11 shrink-0 rounded-xl px-4 py-2 text-sm font-medium text-champagne-ink bg-champagne/10 hover:bg-champagne/15',
            )}
          >
            {t('mobile.done')}
          </button>
        </div>
      )}
    >
      <ul>
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
                  'fe-tap fe-press flex min-h-12 w-full items-center gap-3 rounded-xl px-3.5 py-3 text-left transition-colors',
                  active
                    ? 'bg-champagne/15 text-champagne-ink'
                    : 'text-text-primary hover:bg-white/60',
                )}
              >
                <span className="min-w-0 flex-1 text-[15px] font-medium leading-snug">
                  {opt.label}
                </span>
                <CountPill count={opt.count} />
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
    </BottomSheet>
  );

  return (
    <div className={cn('mb-4 block lg:hidden', className)}>
      <p className="mb-2 block px-0.5 text-sm font-medium text-text-secondary">
        {sectionLabel}
      </p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          FOCUS_RING_SURFACE,
          'fe-press flex min-h-12 w-full items-center gap-3 rounded-xl px-3.5 text-left shadow-sm fe-glass-2',
          '',
        )}
      >
        <span className="flex min-w-0 flex-1 items-center text-[15px] font-medium text-text-primary">
          <span className="min-w-0 truncate">{selected ? selected.label : t('common.selectEllipsis')}</span>
          {selected && <CountPill count={selected.count} />}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-obsidian-lighter px-2.5 py-1.5 text-xs font-medium text-text-secondary">
          {t('common.change')}
          <ChevronDown className="h-3.5 w-3.5" />
        </span>
      </button>
      {sheet}
    </div>
  );
}
