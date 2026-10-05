import { useEffect, useRef, useState } from 'react';
import {
  ChevronDown, Download, FileSpreadsheet, FileText, Image as ImageIcon, Lock,
} from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import Button from './Button';

/**
 * Одна кнопка «Скачать» над графиком на всех страницах показателей (Россия и мир).
 * Раньше у России было три кнопки или «Войдите, чтобы скачать», у мира меню: страницы одного типа выглядели по-разному.
 * Гостю вход предлагает сам экспорт (замок в пункте и подсказка), поэтому подпись одна и та же у всех.
 */
export default function ChartDownloadMenu({
  onCsv, onExcel, onPng, dataBlocked, imageBlocked, hint,
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => { if (!rootRef.current?.contains(event.target)) setOpen(false); };
    const onKey = (event) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  const items = [
    { id: 'csv', label: t('w2.dl.csv'), Icon: FileText, run: onCsv, blocked: dataBlocked, hint: dataBlocked ? t('download.dataBlocked') : undefined },
    { id: 'excel', label: t('w2.dl.excel'), Icon: FileSpreadsheet, run: onExcel, blocked: dataBlocked, hint: dataBlocked ? t('download.dataBlocked') : undefined },
    { id: 'png', label: t('w2.dl.png'), Icon: ImageIcon, run: onPng, blocked: imageBlocked, hint: imageBlocked ? t('download.chartBlocked') : t('download.chartPng') },
  ];
  return (
    <div ref={rootRef} className="relative" data-no-export="true" title={hint || undefined}>
      <Button
        variant="secondary"
        size="sm"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
        className="gap-1.5"
      >
        <Download size={14} aria-hidden="true" />
        {t('w2.dl.title')}
        <ChevronDown size={13} aria-hidden="true" className={cn('transition-transform', open && 'rotate-180')} />
      </Button>
      {open && (
        <div role="menu" className="fe-dialog-panel absolute right-0 top-full z-50 mt-2 min-w-[15rem] rounded-2xl border border-border-subtle bg-surface p-1.5 shadow-2xl">
          {items.map(({ id, label, Icon, run, blocked, hint: itemHint }) => (
            <button
              key={id}
              type="button"
              role="menuitem"
              title={itemHint}
              onClick={() => { setOpen(false); run?.(); }}
              className="flex min-h-11 w-full items-center gap-2.5 rounded-xl px-3 text-left text-sm text-text-primary transition-colors hover:bg-obsidian-light"
            >
              <Icon size={16} className="shrink-0 text-text-secondary" aria-hidden="true" />
              <span className="min-w-0 flex-1">{label}</span>
              {blocked && <Lock size={14} className="shrink-0 text-text-tertiary" aria-label={itemHint} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
