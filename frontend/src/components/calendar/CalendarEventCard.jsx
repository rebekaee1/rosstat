import { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Clock, ExternalLink } from 'lucide-react';
import gsap from 'gsap';
import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';

const SOURCE_STYLES = {
  cbr: {
    border: 'border-l-blue-500',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-500',
    label: 'ЦБ РФ',
  },
  rosstat: {
    border: 'border-l-emerald-500',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    dot: 'bg-emerald-500',
    label: 'Росстат',
  },
  minfin: {
    border: 'border-l-amber-500',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    dot: 'bg-amber-500',
    label: 'Минфин',
  },
};

const IMPORTANCE_CONFIG = {
  3: { dots: 3, label: 'Высокая', color: 'text-red-500' },
  2: { dots: 2, label: 'Средняя', color: 'text-champagne' },
  1: { dots: 1, label: 'Низкая', color: 'text-text-tertiary' },
};

function ImportanceDots({ level }) {
  const cfg = IMPORTANCE_CONFIG[level] || IMPORTANCE_CONFIG[2];
  return (
    <span className={cn('inline-flex gap-0.5', cfg.color)} title={cfg.label + ' важность'}>
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
  if (!value && value !== 0) {
    return (
      <div className="text-center">
        <div className="text-[10px] uppercase tracking-wider text-text-tertiary mb-0.5">Факт</div>
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
      <div className="text-[10px] uppercase tracking-wider text-text-tertiary mb-0.5">Факт</div>
      <div className={cn('text-sm font-bold tabular-nums', color)}>
        {value}{arrow}
      </div>
    </div>
  );
}

export default function CalendarEventCard({ event, isPast, isToday, index = 0 }) {
  const ref = useRef(null);
  const src = SOURCE_STYLES[event.source] || SOURCE_STYLES.cbr;
  const isHigh = event.importance === 3;
  const isLow = event.importance === 1;
  const hasValues = event.previous_value || event.forecast_value || event.actual_value;

  useEffect(() => {
    if (!ref.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(ref.current,
      { y: 12, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.4, ease: 'power2.out', delay: index * 0.04 }
    );
    return () => tween.kill();
  }, [index]);

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
        {event.indicator_code && (
          <Link
            to={`/indicator/${event.indicator_code}`}
            className={cn(FOCUS_RING_SURFACE, 'text-champagne hover:text-champagne-muted rounded-md')}
            title={event.indicator_name || event.indicator_code}
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
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
              {src.label}
            </span>
            <ImportanceDots level={event.importance} />
            {event.is_estimated && (
              <span className="inline-flex items-center gap-1 text-[10px] text-text-tertiary">
                <Clock className="w-3 h-3" />
                Ожид.
              </span>
            )}
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

        {event.description && isHigh && (
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

        <div className="flex items-center gap-3 mt-3 pt-2">
          {event.indicator_code && (
            <Link
              to={`/indicator/${event.indicator_code}`}
              className={cn(
                FOCUS_RING_SURFACE,
                'inline-flex items-center gap-1.5 text-xs font-medium text-champagne hover:text-champagne-muted rounded-lg transition-colors',
              )}
            >
              {event.indicator_name || event.indicator_code}
              <ArrowUpRight className="w-3 h-3" />
            </Link>
          )}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
            >
              Источник <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
