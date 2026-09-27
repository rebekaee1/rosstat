import { describe, expect, it } from 'vitest';
import { bindUiLocale } from '../i18n/locale';
import {
  breadcrumbJsonLd,
  globalMarketIndicatorTrail,
  regionRatingTrail,
  russiaCategoryTrail,
  russiaIndicatorTrail,
  worldCountryTrail,
  worldRatingTrail,
} from './breadcrumbs';
import { isGlobalMarketIndicator } from './globalMarketIndicators';
import {
  countryPath,
  regionRatingHubPath,
  russiaCategoriesPath,
  russiaHomePath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';

describe('breadcrumbs', () => {
  it('uses canonical item and url fields and skips a one-item root trail', () => {
    const trail = breadcrumbJsonLd([
      { name: 'Home', path: '/' },
      { name: 'Germany', path: '/germany' },
    ], 'https://forecasteconomy.com/');
    expect(trail.itemListElement[0].item).toBe('https://forecasteconomy.com');
    expect(trail.itemListElement[1].item).toBe('https://forecasteconomy.com/germany');
    expect(trail.itemListElement.every((item) => item.item === item.url)).toBe(true);
    expect(breadcrumbJsonLd([{ name: 'Home', path: '/' }])).toBeNull();
  });

  it('валюты: самостоятельный раздел без России', () => {
    const trail = russiaCategoryTrail('Валюты', 'currencies');
    expect(trail.map((c) => c.name)).toEqual(['Главная', 'Валюты']);
    expect(trail[1].path).toBe('/currencies');
    expect(trail.map((c) => c.path)).not.toContain(russiaCategoriesPath());
  });

  it('EN-крошки валютного раздела без России', () => {
    bindUiLocale('en');
    try {
      expect(russiaCategoryTrail('Currencies', 'currencies').map((c) => c.name)).toEqual([
        'Home', 'Currencies',
      ]);
    } finally {
      bindUiLocale(undefined);
    }
  });

  it('индикатор России: Главная / Россия / категория / имя, Россия ведёт на страну', () => {
    const trail = russiaIndicatorTrail('Цены', 'prices', 'ИПЦ', 'cpi');
    expect(trail.map((c) => c.name)).toEqual(['Главная', 'Россия', 'Цены', 'ИПЦ']);
    expect(trail[1].path).toBe(russiaHomePath());
  });

  it('мировой рыночный ряд: без России — Главная / категория / имя', () => {
    expect(isGlobalMarketIndicator('ust-10y')).toBe(true);
    expect(isGlobalMarketIndicator('ust-10y-avg-month')).toBe(true);
    expect(isGlobalMarketIndicator('cpi')).toBe(false);
    const trail = globalMarketIndicatorTrail(
      'Индексы',
      'indices',
      'Доходность 10-летних гособлигаций США',
      'ust-10y',
    );
    expect(trail.map((c) => c.name)).toEqual([
      'Главная',
      'Индексы',
      'Доходность 10-летних гособлигаций США',
    ]);
    expect(trail.map((c) => c.name)).not.toContain('Россия');
  });

  it('страна мира: Главная / имя — витрины /world больше нет', () => {
    const trail = worldCountryTrail('Германия', 'germany');
    expect(trail.map((c) => c.name)).toEqual(['Главная', 'Германия']);
    expect(trail[1].path).toBe(countryPath('germany'));
  });

  it('рейтинг стран ведёт на показатель, а не на 301-путь /world/rating', () => {
    const trail = worldRatingTrail('Безработица', 'unemployment-rate');
    expect(trail.map((c) => c.name)).toEqual([
      'Главная', 'Рейтинг стран', 'Безработица',
    ]);
    expect(trail[1].path).toBe(worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT));
  });

  it('EN-крошки рейтинга не оставляют русские узлы', () => {
    bindUiLocale('en');
    try {
      expect(worldRatingTrail('GDP', 'gdp-usd').map((c) => c.name)).toEqual([
        'Home', 'Country rankings', 'GDP',
      ]);
    } finally {
      bindUiLocale(undefined);
    }
  });

  it('рейтинг регионов включает узел Рейтинг', () => {
    const trail = regionRatingTrail('Население', 'naselenie');
    expect(trail.map((c) => c.name)).toEqual([
      'Главная', 'Россия', 'Регионы', 'Рейтинг', 'Население',
    ]);
    expect(trail[3].path).toBe(regionRatingHubPath());
  });
});
