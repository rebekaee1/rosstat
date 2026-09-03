import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';
import {
  DEFAULT_HOME_COUNTRY_CONCEPT,
  HOME_MAP_CONCEPT_ORDER,
  HOME_MARKET_PULSE,
  HOME_RATING_LIMIT,
  HOME_TODAY_CODES,
  displayPulseValue,
  HOME_SCOPE_COUNTRIES_FALLBACK,
  homeMapConcepts,
  homeScopeCountriesCount,
  resolveHomeConcept,
  heatmapValuesBySlug,
  homeConceptLabel,
  homePulseLabel,
  homePulseUnitShort,
  pickIndicatorsByCodes,
  rankHeatmapValues,
  resolveActiveMapYear,
  russiaDeepLinksForConcept,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  defaultSortForConcept,
  worldRatingTitle,
  worldYearItems,
  mapSeriesFromSnapshot,
  resolveHomeMapSeries,
  mapSelectHref,
  mapSurfaceCountries,
  isWeoMapConcept,
} from './homeWorkbench';

describe('homeWorkbench', () => {
  it('набор показателей главной закрыт и идёт заданным порядком', () => {
    expect(HOME_MAP_CONCEPT_ORDER).toEqual([
      'gdp-usd',
      'gdp-per-capita-usd',
      'unemployment-rate',
      'hicp-index',
      'population',
      'policy-rate',
      'budget-balance-gdp',
      'government-debt-gdp',
    ]);
    for (const slug of HOME_MAP_CONCEPT_ORDER) {
      expect(homeConceptLabel(slug, (k) => translate(k, undefined, 'ru'))).toBeTruthy();
      expect(homeConceptLabel(slug, (k) => translate(k, undefined, 'en'))).toBeTruthy();
    }
    // Порядок API игнорируется: показываем свой, лишние показатели отсекаем.
    const api = [
      { slug: 'activity-rate', name: 'Экономическая активность' },
      { slug: 'unemployment-rate', name: 'Безработица' },
      { slug: 'gdp-usd', name: 'ВВП' },
    ];
    expect(homeMapConcepts(api).map((c) => c.slug)).toEqual(['gdp-usd', 'unemployment-rate']);
    expect(resolveHomeConcept(api)).toBe(DEFAULT_HOME_COUNTRY_CONCEPT);
    // Нет предпочтённого — берём первый доступный, а не пустоту.
    expect(resolveHomeConcept([{ slug: 'gdp-usd' }])).toBe('gdp-usd');
    // Ни одного «нашего» — отдаём список как есть, чтобы карта не осталась без выбора.
    expect(homeMapConcepts([{ slug: 'activity-rate' }]).map((c) => c.slug)).toEqual(['activity-rate']);
    expect(DEFAULT_HOME_COUNTRY_CONCEPT).toBe('gdp-usd');
    expect(HOME_RATING_LIMIT).toBe(32);
    expect(HOME_RATING_LIMIT).toBeGreaterThanOrEqual(28);
    expect(HOME_RATING_LIMIT).toBeLessThanOrEqual(36);
  });

  it('собирает мировой рыночный срез из одного массива объектов', () => {
    expect(HOME_TODAY_CODES).toEqual(HOME_MARKET_PULSE.map((i) => i.code));
    expect(HOME_TODAY_CODES).toEqual([
      'btc-usd', 'brent', 'eur-usd', 'usd-index', 'ust-10y', 'natural-gas',
    ]);
    // gold-price — руб./г от ЦБ, не мировая мера; альткоины — не мировые рынки.
    // Месячные Pink Sheet (silver/copper) в оперативный срез не входят.
    expect(HOME_TODAY_CODES).not.toContain('gold-price');
    expect(HOME_TODAY_CODES).not.toContain('eth-usd');
    expect(HOME_TODAY_CODES).not.toContain('sol-usd');
    expect(HOME_TODAY_CODES).not.toContain('silver');
    expect(HOME_TODAY_CODES).not.toContain('copper');
    for (const item of HOME_MARKET_PULSE) {
      expect(item.labelKey).toBeTruthy();
      expect(item.unitKey).toBeTruthy();
      expect(homePulseLabel(item.code, (k) => translate(k, undefined, 'ru'))).toBeTruthy();
      expect(homePulseUnitShort(item.code, (k) => translate(k, undefined, 'en'))).toBeTruthy();
    }
    expect(homePulseLabel('btc-usd', (k) => translate(k, undefined, 'en'))).toBe('Bitcoin');
    expect(homePulseUnitShort('natural-gas', (k) => translate(k, undefined, 'ru'))).toBe('$/млн БТЕ');
    expect(homePulseUnitShort('natural-gas', (k) => translate(k, undefined, 'en'))).toBe('$/mmBtu');
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
    const fromSnap = mapSeriesFromSnapshot({
      items: [
        {
          country_code: 'DE',
          country_slug: 'germany',
          country_name: 'Германия',
          date: '2025-06-01',
          value: 3.1,
        },
        {
          country_code: 'FR',
          country_slug: 'france',
          country_name: 'Франция',
          date: '2024-12-31',
          value: 7.2,
        },
      ],
      concept: { name: 'Безработица', unit: '%' },
      average: 5,
      average_label: 'Среднее',
    });
    expect(fromSnap.years).toEqual([2024, 2025]);
    expect(fromSnap.values_by_year['2025'].DE.value).toBeCloseTo(3.1);
    expect(fromSnap.benchmark_by_year['2025'].value).toBe(5);
    const emptySeries = { years: [], values_by_year: {}, concept: {} };
    expect(resolveHomeMapSeries(emptySeries, { items: [{ country_code: 'DE', date: '2025-01-01', value: 1 }] }))
      .toBe(emptySeries);
    expect(resolveHomeMapSeries(null, {
      items: [{ country_code: 'DE', date: '2025-01-01', value: 1 }],
      concept: { slug: 'gdp-usd' },
    }).years).toEqual([2025]);
    // Направление задаёт каталог: у безработицы первое место — минимум.
    expect(worldRankingFromYearItems(items, 1, 'asc')[0].country_slug).toBe('germany');
    expect(defaultSortForConcept('unemployment-rate', [])).toBe('asc');
    expect(defaultSortForConcept('gdp-usd', [])).toBe('desc');
    expect(defaultSortForConcept('gdp-usd', [{ slug: 'gdp-usd', default_sort: 'asc' }])).toBe('asc');

    const tRu = (key, vars) => translate(key, vars, 'ru');
    expect(worldRatingTitle('unemployment-rate', 'Уровень безработицы', 2026, tRu)).toBe(
      'Рейтинг стран по уровню безработицы за 2026 год',
    );
    expect(worldRatingTitle('hicp-index', 'Изменение потребительских цен за год', 2025, tRu)).toBe(
      'Рейтинг стран по изменению потребительских цен за год, 2025',
    );
    const tEn = (key, vars) => translate(key, vars, 'en');
    expect(worldRatingTitle('unemployment-rate', 'Unemployment rate', 2026, tEn)).toBe(
      'Country ranking by unemployment rate for 2026',
    );
    expect(worldRatingTitle('hicp-index', 'YoY CPI', 2025, tEn)).toBe(
      'Country ranking by year-over-year change in consumer prices, 2025',
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

  it('ведёт клик по ВВП на карточку ряда МВФ, Россию — на weo-gdp-usd', () => {
    expect(isWeoMapConcept('gdp-usd')).toBe(true);
    expect(isWeoMapConcept('government-debt-gdp')).toBe(true);
    expect(isWeoMapConcept('unemployment-rate')).toBe(false);
    expect(mapSelectHref(
      { code: 'US', slug: 'united-states' },
      { indicator_code: 'us-ngdpd' },
      { conceptSlug: 'gdp-usd' },
    )).toBe('/united-states/indicator/us-ngdpd');
    // Сервер может отдать код ряда значения (национальный мост) — клик всё
    // равно на карточку МВФ в каталоге России.
    expect(mapSelectHref(
      { code: 'RU', slug: 'russia' },
      { indicator_code: 'gdp-nominal-annual' },
      {
        conceptSlug: 'gdp-usd',
        russiaIndicatorCode: 'gdp-nominal-annual',
      },
    )).toBe('/russia/indicator/weo-gdp-usd');
    expect(mapSelectHref(
      { code: 'RU', slug: 'russia' },
      { indicator_code: 'weo-gdp-usd' },
      { conceptSlug: 'gdp-usd' },
    )).toBe('/russia/indicator/weo-gdp-usd');
    expect(mapSelectHref(
      { code: 'RU', slug: 'russia' },
      {},
      { conceptSlug: 'government-debt-gdp' },
    )).toBe('/russia/indicator/weo-government-debt-gdp');
    expect(mapSelectHref(
      { code: 'DE', slug: 'germany' },
      {},
      { conceptSlug: 'gdp-usd' },
    )).toBe('/germany');
    // Не-WEO: по-прежнему берём indicator_code с сервера.
    expect(mapSelectHref(
      { code: 'RU', slug: 'russia' },
      { indicator_code: 'unemployment' },
      { conceptSlug: 'unemployment-rate' },
    )).toBe('/russia/indicator/unemployment');
    const merged = mapSurfaceCountries(
      [{ code: 'DE', slug: 'germany', name: 'Германия' }],
      {
        US: {
          country_code: 'US',
          country_slug: 'united-states',
          country_name: 'США',
          value: 28,
        },
        DE: { country_code: 'DE', country_slug: 'germany', value: 4 },
      },
    );
    expect(merged.map((c) => c.code)).toEqual(['DE', 'US']);
  });

  it('даёт перелинковку в регионы для сопоставимых концептов', () => {
    const links = russiaDeepLinksForConcept('unemployment-rate');
    expect(links.countryHref).toBe('/russia/indicator/unemployment');
    expect(links.regionsHref).toBe('/russia/region');
    expect(links.regionRatingHref).toBe('/russia/region-rating/uroven-bezrabotitsy');
    expect(russiaDeepLinksForConcept('gdp-usd').countryHref).toBe(
      '/russia/indicator/weo-gdp-usd',
    );
    expect(russiaDeepLinksForConcept('government-debt-gdp').countryHref).toBe(
      '/russia/indicator/weo-government-debt-gdp',
    );
  });

  it('считает страны витрины из каталога API и игнорирует мок', () => {
    expect(HOME_SCOPE_COUNTRIES_FALLBACK).toBe(55);
    expect(homeScopeCountriesCount({
      countries: [
        { code: 'DE', is_active: true },
        { code: 'RU', is_active: true },
        { code: 'XX', is_active: false },
      ],
      total: 3,
    })).toBe(2);
    expect(homeScopeCountriesCount({
      _fromMock: true,
      countries: [{ code: 'DE' }],
      total: 10,
    })).toBeNull();
    expect(homeScopeCountriesCount({
      _fromMock: true,
      countries: [{ code: 'DE' }],
      total: 10,
    }, { allowMock: true })).toBe(1);
    expect(homeScopeCountriesCount({ total: 55, countries: [] })).toBe(55);
  });
});
