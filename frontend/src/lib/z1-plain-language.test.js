import { describe, expect, it } from 'vitest';
import { localizeWorldUnit } from './worldApi';
import { indicatorPublicName, tidyPublicName } from './worldViewModes';
import { pickerLabel } from './pickerLabels';

describe('localizeWorldUnit without jargon', () => {
  it('spells out Eurostat shorthand', () => {
    expect(localizeWorldUnit('Index, 2015=100 (NSA)', 'en')).toBe('Index, 2015 = 100, not seasonally adjusted');
    expect(localizeWorldUnit('chain-linked volumes, 2015, million euro', 'en')).toBe('in 2015 prices, million euro');
    expect(localizeWorldUnit('% ЭАН', 'ru')).toBe('% от рабочей силы');
    expect(localizeWorldUnit('индекс 2015=100', 'ru')).toBe('индекс 2015 = 100');
  });
});

describe('tidyPublicName', () => {
  it('drops the date range, the frequency tail and the abbreviation', () => {
    expect(indicatorPublicName({ name_en: 'HICP at constant tax rates - monthly data (index) (2002-2025)' }, 'en'))
      .toBe('Harmonised consumer price index at constant tax rates');
  });
  it('does not repeat "index" at the tail of a title that already says it', () => {
    expect(tidyPublicName('Гармонизированный индекс потребительских цен, индекс (2015 = 100)', 'ru'))
      .toBe('Гармонизированный индекс потребительских цен');
    expect(tidyPublicName('Harmonised index of consumer prices, index (2015 = 100)', 'en'))
      .toBe('Harmonised index of consumer prices');
  });
  it('keeps a title that has no index of its own', () => {
    expect(tidyPublicName('Цены на жильё, индекс (2015 = 100)', 'ru')).toBe('Цены на жильё, индекс (2015 = 100)');
  });
});

describe('pickerLabel', () => {
  it('expands the labour-force shorthand', () => {
    expect(pickerLabel('% ЭАН', 'ru')).toBe('% от рабочей силы');
  });
});
