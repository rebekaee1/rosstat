// Состояния блока графика «Сравнения»: загрузка рядов, показатели не выбраны, нет точек, ошибка.
// Все они занимают ту же высоту, что и готовый график (height — высота области графика, px),
// поэтому при смене состояния страница не подпрыгивает. Видимое сообщение дублируется для
// скринридеров: загрузка и «пусто» — role="status" (вежливо), ошибка — role="alert".
import { GitCompare, TriangleAlert } from 'lucide-react';
import { SkeletonBox } from './Skeleton';
import Button from './Button';
import { useT } from '../i18n';
import '../styles/z7-compare.css';

// Высота «шапки» карточки графика (заголовок, подсказка, легенда) — как у готового графика.
const CARD_EXTRA = 150;

export default function CompareChartState({
  kind, height = 390, message = '', onRetry, retrying = false, compact = false,
}) {
  const t = useT();

  if (kind === 'loading') {
    return (
      <div
        data-testid="compare-chart-skeleton"
        role="status"
        aria-busy="true"
        className="fe-panel rounded-[2rem] border border-border-subtle bg-surface p-4 md:p-6"
      >
        <span className="sr-only">{t('compare.loadingSeries')}</span>
        <div aria-hidden="true">
          <SkeletonBox className="mx-auto mb-1 h-7 w-2/3" />
          <SkeletonBox className="mx-auto mb-4 h-4 w-1/2" />
          <div className="mb-4 flex justify-center border-b border-border-subtle pb-4">
            <SkeletonBox className="h-4 w-5/6 max-w-md" />
          </div>
          <div className="skeleton w-full rounded-2xl" style={{ height }} />
        </div>
      </div>
    );
  }

  if (kind === 'error') {
    return (
      <div
        data-testid="compare-empty"
        data-state="error"
        role="alert"
        aria-live="assertive"
        className="fe-z7-unavailable"
      >
        {/* Эскиз графика: сетка и две пунктирные линии. Читается как «график есть, данные не пришли», а не как поломка. */}
        <svg className="fe-z7-unavailable__sketch" viewBox="0 0 600 240" preserveAspectRatio="none" aria-hidden="true" focusable="false">
          {[40, 90, 140, 190].map((y) => (
            <line key={y} x1="0" x2="600" y1={y} y2={y} stroke="currentColor" strokeOpacity="0.10" strokeDasharray="3 5" />
          ))}
          <path d="M0 170 C90 150 150 190 240 140 S400 90 470 100 S560 60 600 40" fill="none" stroke="#AD8A48" strokeOpacity="0.55" strokeWidth="3" strokeLinecap="round" strokeDasharray="2 9" />
          <path d="M0 200 C100 195 160 170 250 175 S410 150 480 140 S560 130 600 110" fill="none" stroke="#202A3C" strokeOpacity="0.28" strokeWidth="3" strokeLinecap="round" strokeDasharray="2 9" />
        </svg>
        <div className="fe-z7-unavailable__body">
          <span className="fe-z7-unavailable__icon" aria-hidden="true"><TriangleAlert className="h-5 w-5" /></span>
          <p className="fe-z7-unavailable__title">{t('z7.compare.unavailableTitle')}</p>
          <p className="fe-z7-unavailable__text">{message}</p>
          {onRetry && (
            <Button variant="primary" className="mt-4" onClick={onRetry} loading={retrying}>
              {t('common.retry')}
            </Button>
          )}
        </div>
      </div>
    );
  }

  const title = kind === 'none' ? t('compare.emptyNoneTitle') : '';

  return (
    <div
      data-testid="compare-empty"
      data-state={kind}
      role="status"
      aria-live="polite"
      style={compact ? undefined : { minHeight: height + CARD_EXTRA }}
      className={`flex flex-col items-center justify-center rounded-[2rem] border border-dashed border-border-subtle bg-surface text-center ${compact ? 'p-5' : 'p-6 md:p-8'}`}
    >
      <GitCompare className={`${compact ? 'mb-2 h-7 w-7' : 'mb-4 h-10 w-10'} text-champagne-ink opacity-70`} aria-hidden="true" />
      {title && <p className="mb-1 text-base font-semibold text-text-primary">{title}</p>}
      <p className="max-w-md text-sm text-text-secondary">{message}</p>
    </div>
  );
}
