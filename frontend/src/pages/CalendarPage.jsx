import { useState, useMemo, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronRight, Download, X } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useCalendarEvents, useCalendarUpcoming } from '../lib/hooks';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import CalendarHero from '../components/calendar/CalendarHero';
import CalendarGrid from '../components/calendar/CalendarGrid';
import CalendarEventCard from '../components/calendar/CalendarEventCard';
import { SkeletonBox } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';

const MONTHS_GENITIVE = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

const WEEKDAYS_RU = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];

function formatDayLabel(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const eventDate = new Date(d);
  eventDate.setHours(12, 0, 0, 0);

  const day = d.getDate();
  const month = MONTHS_GENITIVE[d.getMonth()];
  const year = d.getFullYear();
  const weekday = WEEKDAYS_RU[d.getDay()];
  const cap = weekday.charAt(0).toUpperCase() + weekday.slice(1);

  if (eventDate.getTime() === today.getTime()) return `Сегодня, ${day} ${month}`;
  if (eventDate.getTime() === tomorrow.getTime()) return `Завтра, ${day} ${month}`;
  return `${cap}, ${day} ${month} ${year}`;
}

function monthRange(year, month) {
  const from = `${year}-${String(month + 1).padStart(2, '0')}-01`;
  const lastDay = new Date(year, month + 1, 0).getDate();
  const to = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  return { from, to };
}

function CalendarSkeleton() {
  return (
    <div className="space-y-4">
      <SkeletonBox className="h-[22rem] w-full rounded-2xl" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => <SkeletonBox key={i} className="h-24 w-full rounded-2xl" />)}
      </div>
    </div>
  );
}

const FAQ_ITEMS = [
  {
    q: 'Когда следующее заседание ЦБ по ключевой ставке?',
    a: 'Банк России проводит 8 заседаний в год. Расписание публикуется в январе на весь год. Пресс-релиз выходит в 13:30 МСК, пресс-конференция — в 15:00 МСК.',
  },
  {
    q: 'Когда Росстат публикует данные по инфляции (ИПЦ)?',
    a: 'Индекс потребительских цен (ИПЦ) за предыдущий месяц обычно публикуется 5–7 числа следующего месяца в соответствии с Advance Release Calendar МВФ.',
  },
  {
    q: 'Что такое Advance Release Calendar?',
    a: 'Advance Release Calendar (ARC) — стандарт МВФ SDDS, обязывающий страны публиковать расписание выхода статистических данных. Россия публикует ARC через Минфин.',
  },
];

