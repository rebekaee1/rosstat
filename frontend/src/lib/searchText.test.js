import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';
import {
  inCountry, inflationTitle, plainTitle, plainUnit,
} from './searchText';

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
