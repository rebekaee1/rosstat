import { describe, expect, it, vi } from 'vitest';
import api from './api';
import { ratingHref, localizeWorldUnit, fetchWorldCompareOrCard } from './worldApi';

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

describe('fetchWorldCompareOrCard', () => {
  it('после 404 понятия сравнения берёт национальную карточку', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation((url) => {
      if (url === '/world/compare/series/united-states/us-unemployment-rate') {
        const err = new Error('not found');
        err.response = { status: 404 };
        return Promise.reject(err);
      }
      if (url === '/world/indicators/united-states/us-unemployment-rate') {
        return Promise.resolve({
          data: {
            country: { slug: 'united-states', name: 'США', name_en: 'United States' },
            indicator: {
              code: 'us-unemployment-rate',
              name: 'Уровень безработицы',
              name_en: 'Unemployment Rate',
              unit: '%',
              frequency: 'monthly',
              concept_slug: 'unemployment-rate',
            },
          },
        });
      }
      if (url === '/world/indicators/united-states/us-unemployment-rate/data') {
        return Promise.resolve({
          data: { points: [{ date: '2025-08-01', value: 4.3 }] },
        });
      }
      const err = new Error(`unmocked ${url}`);
      err.response = { status: 404 };
      return Promise.reject(err);
    });
    try {
      const payload = await fetchWorldCompareOrCard('united-states', 'us-unemployment-rate');
      expect(payload.meta.country_slug).toBe('united-states');
      expect(payload.meta.concept_name).toBe('Уровень безработицы');
      expect(payload.data).toEqual([{ date: '2025-08-01', value: 4.3 }]);
    } finally {
      get.mockRestore();
    }
  });

  it('не падает на 409 curated-конфликта — тоже карточка', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation((url) => {
      if (url.startsWith('/world/compare/series/')) {
        const err = new Error('conflict');
        err.response = { status: 409 };
        return Promise.reject(err);
      }
      if (url.endsWith('/data')) {
        return Promise.resolve({ data: { data: [{ date: '2024-01-01', value: 1 }] } });
      }
      return Promise.resolve({
        data: {
          country: { slug: 'united-states', name: 'США' },
          indicator: { code: 'us-unemployment-rate', name: 'UR', unit: '%' },
        },
      });
    });
    try {
      const payload = await fetchWorldCompareOrCard('united-states', 'us-unemployment-rate');
      expect(payload.data[0].value).toBe(1);
    } finally {
      get.mockRestore();
    }
  });
});
