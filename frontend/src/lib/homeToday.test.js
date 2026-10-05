import { describe, expect, it } from 'vitest';
import {
  buildTodayTiles, ladderHeights, metricTone, parseShownNumber, sparkTrend, splitEconomy, splitPercent, yearOfItem,
} from './homeToday';

const item = (code, value, extra = {}) => ({
  country_code: code, country_slug: code.toLowerCase(), country_name: code, indicator_code: `${code}-x`, date: '2025-12-31', value, unit: '%', ...extra,
});

const GDP = {
  items: [
    item('US', 30767, { unit: 'млрд $' }),
    item('CN', 19400, { unit: 'млрд $' }),
    item('DE', 4900, { unit: 'млрд $' }),
    item('TV', 0.06, { unit: 'млрд $' }),
  ],
};
const PRICES = {
  items: [item('TR', 34.9), item('RU', 8.1), item('US', 2.9), item('JP', 2.1), item('CH', 0.4)],
};
const JOBS = {
  items: [item('JP', 2.5), item('DE', 3.1), item('ES', 11.6), item('XX', 0)],
};

describe('homeToday', () => {
  it('ladderHeights: пустой список, диапазон 0..1 и потолок для выбросов', () => {
    expect(ladderHeights([])).toEqual([]);
    const heights = ladderHeights([200, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]);
    expect(Math.max(...heights)).toBeLessThanOrEqual(1);
    expect(Math.min(...heights)).toBeGreaterThan(0);
    // Выброс не сплющивает остальных: 3 заметно выше 1.
    expect(heights[1]).toBeGreaterThan(heights[4]);
  });

  it('splitEconomy: русский и английский, триллионы, миллиарды, миллионы', () => {
    expect(splitEconomy(30767, 'ru')).toEqual({ num: '30,8', unit: 'трлн $' });
    expect(splitEconomy(30767, 'en')).toEqual({ num: '$30.8', unit: 'trillion' });
    expect(splitEconomy(580, 'ru').unit).toBe('млрд $');
    expect(splitEconomy(0.4, 'ru').unit).toBe('млн $');
    expect(splitEconomy(0, 'ru')).toBeNull();
  });

  it('parseShownNumber: число, знаки после запятой и обрамление для счёта цифр', () => {
    expect(parseShownNumber('30,8', 'ru')).toEqual({ prefix: '', value: 30.8, digits: 1, suffix: '' });
    expect(parseShownNumber('$30.8', 'en')).toEqual({ prefix: '$', value: 30.8, digits: 1, suffix: '' });
    expect(parseShownNumber('4\u00a0900', 'ru')).toEqual({ prefix: '', value: 4900, digits: 0, suffix: '' });
    expect(parseShownNumber('1,215', 'en')).toEqual({ prefix: '', value: 1215, digits: 0, suffix: '' });
    expect(parseShownNumber('—', 'ru')).toBeNull();
    expect(parseShownNumber('', 'ru')).toBeNull();
  });

  it('splitPercent и yearOfItem', () => {
    expect(splitPercent(34.94, 'ru')).toEqual({ num: '34,9', unit: '%' });
    expect(splitPercent('x', 'ru')).toBeNull();
    expect(yearOfItem({ date: '2025-12-31' })).toBe(2025);
    expect(yearOfItem({})).toBeNull();
  });

  it('четыре плитки: крупнейшая экономика, быстрее всех дорожает, меньше всего безработных, Россия', () => {
    const tiles = buildTodayTiles({ gdp: GDP, inflation: PRICES, unemployment: JOBS, locale: 'ru' });
    expect(tiles.map((tile) => tile.id)).toEqual(['economy', 'prices', 'jobs', 'home']);
    expect(tiles[0].item.country_code).toBe('US');
    expect(tiles[0].ladder.rank).toBe(1);
    expect(tiles[1].item.country_code).toBe('TR');
    // Ноль безработицы — это отсутствие данных, а не рекорд.
    expect(tiles[2].item.country_code).toBe('JP');
    expect(tiles[3].item.country_code).toBe('RU');
    expect(tiles[3].ladder.rank).toBe(2);
    expect(tiles[3].ladder.total).toBe(5);
    for (const tile of tiles) {
      expect(tile.ladder.bars.length).toBe(tile.ladder.total);
      expect(tile.ladder.mark).toBe(tile.ladder.rank - 1);
    }
  });

  it('на английском домашняя страна США; нет страны в срезе: «обычная страна» без названия', () => {
    const en = buildTodayTiles({ gdp: GDP, inflation: PRICES, unemployment: JOBS, locale: 'en' });
    expect(en[3].id).toBe('home');
    expect(en[3].item.country_code).toBe('US');
    const withoutHome = buildTodayTiles({
      gdp: GDP, inflation: { items: PRICES.items.filter((i) => i.country_code !== 'RU') }, unemployment: JOBS, locale: 'ru',
    });
    expect(withoutHome[3].id).toBe('median');
    expect(withoutHome[3].country).toBeNull();
  });

  it('данных мало или нет: пустой список, без выдуманных чисел', () => {
    expect(buildTodayTiles({ locale: 'ru' })).toEqual([]);
    expect(buildTodayTiles({ gdp: { items: GDP.items.slice(0, 2) }, locale: 'ru' })).toEqual([]);
  });

  it('название страны берёт из каталога на языке сайта', () => {
    const countries = new Map([['US', { code: 'US', name: 'США', name_en: 'United States' }]]);
    const tiles = buildTodayTiles({
      gdp: GDP, locale: 'ru', countriesByCode: countries, localeName: (c) => c.name,
    });
    expect(tiles[0].country).toBe('США');
  });

  it('metricTone: инфляция и безработица делятся на спокойно, внимание и тревожно', () => {
    expect(metricTone('inflation', 2.3)).toBe('good');
    expect(metricTone('inflation', 7)).toBe('warn');
    expect(metricTone('inflation', -0.5)).toBe('warn');
    expect(metricTone('inflation', 34.9)).toBe('bad');
    expect(metricTone('unemployment', 3.2)).toBe('good');
    expect(metricTone('unemployment', 7)).toBe('warn');
    expect(metricTone('unemployment', 12)).toBe('bad');
    expect(metricTone('unemployment', null)).toBeNull();
    expect(metricTone('other', 1)).toBeNull();
  });

  it('sparkTrend: рост, падение и «ровно»', () => {
    expect(sparkTrend([1, 2, 3, 4, 5, 6, 8])).toBe('up');
    expect(sparkTrend([8, 7, 6, 5, 4, 3, 2])).toBe('down');
    expect(sparkTrend([5, 5, 5, 5.05, 5, 5, 5.02])).toBe('flat');
    expect(sparkTrend([1, 2])).toBe('flat');
  });
});
