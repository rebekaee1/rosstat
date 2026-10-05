// Волна 6, G: плитки населения, выбор стран на странице показателя, плашка «в процентах», витрина калькуляторов, главная.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PopulationStats from './PopulationStats';
import CountryComparePanel, { ScaleNudge } from './CountryComparePicker';
import CalculatorShowcase from './CalculatorShowcase';
import HomeTools from './home/HomeTools';
import CalcBeforeAfter from './CalcBeforeAfter';
import { renderPage, mockApiGet } from '../test/renderPage';
import { LocaleProvider } from '../i18n';

afterEach(() => vi.restoreAllMocks());

function populationPoints() {
  const points = [];
  for (let year = 2014; year <= 2026; year += 1) {
    points.push({ date: `${year}-01-01`, value: 24_000_000 + (year - 2014) * 300_000 });
  }
  return points;
}

describe('PopulationStats', () => {
  it('«28,1 млн», «оценка на 2026», прирост с процентами, место среди стран, рост за 10 лет; без «,00» и «среднего»', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/compare/snapshot/population', {
        items: [
          { country_slug: 'china', value: 1_400_000_000 },
          { country_slug: 'india', value: 1_390_000_000 },
          { country_slug: 'australia', value: 27_600_000 },
          { country_slug: 'austria', value: 9_100_000 },
        ],
      }],
    ]);
    const { container } = renderPage(
      <PopulationStats points={populationPoints()} unit="человек" countrySlug="australia" />,
    );
    const tiles = [...container.querySelectorAll('.w2-stat')];
    expect(tiles[0].textContent).toContain('Население, оценка на 2026 год');
    expect(tiles[0].textContent).toContain('27,6\u00A0млн');
    expect(tiles[0].textContent).toContain('человек');
    expect(tiles[1].textContent).toContain('За год');
    expect(tiles[1].textContent).toContain('+300\u00A0тыс.');
    expect(tiles[1].textContent).toMatch(/\+1,1\s%/);
    await vi.waitFor(() => expect(container.querySelectorAll('.w2-stat').length).toBe(4));
    const rest = [...container.querySelectorAll('.w2-stat')].map((n) => n.textContent);
    expect(rest[2]).toContain('Место среди стран');
    expect(rest[2]).toContain('3-е');
    expect(rest[2]).toContain('из 4 стран на сайте');
    expect(rest[3]).toContain('За 10 лет');
    expect(rest[3]).toContain('с 2016 года');
    expect(container.textContent).not.toMatch(/,00|Исторический максимум|В среднем/);
  });

  it('значения в миллионах человек тоже читаются: единица ряда учитывается', () => {
    mockApiGet([['/auth/me', { user: null }]]);
    const points = [
      { date: '2024-01-01', value: 27.3 },
      { date: '2025-01-01', value: 27.6 },
    ];
    const { container } = renderPage(<PopulationStats points={points} unit="млн чел." countrySlug="x" />);
    expect(container.querySelector('.w2-stat').textContent).toContain('27,6\u00A0млн');
    expect(container.querySelector('.w2-stat').textContent).toContain('Население в 2025 году');
  });

  it('пока данных нет, рисует скелет той же сетки', () => {
    mockApiGet([['/auth/me', { user: null }]]);
    const { container } = renderPage(<PopulationStats points={[]} unit="человек" countrySlug="x" />);
    expect(container.querySelectorAll('.skeleton').length).toBe(4);
  });
});

