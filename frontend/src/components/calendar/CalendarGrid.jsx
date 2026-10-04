import { useMemo } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';
import Button from '../Button';
import Chip from '../Chip';
import { track, events as trackEvents } from '../../lib/track';
import { useT } from '../../i18n';
import '../../styles/indicator-russia.css';

const SOURCE_DOT = {
  cbr: 'bg-blue-500',
  rosstat: 'bg-emerald-500',
  minfin: 'bg-amber-500',
};

function buildGrid(year, month) {
  const first = new Date(year, month, 1);
  let startDay = first.getDay() - 1;
  if (startDay < 0) startDay = 6;
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells = [];
  for (let i = 0; i < startDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function fmt(year, month, day) {
  const m = String(month + 1).padStart(2, '0');
  const d = String(day).padStart(2, '0');
  return `${year}-${m}-${d}`;
}

export default function CalendarGrid({
  year, month,
  onPrev, onNext,
  events = [],
  selectedDate, onSelectDate,
  source, onSourceChange,
}) {
  const t = useT();
  const todayStr = useMemo(() => {
    const n = new Date();
    return fmt(n.getFullYear(), n.getMonth(), n.getDate());
  }, []);

  const cells = useMemo(() => buildGrid(year, month), [year, month]);

  const eventsByDate = useMemo(() => {
    const map = {};
    for (const ev of events) {
      if (!map[ev.scheduled_date]) map[ev.scheduled_date] = [];
      map[ev.scheduled_date].push(ev);
    }
    return map;
  }, [events]);

  const weekdays = [
    t('calendar.weekday.0'),
    t('calendar.weekday.1'),
    t('calendar.weekday.2'),
    t('calendar.weekday.3'),
    t('calendar.weekday.4'),
    t('calendar.weekday.5'),
    t('calendar.weekday.6'),
  ];

  const sourceButtons = [
    { value: '', label: t('calendar.source.all') },
    { value: 'cbr', label: t('calendar.source.cbr'), dot: 'bg-blue-500' },
    { value: 'rosstat', label: t('calendar.source.rosstat'), dot: 'bg-emerald-500' },
    { value: 'minfin', label: t('calendar.source.minfin'), dot: 'bg-amber-500' },
  ];

  return (
    <div className="fe-panel rounded-[1.5rem] border border-border-subtle bg-surface overflow-hidden mb-6">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
        <Button
          variant="ghost"
          onClick={() => { onPrev(); track(trackEvents.CALENDAR_MONTH_NAV, { direction: 'prev' }); }}
          className="min-h-11 min-w-11 px-0!"
          aria-label={t('calendar.prevMonth')}
        >
          <ChevronLeft className="w-5 h-5 text-text-secondary" aria-hidden="true" />
        </Button>

        <h2 className="text-base font-semibold text-text-primary select-none">
          {t(`calendar.month.${month}`)} {year}
        </h2>

        <Button
          variant="ghost"
          onClick={() => { onNext(); track(trackEvents.CALENDAR_MONTH_NAV, { direction: 'next' }); }}
          className="min-h-11 min-w-11 px-0!"
          aria-label={t('calendar.nextMonth')}
        >
          <ChevronRight className="w-5 h-5 text-text-secondary" aria-hidden="true" />
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 px-4 py-2.5 border-b border-border-subtle bg-obsidian/40">
        {sourceButtons.map((sb) => (
          <Chip
            key={sb.value}
            active={source === sb.value}
            onClick={() => { onSourceChange(sb.value); track(trackEvents.CALENDAR_SOURCE_FILTER, { source: sb.value || 'all' }); }}
            className="gap-1.5"
          >
            {sb.dot && <span className={cn('w-2 h-2 rounded-full', sb.dot)} aria-hidden="true" />}
            {sb.label}
          </Chip>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {weekdays.map((wd) => (
          <div key={wd} className="text-center text-xs font-semibold text-text-secondary py-2">
            {wd}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 border-t border-border-subtle">
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} className="min-h-[3.5rem] md:min-h-[4.5rem] border-b border-r border-border-subtle/50 bg-obsidian/20" />;
          }

          const dateStr = fmt(year, month, day);
          const dayEvents = eventsByDate[dateStr] || [];
          const isToday = dateStr === todayStr;
          const isSelected = dateStr === selectedDate;
          const isPast = dateStr < todayStr;
          const hasHigh = dayEvents.some((e) => e.importance === 3);
          // Плотность дня оттенком фона: чем больше событий, тем темнее. Число в ячейке не нужно.
          const heat = dayEvents.length === 0 ? 0 : dayEvents.length < 3 ? 1 : dayEvents.length < 6 ? 2 : 3;

          const uniqueSources = [...new Set(dayEvents.map((e) => e.source))];

          return (
            <button
              key={dateStr}
              type="button"
              onClick={() => { onSelectDate(isSelected ? null : dateStr); if (!isSelected) track(trackEvents.CALENDAR_DAY_SELECT, { day: dateStr }); }}
              data-heat={heat || undefined}
              aria-pressed={isSelected}
              aria-label={dayEvents.length ? t('w3.cal.dayLabel', { day, n: dayEvents.length }) : undefined}
              className={cn(
                'fe-cal-day relative min-h-[3.5rem] md:min-h-[4.5rem] border-b border-r border-border-subtle/50 transition-all',
                'flex flex-col items-center pt-1.5 gap-1',
                FOCUS_RING_SURFACE,
                isSelected && 'bg-champagne/8 ring-1 ring-inset ring-champagne/20',
                !isSelected && dayEvents.length > 0 && 'hover:bg-surface-hover cursor-pointer',
                !isSelected && dayEvents.length === 0 && 'cursor-default',
                isPast && !isSelected && 'opacity-50',
              )}
            >
              <span className={cn(
                'w-7 h-7 flex items-center justify-center rounded-full text-sm tabular-nums leading-none',
                isToday && !isSelected && 'bg-champagne-ink text-white font-bold',
                isToday && isSelected && 'bg-champagne-ink text-white font-bold',
                !isToday && isSelected && 'bg-champagne/15 text-champagne-ink font-semibold',
                !isToday && !isSelected && hasHigh && 'font-semibold text-text-primary',
                !isToday && !isSelected && !hasHigh && 'text-text-secondary',
              )}>
                {day}
              </span>

              {uniqueSources.length > 0 && (
                <div className="flex gap-0.5">
                  {uniqueSources.slice(0, 3).map((s) => (
                    <span key={s} className={cn('w-2 h-2 rounded-full', SOURCE_DOT[s] || 'bg-text-tertiary')} />
                  ))}
                </div>
              )}

            </button>
          );
        })}
      </div>

      <div className="fe-cal-legend">
        <div className="fe-cal-legend__row">
          <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500" /> {t('calendar.source.cbr')}</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /> {t('calendar.source.rosstat')}</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500" /> {t('calendar.source.minfin')}</span>
          <span className="fe-cal-legend__count">{t('calendar.eventsCount', { n: events.length })}</span>
        </div>
        <p className="fe-cal-legend__hint">{t('w3.cal.legendHint')}</p>
      </div>
    </div>
  );
}
