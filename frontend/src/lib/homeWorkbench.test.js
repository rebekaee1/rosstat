import { describe, expect, it } from 'vitest';
import {
  HOME_MAP_SIDE_LINKS,
  HOME_TODAY_CODES,
  displayPulseValue,
  heatmapValuesBySlug,
  pickIndicatorsByCodes,
  rankHeatmapValues,
  resolveActiveMapYear,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldYearItems,
} from './homeWorkbench';

describe('homeWorkbench', () => {
  it('держит боковые переходы карты без mid-dot', () => {
    expect(HOME_MAP_SIDE_LINKS.map((l) => l.id)).toEqual([
      'russia-macro', 'regions', 'europe', 'world',
    ]);
    for (const link of HOME_MAP_SIDE_LINKS) {
      expect(link.label.includes('·')).toBe(false);
      expect(link.to.startsWith('/')).toBe(true);
    }
    expect(HOME_MAP_SIDE_LINKS[0].scrollId).toBe('russia-categories');
  });

  it('собирает «Россия сегодня» из листинга без лишних кодов', () => {
    expect(HOME_TODAY_CODES).toHaveLength(6);
    const list = [
      { code: 'usd-rub', current_value: 90 },
      { code: 'cpi', hero_value: 5.3, hero_unit: '%', hero_label: 'Год к году' },
      { code: 'noise', current_value: 1 },
    ];
    const picked = pickIndicatorsByCodes(list, HOME_TODAY_CODES);
    expect(picked.map((i) => i.code)).toEqual(['usd-rub', 'cpi']);
  });

  it('displayPulseValue предпочитает hero и корректирует сырой ИПЦ', () => {
    expect(displayPulseValue({
      code: 'cpi',
      hero_value: 5.32,
      hero_unit: '%',
      hero_change: 0.1,
    })).toEqual({
      value: 5.32,
      unit: '%',
      label: null,
      change: 0.1,
    });
    expect(displayPulseValue({
      code: 'cpi',
      current_value: 100.4,
      unit: '%',
      change: 0.2,
    }).value).toBeCloseTo(0.4);
  });

  it('ранжирует регионы и собирает Map для карты', () => {
    const values = [
      { slug: 'a', name: 'A', value: 10 },
      { slug: 'b', name: 'B', value: 30 },
      { slug: 'c', name: 'C', value: 20 },
    ];
    expect(rankHeatmapValues(values, { limit: 2 }).map((r) => r.slug)).toEqual(['b', 'c']);
    expect(rankHeatmapValues(values, { betterIsLow: true, limit: 1 })[0].slug).toBe('a');
    const map = heatmapValuesBySlug({ values });
    expect(map.get('b')).toBe(30);
  });

  it('готовит мировой рейтинг и оверлей РФ', () => {
    const series = {
      values_by_year: {
        2024: {
          DE: { country_slug: 'germany', country_name: 'Германия', value: 5 },
          FR: { country_slug: 'france', country_name: 'Франция', value: 7 },
        },
      },
    };
    expect(resolveActiveMapYear([2022, 2023, 2024], null)).toBe(2024);
    expect(resolveActiveMapYear([2024, 2025, 2026], null, {
      2024: Object.fromEntries([...Array(20)].map((_, i) => [`C${i}`, { value: 1 }])),
      2025: Object.fromEntries([...Array(20)].map((_, i) => [`C${i}`, { value: 1 }])),
      2026: { US: { value: 1 } },
    })).toBe(2025);
    const items = worldYearItems(series, 2024);
    expect(worldRankingFromYearItems(items, 1)[0].country_slug).toBe('france');

    const overlay = withRussiaOnHomeMap({
      countries: [{ code: 'DE', slug: 'germany', name: 'Германия' }],
      yearItems: items,
      indicators: [{ code: 'unemployment', current_value: 2.2 }],
      conceptSlug: 'unemployment-rate',
      activeYear: 2024,
    });
    expect(overlay.countries.some((c) => c.code === 'RU')).toBe(true);
    expect(overlay.yearItems.RU.value).toBeCloseTo(2.2);
    expect(overlay.russiaIndicatorCode).toBe('unemployment');
  });
});