describe('выбор стран на странице показателя', () => {
  const options = [
    { code: 'a', country_slug: 'albania', country_name: 'Албания' },
    { code: 'c', country_slug: 'china', country_name: 'Китай' },
    { code: 'r', country_slug: 'russia', country_name: 'Россия' },
    { code: 'g', country_slug: 'germany', country_name: 'Германия' },
    { code: 'u', country_slug: 'united-states', country_name: 'США' },
    { code: 'i', country_slug: 'india', country_name: 'Индия' },
    { code: 'b', country_slug: 'brazil', country_name: 'Бразилия' },
  ];

  function renderPanel(props = {}) {
    const onToggle = vi.fn();
    const utils = render(
      <MemoryRouter>
        <LocaleProvider locale="ru">
          <CountryComparePanel
            pickerOptions={options}
            activeComparisonIds={[]}
            selectedComparisons={[]}
            comparisonQueries={[]}
            comparisonScale="values"
            onToggle={onToggle}
            onOpen={() => {}}
            onScale={() => {}}
            conceptSlug="population"
            countrySlug="australia"
            compareCodes={[]}
            rebased={null}
            loadedComparisonSeries={[]}
            {...props}
          />
        </LocaleProvider>
      </MemoryRouter>,
    );
    return { ...utils, onToggle };
  }

  it('порядок: Россия, США, Китай, Германия, Индия, потом по алфавиту; панель непрозрачная', () => {
    renderPanel();
    // Поиск других стран открывается по кнопке «Другие страны» (чипы «Сравнить с» стоят выше).
    fireEvent.click(screen.getByRole('button', { name: 'Другие страны' }));
    fireEvent.focus(screen.getByRole('searchbox'));
    const panel = document.querySelector('.fe-w6g-solid-panel');
    expect(panel).toBeTruthy();
    expect(panel.className).toContain('fe-dialog-panel');
    const names = [...panel.querySelectorAll('button')].map((b) => b.textContent.replace(/[\u{1F1E6}-\u{1F1FF}]/gu, '').trim());
    expect(names).toEqual(['Россия', 'США', 'Китай', 'Германия', 'Индия', 'Албания', 'Бразилия']);
  });

  it('после выбора список закрывается, поле теряет фокус и страница подкручивается к графику', async () => {
    const scrollIntoView = vi.fn();
    const chart = document.createElement('section');
    chart.id = 'chart';
    chart.scrollIntoView = scrollIntoView;
    chart.getBoundingClientRect = () => ({ top: -400 });
    document.body.appendChild(chart);
    try {
      const { onToggle } = renderPanel();
      fireEvent.click(screen.getByRole('button', { name: 'Другие страны' }));
      const input = screen.getByRole('searchbox');
      input.focus();
      fireEvent.focus(input);
      fireEvent.click(within(document.querySelector('.fe-w6g-solid-panel')).getByRole('button', { name: /Германия/ }));
      expect(onToggle).toHaveBeenCalledWith('g');
      expect(document.querySelector('.fe-w6g-solid-panel')).toBeNull();
      expect(document.activeElement).not.toBe(input);
      await vi.waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
    } finally {
      chart.remove();
    }
  });

  it('страны разного размера: плашка «Показать в процентах» включает проценты', () => {
    const onScale = vi.fn();
    render(
      <LocaleProvider locale="ru"><ScaleNudge show onScale={onScale} /></LocaleProvider>,
    );
    const nudge = screen.getByTestId('compare-scale-nudge');
    expect(nudge.textContent).toMatch(/меньшая линия кажется ровной/);
    fireEvent.click(within(nudge).getByRole('button', { name: 'Показать в процентах' }));
    expect(onScale).toHaveBeenCalledWith('index');
  });

  it('плашки нет, когда масштабы близки или уже включены проценты', () => {
    render(<LocaleProvider locale="ru"><ScaleNudge show={false} onScale={() => {}} /></LocaleProvider>);
    expect(screen.queryByTestId('compare-scale-nudge')).toBeNull();
  });
});

