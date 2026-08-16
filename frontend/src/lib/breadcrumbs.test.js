import { describe, expect, it } from 'vitest';
import {
  regionRatingTrail,
  russiaCategoryTrail,
  russiaIndicatorTrail,
  worldCountryTrail,
} from './breadcrumbs';
import {
  regionRatingHubPath,
  russiaCategoriesPath,
  russiaHomePath,
  worldHubPath,
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

  it('страна мира: Главная / Страны / имя', () => {
    const trail = worldCountryTrail('Германия', 'germany');
    expect(trail.map((c) => c.name)).toEqual(['Главная', 'Страны', 'Германия']);
    expect(trail[1].path).toBe(worldHubPath());
  });

  it('рейтинг регионов включает узел Рейтинг', () => {
    const trail = regionRatingTrail('Население', 'naselenie');
    expect(trail.map((c) => c.name)).toEqual([
      'Главная', 'Россия', 'Регионы', 'Рейтинг', 'Население',
    ]);
    expect(trail[3].path).toBe(regionRatingHubPath());
  });
});
