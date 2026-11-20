import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';
import { searchSuggestions } from './searchExamples';
import { withTaxEra } from './searchGroups';
import {
  SECTION_TOURISM, cleanRecentPages, cleanRecentQueries, searchSectionOf,
} from './searchSection';

const ru = (key, vars) => translate(key, vars, 'ru');
const en = (key, vars) => translate(key, vars, 'en');

describe('searchSectionOf: раздел по адресу страницы', () => {
  it('страницы «Туризма»', () => {
    expect(searchSectionOf('/russia/category/tourism')).toBe(SECTION_TOURISM);
    expect(searchSectionOf('/russia/indicator/tour-hotel-nights')).toBe(SECTION_TOURISM);
    expect(searchSectionOf('/russia/region/krasnodarskiy-kray/tour-tax')).toBe(SECTION_TOURISM);
    expect(searchSectionOf('/russia/region-rating/tour-nalog-za-god')).toBe(SECTION_TOURISM);
  });

  it('остальные страницы — без раздела', () => {
    expect(searchSectionOf('/')).toBeNull();
    expect(searchSectionOf('/russia/category/prices')).toBeNull();
    expect(searchSectionOf('/russia/indicator/key-rate')).toBeNull();
    expect(searchSectionOf('/russia/category/tourism-fake-section-x')).toBeNull();
    expect(searchSectionOf(undefined)).toBeNull();
  });
});

describe('«Популярное» по разделу', () => {
  it('в «Туризме» — туристские запросы на обоих языках', () => {
    const texts = searchSuggestions(ru, undefined, SECTION_TOURISM).map((item) => item.text);
    expect(texts).toContain('Турция');
    expect(texts.join(' ')).not.toMatch(/яйц|сум/i);
    expect(searchSuggestions(en, undefined, SECTION_TOURISM).map((item) => item.text)).toContain('Turkey');
  });

  it('вне раздела прежний список', () => {
    const texts = searchSuggestions(ru).map((item) => item.text);
    expect(texts).toContain('Цены на яйца в Москве');
    expect(searchSuggestions(ru, 3)).toHaveLength(3);
    expect(searchSuggestions(ru, 3, 'unknown')).toHaveLength(3);
  });
});

describe('cleanRecentPages: недавнее без дублей и на языке интерфейса', () => {
  const page = (title, path) => ({ title, path, kind: 'other', ts: 1 });

  it('одно название и один адрес показываются один раз', () => {
    const rows = cleanRecentPages([
      page('Туризм в России', '/russia/category/tourism'),
      page('туризм  в России', '/other'),
      page('Ключевая ставка', '/russia/indicator/key-rate'),
      page('Ключевая ставка 2', '/russia/indicator/key-rate?x=1'),
    ], 'ru');
    expect(rows.map((row) => row.title)).toEqual(['Туризм в России', 'Ключевая ставка']);
  });

  it('в английском интерфейсе русские названия скрыты, в русском — чисто английские', () => {
    const rows = [page('Tourism in Russia', '/a'), page('Туризм в России', '/b'), page('USD/RUB', '/c')];
    expect(cleanRecentPages(rows, 'en').map((row) => row.path)).toEqual(['/a', '/c']);
    expect(cleanRecentPages(rows, 'ru').map((row) => row.path)).toEqual(['/b', '/c']);
  });

  it('запросы без повторов с точностью до регистра и «ё»; название страницы не дублирует запрос', () => {
    const pages = [{ title: 'Туризм в России', path: '/t' }];
    expect(cleanRecentQueries(['Ночёвки', 'ночевки', 'туризм в россии', 'Турция'], pages)).toEqual(['Ночёвки', 'Турция']);
  });
});

describe('withTaxEra: курортный сбор и туристический налог различимы (правка 24)', () => {
  it('годы действия в подписи, оба языка', () => {
    expect(withTaxEra('Курортный сбор в России', ru)).toBe('Курортный сбор в России (до 2024 года)');
    expect(withTaxEra('Туристический налог: поступило с начала года', ru)).toBe('Туристический налог: поступило с начала года (с 2025 года)');
    expect(withTaxEra('Tourist tax in Russia', en)).toBe('Tourist tax in Russia (from 2025)');
    expect(withTaxEra('Resort fee in Russia', en)).toBe('Resort fee in Russia (until 2024)');
  });

  it('другие названия и названия с годом остаются как есть', () => {
    expect(withTaxEra('Налог на прибыль', ru)).toBe('Налог на прибыль');
    expect(withTaxEra('Туристический налог за 2025 год', ru)).toBe('Туристический налог за 2025 год');
    expect(withTaxEra('', ru)).toBe('');
  });
});
