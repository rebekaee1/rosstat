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

  it('главная: две карточки без заголовка «Инструменты»', () => {
    render(
      <MemoryRouter>
        <LocaleProvider locale="ru"><HomeTools /></LocaleProvider>
      </MemoryRouter>,
    );
    const links = screen.getAllByRole('link');
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/calculator', '/currencies']);
    expect(links[0].textContent).toContain('Сколько стоили бы ваши деньги');
    expect(screen.queryByText('Инструменты')).toBeNull();
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
