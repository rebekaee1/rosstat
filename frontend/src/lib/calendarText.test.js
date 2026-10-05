import { describe, it, expect } from 'vitest';
import { plainEventTitle, localizeReferencePeriod, pluralForm, groupDescription } from './calendarText';

describe('plainEventTitle', () => {
  it('turns service wording into plain titles', () => {
    expect(plainEventTitle('Заседание ЦБ по ключевой ставке (опорное)', 'ru')).toBe('Решение по ключевой ставке');
    expect(plainEventTitle('Заседание ЦБ по ключевой ставке (промежуточное)', 'ru')).toBe('Решение по ключевой ставке');
    expect(plainEventTitle('Ставка RUONIA', 'ru')).toBe('Однодневная ставка межбанковских кредитов');
    expect(plainEventTitle('CBR Key Rate Decision (core)', 'en')).toBe('Key rate decision');
    expect(plainEventTitle('RUONIA Rate', 'en')).toBe('Overnight interbank rate');
  });
  it('drops a trailing abbreviation in brackets', () => {
    expect(plainEventTitle('Индекс потребительских цен (ИПЦ)', 'ru')).toBe('Индекс потребительских цен');
    expect(plainEventTitle('Consumer Price Index (CPI)', 'en')).toBe('Consumer Price Index');
  });
});

describe('localizeReferencePeriod', () => {
  it('keeps Russian periods and spells quarters out', () => {
    expect(localizeReferencePeriod('сентябрь 2026', 'ru')).toBe('сентябрь 2026');
    expect(localizeReferencePeriod('Q2 2026', 'ru')).toBe('II квартал 2026');
  });
  it('translates months and quarters into English and hides what it cannot translate', () => {
    expect(localizeReferencePeriod('сентябрь 2026', 'en')).toBe('September 2026');
    expect(localizeReferencePeriod('Q2 2026', 'en')).toBe('Q2 2026');
    expect(localizeReferencePeriod('II квартал 2026', 'en')).toBe('Q2 2026');
    expect(localizeReferencePeriod('за какой-то период', 'en')).toBe('');
    expect(localizeReferencePeriod('', 'en')).toBe('');
  });
});

describe('pluralForm', () => {
  it('declines Russian counts and keeps English to one/many', () => {
    expect(pluralForm(1, 'ru')).toBe('one');
    expect(pluralForm(2, 'ru')).toBe('few');
    expect(pluralForm(7, 'ru')).toBe('many');
    expect(pluralForm(21, 'ru')).toBe('one');
    expect(pluralForm(12, 'ru')).toBe('many');
    expect(pluralForm(2, 'en')).toBe('many');
    expect(pluralForm(1, 'en')).toBe('one');
  });
});

describe('groupDescription', () => {
  it('uses the head indicator for nested codes', () => {
    const events = [
      { indicator_code: 'cpi-services', description: 'services' },
      { indicator_code: 'cpi', description: 'headline' },
      { indicator_code: 'cpi-food', description: 'food' },
    ];
    expect(groupDescription(events)).toBe('headline');
  });
  it('leaves the description out when parts are unrelated', () => {
    const events = [
      { indicator_code: 'exports', description: 'e' },
      { indicator_code: 'imports', description: 'i' },
    ];
    expect(groupDescription(events)).toBeUndefined();
  });
  it('keeps a shared description', () => {
    expect(groupDescription([{ indicator_code: 'a', description: 'x' }, { indicator_code: 'b', description: 'x' }])).toBe('x');
  });
});
