import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { Info } from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import '../styles/z4-indicator.css';

/**
 * Прогноз в шапке графика. Есть прогноз: подписанный переключатель, по умолчанию включён.
 * Нет прогноза: вместо серой фразы в шапке маленькая «i»; по наведению, фокусу или нажатию открывается пояснение
 * («Прогноз для этого показателя пока не строится», причина и ссылка «Как мы считаем прогнозы»).
 * `suggestion` ({ to, label }) добавляет в пояснение ссылку на ближайший показатель, у которого прогноз есть.
 */
export default function ForecastControl({
  enabled, on, onToggle, reason, suggestion = null,
}) {
  const t = useT();
  const popId = useId();
  const [open, setOpen] = useState(false);
  if (!enabled) {
    return (
      <div
        className={cn('fe-forecast-none z4-info', open && 'is-open')}
        data-no-export="true"
        onMouseLeave={() => setOpen(false)}
      >
        <button
          type="button"
          className="z4-info__btn fe-press"
          aria-label={t('w6e.forecast.none')}
          aria-describedby={popId}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          onBlur={(event) => {
            if (!event.currentTarget.parentElement?.contains(event.relatedTarget)) setOpen(false);
          }}
          onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false); }}
        >
          <Info size={16} aria-hidden="true" />
        </button>
        <div id={popId} role="tooltip" className="z4-info__pop">
          <p className="z4-info__title">{t('w6e.forecast.none')}</p>
          {reason ? <p className="z4-info__text">{reason}</p> : null}
          <div className="z4-info__links">
            {suggestion?.to ? (
              <Link to={suggestion.to} className="z4-info__link">{suggestion.label}</Link>
            ) : null}
            <Link to="/methodology" className="z4-info__link">{t('z4.forecast.how')}</Link>
          </div>
        </div>
      </div>
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
