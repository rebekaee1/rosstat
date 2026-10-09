import {
  useCallback, useEffect, useLayoutEffect, useRef, useState,
} from 'react';
import {
  ChevronDown, Download, FileSpreadsheet, FileText, Image as ImageIcon, Lock,
} from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import Button from './Button';
import BottomSheet from './BottomSheet';
import useMediaQuery from '../lib/useMediaQuery';
import { placeMenu } from '../lib/popupPlacement';
import '../styles/z4-indicator.css';
import '../styles/c11c-charts.css';

/**
 * Две кнопки над графиком на всех страницах показателей (Россия и мир): «Скачать» (таблица CSV, Excel, картинка)
 * и отдельная заметная «Сохранить картинкой»: график с названием, источником и адресом сайта в фирменной рамке.
 * Раньше у России было три кнопки или «Войдите, чтобы скачать», у мира меню: страницы одного типа выглядели по-разному.
 * Гостю вход предлагает сам экспорт (замок в пункте и подсказка), поэтому подпись одна и та же у всех.
 * `showSaveButton={false}` убирает отдельную кнопку (остаётся пункт меню).
 */
export default function ChartDownloadMenu({
  onCsv, onExcel, onPng, dataBlocked, imageBlocked, hint, showSaveButton = true,
  formats = null, label = '', menuLabel = '',
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [place, setPlace] = useState({ left: 0, up: false });
  const rootRef = useRef(null);
  const phone = useMediaQuery('(max-width: 639px)');
  // Круг 11: на телефоне меню открывается нижним листом (нижний пункт не прячется под панелью браузера), на компьютере считаем место.
  const measure = useCallback(() => {
    const el = rootRef.current;
    if (!el || typeof window === 'undefined') return;
    setPlace(placeMenu(el.getBoundingClientRect(), { viewportW: window.innerWidth, viewportH: window.innerHeight }));
  }, []);
  useLayoutEffect(() => {
    if (open && !phone) measure();
  }, [open, phone, measure]);
  useEffect(() => {
    if (!open || phone) return undefined;
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [open, phone, measure]);
  useEffect(() => {
    if (!open || phone) return undefined;
    const onDown = (event) => { if (!rootRef.current?.contains(event.target)) setOpen(false); };
    const onKey = (event) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, phone]);
  const items = [
    { id: 'csv', label: t('w2.dl.csv'), Icon: FileText, run: onCsv, blocked: dataBlocked, hint: dataBlocked ? t('download.dataBlocked') : undefined },
    { id: 'excel', label: t('w2.dl.excel'), Icon: FileSpreadsheet, run: onExcel, blocked: dataBlocked, hint: dataBlocked ? t('download.dataBlocked') : undefined },
    { id: 'png', label: t('w2.dl.png'), Icon: ImageIcon, run: onPng, blocked: imageBlocked, hint: imageBlocked ? t('download.chartBlocked') : t('download.chartPng') },
  ].filter((item) => !formats || formats.includes(item.id));
  const renderItem = ({
    id, label: itemLabel, Icon, run, blocked, hint: itemHint,
  }) => (
    <button
      key={id}
      type="button"
      role={phone ? undefined : 'menuitem'}
      title={itemHint}
      onClick={() => { setOpen(false); run?.(); }}
      className="flex min-h-11 w-full items-center gap-2.5 rounded-xl px-3 text-left text-sm text-text-primary transition-colors hover:bg-white/60 hover:shadow-[var(--fe-l2-shadow)]"
    >
      <Icon size={16} className="shrink-0 text-text-secondary" aria-hidden="true" />
      <span className="min-w-0 flex-1">{itemLabel}</span>
      {blocked && <Lock size={14} className="shrink-0 text-text-tertiary" aria-label={itemHint} />}
    </button>
  );
  return (
    <div className="z4-dl" data-no-export="true">
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
          {label || t('w2.dl.title')}
          <ChevronDown size={13} aria-hidden="true" className={cn('transition-transform', open && 'rotate-180')} />
        </Button>
        {open && !phone && (
          <div
            role="menu"
            className={cn(
              'fe-dialog-panel fe-w6g-solid-panel c11c-dl-menu absolute z-50 min-w-[15rem] rounded-2xl p-1.5',
              place.up ? 'bottom-full mb-2' : 'top-full mt-2',
            )}
            style={{ left: place.left }}
          >
            {items.map(renderItem)}
          </div>
        )}
        <BottomSheet
          open={open && phone}
          onClose={() => setOpen(false)}
          ariaLabel={menuLabel || label || t('w2.dl.title')}
          bodyClassName="c11c-dl-sheet"
        >
          <div className="grid gap-1 px-3 pt-1">
            {items.map(renderItem)}
          </div>
        </BottomSheet>
      </div>
      {showSaveButton && onPng ? <ChartSaveButton onPng={onPng} imageBlocked={imageBlocked} /> : null}
    </div>
  );
}

/**
 * Отдельная заметная кнопка «Сохранить картинкой». Нужна не только в меню «Скачать»: на страницах без таблиц
 * (например «Сегодня») она стоит одна. Гостю вместо файла открывается окно входа (замок рядом с подписью).
 */
export function ChartSaveButton({ onPng, imageBlocked = false, className }) {
  const t = useT();
  return (
    <Button
      variant="secondary"
      size="sm"
      className={cn('z4-png-btn gap-1.5', imageBlocked && 'z4-png-btn--locked', className)}
      aria-label={t('z4.png.aria')}
      title={imageBlocked ? t('download.chartBlocked') : t('z4.png.title')}
      data-no-export="true"
      onClick={() => onPng?.()}
    >
      <ImageIcon size={14} aria-hidden="true" />
      <span className="z4-png-btn__text">{t('z4.png.save')}</span>
      {imageBlocked ? <Lock size={12} className="shrink-0 opacity-70" aria-hidden="true" /> : null}
    </Button>
  );
}