export default function CalendarPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const now = new Date();
  const [year, setYear] = useState(() => {
    const p = parseInt(searchParams.get('y'), 10);
    return isNaN(p) ? now.getFullYear() : p;
  });
  const [month, setMonth] = useState(() => {
    const p = parseInt(searchParams.get('m'), 10);
    return isNaN(p) ? now.getMonth() : Math.max(0, Math.min(11, p));
  });
  const [source, setSource] = useState(searchParams.get('source') || '');
  const [selectedDate, setSelectedDate] = useState(null);

  useDocumentMeta({
    title: 'Экономический календарь России 2026 — даты ЦБ, Росстата, Минфина',
    description:
      'Расписание публикаций экономических данных: заседания ЦБ по ключевой ставке, ИПЦ, ВВП, безработица, денежная масса. ' +
      'Бесплатный экономический календарь с фильтрами по источникам и важности.',
    path: '/calendar',
  });

  const syncParams = useCallback((y, m, src) => {
    const next = new URLSearchParams(searchParams);
    const isCurrentMonth = y === now.getFullYear() && m === now.getMonth();
    if (isCurrentMonth) { next.delete('y'); next.delete('m'); }
    else { next.set('y', String(y)); next.set('m', String(m)); }
    if (src) next.set('source', src); else next.delete('source');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, now]);

  const goMonth = useCallback((delta) => {
    let newMonth = month + delta;
    let newYear = year;
    if (newMonth > 11) { newMonth = 0; newYear++; }
    else if (newMonth < 0) { newMonth = 11; newYear--; }
    setMonth(newMonth);
    setYear(newYear);
    setSelectedDate(null);
    syncParams(newYear, newMonth, source);
  }, [month, year, source, syncParams]);

  const handleSourceChange = useCallback((v) => {
    setSource(v);
    syncParams(year, month, v);
  }, [year, month, syncParams]);

  const handleSelectDate = useCallback((d) => {
    setSelectedDate(d);
  }, []);

  const dates = useMemo(() => monthRange(year, month), [year, month]);

  const apiParams = useMemo(() => ({
    from: dates.from,
    to: dates.to,
    source: source || undefined,
    limit: 500,
  }), [dates, source]);

  const { data, isLoading, isError, refetch, isFetching } = useCalendarEvents(apiParams);
  const { data: upcomingData } = useCalendarUpcoming({ limit: 1, importance_min: 3 });
  const nextImportant = upcomingData?.events?.[0] || null;

  const allEvents = data?.events || [];

  const todayStr = now.toISOString().slice(0, 10);

  const visibleEvents = useMemo(() => {
    if (!selectedDate) return allEvents;
    return allEvents.filter((e) => e.scheduled_date === selectedDate);
  }, [allEvents, selectedDate]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const ev of visibleEvents) {
      const key = ev.scheduled_date;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(ev);
    }
    return Array.from(map.entries()).map(([dateStr, events]) => ({
      dateStr,
      events: events.sort((a, b) => {
        if (a.importance !== b.importance) return b.importance - a.importance;
        return (a.scheduled_time || '').localeCompare(b.scheduled_time || '');
      }),
      label: formatDayLabel(dateStr),
      isToday: dateStr === todayStr,
    }));
  }, [visibleEvents, todayStr]);

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 pt-20 pb-24">
      <nav className="flex items-center gap-2 text-sm text-text-tertiary mb-6" aria-label="Хлебные крошки">
        <Link to="/" className="hover:text-champagne transition-colors rounded-sm">Главная</Link>
        <ChevronRight className="w-4 h-4 shrink-0 opacity-60" />
        <span className="text-text-primary font-medium">Календарь</span>
      </nav>

      <header className="mb-6">
        <h1 className="font-display text-3xl md:text-[2.4rem] font-bold text-text-primary tracking-tight mb-3">
          Экономический календарь
        </h1>
        <p className="text-text-secondary leading-relaxed max-w-2xl">
          Расписание публикаций Росстата, заседаний ЦБ РФ и данных Минфина.
          Фактические значения обновляются автоматически.
        </p>
      </header>

      <CalendarHero nextEvent={nextImportant} />

      {isError && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          <span className="font-semibold">Календарь временно недоступен.</span>{' '}
          Попробуйте обновить через минуту.
        </ApiRetryBanner>
      )}

      {isLoading ? (
        <CalendarSkeleton />
      ) : (
        <>
          <CalendarGrid
            year={year}
            month={month}
            onPrev={() => goMonth(-1)}
            onNext={() => goMonth(1)}
            events={allEvents}
            selectedDate={selectedDate}
            onSelectDate={handleSelectDate}
            source={source}
            onSourceChange={handleSourceChange}
          />

          {selectedDate && (
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-sm font-semibold text-text-primary">
                {formatDayLabel(selectedDate)}
              </h2>
              <button
                type="button"
                onClick={() => setSelectedDate(null)}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs text-text-tertiary hover:text-text-primary hover:bg-surface-hover transition-colors"
              >
                <X className="w-3 h-3" />
                Показать весь месяц
              </button>
            </div>
          )}

          {grouped.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-text-secondary text-lg mb-2">
                {selectedDate ? 'Нет событий в этот день' : 'Нет событий в этом месяце'}
              </p>
              <p className="text-text-tertiary text-sm">
                {selectedDate
                  ? 'Выберите другую дату или покажите весь месяц'
                  : 'Попробуйте другой месяц или сбросьте фильтр источника'}
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {grouped.map((group) => {
                const isPast = group.dateStr < todayStr;
                return (
                  <section key={group.dateStr}>
                    {!selectedDate && (
                      <h3 className={cn(
                        'text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2',
                        group.isToday ? 'text-champagne' : 'text-text-tertiary',
                      )}>
                        {group.label}
                        {group.isToday && (
                          <span className="px-1.5 py-px rounded bg-champagne/10 text-champagne text-[10px] font-bold">
                            Сегодня
                          </span>
                        )}
                        <span className="text-text-tertiary font-normal">
                          — {group.events.length} {group.events.length === 1 ? 'событие' : group.events.length < 5 ? 'события' : 'событий'}
                        </span>
                      </h3>
                    )}
                    <div className="space-y-2.5">
                      {group.events.map((ev, i) => (
                        <CalendarEventCard
                          key={ev.id}
                          event={ev}
                          isPast={isPast}
                          isToday={group.isToday}
                          index={i}
                        />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </>
      )}

      {data?.total > 0 && (
        <div className="flex items-center justify-center gap-4 mt-10 pt-6 border-t border-border-subtle">
          <a
            href="/api/v1/calendar/export/ical?importance_min=2"
            className={cn(
              FOCUS_RING_SURFACE,
              'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium',
              'border border-border-subtle text-text-secondary hover:text-text-primary hover:border-champagne/30 transition-colors',
            )}
            download
          >
            <Download className="w-4 h-4" />
            Экспорт в iCal
          </a>
        </div>
      )}

      <section className="mt-16">
        <h2 className="font-display text-xl font-bold text-text-primary mb-6">
          Частые вопросы
        </h2>
        <dl className="space-y-4">
          {FAQ_ITEMS.map((item, i) => (
            <div key={i} className="rounded-2xl border border-border-subtle bg-surface p-5">
              <dt className="font-semibold text-text-primary text-sm mb-2">{item.q}</dt>
              <dd className="text-sm text-text-secondary leading-relaxed">{item.a}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
