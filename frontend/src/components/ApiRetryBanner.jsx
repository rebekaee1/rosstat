import { useEffect, useRef, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import Button from './Button';

// Один тихий повтор до показа ошибки (волна 6, 1.3): большинство сбоев — короткие, и после
// повтора страница открывается сама. В тестах отключён, чтобы они видели ошибку сразу.
const AUTO_RETRIES = import.meta.env.MODE === 'test' ? 0 : 1;
const AUTO_RETRY_DELAY_MS = 900;
const AUTO_RETRY_GRACE_MS = 9000;

/**
 * Единый блок «данные не пришли» — непрозрачный фон, контрастная кнопка «Повторить» (есть всегда).
 * Сначала делает один повтор молча: пока он идёт, вместо тревожной плашки спокойная подпись «Загружаем
 * данные…». Если повтор не помог, показывает плашку и ставит на <html> признак data-fe-error,
 * по которому приглашение зарегистрироваться не перекрывает ошибку.
 */
export default function ApiRetryBanner({ children, onRetry, isFetching, className, autoRetries = AUTO_RETRIES }) {
  const t = useT();
  const onRetryRef = useRef(onRetry);
  useEffect(() => { onRetryRef.current = onRetry; });
  const [graceOver, setGraceOver] = useState(autoRetries <= 0);
  const [sawFetching, setSawFetching] = useState(false);
  if (isFetching && !sawFetching) setSawFetching(true);
  const retryFinished = sawFetching && isFetching === false;
  const quiet = !graceOver && !retryFinished;

  useEffect(() => {
    if (autoRetries <= 0) return undefined;
    const retryTimer = setTimeout(() => { try { onRetryRef.current?.(); } catch { /* повтор не должен ронять страницу */ } }, AUTO_RETRY_DELAY_MS);
    const graceTimer = setTimeout(() => setGraceOver(true), AUTO_RETRY_GRACE_MS);
    return () => { clearTimeout(retryTimer); clearTimeout(graceTimer); };
  }, [autoRetries]);

  useEffect(() => {
    if (quiet || typeof document === 'undefined') return undefined;
    const root = document.documentElement;
    root.setAttribute('data-fe-error', '1');
    return () => root.removeAttribute('data-fe-error');
  }, [quiet]);

  if (quiet) {
    return (
      <div className={cn('fe-loading-note', className)} role="status" aria-live="polite" data-testid="retry-quiet">
        <span className="fe-loading-note__dot" aria-hidden="true" />
        <span>{t('w6a.loading.caption')}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-2xl bg-warn-surface px-4 py-4 text-sm shadow-md sm:flex-row sm:items-center sm:justify-between fe-shadow-2',
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
