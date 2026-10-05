import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';
import {
  groupByTopic, inCountry, inflationTitle, isIndexUnit, openingLabel, plainTitle, plainUnit,
} from './searchText';

describe('раунд 2 (Z8): подписи выдачи', () => {
  it('индекс без базы узнаётся по единице', () => {
    expect(isIndexUnit('индекс 2015 = 100')).toBe(true);
    expect(isIndexUnit('index')).toBe(true);
    expect(isIndexUnit('%')).toBe(false);
    expect(isIndexUnit('')).toBe(false);
  });

  it('«Открываем: …» только из названия: числа убираются, годы остаются', () => {
    expect(openingLabel('Инфляция в Турции, 34,9 %')).toBe('Инфляция в Турции');
    expect(openingLabel('Индекс цен 1 645,7')).toBe('Индекс цен');
    expect(openingLabel('ВВП России, 2024')).toBe('ВВП России, 2024');
    expect(openingLabel('Курс доллара — 83,48')).toBe('Курс доллара');
    expect(openingLabel('123')).toBe('123');
    expect(openingLabel('')).toBe('');
  });

  it('группы по темам: крупные первыми, «прочее» последним', () => {
    const rows = ['a', 'b', 'c', 'd', 'e'];
    const topic = { a: 'chart', b: 'rates', c: 'prices', d: 'prices', e: 'prices' };
    const groups = groupByTopic(rows, (row) => topic[row]);
    expect(groups.map((g) => g.id)).toEqual(['prices', 'rates', 'chart']);
    expect(groups[0].rows).toEqual(['c', 'd', 'e']);
  });
});

describe('plainTitle', () => {
  it('убирает базу индекса, цепные объёмы и расшифровывает служебные слова', () => {
    expect(plainTitle('Индекс цен (2015 = 100)')).toBe('Индекс цен');
    expect(plainTitle('ВВП, цепные объёмы')).toBe('ВВП');
    expect(plainTitle('ИПЦ')).toBe('Потребительские цены');
    expect(plainTitle('HICP, инфляция')).toBe('Потребительские цены (метод ЕС), инфляция');
    expect(plainTitle('Сальдо бюджета сектора государственного управления')).toBe('Сальдо бюджета государства');
    expect(plainTitle('Упрощённый энергобаланс')).toBe('Энергобаланс');
    expect(plainTitle('Денежный агрегат M2')).toBe('Денежная масса M2');
  });

  it('не ломает слова, которые только содержат аббревиатуру, и не оставляет пустого названия', () => {
    expect(plainTitle('Рыночный ИПЦИ')).toBe('Рыночный ИПЦИ');
    expect(plainTitle('(2015 = 100)')).toBe('(2015 = 100)');
  });

  it('английские названия: HICP и general government', () => {
    expect(plainTitle('HICP at constant tax rates', 'en')).toBe('Consumer prices (EU method) at constant tax rates');
    expect(plainTitle('Budget balance of general government', 'en')).toBe('Budget balance of government');
    expect(plainTitle('Index, 2015=100', 'en')).toBe('Index');
  });
});

describe('plainUnit', () => {
  it('говорит человеческими словами', () => {
    expect(plainUnit('USD/баррель')).toBe('$ за баррель');
    expect(plainUnit('100 млн юаней')).toBe('сотни млн юаней');
    expect(plainUnit('тыс. т н. э.')).toBe('тыс. тонн нефтяного эквивалента');
    expect(plainUnit('% ЭАН')).toBe('% от рабочей силы');
    expect(plainUnit('USD/barrel', 'en')).toBe('$ per barrel');
    expect(plainUnit('индекс (2015 = 100)')).toBe('индекс');
    expect(plainUnit('index 2015=100', 'en')).toBe('index');
    expect(plainUnit('%')).toBe('%');
    expect(plainUnit('')).toBe('');
  });
});

describe('inflation titles', () => {
  const ru = (key, vars) => translate(key, vars, 'ru');
  const en = (key, vars) => translate(key, vars, 'en');
  it('склоняет известные страны', () => {
    expect(inCountry('Франция')).toBe('во Франции');
    expect(inCountry('Мальта')).toBe('на Мальте');
    expect(inCountry('Неведомая')).toBeNull();
    expect(inflationTitle('Турция', ru)).toBe('Инфляция в Турции');
    expect(inflationTitle('Неведомая', ru)).toBe('Инфляция: Неведомая');
    expect(inflationTitle('Turkey', en, 'en')).toBe('Inflation in Turkey');
    expect(inflationTitle('United Kingdom', en, 'en')).toBe('Inflation in the United Kingdom');
  });
});
