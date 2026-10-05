import { Link } from 'react-router-dom';
import { ArrowUpRight, CheckCircle2, Clock3, ExternalLink } from 'lucide-react';
import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';
import { isExternalHref } from '../../lib/sourceLink';
import SourceLink from '../SourceLink';
import {
  calendarPath,
  russiaIndicatorPath,
} from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import { plainEventTitle, plainEventText, localizeReferencePeriod, pluralForm } from '../../lib/calendarText';
import { deltaTone, indicatorPolarity } from '../../lib/deltaTone';
import '../../styles/ui-detail-nav-calendar.css';

const SOURCE_STYLES = {
  cbr: {
    border: 'border-l-blue-500',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-500',
    labelKey: 'calendar.filter.cbr',
  },
  rosstat: {
    border: 'border-l-emerald-500',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    dot: 'bg-emerald-500',
    labelKey: 'calendar.filter.rosstat',
  },
  minfin: {
    border: 'border-l-amber-500',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    dot: 'bg-amber-500',
    labelKey: 'calendar.filter.minfin',
  },
};

/** Важное событие помечено словами: три одинаковых точки без расшифровки никому ничего не говорят. */
function ImportanceBadge({ level }) {
  const t = useT();
  if (level !== 3) return null;
  return (
    <span
      className="inline-flex items-center rounded-md bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700"
      title={t('calendar.event.importance', { level: t('calendar.event.importance.high').toLowerCase() })}
    >
      {t('w3.cal.important')}
    </span>
  );
}

/** Подтверждена ли дата: «Дата подтверждена» (объявлена источником) или «Ориентировочно» (по графику источника). */
function DateStatus({ event }) {
  const t = useT();
  const tentative = event.date_confidence === 'official_rule' || event.status === 'awaiting_confirmation';
  const Icon = tentative ? Clock3 : CheckCircle2;
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-xs', tentative ? 'text-text-secondary' : 'text-emerald-700')}
      title={tentative ? t('w3.cal.tentativeHint') : t('w3.cal.confirmedHint')}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {tentative ? t('w3.cal.tentative') : t('w3.cal.confirmed')}
    </span>
  );
}

function ValueCell({ label, value, className }) {
  if (!value && value !== 0) return <div className={cn('text-center', className)}><span className="text-text-tertiary">—</span></div>;
  return (
    <div className={cn('text-center', className)}>
      <div className="text-[13px] text-text-secondary mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-text-primary tabular-nums">{value}</div>
    </div>
  );
}

function ActualValueCell({ value, previous, forecast, polarity }) {
  const t = useT();
  if (!value && value !== 0) {
    return (
      <div className="text-center">
        <div className="text-[13px] text-text-secondary mb-0.5">{t('calendar.event.fact')}</div>
        <div className="text-sm text-text-tertiary">—</div>
      </div>
    );
  }

  const numVal = Number(value);
  const compareTo = forecast ?? previous;
  const numCompare = compareTo != null ? Number(compareTo) : null;
  let arrow = '';
  let toneClass = 'text-text-primary';
  if (numCompare != null && isFinite(numVal) && isFinite(numCompare) && numVal !== numCompare) {
    const delta = numVal - numCompare;
    arrow = delta > 0 ? ' ↑' : ' ↓';
    // Цвет по смыслу показателя: рост безработицы не «зелёный», а у неизвестного смысла цвета нет.
    const tone = deltaTone(delta, polarity);
    if (tone === 'good') toneClass = 'fe-tone--good';
    else if (tone === 'bad') toneClass = 'fe-tone--bad';
  }

  return (
    <div className="text-center">
      <div className="text-[13px] text-text-secondary mb-0.5">{t('calendar.event.fact')}</div>
      <div className={cn('text-sm font-bold tabular-nums', toneClass)}>
        {value}{arrow}
      </div>
    </div>
  );
}

