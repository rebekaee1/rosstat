// Волна 6, зона F: 404, календарь, рейтинг и карта регионов, страница региона, штаты США.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import NotFound from './NotFound';
import CalendarPage from './CalendarPage';
import RegionsHome from './RegionsHome';
import RegionProfile from './RegionProfile';
import RegionsMap from '../components/RegionsMap';
import RegionAnnualChart from '../components/RegionAnnualChart';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/MapTimeline', () => ({ default: () => null }));
vi.mock('../components/RegionsMap', async () => {
  const real = await vi.importActual('../components/RegionsMap');
  return real;
});

afterEach(() => vi.restoreAllMocks());

describe('404: подсказка и возврат', () => {
  it('по адресу /ranking/gdp предлагает «Рейтинг стран по ВВП», есть «Вернуться назад» и чипы с валютами', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/indicators/, []]]);
    renderPage(<NotFound />, { path: '*', route: '/ranking/gdp' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Такой страницы нет' })).toBeTruthy();
    const guess = document.querySelector('[data-nf-guess]');
    expect(guess).toBeTruthy();
    expect(within(guess).getByRole('link', { name: 'Рейтинг стран по ВВП' }).getAttribute('href')).toBe('/world/rating/gdp-usd');
    expect(screen.getByRole('button', { name: 'Вернуться назад' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Валюты' }).getAttribute('href')).toBe('/currencies');
    // Раунд 3 (K2): золотая «404» из толстого стекла, нуль заменён хрустальным глобусом; цифры декоративны (скрыты от скринридера),
    // само сообщение об ошибке даёт заголовок и подпись «Ошибка 404».
    expect(document.querySelector('.z2-nf-code .fe-nf-globe img')).toBeTruthy();
    expect(document.querySelector('.z2-nf-code').getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByText('Ошибка 404')).toBeTruthy();
  });

  it('у адреса без знакомых слов подсказки нет', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/indicators/, []]]);
    renderPage(<NotFound />, { path: '*', route: '/zzz' });
    await screen.findByRole('heading', { level: 1, name: 'Такой страницы нет' });
    expect(document.querySelector('[data-nf-guess]')).toBeNull();
  });
});

function ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

describe('календарь России', () => {
  function monthEvents() {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth();
    const days = new Date(y, m + 1, 0).getDate();
    const events = [];
    // Курс доллара — каждый день месяца (ежедневная публикация).
    for (let d = 1; d <= days; d += 1) {
      events.push({
        id: 1000 + d, title: 'Официальный курс доллара', importance: 1, source: 'cbr',
        scheduled_date: ymd(new Date(y, m, d)), scheduled_time: '12:00', source_event_uid: `cbr-usd-${d}`,
      });
    }
    // Одно разовое важное событие сегодня.
    events.push({
      id: 7, title: 'Индекс потребительских цен (ИПЦ)', importance: 3, source: 'rosstat',
      scheduled_date: ymd(now), scheduled_time: '19:00', source_event_uid: `rosstat-cpi-${ymd(now)}`,
      description: 'ИПЦ показывает, как меняются цены. Публикуется раз в месяц.', indicator_code: 'cpi',
      previous_value: '6,0', forecast_value: '6,2',
    });
    return { events, total: events.length, today: ymd(now) };
  }

  function mount() {
    const data = monthEvents();
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/calendar\?/, { events: data.events, total: data.total }],
      [/^\/calendar\/upcoming/, { events: [{ ...data.events[data.events.length - 1] }] }],
    ]);
    return renderPage(<CalendarPage />, { path: '/russia/calendar', route: '/russia/calendar' });
  }

  it('ежедневный курс не рисует точки в клетках, а день с настоящим событием открыт по умолчанию', async () => {
    const { container } = mount();
    const todayCell = await waitFor(() => {
      const cell = container.querySelector('.fe-cal-day[aria-pressed="true"]');
      expect(cell).toBeTruthy();
      return cell;
    });
    // Число дня стоит в первом элементе клетки (дальше точки и число событий).
    expect(Number(todayCell.firstElementChild.textContent)).toBe(new Date().getDate());
    // Волна 7: на телефоне в клетке точки и число событий (названия видны только от планшета).
    expect(todayCell.querySelector('.fe-cal-day__n').textContent).toBe('1');
    // Клетки без разовых событий не «событийные»: у них нет оттенка и нет точек.
    const heated = container.querySelectorAll('.fe-cal-day[data-heat]');
    expect(heated.length).toBe(1);
    // Карточка дня: одна фраза «что это» без жаргона и подпись «Ожидание».
    expect(await screen.findByText(/Инфляция показывает, как меняются цены\./)).toBeTruthy();
    expect(screen.getByText('Ожидание')).toBeTruthy();
    expect(screen.getAllByText('по Москве').length).toBeGreaterThan(0);
    // Ежедневные курсы собраны одной строкой, когда выбран весь месяц.
    fireEvent.click(screen.getByRole('button', { name: 'Показать весь месяц' }));
    expect(await screen.findByTestId('calendar-recurring')).toBeTruthy();
    expect(screen.getByText('Каждый день')).toBeTruthy();
  });

  it('есть фильтр «Только важные» и кнопка «Добавить в календарь телефона»', async () => {
    mount();
    const toggle = await screen.findByTestId('calendar-only-important');
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(toggle);
    expect(screen.getByTestId('calendar-only-important').getAttribute('aria-pressed')).toBe('true');
    expect(await screen.findByRole('link', { name: /Добавить в календарь телефона/ })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/iCal/);
  });

  it('рядом с сеткой блок «Ближайшие события» (планшет и компьютер)', async () => {
    mount();
    const upcoming = await screen.findByTestId('calendar-upcoming');
    expect(upcoming.textContent).toContain('Индекс потребительских цен');
  });
});

