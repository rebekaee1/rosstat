import { FOCUS_RING } from '../lib/uiTokens';
import { cn } from '../lib/format';

/**
 * Единый блок «данные не пришли» — непрозрачный фон, контрастная кнопка (не сливается с баннером).
 */
export default function ApiRetryBanner({ children, onRetry, isFetching, className }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-2xl border border-champagne/35 bg-warn-surface px-4 py-4 text-sm shadow-md sm:flex-row sm:items-center sm:justify-between',
        className
      )}
      role="alert"
    >
      <p className="min-w-0 text-[0.9375rem] leading-relaxed text-text-primary">{children}</p>
      <button
        type="button"
        onClick={onRetry}
        disabled={isFetching}
        className={cn(
          FOCUS_RING,
          'shrink-0 rounded-xl bg-champagne px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-[opacity,transform] hover:opacity-95 active:scale-[0.98] disabled:opacity-60'
        )}
      >
        {isFetching ? 'Загрузка…' : 'Повторить'}
      </button>
    </div>
  );
}
