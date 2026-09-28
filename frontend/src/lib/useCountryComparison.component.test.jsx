/** @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest';
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
});
