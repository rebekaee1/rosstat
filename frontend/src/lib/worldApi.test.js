import { describe, expect, it } from 'vitest';
import { ratingHref, localizeWorldUnit } from './worldApi';

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

describe('localizeWorldUnit', () => {
  it('переводит млрд $ на EN и не трогает RU', () => {
    expect(localizeWorldUnit('млрд $', 'en')).toBe('billion $');
    expect(localizeWorldUnit('млрд $', 'ru')).toBe('млрд $');
    expect(localizeWorldUnit('% ВВП', 'en')).toBe('% of GDP');
    expect(localizeWorldUnit('% ЭАН', 'en')).toBe('% of the labour force');
    expect(localizeWorldUnit('тыс. человек', 'en')).toBe('ths persons');
  });
});
