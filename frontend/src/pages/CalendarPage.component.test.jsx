import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import CalendarPage from './CalendarPage';
import { renderPage, mockApiGet } from '../test/renderPage';
import api from '../lib/api';

afterEach(() => vi.restoreAllMocks());

function render(locale, route = '/calendar/2031/05') {
  return renderPage(<CalendarPage fixedYear={2031} fixedMonth={4} seoPath="/calendar/2031/05" />, {
    path: '/calendar/:year/:month',
    route,
    locale,
  });
}

describe('CalendarPage: видимые состояния', () => {
  it('пустой месяц: заголовок и подсказка, не пустой экран (ru)', async () => {
    mockApiGet([
      [/^\/calendar\?/, { events: [], total: 0 }],
      [/^\/calendar\/upcoming/, { events: [] }],
    ]);
    render('ru');
    expect(await screen.findByText('Нет событий в этом месяце')).toBeTruthy();
    expect(screen.getByText('Попробуйте другой месяц или сбросьте фильтр источника')).toBeTruthy();
    expect(screen.getByTestId('calendar-empty').getAttribute('role')).toBe('status');
  });

  it('пустой месяц на английском', async () => {
    mockApiGet([
      [/^\/calendar\?/, { events: [], total: 0 }],
      [/^\/calendar\/upcoming/, { events: [] }],
    ]);
    render('en');
    expect(await screen.findByText('No events this month')).toBeTruthy();
  });

  it('ошибка загрузки: баннер с повтором, без ложного «нет событий» (ru и en)', async () => {
    for (const [locale, title] of [['ru', 'Не получилось загрузить календарь.'], ['en', 'Could not load the calendar.']]) {
      vi.restoreAllMocks();
      vi.spyOn(api, 'get').mockImplementation((url) => {
        const err = new Error(`fail ${url}`);
        err.response = { status: 500 };
        return Promise.reject(err);
      });
      const { unmount } = render(locale);
      await waitFor(() => expect(screen.getByRole('alert').textContent).toContain(title));
      expect(screen.queryByTestId('calendar-empty')).toBeNull();
      // Волна 6: при ошибке без данных сетку календаря не рисуем (раньше «недоступен» стоял над готовой сеткой).
      expect(screen.queryByTestId('calendar-grid')).toBeNull();
      unmount();
    }
  });

  it('ежедневные курсы (низкая важность) сворачиваются в одну строку, важное остаётся на виду', async () => {
    const day = '2031-05-14';
    const rate = (id, title) => ({
      id, title, importance: 1, source: 'cbr', scheduled_date: day, scheduled_time: '12:00',
      source_event_uid: `cbr-rate-${id}-${day}`, indicator_code: `rate-${id}`,
    });
    mockApiGet([
      [/^\/calendar\?/, {
        total: 5,
        events: [
          { id: 100, title: 'Индекс потребительских цен (ИПЦ)', importance: 3, source: 'rosstat', scheduled_date: day, scheduled_time: '19:00', source_event_uid: `rosstat-cpi-${day}`, indicator_code: 'cpi' },
          rate(1, 'Официальный курс евро'), rate(2, 'Официальный курс доллара'), rate(3, 'Официальный курс юаня'), rate(4, 'Учётная цена на золото'),
        ],
      }],
      [/^\/calendar\/upcoming/, { events: [] }],
    ]);
    render('ru');
    expect(await screen.findByText('Индекс потребительских цен')).toBeTruthy();
    const summary = screen.getByText('Ежедневные курсы и ставки: 4');
    expect(summary.closest('details').hasAttribute('open')).toBe(false);
  });
  it('лендинг прошедшего месяца показывает все события месяца, а не только будущие', async () => {
    mockApiGet([
      [/^\/calendar\?/, {
        total: 1,
        events: [
          { id: 7, title: 'Индекс потребительских цен (ИПЦ)', importance: 3, source: 'rosstat', scheduled_date: '2020-04-10', scheduled_time: '19:00', source_event_uid: 'rosstat-cpi-2020-04-10', indicator_code: 'cpi' },
        ],
      }],
      [/^\/calendar\/upcoming/, { events: [] }],
    ]);
    renderPage(<CalendarPage fixedYear={2020} fixedMonth={3} seoPath="/calendar/2020/04" />, {
      path: '/calendar/:year/:month', route: '/calendar/2020/04', locale: 'ru',
    });
    expect(await screen.findByText('Индекс потребительских цен')).toBeTruthy();
    expect(screen.queryByTestId('calendar-empty')).toBeNull();
  });
});

