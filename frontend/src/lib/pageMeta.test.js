import { describe, it, expect } from 'vitest';
import pageMeta, {
  getPageSeo,
  getCategorySeo,
  worldCountryTitle,
  worldCountryDescription,
  worldIndicatorsPhrase,
} from './pageMeta';
import { CATEGORIES } from './categories';
import {
  formatTodayNumber,
  formatTodayRuDate,
  todayChangePhrase,
  buildTodayIndicatorMeta,
} from './todayFormat';

describe('pageMeta single source', () => {
  it('exposes pages and categories from generated mirror', () => {
    expect(Object.keys(pageMeta.pages).length).toBeGreaterThanOrEqual(10);
    expect(getPageSeo('about').h1).toBe('О проекте Forecast Economy');
    expect(getPageSeo('methodology').h1).toBe('Методология прогнозирования');
    expect(getCategorySeo('prices').h1).toBe('Цены и инфляция в России');
  });

  it('demographics EN twin comes from PAGE_META_EN mirror', () => {
    const en = getPageSeo('demographics', 'en');
    expect(en.title).toBe("Age structure of Russia's population");
    expect(en.title).not.toMatch(/[А-Яа-яЁё]/);
    expect(getPageSeo('demographics', 'ru').title).toContain('Возрастная структура');
  });

  it('home and category EN titles come from PAGE_META_EN (preview_locale path)', () => {
    const homeEn = getPageSeo('home', 'en');
    expect(homeEn.title).toBe(
      'Forecast Economy — macroeconomic indicators for countries and Russia',
    );
    expect(homeEn.title).not.toMatch(/[А-Яа-яЁё]/);
    expect(homeEn.description).not.toMatch(/[А-Яа-яЁё]/);
    expect(getPageSeo('home', 'ru').title).toContain('макроэкономические');

    const pricesEn = getCategorySeo('prices', 'en');
    expect(pricesEn.title).toBe('Prices and inflation in Russia');
    expect(pricesEn.title).not.toMatch(/[А-Яа-яЁё]/);

    const russiaEn = getPageSeo('russia', 'en');
    expect(russiaEn.h1).toBe('Russia');
    expect(russiaEn.intro).not.toMatch(/[А-Яа-яЁё]/);
    expect(getPageSeo('russia', 'ru').h1).toBe('Россия');

    const catsEn = getPageSeo('russia-categories', 'en');
    expect(catsEn.h1).toBe('Russia indicator categories');
    expect(catsEn.intro).not.toMatch(/[А-Яа-яЁё]/);
    expect(getPageSeo('russia-categories', 'ru').h1).toContain('Категории');
  });

  it('CATEGORIES seo fields match generated CATEGORY_META', () => {
    for (const cat of CATEGORIES) {
      const seo = getCategorySeo(cat.slug);
      expect(cat.seoTitle).toBe(seo.title);
      expect(cat.seoDescription).toBe(seo.description);
      expect(cat.seoH1).toBe(seo.h1);
      expect(cat.name).toBe(seo.name);
    }
  });

  it('world country title uses genitive template', () => {
    expect(worldCountryTitle('germany', 'Германия')).toBe(
      'Экономика Германии: статистика и показатели',
    );
    expect(worldCountryTitle('germany', 'Германия', 'ru')).toBe(
      'Экономика Германии: статистика и показатели',
    );
    expect(worldIndicatorsPhrase(22)).toBe('22 показателя');
    expect(worldCountryDescription('germany', 'Германия', 22)).toContain('Евростата');
  });

  it('world country EN title for Sweden has no Cyrillic', () => {
    const title = worldCountryTitle('sweden', 'Sweden', 'en');
    expect(title).toBe('Economy of Sweden: statistics and indicators');
    expect(title).not.toMatch(/[А-Яа-яЁё]/);
    expect(worldCountryTitle('sweden', 'Швеция', 'ru')).toBe(
      'Экономика Швеции: статистика и показатели',
    );
    const desc = worldCountryDescription('sweden', 'Sweden', 22, {
      locale: 'en',
      sourcePhrase: 'Eurostat',
    });
    expect(desc).toContain('Sweden');
    expect(desc).toContain('Eurostat');
    expect(desc).not.toMatch(/[А-Яа-яЁё]/);
    expect(worldIndicatorsPhrase(1, 'en')).toBe('1 indicator');
    expect(worldIndicatorsPhrase(22, 'en')).toBe('22 indicators');
  });
});

describe('todayFormat mirrors seo_today', () => {
  it('strips trailing zeros like server _format_number', () => {
    expect(formatTodayNumber(6)).toBe('6');
    expect(formatTodayNumber(6.0)).toBe('6');
    expect(formatTodayNumber(6.5)).toBe('6,5');
    expect(formatTodayNumber(106.25)).toBe('106,3');
  });

  it('formats genitive dates', () => {
    expect(formatTodayRuDate('2026-08-16')).toBe('16 августа 2026 года');
  });

  it('builds meta only with source and change phrase', () => {
    const meta = buildTodayIndicatorMeta({
      query: 'Инфляция',
      value: 6.0,
      prevValue: 5.8,
      unit: '%',
      lastDate: '2026-07-01',
      frequency: 'monthly',
      source: 'Росстат',
    });
    expect(meta.title).toContain('Инфляция');
    expect(meta.title).toContain('6');
    expect(meta.description).toContain('Источник — Росстат');
    expect(meta.description).not.toContain('undefined');
    expect(todayChangePhrase(6, 5.8, '%')).toContain('п. п.');
  });
});
