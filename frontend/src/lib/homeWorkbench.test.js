import { describe, expect, it } from 'vitest';
import {
  HOME_MAP_SIDE_LINKS,
  HOME_MARKET_PULSE,
  HOME_TODAY_CODES,
  HOME_TODAY_LABELS,
  HOME_TODAY_UNIT_SHORT,
  WORLD_CONCEPT_GROUPS,
  displayPulseValue,
  heatmapValuesBySlug,
  pickIndicatorsByCodes,
  rankHeatmapValues,
  resolveActiveMapYear,
  russiaDeepLinksForConcept,
  russiaNoteForConcept,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldRatingTitle,
  worldYearItems,
} from './homeWorkbench';

describe('homeWorkbench', () => {
  it('держит боковые переходы карты без mid-dot и без дубля Европа/Мир', () => {
    expect(HOME_MAP_SIDE_LINKS.map((l) => l.id)).toEqual([
      'russia-macro', 'regions', 'world',
    ]);
    for (const link of HOME_MAP_SIDE_LINKS) {
      expect(link.label.includes('·')).toBe(false);
      expect(link.to.startsWith('/')).toBe(true);
    }
    expect(HOME_MAP_SIDE_LINKS.filter((l) => l.to === '/world')).toHaveLength(1);
  });

  it('собирает мировой рыночный срез из одного массива объектов', () => {
    expect(HOME_TODAY_CODES).toEqual(HOME_MARKET_PULSE.map((i) => i.code));
    expect(HOME_TODAY_CODES).toEqual([
      'btc-usd', 'brent', 'usd-index', 'ust-10y', 'natural-gas',
    ]);
    // gold-price — руб./г от ЦБ, не мировая мера; альткоины — не мировые рынки.
    // Месячные Pink Sheet (silver/copper) в оперативный срез не входят.
    expect(HOME_TODAY_CODES).not.toContain('gold-price');
    expect(HOME_TODAY_CODES).not.toContain('eth-usd');
    expect(HOME_TODAY_CODES).not.toContain('sol-usd');
    expect(HOME_TODAY_CODES).not.toContain('silver');
    expect(HOME_TODAY_CODES).not.toContain('copper');
    for (const item of HOME_MARKET_PULSE) {
      expect(HOME_TODAY_LABELS[item.code]).toBe(item.label);
      expect(HOME_TODAY_UNIT_SHORT[item.code]).toBe(item.unitShort);
      expect(item.unitShort.includes('фнт')).toBe(false);
    }
    expect(HOME_TODAY_UNIT_SHORT['natural-gas']).toBe('$/млн БТЕ');
    const list = [
      { code: 'btc-usd', current_value: 90000 },
      { code: 'brent', current_value: 80 },
      { code: 'noise', current_value: 1 },
    ];
    const picked = pickIndicatorsByCodes(list, HOME_TODAY_CODES);
    expect(picked.map((i) => i.code)).toEqual(['btc-usd', 'brent']);
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
    // Пик 40 стран → порог max(8, 20)=20; год с 19 странами пропускаем.
    expect(resolveActiveMapYear([2024, 2025], null, {
      2024: Object.fromEntries([...Array(40)].map((_, i) => [`C${i}`, { value: 1 }])),
      2025: Object.fromEntries([...Array(19)].map((_, i) => [`C${i}`, { value: 1 }])),
    })).toBe(2024);
    const items = worldYearItems(series, 2024);
    expect(worldRankingFromYearItems(items, 1)[0].country_slug).toBe('france');

    expect(worldRatingTitle('unemployment-rate', 'Уровень безработицы', 2026)).toBe(
      'Рейтинг стран по уровню безработицы за 2026 год',
    );
    expect(worldRatingTitle('hicp-index', 'Изменение потребительских цен за год', 2025)).toBe(
      'Рейтинг стран по изменению потребительских цен за год, 2025',
    );

    const overlay = withRussiaOnHomeMap({
      countries: [{ code: 'DE', slug: 'germany', name: 'Германия' }],
      yearItems: {
        ...items,
        RU: {
          country_code: 'RU',
          country_slug: 'russia',
          country_name: 'Россия',
          indicator_code: 'unemployment',
          value: 2.2,
        },
      },
      mapSeries: {
        concept: {
          russia: {
            eligible: true,
            indicator_code: 'unemployment',
            country: { code: 'RU', slug: 'russia', name_ru: 'Россия' },
          },
        },
      },
    });
    expect(overlay.countries.some((c) => c.code === 'RU')).toBe(true);
    expect(overlay.yearItems.RU.value).toBeCloseTo(2.2);
    expect(overlay.russiaIndicatorCode).toBe('unemployment');

    const noBudget = withRussiaOnHomeMap({
      countries: [],
      yearItems: {},
      mapSeries: { concept: {} },
    });
    expect(noBudget.yearItems.RU).toBeUndefined();
    expect(noBudget.russiaIndicatorCode).toBeNull();
    expect(noBudget.countries.some((c) => c.code === 'RU')).toBe(false);

    const hicp = withRussiaOnHomeMap({
      countries: [],
      yearItems: {
        RU: {
          country_code: 'RU',
          indicator_code: 'cpi-yoy',
          value: 6.0,
        },
      },
      mapSeries: {
        concept: {
          russia: { eligible: true, indicator_code: 'cpi-yoy' },
        },
      },
    });
    expect(hicp.russiaIndicatorCode).toBe('cpi-yoy');
    expect(hicp.yearItems.RU.value).toBeCloseTo(6.0);

    const pop = withRussiaOnHomeMap({
      countries: [],
      yearItems: {
        RU: {
          country_code: 'RU',
          indicator_code: 'population',
          value: 146_120_000,
        },
      },
      mapSeries: {
        concept: {
          russia: { eligible: true, indicator_code: 'population' },
        },
      },
    });
    expect(pop.yearItems.RU.value).toBeCloseTo(146_120_000);
  });

  it('даёт перелинковку в регионы для сопоставимых концептов', () => {
    const links = russiaDeepLinksForConcept('unemployment-rate');
    expect(links.countryHref).toBe('/russia/indicator/unemployment');
    expect(links.regionsHref).toBe('/russia/region');
    expect(links.regionRatingHref).toBe('/russia/region-rating/uroven-bezrabotitsy');
    expect(russiaNoteForConcept('unemployment-rate')).toMatch(/Росстата/);
    expect(russiaNoteForConcept('budget-balance-gdp')).toBeNull();
    expect(WORLD_CONCEPT_GROUPS.length).toBeGreaterThanOrEqual(5);
  });
});
