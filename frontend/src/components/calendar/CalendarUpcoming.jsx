import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';
import { useLocale, useT } from '../../i18n';
import { plainEventTitle } from '../../lib/calendarText';

const SOURCE_DOT = {
  cbr: 'bg-blue-500',
  rosstat: 'bg-emerald-500',
  minfin: 'bg-amber-500',
};

/**
 * Ближайшие события рядом с сеткой месяца (планшет и компьютер): дата, название, время «по Москве».
 * Нажатие открывает этот день в календаре. На телефоне блок скрыт: там тот же день виден в списке под сеткой.
 */
export default function CalendarUpcoming({ events = [], onPick, limit = 3 }) {
  const t = useT();
  const { locale } = useLocale();
  const items = events.slice(0, limit);
  if (items.length === 0) return null;
  return (
    <section className="fe-cal-upcoming hidden md:block" aria-label={t('w6f.cal.upcoming')} data-testid="calendar-upcoming">
      <h2 className="fe-cal-upcoming__title">{t('w6f.cal.upcoming')}</h2>
      <ul className="fe-cal-upcoming__list">
        {items.map((ev) => {
          const d = new Date(`${ev.scheduled_date}T12:00:00`);
          const dayLabel = `${d.getDate()} ${t(`calendar.monthGen.${d.getMonth()}`)}`;
          return (
            <li key={ev.id ?? `${ev.scheduled_date}-${ev.title}`}>
              <button
                type="button"
                onClick={() => onPick?.(ev.scheduled_date)}
                className={cn(FOCUS_RING_SURFACE, 'fe-cal-upcoming__item fe-press')}
              >
                <span className={cn('fe-cal-upcoming__dot', SOURCE_DOT[ev.source] || 'bg-text-tertiary')} aria-hidden="true" />
                <span className="fe-cal-upcoming__main">
                  <span className="fe-cal-upcoming__name">{plainEventTitle(ev.title, locale)}</span>
                  <span className="fe-cal-upcoming__when">
                    {dayLabel}
                    {ev.scheduled_time ? `, ${ev.scheduled_time} ${t('calendar.hero.msk')}` : ''}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
