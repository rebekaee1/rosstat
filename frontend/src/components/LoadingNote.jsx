import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import Button from './Button';

/**
 * Подпись под скелетом: «Загружаем данные…», а если ждать дольше `slowAfterMs`, ещё и кнопка «Обновить».
 * Человек отличает «грузится» от «сломалось» и может сам повторить, не уходя со страницы.
 * `onRefresh` — повторный запрос данных этой страницы; без него страница перезагружается целиком.
 */
export default function LoadingNote({ onRefresh, slowAfterMs = 5000, className }) {
  const t = useT();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(timer);
  }, [slowAfterMs]);

  const refresh = () => {
    if (typeof onRefresh === 'function') {
      onRefresh();
      return;
    }
    if (typeof window !== 'undefined') window.location.reload();
  };

  return (
    <div
      className={cn('fe-loading-note', className)}
      role="status"
      aria-live="polite"
      data-testid="loading-note"
      data-slow={slow ? 'true' : undefined}
    >
      <span className="fe-loading-note__dot" aria-hidden="true" />
      <span className="fe-loading-note__text">
        {t('w6a.loading.caption')}
        {slow ? ` ${t('w6a.loading.slow')}` : ''}
      </span>
      {slow && (
        <Button variant="secondary" size="sm" onClick={refresh} className="fe-loading-note__btn">
          <RefreshCw size={14} aria-hidden="true" />
          {t('w6a.loading.refresh')}
        </Button>
      )}
    </div>
  );
}
