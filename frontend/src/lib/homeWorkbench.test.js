import { describe, expect, it } from 'vitest';
import {
  HOME_TODAY_CODES,
  WORKBENCH_TABS,
  countryCoverageNote,
  displayPulseValue,
  heatmapValuesBySlug,
  isWorkbenchTab,
  pickIndicatorsByCodes,
  rankHeatmapValues,
  resolveActiveMapYear,
  resolveCountryMacroregion,
  resolveWorkbenchTab,
  worldRankingFromYearItems,
  worldYearItems,
} from './homeWorkbench';

describe('homeWorkbench', () => {
  it('держит три вкладки Россия / Регионы / Страны', () => {
    expect(WORKBENCH_TABS.map((t) => t.id)).toEqual(['russia', 'regions', 'countries']);
    expect(WORKBENCH_TABS.map((t) => t.label)).toEqual(['Россия', 'Регионы', 'Страны']);
    expect(isWorkbenchTab('europe')).toBe(false);
    expect(resolveWorkbenchTab('countries')).toBe('countries');
    expect(resolveWorkbenchTab('europe')).toBe('russia');
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

  it('готовит мировой рейтинг и честную подпись покрытия', () => {
    const series = {
      values_by_year: {
        2024: {
          DE: { country_slug: 'germany', country_name: 'Германия', value: 5 },
          FR: { country_slug: 'france', country_name: 'Франция', value: 7 },
        },
      },
    };
    expect(resolveActiveMapYear([2022, 2023, 2024], null)).toBe(2024);
    const items = worldYearItems(series, 2024);
    expect(worldRankingFromYearItems(items, 1)[0].country_slug).toBe('france');
    expect(resolveCountryMacroregion('asia')).toBe('europe');
    expect(countryCoverageNote('europe')).toMatch(/Европ/i);
  });
});
