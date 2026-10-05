import { useState, useMemo, useCallback } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { CalendarX2, ChevronDown, Download, X } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useCalendarEvents, useCalendarUpcoming } from '../lib/hooks';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import CalendarHero from '../components/calendar/CalendarHero';
import CalendarGrid from '../components/calendar/CalendarGrid';
import CalendarEventCard from '../components/calendar/CalendarEventCard';
import { SkeletonBox } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import Breadcrumbs from '../components/Breadcrumbs';
import { track, events } from '../lib/track';
import { plainEventTitle, pluralForm } from '../lib/calendarText';
import { groupSimilarEvents, findDailyRecurring, recurringKeyOf } from '../lib/calendarGrouping';
import { calendarMonthTrail, calendarTrail } from '../lib/breadcrumbs';
import {
  calendarPath,
} from '../lib/sitePaths';
import { useT, useLocale } from '../i18n';
import '../styles/indicator-russia.css';
import '../styles/regions-w4.css';
import '../styles/w5-pages.css';

const WEEKDAY_KEYS = [
  'calendar.weekday.sun',
  'calendar.weekday.mon',
  'calendar.weekday.tue',
  'calendar.weekday.wed',
  'calendar.weekday.thu',
  'calendar.weekday.fri',
  'calendar.weekday.sat',
];

function formatDayLabel(dateStr, t) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const eventDate = new Date(d);
  eventDate.setHours(12, 0, 0, 0);

  const day = d.getDate();
  const month = t(`calendar.monthGen.${d.getMonth()}`);
  const year = d.getFullYear();
  const weekday = t(WEEKDAY_KEYS[d.getDay()]);

  if (eventDate.getTime() === today.getTime()) return `${t('calendar.today')}, ${day} ${month}`;
  if (eventDate.getTime() === tomorrow.getTime()) return `${t('calendar.tomorrow')}, ${day} ${month}`;
  return `${weekday}, ${day} ${month} ${year}`;
}

function monthRange(year, month) {
  const from = `${year}-${String(month + 1).padStart(2, '0')}-01`;
  const lastDay = new Date(year, month + 1, 0).getDate();
  const to = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  return { from, to };
}

function CalendarSkeleton({ onRefresh }) {
  return (
    <div className="space-y-4" role="status" aria-busy="true">
      <LoadingNote onRefresh={onRefresh} />
      <SkeletonBox className="h-[22rem] w-full rounded-[1.5rem]" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => <SkeletonBox key={i} className="h-24 w-full rounded-[1.5rem]" />)}
      </div>
    </div>
  );
}

const FAQ_KEYS = [
  { q: 'calendar.faq.q1', a: 'calendar.faq.a1' },
  { q: 'calendar.faq.q2', a: 'calendar.faq.a2' },
  { q: 'calendar.faq.q3', a: 'calendar.faq.a3' },
];

/**
 * События одного дня. Ежедневные курсы и ставки (важность «низкая», их много каждый будний день)
 * сворачиваются в одну строку «Ежедневные курсы и ставки: 4», чтобы редкие важные публикации не тонули.
 */
