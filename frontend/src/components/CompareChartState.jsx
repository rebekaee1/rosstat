// Состояния блока графика «Сравнения»: загрузка рядов, показатели не выбраны, нет точек, ошибка.
// Все они занимают ту же высоту, что и готовый график (height — высота области графика, px),
// поэтому при смене состояния страница не подпрыгивает. Видимое сообщение дублируется для
// скринридеров: загрузка и «пусто» — role="status" (вежливо), ошибка — role="alert".
import { GitCompare, TriangleAlert } from 'lucide-react';
import { SkeletonBox } from './Skeleton';
import Button from './Button';
import { useT } from '../i18n';

// Высота «шапки» карточки графика (заголовок, подсказка, легенда) — как у готового графика.
const CARD_EXTRA = 150;

export default function CompareChartState({ kind, height = 390, message = '', onRetry, retrying = false }) {
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

  const isError = kind === 'error';
  const Icon = isError ? TriangleAlert : GitCompare;
  const title = kind === 'none'
    ? t('compare.emptyNoneTitle')
    : isError
      ? t('compare.errorTitle')
      : '';

  return (
    <div
      data-testid="compare-empty"
      data-state={kind}
      role={isError ? 'alert' : 'status'}
      aria-live={isError ? 'assertive' : 'polite'}
      style={{ minHeight: height + CARD_EXTRA }}
      className="flex flex-col items-center justify-center rounded-[2rem] border border-dashed border-border-subtle bg-surface p-6 text-center md:p-8"
    >
      <Icon className="mb-4 h-10 w-10 text-text-tertiary opacity-60" aria-hidden="true" />
      {title && <p className="mb-1 text-base font-semibold text-text-primary">{title}</p>}
      <p className="max-w-md text-sm text-text-secondary">{message}</p>
      {isError && onRetry && (
        <Button variant="primary" className="mt-5" onClick={onRetry} loading={retrying}>
          {t('common.retry')}
        </Button>
      )}
    </div>
  );
}
