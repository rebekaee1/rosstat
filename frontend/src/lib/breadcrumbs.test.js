import { describe, expect, it } from 'vitest';
import {
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
  it('категория России включает хаб Категории', () => {
    const trail = russiaCategoryTrail('Валюты', 'currencies');
    expect(trail.map((c) => c.name)).toEqual(['Главная', 'Россия', 'Категории', 'Валюты']);
    expect(trail[1].path).toBe(russiaHomePath());
    expect(trail[2].path).toBe(russiaCategoriesPath());
  });

  it('индикатор России: Главная / Россия / категория / имя', () => {
    const trail = russiaIndicatorTrail('Цены', 'prices', 'ИПЦ', 'cpi');
    expect(trail.map((c) => c.name)).toEqual(['Главная', 'Россия', 'Цены', 'ИПЦ']);
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

  it('рейтинг регионов включает узел Рейтинг', () => {
    const trail = regionRatingTrail('Население', 'naselenie');
    expect(trail.map((c) => c.name)).toEqual([
      'Главная', 'Россия', 'Регионы', 'Рейтинг', 'Население',
    ]);
    expect(trail[3].path).toBe(regionRatingHubPath());
  });
});
