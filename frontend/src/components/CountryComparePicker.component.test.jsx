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