function DayEvents({ events: dayEvents, isPast, isToday, defaultOpen }) {
  const t = useT();
  const lows = dayEvents.filter((e) => e.importance === 1);
  const collapse = lows.length >= 3;
  const main = collapse ? dayEvents.filter((e) => e.importance !== 1) : dayEvents;
  return (
    <div className="space-y-2.5">
      {main.map((ev, i) => (
        <CalendarEventCard key={ev.id} event={ev} isPast={isPast} isToday={isToday} index={i} />
      ))}
      {collapse && (
        <details className="fe-acc rounded-xl border border-border-subtle bg-surface" open={defaultOpen || undefined}>
          <summary className="fe-tap flex items-center justify-between gap-3 rounded-xl px-4 py-2.5 text-sm font-medium text-text-secondary">
            {t('x4.cal.daily', { n: lows.length })}
            <ChevronDown className="fe-acc__chev h-4 w-4 shrink-0" aria-hidden="true" />
          </summary>
          <div className="space-y-2 px-2 pb-2">
            {lows.map((ev, i) => (
              <CalendarEventCard key={ev.id} event={ev} isPast={isPast} isToday={isToday} index={i} forceCompact />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

export default function CalendarPage({ fixedYear, fixedMonth, seoPath } = {}) {
  const t = useT();
  const { locale } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();

  const [initYear] = useState(() => fixedYear ?? new Date().getFullYear());
  const [initMonth] = useState(() => fixedMonth ?? new Date().getMonth());
  const [year, setYear] = useState(() => {
    if (fixedYear != null) return fixedYear;
    const p = parseInt(searchParams.get('y'), 10);
    return isNaN(p) ? initYear : p;
  });
  const [month, setMonth] = useState(() => {
    if (fixedMonth != null) return fixedMonth;
    const p = parseInt(searchParams.get('m'), 10);
    return isNaN(p) ? initMonth : Math.max(0, Math.min(11, p));
  });
  const [source, setSource] = useState(searchParams.get('source') || '');
  const [selectedDate, setSelectedDate] = useState(null);
  const navigate = useNavigate();

  const calendarSeo = getPageSeo('calendar', locale);
  const monthLabel = t(`calendar.month.${month}`);
  const monthGenLabel = t(`calendar.monthGen.${month}`);
  useDocumentMeta({
    title: seoPath
      ? t('calendar.seoMonthTitle', { month: monthLabel, year })
      : calendarSeo.title,
    description: seoPath
      ? t('calendar.seoMonthDesc', { month: monthGenLabel, year })
      : calendarSeo.description,
    path: seoPath || calendarSeo.path,
  });

  const syncParams = useCallback((y, m, src) => {
    const next = new URLSearchParams(searchParams);
    const isCurrentMonth = y === initYear && m === initMonth;
    if (isCurrentMonth) { next.delete('y'); next.delete('m'); }
    else { next.set('y', String(y)); next.set('m', String(m)); }
    if (src) next.set('source', src); else next.delete('source');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, initYear, initMonth]);

  const goMonth = useCallback((delta) => {
    let newMonth = month + delta;
    let newYear = year;
    if (newMonth > 11) { newMonth = 0; newYear++; }
    else if (newMonth < 0) { newMonth = 11; newYear--; }
    if (seoPath) {
      const mm = String(newMonth + 1).padStart(2, '0');
      navigate(calendarPath(newYear, mm));
      return;
    }
    setMonth(newMonth);
    setYear(newYear);
    setSelectedDate(null);
    syncParams(newYear, newMonth, source);
  }, [month, year, source, syncParams, seoPath, navigate]);

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
  // Ближайшее событие — самое важное из нескольких предстоящих, а не ежедневная ставка вроде RUONIA.
  const { data: upcomingData } = useCalendarUpcoming({ limit: 8, importance_min: 2 });
  const upcomingList = upcomingData?.events;
  const nextImportant = upcomingList?.find((e) => e.importance === 3) || upcomingList?.[0] || null;

  const allEvents = useMemo(() => data?.events || [], [data]);
  // Ошибка без данных: сетку не рисуем (раньше «календарь недоступен» стоял над готовой пустой сеткой), остаётся плашка с повтором.
  const failedWithoutData = isError && !data;

  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, []);

  // «Текущий» месяц считаем от реальной даты, а не от открытой страницы: на лендинге прошедшего месяца
  // события не отсекаются по сегодняшнему дню.
  const isCurrentMonth = useMemo(() => {
    const now = new Date();
    return year === now.getFullYear() && month === now.getMonth();
  }, [year, month]);

  // Ежедневные события («Ставка RUONIA», курсы) — одной строкой «Каждый рабочий день», а не в каждом дне.
  const recurring = useMemo(() => findDailyRecurring(allEvents), [allEvents]);
  const showRecurring = !selectedDate && recurring.items.length > 0;

  const visibleEvents = useMemo(() => {
    let filtered = allEvents;
    if (selectedDate) filtered = allEvents.filter((e) => e.scheduled_date === selectedDate);
    else {
      if (isCurrentMonth) filtered = allEvents.filter((e) => e.scheduled_date >= todayStr);
      if (recurring.keys.size > 0) filtered = filtered.filter((e) => !recurring.keys.has(recurringKeyOf(e)));
    }
    return groupSimilarEvents(filtered);
  }, [allEvents, selectedDate, isCurrentMonth, todayStr, recurring]);

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
        const byTime = (a.scheduled_time || '').localeCompare(b.scheduled_time || '');
        // Одинаковое время — всегда один и тот же порядок (евро, доллар, юань, золото не «прыгают» по дням).
        return byTime || (a.title || '').localeCompare(b.title || '', 'ru');
      }),
      label: formatDayLabel(dateStr, t),
      isToday: dateStr === todayStr,
    }));
  }, [visibleEvents, todayStr, t]);

  // Какое пустое состояние показать: день / в текущем месяце остались только прошедшие / месяц без событий.
  const emptyKind = selectedDate
    ? 'emptyDay'
    : (isCurrentMonth && allEvents.length > 0 && !source ? 'emptyUpcoming' : 'emptyMonth');

  return (
    <div className="fe-data-page max-w-4xl mx-auto px-4 md:px-8 pt-20 pb-12 sm:pb-16">
      <Breadcrumbs
        items={seoPath
          ? calendarMonthTrail(`${monthLabel} ${year}`, year, month + 1)
          : calendarTrail()}
        className="mb-6"
      />

      <header className="mb-6">
        <h1 className="font-display text-3xl md:text-[2.4rem] font-bold text-text-primary tracking-tight mb-3">
          {t('z1.cal.title')}
        </h1>
        <p className="text-text-secondary leading-relaxed max-w-2xl">
          {t('z1.cal.lead')}
        </p>
      </header>

      <CalendarHero nextEvent={nextImportant} />

      {isError && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          <span className="font-semibold">{t('calendar.state.error.title')}</span>{' '}
          {t('calendar.state.error.hint')}
        </ApiRetryBanner>
      )}

      {isLoading ? (
        <CalendarSkeleton onRefresh={() => refetch()} />
      ) : failedWithoutData ? null : (
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
                {formatDayLabel(selectedDate, t)}
              </h2>
              <button
                type="button"
                onClick={() => { setSelectedDate(null); track(events.CALENDAR_CLEAR_DAY); }}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs text-text-tertiary hover:text-text-primary hover:bg-surface-hover transition-colors"
              >
                <X className="w-3 h-3" />
                {t('calendar.state.showMonth')}
              </button>
            </div>
          )}

          {showRecurring && (
            <section className="fe-cal-recurring mb-6" aria-label={t(recurring.everyDay ? 'y1.cal.everyDay' : 'y1.cal.everyWorkday')} data-testid="calendar-recurring">
              <h3 className="fe-cal-recurring__title">{t(recurring.everyDay ? 'y1.cal.everyDay' : 'y1.cal.everyWorkday')}</h3>
              <ul className="fe-cal-recurring__list">
                {recurring.items.map((item) => (
                  <li key={item.key}>
                    <span className="min-w-0">{plainEventTitle(item.title, locale)}</span>
                    {item.time ? <span className="fe-num shrink-0 text-text-secondary">{item.time.slice(0, 5)}</span> : null}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {grouped.length === 0 ? (
            // При ошибке загрузки текст «нет событий» был бы неправдой — о причине уже говорит баннер выше.
            !isError && !showRecurring && (
              <div
                className="fe-reveal fe-reveal--free flex flex-col items-center rounded-[1.5rem] border border-border-subtle bg-surface px-6 py-10 text-center"
                role="status"
                data-testid="calendar-empty"
              >
                <CalendarX2 className="mb-3 h-8 w-8 text-text-tertiary" aria-hidden="true" />
                <p className="mb-2 text-lg text-text-secondary">{t(`calendar.state.${emptyKind}.title`)}</p>
                <p className="text-sm text-text-tertiary">{t(`calendar.state.${emptyKind}.hint`)}</p>
                {!selectedDate && source && (
                  <button
                    type="button"
                    onClick={() => handleSourceChange('')}
                    className={cn(
                      FOCUS_RING_SURFACE,
                      'mt-4 inline-flex min-h-11 items-center rounded-xl border border-border-subtle px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:border-champagne/30 hover:text-text-primary',
                    )}
                  >
                    {t('calendar.state.resetFilter')}
                  </button>
                )}
              </div>
            )
          ) : (
            <div className="space-y-6">
              {grouped.map((group) => {
                const isPast = group.dateStr < todayStr;
                return (
                  <section key={group.dateStr}>
                    {!selectedDate && (
                      <h3 className={cn('fe-cal-dayhead', group.isToday && 'is-today')}>
                        {group.label}
                        <span className="fe-cal-dayhead__count">
                          — {group.events.length} {t(`z1.cal.events.${pluralForm(group.events.length, locale)}`)}
                        </span>
                      </h3>
                    )}
                    <DayEvents
                      events={group.events}
                      isPast={isPast}
                      isToday={group.isToday}
                      defaultOpen={Boolean(selectedDate)}
                    />
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
            onClick={() => track(events.DOWNLOAD_ICAL)}
            download
          >
            <Download className="w-4 h-4" />
            {t('calendar.exportIcal')}
          </a>
        </div>
      )}

      <section data-block="faq" className="mt-16">
        <h2 className="font-display text-xl font-bold text-text-primary mb-6">
          {t('calendar.faqHeading')}
        </h2>
        <dl className="space-y-4">
          {FAQ_KEYS.map((item) => (
            <div key={item.q} className="fe-panel rounded-[1.5rem] border border-border-subtle bg-surface p-5">
              <dt className="font-semibold text-text-primary text-sm mb-2">{t(item.q)}</dt>
              <dd className="text-sm text-text-secondary leading-relaxed">{t(item.a)}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
