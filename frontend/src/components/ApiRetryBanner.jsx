import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import Button from './Button';

/**
 * Единый блок «данные не пришли» — непрозрачный фон, контрастная кнопка (не сливается с баннером).
 */
export default function ApiRetryBanner({ children, onRetry, isFetching, className }) {
  const t = useT();
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-2xl border border-champagne/35 bg-warn-surface px-4 py-4 text-sm shadow-md sm:flex-row sm:items-center sm:justify-between',
        className
      )}
      role="alert"
    >
      <p className="min-w-0 text-[0.9375rem] leading-relaxed text-text-primary">{children}</p>
      <Button
        onClick={() => { track(events.API_RETRY); onRetry(); }}
        loading={Boolean(isFetching)}
        className="shrink-0 px-5"
      >
        {isFetching ? t('common.loading') : t('common.retry')}
      </Button>
    </div>
  );
}
