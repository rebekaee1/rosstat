// Круг 9, зона E: Россия, регионы, календарь.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import CalendarUpcoming from '../components/calendar/CalendarUpcoming';
import CalendarEventCard from '../components/calendar/CalendarEventCard';
import RegionComparePick from '../components/regions/RegionComparePick';
import { TrendTick } from '../components/regions/RegionParts';
import { renderPage, mockApiGet } from '../test/renderPage';
import * as ics from '../lib/calendarIcs';

afterEach(() => vi.restoreAllMocks());

function cpi(code, name, uid) {
  return {
    id: uid, title: 'Индекс потребительских цен', importance: 3, source: 'rosstat',
    scheduled_date: '2026-10-09', scheduled_time: '19:00', source_event_uid: `rosstat-${uid}-2026-10-09`,
    indicator_code: code, indicator_name: name,
  };
}

describe('календарь: ближайшие события', () => {
  it('ИПЦ и его составляющие с одним названием склеены в одну строку', () => {
    const events = [
      cpi('cpi', 'ИПЦ', 'cpi'),
      cpi('cpi-food', 'ИПЦ на продукты', 'cpi-food'),
      cpi('cpi-services', 'ИПЦ на услуги', 'cpi-services'),
      { ...cpi('key-rate', 'Ключевая ставка', 'kr'), title: 'Решение по ставке', scheduled_date: '2026-10-23' },
    ];
    renderPage(<CalendarUpcoming events={events} />);
    const items = screen.getAllByRole('button');
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain('Индекс потребительских цен');
    expect(items[0].textContent).toContain('ещё 2');
  });
});

describe('календарь: карточка события', () => {
  it('«В календарь телефона» собирает .ics с московским временем', () => {
    const spy = vi.spyOn(ics, 'downloadIcs').mockReturnValue(true);
    const future = { ...cpi('cpi', 'ИПЦ', 'cpi'), scheduled_date: '2099-10-09', source_url: 'https://rosstat.gov.ru' };
    renderPage(<CalendarEventCard event={future} isPast={false} isToday={false} />);
    fireEvent.click(screen.getByTestId('calendar-add-ics'));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0]).toContain('DTSTART:20991009T160000Z');
  });

  it('у прошедшего события кнопки нет', () => {
    renderPage(<CalendarEventCard event={cpi('cpi', 'ИПЦ', 'cpi')} isPast isToday={false} />);
    expect(screen.queryByTestId('calendar-add-ics')).toBeNull();
  });
});

describe('страница региона: сравнить с другим регионом', () => {
  it('список без самого региона, выбор ведёт на готовое сравнение', async () => {
    mockApiGet([[/^\/regions$/, {
      districts: [{ slug: 'cfo', name: 'Центральный', regions: [
        { slug: 'moskva', name: 'г. Москва' }, { slug: 'tula', name: 'Тульская область' },
      ] }],
    }]]);
    renderPage(<RegionComparePick slug="moskva" />, { path: '/', route: '/' });
    const select = await screen.findByRole('combobox');
    const names = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(names).toEqual(['Сравнить с другим регионом', 'Тульская область']);
  });
});

describe('указатель направления', () => {
  it('рисует стрелку (линия и наконечник), а не график из двух точек', () => {
    const { container } = renderPage(<TrendTick value={10} prevValue={5} polarity="up-good" />);
    const svg = container.querySelector('.fe-trend-tick');
    expect(svg.querySelector('line')).toBeTruthy();
    expect(svg.querySelector('path')).toBeTruthy();
    expect(svg.querySelector('circle')).toBeNull();
  });
});
