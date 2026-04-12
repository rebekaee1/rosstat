import { useMemo } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';
import { track, events as trackEvents } from '../../lib/track';

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

const MONTHS_NOM = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

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

  const sourceButtons = [
    { value: '', label: 'Все' },
    { value: 'cbr', label: 'ЦБ', dot: 'bg-blue-500' },
    { value: 'rosstat', label: 'Росстат', dot: 'bg-emerald-500' },
    { value: 'minfin', label: 'Минфин', dot: 'bg-amber-500' },
  ];

  return (
    <div className="rounded-2xl border border-border-subtle bg-surface overflow-hidden mb-6">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
        <button
          type="button" onClick={() => { onPrev(); track(trackEvents.CALENDAR_MONTH_NAV, { direction: 'prev' }); }}
          className={cn(FOCUS_RING_SURFACE, 'p-1.5 rounded-lg hover:bg-surface-hover transition-colors')}
          aria-label="Предыдущий месяц"
        >
          <ChevronLeft className="w-5 h-5 text-text-secondary" />
        </button>

        <h2 className="text-base font-semibold text-text-primary select-none">
          {MONTHS_NOM[month]} {year}
        </h2>

        <button
          type="button" onClick={() => { onNext(); track(trackEvents.CALENDAR_MONTH_NAV, { direction: 'next' }); }}
          className={cn(FOCUS_RING_SURFACE, 'p-1.5 rounded-lg hover:bg-surface-hover transition-colors')}
          aria-label="Следующий месяц"
        >
          <ChevronRight className="w-5 h-5 text-text-secondary" />
        </button>
      </div>

      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-border-subtle bg-obsidian/40">
        {sourceButtons.map((sb) => (
          <button
            key={sb.value}
            type="button"
            onClick={() => { onSourceChange(sb.value); track(trackEvents.CALENDAR_SOURCE_FILTER, { source: sb.value || 'all' }); }}
            className={cn(
              FOCUS_RING_SURFACE,
              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all',
              source === sb.value
                ? 'bg-champagne/10 text-champagne border border-champagne/20'
                : 'text-text-secondary hover:text-text-primary border border-transparent',
            )}
          >
            {sb.dot && <span className={cn('w-2 h-2 rounded-full', sb.dot)} />}
            {sb.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {WEEKDAYS.map((wd) => (
          <div key={wd} className="text-center text-[11px] font-medium text-text-tertiary uppercase tracking-wider py-2">
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

          const uniqueSources = [...new Set(dayEvents.map((e) => e.source))];

          return (
            <button
              key={dateStr}
              type="button"
              onClick={() => { onSelectDate(isSelected ? null : dateStr); if (!isSelected) track(trackEvents.CALENDAR_DAY_SELECT, { day: dateStr }); }}
              className={cn(
                'relative min-h-[3.5rem] md:min-h-[4.5rem] border-b border-r border-border-subtle/50 transition-all',
                'flex flex-col items-center pt-1.5 gap-0.5',
                FOCUS_RING_SURFACE,
                isSelected && 'bg-champagne/8 ring-1 ring-inset ring-champagne/20',
                !isSelected && dayEvents.length > 0 && 'hover:bg-surface-hover cursor-pointer',
                !isSelected && dayEvents.length === 0 && 'cursor-default',
                isPast && !isSelected && 'opacity-50',
              )}
            >
              <span className={cn(
                'w-7 h-7 flex items-center justify-center rounded-full text-sm tabular-nums leading-none',
                isToday && !isSelected && 'bg-champagne text-white font-bold',
                isToday && isSelected && 'bg-champagne text-white font-bold',
                !isToday && isSelected && 'bg-champagne/15 text-champagne font-semibold',
                !isToday && !isSelected && hasHigh && 'font-semibold text-text-primary',
                !isToday && !isSelected && !hasHigh && 'text-text-secondary',
              )}>
                {day}
              </span>

              {uniqueSources.length > 0 && (
                <div className="flex gap-0.5">
                  {uniqueSources.slice(0, 3).map((s) => (
                    <span key={s} className={cn('w-1.5 h-1.5 rounded-full', SOURCE_DOT[s] || 'bg-text-tertiary')} />
                  ))}
                </div>
              )}

              {dayEvents.length > 1 && (
                <span className="text-[9px] text-text-tertiary leading-none">{dayEvents.length}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between px-4 py-2 text-[11px] text-text-tertiary border-t border-border-subtle">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> ЦБ</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Росстат</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Минфин</span>
        </div>
        <span>{events.length} событий</span>
      </div>
    </div>
  );
}
