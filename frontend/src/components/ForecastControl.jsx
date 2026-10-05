import { Info } from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';

/**
 * Прогноз в шапке графика. Есть прогноз: подписанный переключатель, по умолчанию включён.
 * Нет прогноза: выключенный тумблер ничего не объясняет, поэтому вместо него одна фраза
 * «Прогноз для этого показателя пока не строится» (причину можно прочитать во всплывающей подсказке).
 */
export default function ForecastControl({
  enabled, on, onToggle, reason,
}) {
  const t = useT();
  if (!enabled) {
    return (
      <p className="fe-forecast-none" title={reason || undefined} data-no-export="true">
        <Info size={14} aria-hidden="true" />
        <span>{t('w6e.forecast.none')}</span>
      </p>
    );
  }
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={t('chart.forecastAria')}
      onClick={onToggle}
      data-no-export="true"
      className={cn('fe-forecast-switch fe-press', on && 'is-on')}
    >
      <span className="fe-forecast-switch__track" aria-hidden="true">
        <span className="fe-forecast-switch__thumb" />
      </span>
      <span>{t('common.forecast')}</span>
    </button>
  );
}
