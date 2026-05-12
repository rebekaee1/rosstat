import { describe, it, expect } from 'vitest';
import {
  buildFrequencyItems,
  labelForFrequency,
} from './frequencySwitcher';

describe('labelForFrequency', () => {
  it('maps known frequencies to Russian labels', () => {
    expect(labelForFrequency('weekly')).toBe('Недельные');
    expect(labelForFrequency('monthly')).toBe('Месячные');
    expect(labelForFrequency('quarterly')).toBe('Квартальные');
    expect(labelForFrequency('yearly')).toBe('Годовые');
    expect(labelForFrequency('annual')).toBe('Годовые');
  });

  it('returns raw frequency when unknown', () => {
    expect(labelForFrequency('hourly')).toBe('hourly');
  });

  it('returns dash for empty input', () => {
    expect(labelForFrequency(null)).toBe('—');
    expect(labelForFrequency(undefined)).toBe('—');
    expect(labelForFrequency('')).toBe('—');
  });
});

describe('buildFrequencyItems', () => {
  it('returns empty when no currentCode', () => {
    expect(buildFrequencyItems({})).toEqual([]);
  });

  it('returns empty when neither alternate nor primary set (single indicator)', () => {
    const items = buildFrequencyItems({
      currentCode: 'cpi',
      currentFrequency: 'monthly',
    });
    expect(items).toEqual([]);
  });

  it('builds [current=primary, alt] when alternate_frequencies has entries', () => {
    const items = buildFrequencyItems({
      currentCode: 'exports',
      currentFrequency: 'quarterly',
      alternateFrequencies: { monthly: 'exports-monthly' },
    });
    expect(items).toHaveLength(2);
    expect(items[0]).toEqual({
      code: 'exports',
      frequency: 'quarterly',
      label: 'Квартальные',
      isPrimary: true,
    });
    expect(items[1]).toEqual({
      code: 'exports-monthly',
      frequency: 'monthly',
      label: 'Месячные',
      isPrimary: false,
    });
  });

  it('builds [primary, current=secondary] when primary_indicator_code is set', () => {
    const items = buildFrequencyItems({
      currentCode: 'exports-monthly',
      currentFrequency: 'monthly',
      primaryIndicatorCode: 'exports',
    });
    expect(items).toHaveLength(2);
    expect(items[0].code).toBe('exports');
    expect(items[0].isPrimary).toBe(true);
    expect(items[1].code).toBe('exports-monthly');
    expect(items[1].isPrimary).toBe(false);
  });

  it('prefers alternate_frequencies over primary_indicator_code if both present', () => {
    const items = buildFrequencyItems({
      currentCode: 'exports',
      currentFrequency: 'quarterly',
      alternateFrequencies: { monthly: 'exports-monthly' },
      primaryIndicatorCode: 'something-else',
    });
    expect(items[0].code).toBe('exports');
    expect(items[1].code).toBe('exports-monthly');
  });

  it('skips empty entries in alternate_frequencies', () => {
    const items = buildFrequencyItems({
      currentCode: 'foo',
      currentFrequency: 'quarterly',
      alternateFrequencies: { monthly: 'foo-monthly', weekly: '' },
    });
    expect(items).toHaveLength(2);
    expect(items.map((i) => i.code)).toEqual(['foo', 'foo-monthly']);
  });

  it('handles 3-way switcher (quarterly + monthly + weekly)', () => {
    const items = buildFrequencyItems({
      currentCode: 'cpi',
      currentFrequency: 'monthly',
      alternateFrequencies: {
        weekly: 'inflation-weekly',
        quarterly: 'inflation-quarterly',
      },
    });
    expect(items).toHaveLength(3);
    expect(items[0].code).toBe('cpi');
    expect(items[0].isPrimary).toBe(true);
  });
});
