/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocaleProvider } from '../i18n';
import api from './api';
import { useCountryComparison } from './useCountryComparison';

function wrapper({ children }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <LocaleProvider>{children}</LocaleProvider>
  </QueryClientProvider>;
}

describe('useCountryComparison', () => {
  afterEach(() => vi.restoreAllMocks());
  it('показывает размеры ВВП России и США в долларах по умолчанию, индекс оставляет опцией', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: {
      points: [
        { date: '1992-01-01', value: 6520.325 },
        { date: '2024-01-01', value: 29298.025 },
      ],
    } });
    const { result } = renderHook(() => useCountryComparison({
      surface: 'russia',
      peers: [{ code: 'peer:united-states:gdp', country_slug: 'united-states', country_name: 'США', indicator_code: 'us-gdp', peer_mode: 'level-annual' }],
      conceptSlug: 'gdp-usd',
      countrySlug: 'russia',
      dataPoints: [
        { date: '1992-01-01', value: 71.6031 },
        { date: '2024-01-01', value: 2185.8477 },
      ],
      unit: 'млрд $',
      title: 'ВВП',
      peerMode: 'level-annual',
    }), { wrapper });

    act(() => result.current.toggleComparison('peer:united-states:gdp'));
    await waitFor(() => expect(result.current.loadedComparisonSeries).toHaveLength(1));
    expect(result.current.comparisonScale).toBe('values');
    expect(result.current.displayedDataPoints.at(-1).value).toBeCloseTo(2185.8477);
    expect(result.current.displayedComparisonSeries[0].data.at(-1).value).toBeCloseTo(29298.025);
    expect(result.current.displayedUnit).toBe('млрд $');

    act(() => result.current.setComparisonScale('index'));
    expect(result.current.displayedDataPoints.at(-1).value).toBeCloseTo(3052.73, 1);
    expect(result.current.displayedComparisonSeries[0].data.at(-1).value).toBeCloseTo(449.33, 1);
  });

  it('показывает численность населения в миллионах даже при разных датах публикации', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: {
      points: [
        { date: '2024-07-01', value: 340_000_000 },
        { date: '2025-07-01', value: 341_785_000 },
      ],
    } });
    const { result } = renderHook(() => useCountryComparison({
      surface: 'russia',
      peers: [{
        code: 'peer:united-states:population',
        country_slug: 'united-states',
        country_name: 'США',
        indicator_code: 'us-population-census',
        peer_mode: 'level-annual',
      }],
      conceptSlug: 'population',
      countrySlug: 'russia',
      dataPoints: [{ date: '2025-01-01', value: 146.12 }],
      unit: 'млн чел.',
      title: 'Численность населения',
      peerMode: 'level-annual',
      peerValueScale: 1e-6,
    }), { wrapper });

    act(() => result.current.toggleComparison('peer:united-states:population'));
    await waitFor(() => expect(result.current.loadedComparisonSeries).toHaveLength(1));
    expect(result.current.comparisonScale).toBe('values');
    expect(result.current.displayedDataPoints.at(-1).value).toBe(146.12);
    expect(result.current.displayedComparisonSeries[0].data.at(-1).value).toBeCloseTo(341.785);
    expect(result.current.displayedUnit).toBe('млн чел.');
  });

  it.each([
    ['unemployment-rate', '%', 'values'],
    ['budget-balance-gdp', '% ВВП', 'values'],
    ['gdp-volume-annual', 'млн евро', 'values'],
    ['gdp-volume-quarterly', 'млн евро', 'values'],
    // Круг 11: страница сама проценты не включает, даже для обычной абсолютной величины.
    ['custom-absolute', 'руб.', 'values'],
  ])('сохраняет корректный режим для %s', (conceptSlug, unit, expectedScale) => {
    const { result } = renderHook(() => useCountryComparison({
      surface: 'world',
      peers: [{ code: 'peer', country_slug: 'germany', country_name: 'Германия', indicator_code: 'peer-code' }],
      conceptSlug,
      countrySlug: 'france',
      dataPoints: [{ date: '2024-01-01', value: 100 }],
      unit,
      title: 'Показатель',
      modeMeta: { id: 'level-annual', type: 'level' },
    }), { wrapper });

    act(() => result.current.toggleComparison('peer'));
    expect(result.current.comparisonScale).toBe(expectedScale);
  });

  it('не смешивает уровни индексов с разными базами и готовыми процентами', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: { items: [
      { code: 'w:germany:hicp-index', country_slug: 'germany', concept_slug: 'hicp-index', peer_mode: 'yoy-monthly' },
      { code: 'w:united-states:hicp-index', country_slug: 'united-states', concept_slug: 'hicp-index', indicator_code: 'us-cpi-all', peer_mode: 'yoy-monthly' },
      { code: 'w:russia:hicp-index', country_slug: 'russia', concept_slug: 'hicp-index', peer_mode: 'level-annual' },
    ] } });
    const { result } = renderHook(() => useCountryComparison({
      surface: 'world',
      peers: [
        { code: 'peer:france', country_slug: 'france', country_name: 'Франция', indicator_code: 'fr-hicp' },
        { code: 'peer:russia', country_slug: 'russia', country_name: 'Россия', indicator_code: 'cpi-yoy' },
      ],
      conceptSlug: 'hicp-index',
      countrySlug: 'germany',
      dataPoints: [{ date: '2025-01-01', value: 132 }],
      unit: 'индекс 2015=100',
      title: 'Индекс потребительских цен',
      modeMeta: { id: 'level-monthly', type: 'level' },
    }), { wrapper });

    act(() => result.current.setComparisonPickerActive(true));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/world/compare/catalog', expect.anything()));
    expect(result.current.pickerOptions.map((item) => item.country_slug)).toEqual(['france']);
  });

  it('сопоставляет годовую инфляцию США и Германии в процентах', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url) => {
      if (url === '/world/compare/catalog') return { data: { items: [
        { code: 'w:germany:hicp-index', country_slug: 'germany', concept_slug: 'hicp-index', peer_mode: 'yoy-monthly' },
        { code: 'w:united-states:hicp-index', country_slug: 'united-states', country_name: 'США', concept_slug: 'hicp-index', indicator_code: 'us-cpi-all', peer_mode: 'yoy-monthly' },
        { code: 'w:china:hicp-index', country_slug: 'china', country_name: 'Китай', concept_slug: 'hicp-index', indicator_code: 'cn-cpi-all', peer_mode: 'level-monthly', value_adjust: 'minus_100' },
        { code: 'w:russia:hicp-index', country_slug: 'russia', country_name: 'Россия', concept_slug: 'hicp-index', indicator_code: 'cpi-yoy' },
        { code: 'w:japan:hicp-index', country_slug: 'japan', country_name: 'Япония', concept_slug: 'hicp-index', indicator_code: 'jp-weo-pcpipch', peer_mode: 'level-annual' },
      ] } };
      if (url.includes('/china/')) return { data: { points: [{ date: '2025-01-01', value: 103.35 }] } };
      return { data: { points: [{ date: '2025-01-01', value: 3.35 }] } };
    });
    const { result } = renderHook(() => useCountryComparison({
      surface: 'world',
      conceptSlug: 'hicp-index',
      countrySlug: 'germany',
      dataPoints: [{ date: '2025-01-01', value: 2.92 }],
      unit: '%',
      title: 'Инфляция',
      modeMeta: { id: 'yoy-monthly', type: 'yoy' },
    }), { wrapper });

    act(() => result.current.setComparisonPickerActive(true));
    await waitFor(() => expect(result.current.pickerOptions.some((item) => item.country_slug === 'united-states')).toBe(true));
    expect(result.current.pickerOptions.some((item) => item.country_slug === 'russia')).toBe(false);
    expect(result.current.pickerOptions.some((item) => item.country_slug === 'japan')).toBe(false);
    act(() => result.current.toggleComparison('w:united-states:hicp-index'));
    await waitFor(() => expect(result.current.loadedComparisonSeries).toHaveLength(1));
    expect(api.get).toHaveBeenCalledWith(
      '/world/indicators/united-states/us-cpi-all/data',
      expect.objectContaining({ params: { mode: 'yoy-monthly' } }),
    );
    expect(result.current.displayedComparisonSeries[0].data[0].value).toBe(3.35);
    expect(result.current.comparisonScale).toBe('values');

    act(() => result.current.toggleComparison('w:china:hicp-index'));
    await waitFor(() => expect(result.current.loadedComparisonSeries).toHaveLength(2));
    expect(api.get).toHaveBeenCalledWith(
      '/world/indicators/china/cn-cpi-all/data',
      expect.objectContaining({ params: { mode: 'level-monthly' } }),
    );
    expect(result.current.displayedComparisonSeries[1].data[0].value).toBeCloseTo(3.35);
  });

});