describe('карта регионов: выбор региона, место и сравнение', () => {
  const values = new Map([['moskva', 300], ['sankt-peterburg', 200], ['respublika-tatarstan', 100]]);
  const names = { moskva: 'Москва', 'sankt-peterburg': 'Санкт-Петербург', 'respublika-tatarstan': 'Татарстан' };

  it('выбранный снаружи регион показывает карточку с местом и позволяет собрать сравнение', async () => {
    const { rerender } = renderPage(
      <RegionsMap valuesBySlug={values} nameBySlug={names} unit="₽" pickedSlug="moskva" onPickedChange={() => {}} />,
    );
    const card = await screen.findByRole('status');
    expect(within(card).getByText('Москва')).toBeTruthy();
    expect(within(card).getByTestId('map-pick-rank').textContent).toBe('1-е место из 3');
    expect(within(card).getByRole('button', { name: 'В сравнение' })).toBeTruthy();
    expect(rerender).toBeTruthy();
  });

  it('режим «Пузыри» рисует по кружку на регион', () => {
    const { container } = renderPage(<RegionsMap valuesBySlug={values} nameBySlug={names} unit="₽" shape="bubbles" />);
    expect(container.querySelectorAll('circle[data-bubble="true"]').length).toBeGreaterThan(80);
    expect(container.querySelectorAll('path[data-region-slug]').length).toBe(0);
  });

  it('маркеры городов имеют широкую область нажатия', () => {
    const { container } = renderPage(<RegionsMap valuesBySlug={values} nameBySlug={names} unit="₽" />);
    const marker = container.querySelector('g[data-region-slug="moskva"]');
    expect(marker).toBeTruthy();
    expect(marker.querySelectorAll('circle').length).toBe(2);
  });
});

