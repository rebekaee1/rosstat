import { describe, expect, it } from 'vitest';
import {
  activeCompatibilityNote,
  compareCompatibility,
  parseSubnationalCompareCode,
  parseWorldCompareCode,
  sanitizeCompareCodes,
} from './compareCompatibility';

describe('compareCompatibility', () => {
  it('разбирает типизированный мировой код', () => {
    expect(parseWorldCompareCode('w:germany:unemployment-rate')).toEqual({
      countrySlug: 'germany',
      conceptSlug: 'unemployment-rate',
    });
    expect(parseWorldCompareCode('w:united-states:us-unemployment-rate')).toEqual({
      countrySlug: 'united-states',
      conceptSlug: 'us-unemployment-rate',
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
    expect(result.noteKey).toBe('compare.compat.note.unemployment');
  });

  it('закрывает недоказанное смешение HICP и российского CPI', () => {
    expect(compareCompatibility(
      ['cpi'],
      'w:germany:hicp-index',
    ).allowed).toBe(false);
  });

  it('разрешает российский ВВП из compare-catalog рядом со странами', () => {
    expect(compareCompatibility(
      ['w:united-states:gdp-usd', 'w:canada:gdp-usd'],
      'w:russia:gdp-usd',
    ).allowed).toBe(true);
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
    ])).toBe('compare.compat.note.unemployment');
    expect(activeCompatibilityNote([
      'w:germany:unemployment-rate',
      'w:france:unemployment-rate',
    ])).toBeNull();
  });

  it('разбирает субнациональный код штата', () => {
    expect(parseSubnationalCompareCode('s:united-states:california:unemployment-rate')).toEqual({
      countrySlug: 'united-states',
      regionSlug: 'california',
      indicatorCode: 'unemployment-rate',
    });
    expect(parseSubnationalCompareCode('s:united-states:california')).toBeNull();
  });

  it('разрешает штаты одной страны и национальный ряд той же страны', () => {
    expect(compareCompatibility(
      ['s:united-states:california:unemployment-rate'],
      's:united-states:texas:unemployment-rate',
    ).allowed).toBe(true);
    expect(compareCompatibility(
      ['s:united-states:california:unemployment-rate'],
      'w:united-states:us-unemployment-rate',
    ).allowed).toBe(true);
    expect(compareCompatibility(
      ['w:united-states:us-unemployment-rate'],
      's:united-states:california:unemployment-rate',
    ).allowed).toBe(true);
  });

  it('закрывает штат США с чужой страной или макро РФ', () => {
    expect(compareCompatibility(
      ['s:united-states:california:unemployment-rate'],
      'w:germany:unemployment-rate',
    ).allowed).toBe(false);
    expect(compareCompatibility(
      ['s:united-states:california:unemployment-rate'],
      'unemployment',
    ).allowed).toBe(false);
  });
});
