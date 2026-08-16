import { describe, expect, it } from 'vitest';
import { ratingHref } from './worldApi';

const RATING_CONCEPTS = [
  { slug: 'unemployment-rate', name: 'Уровень безработицы' },
  { slug: 'hicp-index', name: 'Гармонизированный индекс потребительских цен' },
];

describe('ratingHref', () => {
  it('ведёт в полный рейтинг только по показателям, которые сервер отдал как рейтинговые', () => {
    expect(ratingHref('unemployment-rate', RATING_CONCEPTS)).toBe('/world/rating/unemployment-rate');
    expect(ratingHref('hicp-index', RATING_CONCEPTS)).toBe('/world/rating/hicp-index');
  });

  it('молчит по денежным показателям — у них рейтинг отдаёт 404 до пересчёта в доллары', () => {
    expect(ratingHref('gdp-volume-annual', RATING_CONCEPTS)).toBeNull();
    expect(ratingHref('gdp-volume-quarterly', RATING_CONCEPTS)).toBeNull();
  });

  it('молчит, пока список не загружен', () => {
    expect(ratingHref('unemployment-rate', undefined)).toBeNull();
    expect(ratingHref('unemployment-rate', [])).toBeNull();
    expect(ratingHref('', RATING_CONCEPTS)).toBeNull();
  });
});
