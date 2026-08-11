import { describe, expect, it } from 'vitest';
import {
  activeCompatibilityNote,
  compareCompatibility,
  parseWorldCompareCode,
  sanitizeCompareCodes,
} from './compareCompatibility';

describe('compareCompatibility', () => {
  it('разбирает типизированный мировой код', () => {
    expect(parseWorldCompareCode('w:germany:unemployment-rate')).toEqual({
      countrySlug: 'germany',
      conceptSlug: 'unemployment-rate',
    });
    expect(parseWorldCompareCode('w:germany')).toBeNull();
  });

  it('разрешает страны только внутри одного concept', () => {
    expect(compareCompatibility(
      ['w:germany:unemployment-rate'],
      'w:france:unemployment-rate',
    ).allowed).toBe(true);
    expect(compareCompatibility(
      ['w:germany:unemployment-rate'],
      'w:france:hicp-index',
    ).allowed).toBe(false);
  });

  it('разрешает курируемую безработицу РФ, региона и страны', () => {
    const codes = ['unemployment', 'r:moskva:2.10.1'];
    const result = compareCompatibility(codes, 'w:germany:unemployment-rate');
    expect(result.allowed).toBe(true);
    expect(result.note).toContain('сезонной корректировки');
  });

  it('закрывает недоказанное смешение HICP и российского CPI', () => {
    expect(compareCompatibility(
      ['cpi'],
      'w:germany:hicp-index',
    ).allowed).toBe(false);
  });

  it('очищает прямой URL от несовместимых рядов', () => {
    expect(sanitizeCompareCodes([
      'w:germany:unemployment-rate',
      'w:france:hicp-index',
      'key-rate',
      'unemployment',
    ])).toEqual([
      'w:germany:unemployment-rate',
      'unemployment',
    ]);
  });

  it('показывает публичную оговорку только для смешанного bridge', () => {
    expect(activeCompatibilityNote([
      'unemployment',
      'w:germany:unemployment-rate',
    ])).toContain('возрастных границ');
    expect(activeCompatibilityNote([
      'w:germany:unemployment-rate',
      'w:france:unemployment-rate',
    ])).toBeNull();
  });
});
