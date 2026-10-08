/** @vitest-environment jsdom */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import { CountryComparePicker } from './CountryComparePicker';
import CountryComparePanel from './CountryComparePicker';
import IndicatorChartSection from './IndicatorChartSection';
import { renderPage } from '../test/renderPage';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: {
    SEARCH_QUERY: 'search_query',
    CHART_IMAGE_BLOCKED: 'chart_image_blocked',
    CHART_IMAGE_DOWNLOAD: 'chart_image_download',
    METHODOLOGY_CLICK: 'methodology_click',
    FORECAST_TOGGLE: 'forecast_toggle',
  },
}));

function renderPicker(ui) {
  return render(
    <LocaleProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </LocaleProvider>,
  );
}

const OPTIONS = [
  { code: 'peer:germany:de-hicp', country_name: 'Германия', country_slug: 'germany' },
  { code: 'peer:france:fr-hicp', country_name: 'Франция', country_slug: 'france' },
  { code: 'peer:austria:at-hicp', country_name: 'Австрия', country_slug: 'austria' },
  { code: 'peer:italy:it-hicp', country_name: 'Италия', country_slug: 'italy' },
  { code: 'peer:spain:es-hicp', country_name: 'Испания', country_slug: 'spain' },
];

describe('CountryComparePicker', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('lists countries and toggles a peer', () => {
    const onToggle = vi.fn();
    renderPicker(
      <CountryComparePicker
        options={OPTIONS}
        selectedIds={[]}
        onToggle={onToggle}
        onOpen={vi.fn()}
      />,
    );
    const input = screen.getByRole('searchbox');
    fireEvent.focus(input);
    expect(screen.getByText('Германия')).toBeTruthy();
    fireEvent.click(screen.getByText('Германия'));
    expect(onToggle).toHaveBeenCalledWith('peer:germany:de-hicp');
  });

  it('filters by query', () => {
    renderPicker(
      <CountryComparePicker
        options={OPTIONS}
        selectedIds={[]}
        onToggle={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    const input = screen.getByRole('searchbox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'герм' } });
    expect(screen.getByText('Германия')).toBeTruthy();
    expect(screen.queryByText('Франция')).toBeNull();
  });

  it('disables extra countries at the comparison limit', () => {
    renderPicker(
      <CountryComparePicker
        options={OPTIONS}
        selectedIds={[
          'peer:germany:de-hicp',
          'peer:france:fr-hicp',
          'peer:austria:at-hicp',
          'peer:italy:it-hicp',
        ]}
        onToggle={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    const input = screen.getByRole('searchbox');
    fireEvent.focus(input);
    const spain = screen.getByText('Испания').closest('button');
    expect(spain?.disabled).toBe(true);
  });

  it('finds an eligible localized country by English alias and rejects conflicting geography', () => {
    const onToggle = vi.fn();
    renderPicker(<CountryComparePicker options={OPTIONS} selectedIds={[]} onToggle={onToggle} onOpen={vi.fn()} />);
    const input = screen.getByRole('searchbox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Germany' } });
    fireEvent.click(screen.getByText('Германия'));
    expect(onToggle).toHaveBeenCalledWith('peer:germany:de-hicp');
    fireEvent.change(input, { target: { value: 'Germany France' } });
    expect(screen.queryByText('Германия')).toBeNull();
    expect(screen.queryByText('Франция')).toBeNull();
  });

  it('panel shows the compare heading', () => {
    renderPicker(
      <CountryComparePanel
        pickerOptions={OPTIONS}
        activeComparisonIds={[]}
        selectedComparisons={[]}
        comparisonQueries={[]}
        comparisonScale="values"
        onToggle={vi.fn()}
        onOpen={vi.fn()}
        onScale={vi.fn()}
        conceptSlug="hicp-index"
        countrySlug="russia"
        compareCodes={[]}
        rebased={null}
        loadedComparisonSeries={[]}
      />,
    );
    expect(screen.getByText('Сравнение стран')).toBeTruthy();
  });

  it('offers popular countries as one-tap chips and toggles the tapped one', () => {
    const onToggle = vi.fn();
    renderPicker(
      <CountryComparePanel
        pickerOptions={[
          { code: 'average', country_name: 'Среднее по странам' },
          ...OPTIONS,
          { code: 'peer:china:cn', country_name: 'Китай', country_slug: 'china' },
        ]}
        activeComparisonIds={[]}
        selectedComparisons={[]}
        comparisonQueries={[]}
        comparisonScale="values"
        onToggle={onToggle}
        onOpen={vi.fn()}
        onScale={vi.fn()}
        conceptSlug="gdp-usd"
        countrySlug="russia"
        compareCodes={[]}
        rebased={null}
        loadedComparisonSeries={[]}
      />,
    );
    const group = screen.getByRole('group', { name: 'Сравнить с:' });
    const names = [...group.querySelectorAll('button')].map((b) => b.textContent);
    // Китай и Германия популярнее остальных и идут первыми; «Среднее по странам» в чипах не предлагается.
    expect(names.slice(0, 2)).toEqual(['Китай', 'Германия']);
    expect(names).not.toContain('Среднее по странам');
    fireEvent.click(screen.getByRole('button', { name: 'Китай' }));
    expect(onToggle).toHaveBeenCalledWith('peer:china:cn');
  });

  it('shows the base country first without a remove cross, and proposes growth in percent when sizes differ', () => {
    const onScale = vi.fn();
    renderPicker(
      <CountryComparePanel
        pickerOptions={OPTIONS}
        activeComparisonIds={['peer:germany:de-hicp']}
        selectedComparisons={[{ id: 'peer:germany:de-hicp', label: 'Германия', color: '#397C8C' }]}
        comparisonQueries={[]}
        comparisonScale="values"
        onToggle={vi.fn()}
        onOpen={vi.fn()}
        onScale={onScale}
        conceptSlug="gdp-usd"
        countrySlug="australia"
        compareCodes={['w:germany:gdp-usd']}
        rebased={null}
        loadedComparisonSeries={[]}
        baseLabel="Австралия"
        suggestPercent
      />,
    );
    const base = screen.getByText('Австралия').closest('.fe-compare-base');
    expect(base).toBeTruthy();
    expect(base.querySelector('svg')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Показать рост в процентах' }));
    expect(onScale).toHaveBeenCalledWith('index');
  });

  it('круг 10: в режиме «старт периода = 100» объяснение и видимая кнопка «Показать значения»', () => {
    const onScale = vi.fn();
    const props = {
      pickerOptions: OPTIONS,
      activeComparisonIds: ['peer:germany:de-hicp'],
      selectedComparisons: [{ id: 'peer:germany:de-hicp', label: 'Германия', color: '#397C8C' }],
      comparisonQueries: [],
      comparisonScale: 'index',
      onToggle: vi.fn(),
      onOpen: vi.fn(),
      onScale,
      conceptSlug: 'gdp-usd',
      countrySlug: 'australia',
      compareCodes: ['w:germany:gdp-usd'],
      rebased: null,
      loadedComparisonSeries: [{ data: [{ date: '2024-01-01', value: 1 }] }],
    };
    const { unmount } = renderPicker(<CountryComparePanel {...props} />);
    const note = screen.getByTestId('compare-base-explain');
    expect(note.textContent).toMatch(/Старт периода = 100/);
    expect(note.textContent).toMatch(/150/);
    fireEvent.click(screen.getByRole('button', { name: 'Показать значения' }));
    expect(onScale).toHaveBeenCalledWith('values');
    unmount();
    // Когда страница сама включила проценты, то же сказано плашкой над графиком: второго пояснения нет.
    renderPicker(<CountryComparePanel {...props} baseNote={false} />);
    expect(screen.queryByTestId('compare-base-explain')).toBeNull();
  });

  it('круг 10: английская версия — Russia в списке стран не первая, по размеру ВВП', () => {
    const options = [
      { code: 'peer:russia', country_name: 'Russia', country_slug: 'russia' },
      { code: 'peer:germany', country_name: 'Germany', country_slug: 'germany' },
      { code: 'peer:canada', country_name: 'Canada', country_slug: 'canada' },
      { code: 'peer:united-states', country_name: 'United States', country_slug: 'united-states' },
    ];
    render(
      <LocaleProvider locale="en">
        <MemoryRouter>
          <CountryComparePicker options={options} selectedIds={[]} onToggle={vi.fn()} onOpen={vi.fn()} />
        </MemoryRouter>
      </LocaleProvider>,
    );
    fireEvent.focus(screen.getByRole('searchbox'));
    const names = [...document.querySelectorAll('.fe-dialog-panel button')].map((b) => b.textContent.replace(/[\u{1F1E6}-\u{1F1FF}]/gu, '').trim());
    expect(names).toEqual(['United States', 'Germany', 'Russia', 'Canada']);
  });

  it('sends inflation comparisons to the rate ranking instead of raw index levels', () => {
    renderPicker(
      <CountryComparePanel
        pickerOptions={OPTIONS}
        activeComparisonIds={['peer:germany:de-hicp']}
        selectedComparisons={[{ id: 'peer:germany:de-hicp', label: 'Германия', color: '#397C8C' }]}
        comparisonQueries={[]}
        comparisonScale="values"
        onToggle={vi.fn()}
        onOpen={vi.fn()}
        onScale={vi.fn()}
        conceptSlug="hicp-index"
        countrySlug="russia"
        compareCodes={['w:germany:hicp-index']}
        rebased={null}
        loadedComparisonSeries={[]}
      />,
    );
    expect(screen.getByRole('link', { name: 'Сравнить инфляцию в процентах' }).getAttribute('href'))
      .toBe('/world/rating/hicp-index');
    expect(screen.queryByRole('link', { name: 'Открыть полное сравнение' })).toBeNull();
  });
});

describe('IndicatorChartSection world compare', () => {
  it('renders the compare block for a Russia concept card', () => {
    renderPage(
      <IndicatorChartSection
        code="cpi"
        indicator={{ code: 'cpi', name: 'ИПЦ', unit: '%', frequency: 'monthly', category: 'Цены' }}
        chartMode="inflation"
        safeViewMode="inflation"
        isPriceCategory
        chartLoading={false}
        inflationResp={{ actuals: [{ date: '2025-07-01', value: 9.1 }] }}
        dataPoints={[{ date: '2025-07-01', value: 9.1 }]}
        forecastEnabled={false}
        showForecast={false}
        onToggleForecast={vi.fn()}
        onDownloadCsv={vi.fn()}
        onDownloadExcel={vi.fn()}
        worldCompare={{
          concept: {
            slug: 'hicp-index',
            compatible_modes: ['inflation', 'inflation-quarter', 'inflation-year'],
            default_mode: 'inflation',
            peer_mode: 'yoy-monthly',
            peer_value_scale: 1,
          },
          peers: [
            {
              country_slug: 'germany',
              country_name: 'Германия',
              country_name_en: 'Germany',
              indicator_code: 'de-prc_hicp_midx-cp00-i15',
              peer_mode: 'yoy-monthly',
            },
          ],
        }}
      />,
      { path: '/russia/indicator/:code', route: '/russia/indicator/cpi' },
    );
    expect(screen.getByText('Сравнение стран')).toBeTruthy();
    // Страны чипами одним нажатием; поиск остальных открывается по кнопке «Другие страны».
    expect(screen.getByRole('button', { name: 'Германия' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Другие страны' }));
    expect(screen.getByRole('searchbox')).toBeTruthy();
  });

  it('does not mount a compare block without a concept', () => {
    renderPage(
      <IndicatorChartSection
        code="key-rate"
        indicator={{ code: 'key-rate', name: 'Ключевая ставка', unit: '%', frequency: 'daily', category: 'Ставки' }}
        chartMode="cpi"
        safeViewMode="level"
        chartLoading={false}
        dataPoints={[{ date: '2025-07-01', value: 16 }]}
        forecastEnabled={false}
        showForecast={false}
        onToggleForecast={vi.fn()}
        onDownloadCsv={vi.fn()}
        onDownloadExcel={vi.fn()}
        worldCompare={null}
      />,
      { path: '/russia/indicator/:code', route: '/russia/indicator/key-rate' },
    );
    expect(screen.queryByText('Сравнение стран')).toBeNull();
  });
});
