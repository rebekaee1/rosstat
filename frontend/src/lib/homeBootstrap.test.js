/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  HOME_BOOTSTRAP_ID,
  readHomeBootstrap,
  resetHomeBootstrapCache,
  seedQueryClientFromHomeBootstrap,
} from './homeBootstrap';
import { indicatorsListQueryKey } from './hooks';
import {
  worldCompareSnapshotQueryKey,
  worldCountriesQueryKey,
} from './worldApi';

function mountBootstrap(payload) {
  const el = document.createElement('script');
  el.type = 'application/json';
  el.id = HOME_BOOTSTRAP_ID;
  el.textContent = JSON.stringify(payload);
  document.body.appendChild(el);
}

afterEach(() => {
  resetHomeBootstrapCache();
  document.getElementById(HOME_BOOTSTRAP_ID)?.remove();
});

describe('homeBootstrap', () => {
  it('читает JSON из #fe-bootstrap', () => {
    mountBootstrap({
      locale: 'ru',
      indicators: [{ code: 'cpi', name: 'ИПЦ', is_listed: true }],
    });
    expect(readHomeBootstrap().indicators[0].code).toBe('cpi');
  });

  it('кладёт flagships в QueryClient и помечает ключ stale', () => {
    const list = [{ code: 'cpi', name: 'ИПЦ', is_listed: true }];
    mountBootstrap({ locale: 'ru', indicators: list });
    const qc = new QueryClient();
    expect(seedQueryClientFromHomeBootstrap(qc)).toBe(true);
    const key = indicatorsListQueryKey('ru');
    expect(qc.getQueryData(key)).toEqual(list);
    const cached = qc.getQueryCache().find({ queryKey: key });
    expect(cached?.state.isInvalidated).toBe(true);
  });

  it('сидит world-countries без invalidate (cold home counters)', () => {
    const world = {
      countries: [{ code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' }],
      total: 55,
      world_indicators_count: 38146,
      russia_macro_indicators_count: 145,
      regional_indicators_count: 2377,
    };
    mountBootstrap({
      locale: 'en',
      indicators: [{ code: 'cpi', name: 'CPI', is_listed: true }],
      worldCountries: world,
    });
    const qc = new QueryClient();
    expect(seedQueryClientFromHomeBootstrap(qc)).toBe(true);
    const key = worldCountriesQueryKey('en');
    expect(qc.getQueryData(key)).toEqual(world);
    const cached = qc.getQueryCache().find({ queryKey: key });
    expect(cached?.state.isInvalidated).toBe(false);
  });

  it('сидит map snapshot для дефолтного концепта без invalidate', () => {
    const snap = {
      concept: { slug: 'gdp-usd', name: 'GDP', unit: 'billion $' },
      items: [{
        country_code: 'US',
        country_slug: 'united-states',
        country_name: 'United States',
        date: '2024-01-01',
        value: 28000,
      }],
    };
    mountBootstrap({
      locale: 'en',
      indicators: [{ code: 'cpi', name: 'CPI', is_listed: true }],
      mapConcept: 'gdp-usd',
      mapSnapshot: snap,
    });
    const qc = new QueryClient();
    expect(seedQueryClientFromHomeBootstrap(qc)).toBe(true);
    const key = worldCompareSnapshotQueryKey('gdp-usd', 'en');
    expect(qc.getQueryData(key)).toEqual(snap);
    const cached = qc.getQueryCache().find({ queryKey: key });
    expect(cached?.state.isInvalidated).toBe(false);
  });
});
