// Одна кнопка «Скачать» вместо ряда из CSV / Excel / PNG: на телефоне три пилюли
// переносились 3+2 и ломали шапку графика. Меню закрывается по Esc, касанию вне и выбору.
import { useEffect, useId, useRef, useState } from 'react';
import { ChevronDown, Download } from 'lucide-react';
import { cn } from '../../lib/format';
import { useT } from '../../i18n';
import '../../styles/regions-w4.css';

/**
 * items: [{ key, label, hint, icon: Icon, onSelect }]
 */
export default function DownloadMenu({ items, disabled = false, className }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cn('fe-dl', className)} data-no-export="true">
      <button
        type="button"
        className="fe-chip fe-press gap-1.5"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
      >
        <Download size={13} aria-hidden="true" />
        {t('x4.download')}
        <ChevronDown size={13} aria-hidden="true" className={cn('transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div id={menuId} role="menu" className="fe-dl__menu">
          {items.map(({ key, label, hint, icon: Icon, onSelect }) => (
            <button
              key={key}
              type="button"
              role="menuitem"
              className="fe-dl__item fe-press"
              onClick={() => { setOpen(false); onSelect(); }}
            >
              {Icon && <Icon size={15} aria-hidden="true" className="shrink-0 text-champagne-ink" />}
              <span className="min-w-0">
                <span className="block text-sm font-medium text-text-primary">{label}</span>
                {hint && <span className="block text-xs text-text-secondary">{hint}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
