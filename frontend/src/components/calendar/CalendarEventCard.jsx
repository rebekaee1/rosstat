import { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ExternalLink } from 'lucide-react';
import gsap from 'gsap';
import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';
import { trackOutbound } from '../../lib/track';
import {
  russiaIndicatorPath,
} from '../../lib/sitePaths';
import { useT } from '../../i18n';

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

const IMPORTANCE_CONFIG = {
  3: { dots: 3, labelKey: 'calendar.event.importance.high', color: 'text-red-500' },
  2: { dots: 2, labelKey: 'calendar.event.importance.medium', color: 'text-champagne' },
  1: { dots: 1, labelKey: 'calendar.event.importance.low', color: 'text-text-tertiary' },
};

function ImportanceDots({ level }) {
  const t = useT();
  const cfg = IMPORTANCE_CONFIG[level] || IMPORTANCE_CONFIG[2];
  const levelLabel = t(cfg.labelKey);
  return (
    <span className={cn('inline-flex gap-0.5', cfg.color)} title={t('calendar.event.importance', { level: levelLabel })}>
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className={cn(
            'w-1.5 h-1.5 rounded-full',
            i <= cfg.dots ? 'bg-current' : 'bg-current/20'
          )}
        />
      ))}
    </span>
  );
}

function ValueCell({ label, value, className }) {
  if (!value && value !== 0) return <div className={cn('text-center', className)}><span className="text-text-tertiary">—</span></div>;
  return (
    <div className={cn('text-center', className)}>
      <div className="text-[10px] uppercase tracking-wider text-text-tertiary mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-text-primary tabular-nums">{value}</div>
    </div>
  );
}

function ActualValueCell({ value, previous, forecast }) {
  const t = useT();
  if (!value && value !== 0) {
    return (
      <div className="text-center">
        <div className="text-[10px] uppercase tracking-wider text-text-tertiary mb-0.5">{t('calendar.event.fact')}</div>
        <div className="text-sm text-text-tertiary">—</div>
      </div>
    );
  }

  const numVal = Number(value);
  const compareTo = forecast ?? previous;
  const numCompare = compareTo != null ? Number(compareTo) : null;
  let arrow = '';
  let color = 'text-text-primary';
  if (numCompare != null && isFinite(numVal) && isFinite(numCompare)) {
    if (numVal > numCompare) { arrow = ' ↑'; color = 'text-positive'; }
    else if (numVal < numCompare) { arrow = ' ↓'; color = 'text-negative'; }
  }

  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-text-tertiary mb-0.5">{t('calendar.event.fact')}</div>
      <div className={cn('text-sm font-bold tabular-nums', color)}>
        {value}{arrow}
      </div>
    </div>
  );
}

export default function CalendarEventCard({ event, isPast, isToday, index = 0 }) {
  const t = useT();
  const ref = useRef(null);
  const src = SOURCE_STYLES[event.source] || SOURCE_STYLES.cbr;
  const sourceLabel = t(src.labelKey);
  const isHigh = event.importance === 3;
  const isLow = event.importance === 1;
  const hasValues = event.previous_value != null || event.forecast_value != null || event.actual_value != null;

  useEffect(() => {
    if (!ref.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(ref.current,
      { y: 12, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.4, ease: 'power2.out', delay: index * 0.04 }
    );
    return () => tween.kill();
  }, [index]);

  const linkedIndicators = Array.isArray(event.indicators) && event.indicators.length > 0
    ? event.indicators
    : (event.indicator_code
      ? [{ code: event.indicator_code, name: event.indicator_name || event.indicator_code }]
      : []);

  if (isLow && !isToday) {
    return (
      <div
        ref={ref}
        className={cn(
          'group flex items-center gap-3 px-4 py-2.5 rounded-xl',
          'border border-border-subtle bg-surface',
          'transition-colors hover:bg-surface-hover',
          isPast && 'opacity-60',
        )}
      >
        <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', src.dot)} />
        <span className="text-sm text-text-secondary truncate flex-1">{event.title}</span>
        {event.scheduled_time && (
          <span className="text-xs text-text-tertiary font-mono shrink-0">{event.scheduled_time}</span>
        )}
        {event.reference_period && (
          <span className="text-xs text-text-tertiary shrink-0 hidden sm:inline">{event.reference_period}</span>
        )}
        <ImportanceDots level={1} />
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
          <span className="text-xs text-text-tertiary shrink-0">{t('calendar.event.seriesCount', { n: linkedIndicators.length })}</span>
        )}
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className={cn(
        'group relative rounded-2xl border bg-surface transition-all duration-200',
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
              'inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider',
              src.bg, src.text,
            )}>
              {sourceLabel}
            </span>
            <ImportanceDots level={event.importance} />
            <span className="text-[10px] text-text-tertiary">{t('calendar.event.official')}</span>
          </div>
          {event.scheduled_time && (
            <span className="text-sm font-mono text-text-secondary shrink-0">
              {event.scheduled_time} <span className="text-text-tertiary text-xs">МСК</span>
            </span>
          )}
        </div>

        <h3 className={cn(
          'font-semibold text-text-primary leading-snug mb-1',
          isHigh ? 'text-base md:text-lg' : 'text-sm',
        )}>
          {event.title}
        </h3>

        {event.reference_period && (
          <p className="text-sm text-text-secondary mb-2">
            за {event.reference_period}
          </p>
        )}

        {event.description && (
          <p className="text-xs text-text-tertiary leading-relaxed mb-3 max-w-lg">
            {event.description}
          </p>
        )}

        {hasValues && (
          <div className={cn(
            'grid gap-2 pt-3 mt-3 border-t border-border-subtle',
            event.forecast_value ? 'grid-cols-3' : 'grid-cols-2',
          )}>
            <ValueCell label="Предыдущее" value={event.previous_value} />
            {event.forecast_value && (
              <ValueCell label="Прогноз" value={event.forecast_value} />
            )}
            <ActualValueCell
              value={event.actual_value}
              previous={event.previous_value}
              forecast={event.forecast_value}
            />
          </div>
        )}

        <div className="flex items-center gap-2 mt-3 pt-2 flex-wrap">
          {linkedIndicators.map((ind) => (
            <Link
              key={ind.code}
              to={russiaIndicatorPath(ind.code)}
              className={cn(
                FOCUS_RING_SURFACE,
                'inline-flex items-center gap-1.5 text-xs font-medium text-champagne hover:text-champagne-muted rounded-lg transition-colors',
              )}
            >
              {ind.name}
              <ArrowUpRight className="w-3 h-3" />
            </Link>
          ))}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackOutbound(event.source_url)}
              className="inline-flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary transition-colors ml-auto"
            >
              Источник <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
