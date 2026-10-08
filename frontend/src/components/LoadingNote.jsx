import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import Button from './Button';

/**
 * Подпись под скелетом: «Загружаем данные…» с тихим движущимся индикатором (точка и тонкая дорожка, круг 8 W-A6: статичный экран дольше 10 с
 * читался как зависший). Если ждать дольше `slowAfterMs`, добавляется кнопка «Обновить» и «Дольше обычного.»; после `serverSlowAfterMs` вместо
 * этого короткая строка «Сервер отвечает медленно, ещё секунду…». Ничего не мигает: появляется строка один раз, места под неё в ряду хватает
 * (ряд переносится, высота не прыгает: min-height 28 px).
 * Человек отличает «грузится» от «сломалось» и может сам повторить, не уходя со страницы.
 * `onRefresh` — повторный запрос данных этой страницы; без него страница перезагружается целиком.
 */
export default function LoadingNote({ onRefresh, slowAfterMs = 5000, serverSlowAfterMs = 7000, className }) {
  const t = useT();
  const [slow, setSlow] = useState(false);
  const [serverSlow, setServerSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    const serverTimer = setTimeout(() => setServerSlow(true), serverSlowAfterMs);
    return () => { clearTimeout(timer); clearTimeout(serverTimer); };
  }, [slowAfterMs, serverSlowAfterMs]);

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
      data-server-slow={serverSlow ? 'true' : undefined}
    >
      <span className="fe-loading-note__dot" aria-hidden="true" />
      <span className="fe-loading-note__text">
        {t('w6a.loading.caption')}
        {slow ? ` ${serverSlow ? t('c8w.loading.slow') : t('w6a.loading.slow')}` : ''}
      </span>
      <span className="fe-loading-note__track" aria-hidden="true"><span className="fe-loading-note__run" /></span>
      {slow && (
        <Button variant="secondary" size="sm" onClick={refresh} className="fe-loading-note__btn">
          <RefreshCw size={14} aria-hidden="true" />
          {t('w6a.loading.refresh')}
        </Button>
      )}
    </div>
  );
}
