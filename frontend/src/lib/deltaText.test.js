import { describe, expect, it } from 'vitest';
import { deltaUnit, formatDeltaNumber, formatDeltaWithUnit } from './deltaText';

describe('formatDeltaNumber', () => {
  it('рост со знаком плюс, падение с настоящим минусом', () => {
    expect(formatDeltaNumber(0.24, { locale: 'ru' })).toEqual({ flat: false, text: '+0,24' });
    expect(formatDeltaNumber(-3.1, { locale: 'ru' })).toEqual({ flat: false, text: '−3,10' });
  });

  it('ноль после округления — «без изменений», а не красное «−0,00»', () => {
    expect(formatDeltaNumber(-0.001, { locale: 'ru' }).flat).toBe(true);
    expect(formatDeltaNumber(0.004, { locale: 'ru' }).flat).toBe(true);
    expect(formatDeltaNumber(0, { locale: 'ru' }).flat).toBe(true);
  });

  it('пустое значение — без текста', () => {
    expect(formatDeltaNumber(null)).toEqual({ flat: true, text: '' });
    expect(formatDeltaNumber(undefined)).toEqual({ flat: true, text: '' });
    expect(formatDeltaNumber('abc')).toEqual({ flat: true, text: '' });
  });
});

describe('deltaUnit / formatDeltaWithUnit', () => {
  it('для процента изменение в процентных пунктах, для индекса единицы нет', () => {
    expect(deltaUnit('%', 'ru')).toBe('п. п.');
    expect(deltaUnit('%', 'en')).toBe('pp');
    expect(deltaUnit('индекс', 'ru')).toBe('');
    expect(deltaUnit('', 'ru')).toBe('');
  });

  it('число сопровождается единицей, у денег — валютой', () => {
    expect(formatDeltaWithUnit(0.25, '%', { locale: 'ru' }).text).toBe('+0,25 п. п.');
    expect(formatDeltaWithUnit(-12.4, 'млрд руб.', { locale: 'ru' }).text).toBe('−12,40 млрд ₽');
    expect(formatDeltaWithUnit(1.2, 'индекс', { pct: true, locale: 'ru' }).text).toBe('+1,20 %');
  });

  it('нулевое изменение — flat без текста', () => {
    expect(formatDeltaWithUnit(0, '%', { locale: 'ru' })).toEqual({ flat: true, text: '' });
  });
});
