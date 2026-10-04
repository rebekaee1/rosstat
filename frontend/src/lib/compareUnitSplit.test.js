import { describe, expect, it } from 'vitest';
import { formatValueSplit, splitUnit } from './compareUnitSplit';

describe('compareUnitSplit', () => {
  it('keeps a short unit with the number and moves the explanation out', () => {
    expect(splitUnit('% от среднего по ЕС на душу населения')).toEqual({
      short: '%', tail: 'от среднего по ЕС на душу населения',
    });
    expect(splitUnit('п.п. от среднего по ЕС').short).toBe('п.п.');
  });

  it('leaves simple units intact', () => {
    expect(splitUnit('%')).toEqual({ short: '%', tail: '' });
    expect(splitUnit('млрд $')).toEqual({ short: 'млрд $', tail: '' });
    expect(splitUnit('')).toEqual({ short: '', tail: '' });
  });

  it('formats the big number without the long tail', () => {
    const r = formatValueSplit(59.2, '% от среднего по ЕС на душу населения');
    expect(r.main).toBe('59,20%');
    expect(r.tail).toBe('от среднего по ЕС на душу населения');
  });

  it('shows a dash for missing values', () => {
    expect(formatValueSplit(null, '%').main).toBe('—');
  });
});