describe('«Регионы России»: рейтинг вместо алфавитного списка', () => {
  const landing = {
    totals: { points: 3, indicators: 2, regions: 3 },
    districts: [{ slug: 'cfo', name: 'Центральный округ', regions: [
      { slug: 'moskva', name: 'Москва', stats: {} },
      { slug: 'tulskaya-oblast', name: 'Тульская область', stats: {} },
      { slug: 'ryazanskaya-oblast', name: 'Рязанская область', stats: {} },
    ] }],
  };
  const heat = (name, unit) => ({
    year: 2024, default_sort: 'desc', rank_as_achievement: true,
    indicator: { code: 'x', name, unit },
    values: [
      { slug: 'ryazanskaya-oblast', name: 'Рязанская область', value: 60000, raw: 60000 },
      { slug: 'moskva', name: 'Москва', value: 150000, raw: 150000 },
      { slug: 'tulskaya-oblast', name: 'Тульская область', value: 70000, raw: 70000 },
    ],
  });
  const catalog = { sections: [{ name: 'Труд', indicators: [
    { code: 'a', name: 'Зарплата', unit: '₽' }, { code: 'b', name: 'Занятость', unit: '%' },
  ] }] };

  function mount() {
    return mockApiGet([
      ['/auth/me', { user: null }], ['/regions', landing], ['/regions/catalog', catalog],
      [/^\/regions\/heatmap\//, (url) => heat(url.includes('zarabotnaya') ? 'Среднемесячная зарплата' : 'Показатель', '₽')],
    ]);
  }

  it('по умолчанию виден рейтинг: выбранный показатель, места, полосы и кубок только у тройки', async () => {
    mount();
    renderPage(<RegionsHome />, { path: '/russia/region', route: '/russia/region' });
    const ranking = await screen.findByTestId('region-ranking');
    const rows = await waitFor(() => {
      const found = ranking.querySelectorAll('.fe-rank__row');
      expect(found.length).toBe(3);
      return found;
    });
    // Сначала самое высокое значение, с номером места.
    expect(rows[0].textContent).toContain('Москва');
    expect(rows[0].querySelector('.fe-rank__place').textContent).toBe('1');
    expect(rows[0].querySelector('.fe-rank__bar')).toBeTruthy();
    // Выбранный показатель заметен: нажатая кнопка-чип.
    const chips = within(ranking).getAllByRole('button', { pressed: true });
    expect(chips.length).toBeGreaterThanOrEqual(1);
    expect(within(ranking).getByRole('button', { name: /Сколько производит один житель \(ВРП\)/ })).toBeTruthy();
    expect(within(ranking).queryByText('Экономика на человека')).toBeNull();
    // Гранёная медаль у троих лидеров (R3 K6: вместо кубка; здесь регионов всего три, у всех место ≤ 3).
    const medals = [...ranking.querySelectorAll('.fe-rank__place [data-medal]')];
    expect(medals.map((medal) => medal.getAttribute('data-medal'))).toEqual(['1', '2', '3']);
    expect(medals.every((medal) => medal.getAttribute('title') === 'Тройка лидеров')).toBe(true);
  });

  it('«Ещё показатели» открывает поиск по всему каталогу и переключает рейтинг', async () => {
    const get = mount();
    renderPage(<RegionsHome />, { path: '/russia/region', route: '/russia/region' });
    const more = await screen.findByTestId('ranking-more');
    await waitFor(() => expect(screen.getByTestId('ranking-more').textContent).toContain('Ещё показатели: 2'));
    fireEvent.click(more);
    const input = await screen.findByRole('searchbox', { name: /Поиск рейтинга/ }).catch(() => null)
      || screen.getByLabelText('Поиск рейтинга по показателю');
    fireEvent.change(input, { target: { value: 'Занятость' } });
    fireEvent.click(await screen.findByRole('button', { name: /Занятость/ }));
    await waitFor(() => expect(get.mock.calls.some(([url]) => url === '/regions/heatmap/b')).toBe(true));
  });
});

describe('страница региона: подпись данных и подсказки', () => {
  const profile = {
    region: { slug: 'tulskaya-oblast', name: 'Тульская область', district_name: 'Центральный округ' },
    headline: {
      '1.1': { code: '1.1', name: 'Население', value: 1500000, unit: 'чел.', year: 2023, prev_value: 1510000 },
      '3.4': { code: '3.4', name: 'Зарплата', value: 60000, unit: '₽', year: 2024, prev_value: 55000 },
    },
    sections: [{ num: 1, name: 'Население', indicators: [
      { code: 'dep', name: 'Коэффициент демографической нагрузки', unit: '', value: 274, prev_value: 270, year: 2023 },
    ] }],
  };

  it('одна подпись «последние данные», кнопка «Сравнить с Россией», подсказка к сложному названию и указатель тренда', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/regions\/region\//, profile], [/^\/regions\/tulskaya/, profile]]);
    renderPage(<RegionProfile />, { path: '/russia/region/:slug', route: '/russia/region/tulskaya-oblast' });
    expect(await screen.findByTestId('region-latest-note')).toBeTruthy();
    expect(screen.getByTestId('region-latest-note').textContent).toMatch(/Последние данные/);
    const cmp = screen.getByTestId('region-compare-russia');
    expect(cmp.textContent).toContain('Сравнить с Россией');
    expect(cmp.getAttribute('href')).toBe('/russia/region/tulskaya-oblast/3.4');
    expect((await screen.findByTestId('row-explain')).textContent).toMatch(/тысячу человек трудоспособного возраста/);
    expect(document.querySelector('.fe-trend-tick')).toBeTruthy();
  });
});

describe('график региона: «Россия = 100» вместо двух разных осей', () => {
  const series = [2021, 2022, 2023].map((year, i) => ({ year, value: 30 + i * 5 }));
  const russia = [2021, 2022, 2023].map((year, i) => ({ year, value: 8 + i }));

  it('при несопоставимых масштабах обе линии на одной оси, легенда объясняет индекс', () => {
    renderPage(
      <RegionAnnualChart series={series} russiaSeries={russia} regionName="Республика Ингушетия" unit="%" />,
    );
    expect(screen.getByTestId('index-note').textContent).toMatch(/Республика Ингушетия показан в процентах от российского значения/);
    expect(document.body.textContent).toContain('Россия = 100');
    expect(document.body.textContent).not.toMatch(/левая ось|правая ось/);
  });

  it('при сопоставимых масштабах индекса нет', () => {
    renderPage(
      <RegionAnnualChart series={series} russiaSeries={series.map((p) => ({ ...p, value: p.value + 1 }))} regionName="Регион" unit="%" />,
    );
    expect(screen.queryByTestId('index-note')).toBeNull();
  });
});
