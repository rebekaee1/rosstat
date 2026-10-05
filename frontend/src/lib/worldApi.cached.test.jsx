/** @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocaleProvider } from '../i18n';
import { useCachedWorldCountry, worldCountriesQueryKey } from './worldApi';

function wrapperWith(client, locale = 'ru') {
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={client}>
        <LocaleProvider locale={locale}>{children}</LocaleProvider>
      </QueryClientProvider>
    );
  };
}

describe('useCachedWorldCountry (name and flag at once after a tap)', () => {
  it('finds the country in the already loaded catalog without making a request', () => {
    const client = new QueryClient();
    client.setQueryData(worldCountriesQueryKey('ru'), {
      countries: [
        { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа' },
        { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', region: 'Европа' },
      ],
    });
    const { result } = renderHook(() => useCachedWorldCountry('germany'), { wrapper: wrapperWith(client) });
    expect(result.current).toMatchObject({ code: 'DE', name: 'Германия' });
  });

  it('is null while the catalog is not in the cache or the slug is unknown', () => {
    const client = new QueryClient();
    const empty = renderHook(() => useCachedWorldCountry('germany'), { wrapper: wrapperWith(client) });
    expect(empty.result.current).toBeNull();
    client.setQueryData(worldCountriesQueryKey('ru'), { countries: [{ code: 'DE', slug: 'germany', name: 'Германия' }] });
    const unknown = renderHook(() => useCachedWorldCountry('narnia'), { wrapper: wrapperWith(client) });
    expect(unknown.result.current).toBeNull();
  });
});
