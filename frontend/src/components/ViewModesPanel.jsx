import { useCallback, useId, useMemo, useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { useT } from '../i18n';
import { cn } from '../lib/format';
import { PanelContext } from './viewModesContext';
import '../styles/y2-indicator.css';
import '../styles/z4-indicator.css';

/**
 * Панель «Вид» над графиком показателя.
 *
 * Компьютер: все переключатели («Что показать», «Показать как», детализация) собраны в одну стеклянную полосу
 * с подписями слева, чтобы график начинался сразу под ней (стили `.z4-desk` в z4-indicator.css).
 *
 * Телефон: переключатели занимают 300–700 px и уводят график на третий экран. Поэтому на узких экранах панель свёрнута
 * в одну строку: слева то, что выбрано сейчас («Год к году, по месяцам»), справа шестерёнка «Изменить вид».
 * От 768 px переключатели показаны сразу, а строка-заголовок скрыта.
 *
 * Сами переключатели сообщают панели свою подпись через `useViewModeSummary`; если ни один
 * не сообщил (или их нет), панель ничего не сворачивает и ничего не рисует лишнего.
 */
export function ViewModesPanel({ children, className, label }) {
  const t = useT();
  const baseId = useId();
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState({});

  const register = useCallback((id, key, order, text, fallback = '') => {
    setEntries((prev) => {
      if (!text && !fallback) {
        if (!(id in prev)) return prev;
        const next = { ...prev };
        delete next[id];
        return next;
      }
      const old = prev[id];
      if (old && old.key === key && old.order === order && old.text === text && old.fallback === fallback) return prev;
      return { ...prev, [id]: { key, order, text, fallback } };
    });
  }, []);

  const ctx = useMemo(() => ({ register }), [register]);

  const summary = useMemo(() => {
    const list = Object.values(entries).sort((a, b) => a.order - b.order);
    const byKey = new Map();
    list.forEach((e) => { if (e.text && !byKey.has(e.key)) byKey.set(e.key, e.text); });
    const joined = [...byKey.values()].join(', ');
    if (joined) return joined;
    // Все переключатели стоят на значении по умолчанию: показываем его, чтобы панель всё равно сворачивалась.
    return list.find((e) => e.fallback)?.fallback || '';
  }, [entries]);

  const collapsible = summary !== '';
  const bodyId = `${baseId}-body`;

  return (
    <PanelContext.Provider value={ctx}>
      <div
        className={cn('fe-vm-panel z4-desk', className)}
        data-open={open ? 'true' : 'false'}
        data-collapsible={collapsible ? 'true' : 'false'}
      >
        {collapsible && (
          <button
            type="button"
            className="fe-vm-toggle fe-press"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((v) => !v)}
          >
            <span className="fe-vm-toggle__main">
              <span className="fe-vm-toggle__label">{label || t('y2.view.label')}</span>
              <span className="fe-vm-toggle__sum">{summary}</span>
            </span>
            <span className="fe-vm-toggle__act">
              <span className="fe-vm-toggle__act-text">{open ? t('y2.view.close') : t('y2.view.change')}</span>
              <SlidersHorizontal className="fe-vm-toggle__chev" size={18} aria-hidden="true" />
            </span>
          </button>
        )}
        <div id={bodyId} className="fe-vm-body">{children}</div>
      </div>
    </PanelContext.Provider>
  );
}