export default function CalendarEventCard({ event, isPast, isToday, index = 0, forceCompact = false }) {
  const t = useT();
  const { locale } = useLocale();
  // Вход карточки средствами CSS, каскад ≤ 200 мс. Прошедшие события приглушены (opacity) — их не анимируем,
  // иначе в конце входа прозрачность «щёлкнула» бы с 1 до 0.7.
  const revealClass = isPast ? null : 'fe-reveal fe-reveal--free fe-reveal--stagger';
  const revealStyle = isPast ? undefined : { '--i': Math.min(index, 5), '--fe-duration': '0.35s', '--fe-rise': '10px' };
  const src = SOURCE_STYLES[event.source] || SOURCE_STYLES.cbr;
  const sourceLabel = t(src.labelKey);
  const isHigh = event.importance === 3;
  const isLow = event.importance === 1;
  const title = plainEventTitle(event.title, locale);
  const period = localizeReferencePeriod(event.reference_period, locale);
  const hasValues = event.previous_value != null || event.forecast_value != null || event.actual_value != null;

  const linkedIndicators = Array.isArray(event.indicators) && event.indicators.length > 0
    ? event.indicators
    : (event.indicator_code
      ? [{ code: event.indicator_code, name: event.indicator_name || event.indicator_code }]
      : []);

  if (isLow && (!isToday || forceCompact)) {
    return (
      <div
        style={revealStyle}
        className={cn(
          revealClass,
          'group flex items-center gap-3 px-4 py-2.5 rounded-xl',
          'border border-border-subtle bg-surface',
          'transition-colors hover:bg-surface-hover',
          isPast && 'opacity-60',
        )}
      >
        <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', src.dot)} />
        <span className="min-w-0 flex-1 text-sm leading-snug text-text-secondary line-clamp-2">{title}</span>
        {event.scheduled_time && (
          <span className="text-xs text-text-tertiary font-mono shrink-0">{event.scheduled_time}</span>
        )}
        {period && (
          <span className="text-xs text-text-tertiary shrink-0 hidden sm:inline">{period}</span>
        )}
        {linkedIndicators.length === 1 ? (
          <Link
            to={russiaIndicatorPath(linkedIndicators[0].code)}
            className={cn(FOCUS_RING_SURFACE, 'text-champagne hover:text-champagne-muted rounded-md')}
            title={linkedIndicators[0].name}
            aria-label={t('calendar.event.goTo', { name: linkedIndicators[0].name })}
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        ) : (
          <span className="text-xs text-text-tertiary shrink-0">{linkedIndicators.length > 0
              ? `${linkedIndicators.length} ${t(`z1.cal.ind.${pluralForm(linkedIndicators.length, locale)}`)}`
              : null}</span>
        )}
      </div>
    );
  }

  return (
    <div
      style={revealStyle}
      className={cn(
        revealClass,
        'fe-calendar-event group relative rounded-[1.5rem] border bg-surface transition-all duration-200',
        'border-l-[3px]',
        src.border,
        isHigh ? 'border-border-subtle shadow-sm hover:shadow-md' : 'border-border-subtle',
        isPast && 'opacity-70',
        isToday && 'ring-1 ring-champagne/20',
      )}
    >
      <div className={cn('px-5 py-4', isHigh ? 'md:px-6 md:py-5' : '')}>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn(
              'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold',
              src.bg, src.text,
            )}>
              {sourceLabel}
            </span>
            <ImportanceBadge level={event.importance} />
            <DateStatus event={event} />
          </div>
          {event.scheduled_time && (
            <span className="text-sm font-mono text-text-secondary shrink-0">
              {event.scheduled_time} <span className="text-text-tertiary text-xs">{t('calendar.hero.msk')}</span>
            </span>
          )}
        </div>

        <h3 className={cn(
          'font-semibold text-text-primary leading-snug mb-1',
          isHigh ? 'text-base md:text-lg' : 'text-sm',
        )}>
          {title}
        </h3>

        {period && (
          <p className="text-sm text-text-secondary mb-2">
            {t('z1.cal.period', { period })}
          </p>
        )}

        {event.description && (
          // Одна строка «что это»: первая фраза описания, сокращения расшифрованы.
          <p className="fe-cal-what mb-3" title={plainEventText(event.description, locale)}>
            {plainEventText(event.description, locale)}
          </p>
        )}

        {hasValues && (
          <div className={cn(
            'grid gap-2 pt-3 mt-3 border-t border-border-subtle',
            event.forecast_value ? 'grid-cols-3' : 'grid-cols-2',
          )}>
            <ValueCell label={t('z1.cal.prev')} value={event.previous_value} />
            {event.forecast_value && (
              <ValueCell label={t('z1.cal.forecast')} value={event.forecast_value} />
            )}
            <ActualValueCell
              value={event.actual_value}
              previous={event.previous_value}
              forecast={event.forecast_value}
              polarity={indicatorPolarity(event.title, event.indicator_name)}
            />
          </div>
        )}

        <div className="mt-3 flex flex-col items-start gap-2 pt-2">
          {linkedIndicators.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {linkedIndicators.map((ind) => (
                <li key={ind.code}>
                  <Link
                    to={russiaIndicatorPath(ind.code)}
                    className={cn(
                      FOCUS_RING_SURFACE,
                      'inline-flex items-center gap-1.5 rounded-lg py-0.5 text-sm font-medium text-champagne-ink transition-colors hover:text-champagne-muted',
                    )}
                  >
                    {ind.name}
                    <ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <SourceLink
            href={event.source_url}
            fallbackTo={linkedIndicators[0] ? russiaIndicatorPath(linkedIndicators[0].code) : calendarPath()}
            className="inline-flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
          >
            {t('z1.cal.source')}
            {isExternalHref(event.source_url) ? <ExternalLink className="w-3 h-3" aria-hidden="true" /> : null}
          </SourceLink>
        </div>
      </div>
    </div>
  );
}