describe('витрина калькуляторов, главная, было/стало', () => {
  it('витрина: три карточки с пометкой «для каких стран», текущая отмечена', () => {
    render(
      <MemoryRouter>
        <LocaleProvider locale="ru"><CalculatorShowcase current="mortgage" /></LocaleProvider>
      </MemoryRouter>,
    );
    const links = screen.getAllByRole('link');
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/calculator', '/calculator/mortgage', '/calculator/compound']);
    expect(links[1].getAttribute('aria-current')).toBe('page');
    expect(links[0].getAttribute('aria-current')).toBeNull();
    expect(links[1].textContent).toContain('Для рублёвой ипотеки в России');
  });

  it('главная: «Попробуйте сами», три живых мини-инструмента со ссылками на большие страницы', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      ['/world/countries', { countries: [], total: 0 }],
      [/^\/world\/compare\/snapshot\//, { items: [] }],
    ]);
    renderPage(<HomeTools />, { path: '/', route: '/' });
    expect(screen.getByRole('heading', { name: 'Попробуйте сами' })).toBeTruthy();
    expect(screen.queryByText('Инструменты')).toBeNull();
    const more = [...document.querySelectorAll('.fe-tool__more')].map((a) => a.getAttribute('href'));
    expect(more).toEqual(['/currencies', '/calculator', '/compare']);
    expect(screen.getByRole('heading', { name: 'Конвертер валют' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Что будет с деньгами' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Сравните две страны' })).toBeTruthy();
  });

  it('главная: конвертер считает сумму по курсам списка показателей, меняет валюты местами и просит цифры', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, [
        { code: 'usd-rub', name: 'USD/RUB', unit: '₽', current_value: 80, current_date: '2026-10-03', is_active: true },
        { code: 'eur-rub', name: 'EUR/RUB', unit: '₽', current_value: 90, current_date: '2026-10-03', is_active: true },
      ]],
      ['/world/countries', { countries: [], total: 0 }],
      [/^\/world\/compare\/snapshot\//, { items: [] }],
    ]);
    renderPage(<HomeTools />, { path: '/', route: '/' });
    const amount = screen.getByLabelText('Сумма');
    // 100 $ по 80 ₽: 8 000 ₽, под числом дата курса.
    expect(await screen.findByText(/8\s000/)).toBeTruthy();
    expect(screen.getByText(/Пересчёт по официальным курсам на 3 октября/)).toBeTruthy();
    fireEvent.change(amount, { target: { value: '250,5' } });
    expect(await screen.findByText(/20\s040/)).toBeTruthy();
    fireEvent.change(amount, { target: { value: 'abc' } });
    expect(screen.getByText('Введите сумму цифрами')).toBeTruthy();
    expect(amount.getAttribute('aria-invalid')).toBe('true');
    // Кнопка «Поменять валюты местами»: из рубля в доллар.
    fireEvent.change(amount, { target: { value: '8000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Поменять валюты местами' }));
    expect((screen.getByLabelText('Из')).value).toBe('RUB');
    expect(await screen.findByText(/^100/)).toBeTruthy();
  });

  it('главная: инфляция «на пальцах» берёт ставку России из среза и пересчитывает при движении ползунка', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      ['/world/countries', { countries: [], total: 0 }],
      ['/world/compare/snapshot/hicp-index', { items: [{ country_code: 'RU', country_slug: 'russia', value: 8, unit: '%' }] }],
      [/^\/world\/compare\/snapshot\//, { items: [] }],
    ]);
    renderPage(<HomeTools />, { path: '/', route: '/' });
    // 100 000 ₽ через 10 лет при 8 % в год: 100000 / 1,08^10 = 46 319.
    expect(await screen.findByText(/46\s319/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Через сколько лет/), { target: { value: '1' } });
    // Через 1 год: 92 593, и «1 год» в единственном числе.
    expect(await screen.findByText(/92\s593/)).toBeTruthy();
    expect(screen.getAllByText(/1 год(?!а)/).length).toBeGreaterThan(0);
  });

  it('главная: сравнение ведёт на готовый график выбранных стран и показателя', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      ['/world/countries', { countries: [
        { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
        { code: 'CN', slug: 'china', name: 'Китай', name_en: 'China' },
        { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' },
      ], total: 3 }],
      [/^\/world\/compare\/snapshot\//, { items: [] }],
    ]);
    renderPage(<HomeTools />, { path: '/', route: '/' });
    const go = await screen.findByRole('link', { name: 'Показать график' });
    expect(decodeURIComponent(go.getAttribute('href'))).toBe('/compare?codes=w:united-states:gdp-usd,w:china:gdp-usd');
    fireEvent.change(screen.getByLabelText('Вторая страна'), { target: { value: 'germany' } });
    fireEvent.click(screen.getByRole('button', { name: 'Цены' }));
    const href = decodeURIComponent(screen.getByRole('link', { name: 'Показать график' }).getAttribute('href'));
    expect(href).toContain('codes=w:united-states:hicp-index,w:germany:hicp-index');
    expect(href).toContain('rep=w:united-states:hicp-index:yoy,w:germany:hicp-index:yoy');
  });

  it('было / стало: высота столбика пропорциональна сумме, меньший не пропадает', () => {
    const { container } = render(
      <CalcBeforeAfter
        ariaLabel="Две суммы"
        before={{ label: '2016', value: 100000, text: '100 000 ₽' }}
        after={{ label: '2026', value: 192104, text: '192 104 ₽' }}
      />,
    );
    const bars = [...container.querySelectorAll('.fe-w6g-ba__bar')].map((b) => b.style.height);
    expect(bars).toEqual(['52%', '100%']);
    expect(screen.getByRole('img', { name: 'Две суммы' })).toBeTruthy();
    expect(container.textContent).toContain('192 104 ₽');
  });
});
