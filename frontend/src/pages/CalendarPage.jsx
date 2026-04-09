import { useState, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronRight, Download } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useCalendarEvents, useCalendarUpcoming } from '../lib/hooks';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import CalendarHero from '../components/calendar/CalendarHero';
import CalendarFilters from '../components/calendar/CalendarFilters';
import CalendarEventCard from '../components/calendar/CalendarEventCard';
import { SkeletonBox } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';

const WEEKDAYS_RU = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const MONTHS_GENITIVE = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

function formatDayHeader(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const eventDate = new Date(d);
  eventDate.setHours(12, 0, 0, 0);

  const day = d.getUTCDate();
  const month = MONTHS_GENITIVE[d.getUTCMonth()];
  const year = d.getUTCFullYear();
  const weekday = WEEKDAYS_RU[d.getDay()];
  const capitalized = weekday.charAt(0).toUpperCase() + weekday.slice(1);

  if (eventDate.getTime() === today.getTime()) {
    return { label: `Сегодня, ${day} ${month}`, isToday: true };
  }
  if (eventDate.getTime() === tomorrow.getTime()) {
    return { label: `Завтра, ${day} ${month}`, isToday: false };
  }
  return { label: `${capitalized}, ${day} ${month} ${year}`, isToday: false };
}

function periodToDates(period) {
  const now = new Date();
  const from = new Date(now);
  from.setDate(from.getDate() - 7);
  const to = new Date(now);
  if (period === 'week') to.setDate(to.getDate() + 7);
  else if (period === 'quarter') to.setDate(to.getDate() + 90);
  else to.setDate(to.getDate() + 30);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { from: fmt(from), to: fmt(to) };
}

function CalendarSkeleton() {
  return (
    <div className="space-y-6">
      {[1, 2, 3].map((g) => (
        <div key={g}>
          <SkeletonBox className="h-5 w-48 mb-4" />
          <div className="space-y-3">
            {[1, 2].map((i) => <SkeletonBox key={i} className="h-28 w-full rounded-2xl" />)}
          </div>
        </div>
      ))}
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
  const [source, setSource] = useState(searchParams.get('source') || '');
  const [importance, setImportance] = useState(searchParams.get('importance') || '');
  const [period, setPeriod] = useState(searchParams.get('period') || 'month');

  useDocumentMeta({
    title: 'Экономический календарь России 2026 — даты ЦБ, Росстата, Минфина',
    description:
      'Расписание публикаций экономических данных: заседания ЦБ по ключевой ставке, ИПЦ, ВВП, безработица, денежная масса. ' +
      'Бесплатный экономический календарь с фильтрами по источникам и важности.',
    path: '/calendar',
  });

  const updateParam = (key, value, setter) => {
    setter(value);
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const dates = useMemo(() => periodToDates(period), [period]);

  const apiParams = useMemo(() => ({
    from: dates.from,
    to: dates.to,
    source: source || undefined,
    importance: importance || undefined,
    limit: 300,
  }), [dates, source, importance]);

  const { data, isLoading, isError, refetch, isFetching } = useCalendarEvents(apiParams);
  const { data: upcomingData } = useCalendarUpcoming({ limit: 1, importance_min: 3 });

  const nextImportant = upcomingData?.events?.[0] || null;

  const grouped = useMemo(() => {
    if (!data?.events) return [];
    const map = new Map();
    for (const ev of data.events) {
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
      ...formatDayHeader(dateStr),
    }));
  }, [data]);

  const todayStr = new Date().toISOString().slice(0, 10);

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 pt-20 pb-24">
      <nav
        className="flex items-center gap-2 text-sm text-text-tertiary mb-6"
        aria-label="Хлебные крошки"
      >
        <Link to="/" className="hover:text-champagne transition-colors rounded-sm">
          Главная
        </Link>
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

      <CalendarFilters
        source={source}
        onSourceChange={(v) => updateParam('source', v, setSource)}
        importance={importance}
        onImportanceChange={(v) => updateParam('importance', v, setImportance)}
        period={period}
        onPeriodChange={(v) => updateParam('period', v, setPeriod)}
      />

      {isError && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          <span className="font-semibold">Календарь временно недоступен.</span>{' '}
          Попробуйте обновить через минуту.
        </ApiRetryBanner>
      )}

      {isLoading ? (
        <CalendarSkeleton />
      ) : grouped.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-text-secondary text-lg mb-2">Нет событий в выбранном периоде</p>
          <p className="text-text-tertiary text-sm">Попробуйте расширить диапазон или сбросить фильтры</p>
        </div>
      ) : (
        <div className="relative">
          <div className="absolute left-3 md:left-4 top-0 bottom-0 w-px bg-gradient-to-b from-champagne/30 via-border-subtle to-transparent pointer-events-none" />

          <div className="space-y-8">
            {grouped.map((group) => {
              const isPast = group.dateStr < todayStr;
              return (
                <section key={group.dateStr}>
                  <div className="relative flex items-center gap-3 mb-4">
                    <div className={cn(
                      'w-2.5 h-2.5 rounded-full shrink-0 ring-4 ring-obsidian z-10',
                      group.isToday ? 'bg-champagne' : isPast ? 'bg-slate-dark' : 'bg-border-subtle',
                    )} />
                    <h2 className={cn(
                      'text-sm font-semibold uppercase tracking-wider',
                      group.isToday ? 'text-champagne' : 'text-text-secondary',
                    )}>
                      {group.label}
                    </h2>
                    {group.isToday && (
                      <span className="px-2 py-0.5 rounded-full bg-champagne/10 text-champagne text-[10px] font-bold uppercase tracking-wider">
                        Сегодня
                      </span>
                    )}
                  </div>

                  <div className="ml-6 md:ml-8 space-y-3">
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
        </div>
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