// Пульс 363 (19.11.2026): на каждый новый месяц сетка с кнопками пропадала под заглушкой, нажатия
// попадали в заглушку. Теперь прежний месяц стоит до ответа, соседние месяцы предзагружаются.
describe('CalendarPage: переключение месяца без заглушки', () => {
  const ev = (id, title, date) => ({
    id, title, importance: 3, source: 'rosstat', scheduled_date: date, scheduled_time: '19:00',
    source_event_uid: `rosstat-${id}-${date}`, indicator_code: `code-${id}`,
  });

  /** Ответы `/calendar?from=…` держатся, пока тест не отпустит месяц: `release('2031-04-01', data)`. */
  function mockMonths(ready) {
    const waiting = new Map();
    const spy = vi.spyOn(api, 'get').mockImplementation((url) => {
      if (url.startsWith('/calendar/upcoming')) return Promise.resolve({ data: { events: [] } });
      const from = new URLSearchParams(url.split('?')[1]).get('from');
      if (ready[from]) return Promise.resolve({ data: ready[from] });
      return new Promise((resolve) => { waiting.set(from, resolve); });
    });
    const release = (from, data) => waiting.get(from)?.({ data });
    return { spy, waiting, release };
  }

  const renderLive = () => renderPage(<CalendarPage />, { path: '/calendar', route: '/calendar?y=2031&m=4', locale: 'ru' });
  const may = { '2031-05-01': { events: [ev(1, 'Майский выпуск', '2031-05-14')], total: 1 } };

  it('после загрузки месяца запрашивает соседние месяцы заранее', async () => {
    const { spy } = mockMonths(may);
    renderLive();
    expect((await screen.findAllByText('Майский выпуск')).length).toBeGreaterThan(0);
    await waitFor(() => {
      const froms = spy.mock.calls.map(([u]) => new URLSearchParams(u.split('?')[1] || '').get('from'));
      expect(froms).toContain('2031-04-01');
      expect(froms).toContain('2031-06-01');
    });
  });

  it('пока грузится новый месяц, сетка и кнопки на месте, прежний список тускнеет; затем приходит новый', async () => {
    const { release, waiting } = mockMonths(may);
    renderLive();
    expect((await screen.findAllByText('Майский выпуск')).length).toBeGreaterThan(0);
    await waitFor(() => expect(waiting.has('2031-04-01')).toBe(true));

    fireEvent.click(screen.getByRole('button', { name: 'Предыдущий месяц' }));

    const grid = screen.getByTestId('calendar-grid');
    expect(grid.textContent).toContain('Апрель 2031');
    expect(grid.getAttribute('aria-busy')).toBe('true');
    expect(screen.getByTestId('calendar-list').className).toContain('is-pending');
    expect(screen.queryByTestId('calendar-empty')).toBeNull();
    expect(screen.getByRole('button', { name: 'Предыдущий месяц' })).toBeTruthy();

    release('2031-04-01', { events: [ev(2, 'Апрельский выпуск', '2031-04-10')], total: 1 });
    expect((await screen.findAllByText('Апрельский выпуск')).length).toBeGreaterThan(0);
    expect(screen.queryAllByText('Майский выпуск')).toHaveLength(0);
    expect(screen.getByTestId('calendar-grid').getAttribute('aria-busy')).toBeNull();
  });

  it('быстрые нажатия: поздний ответ прошлого месяца не подменяет открытый', async () => {
    const { release, waiting } = mockMonths(may);
    renderLive();
    expect((await screen.findAllByText('Майский выпуск')).length).toBeGreaterThan(0);
    await waitFor(() => expect(waiting.has('2031-04-01')).toBe(true));

    const prev = () => fireEvent.click(screen.getByRole('button', { name: 'Предыдущий месяц' }));
    prev();
    prev();
    expect(screen.getByTestId('calendar-grid').textContent).toContain('Март 2031');
    await waitFor(() => expect(waiting.has('2031-03-01')).toBe(true));

    release('2031-03-01', { events: [ev(3, 'Мартовский выпуск', '2031-03-12')], total: 1 });
    expect((await screen.findAllByText('Мартовский выпуск')).length).toBeGreaterThan(0);
    release('2031-04-01', { events: [ev(2, 'Апрельский выпуск', '2031-04-10')], total: 1 });
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryAllByText('Апрельский выпуск')).toHaveLength(0);
    expect(screen.getAllByText('Мартовский выпуск').length).toBeGreaterThan(0);
  });
});
