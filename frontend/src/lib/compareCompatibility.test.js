import { describe, expect, it } from 'vitest';
import {
  activeCompatibilityNote,
  compareCompatibility,
  compareCompatibilityWithTwins,
  macroTwinCode,
  macroTwinConcept,
  normalizeCompareCodes,
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

describe('двойники российских показателей (круг 9, C1)', () => {
  const has = (code) => ['w:russia:hicp-index', 'w:russia:unemployment-rate'].includes(code);

  it('ИПЦ России заменяется на инфляцию России, когда рядом ставят ту же инфляцию Турции', () => {
    expect(compareCompatibility(['cpi'], 'w:turkey:hicp-index').allowed).toBe(false);
    const result = compareCompatibilityWithTwins(['cpi'], 'w:turkey:hicp-index', has);
    expect(result.allowed).toBe(true);
    expect(result.replaceWith).toEqual(['w:russia:hicp-index']);
    expect(result.swapNoteKey).toBe('c9d.compare.twinSwapped');
  });

  it('другой показатель или нет двойника в каталоге: отказ прежний', () => {
    expect(compareCompatibilityWithTwins(['cpi'], 'w:turkey:gdp-usd', has).allowed).toBe(false);
    expect(compareCompatibilityWithTwins(['cpi'], 'w:turkey:hicp-index', () => false).allowed).toBe(false);
    expect(compareCompatibilityWithTwins(['key-rate'], 'w:turkey:hicp-index', has).allowed).toBe(false);
  });

  it('обычное сочетание проходит без замены; повтор остаётся повтором', () => {
    const ok = compareCompatibilityWithTwins(['w:russia:hicp-index'], 'w:turkey:hicp-index', has);
    expect(ok.allowed).toBe(true);
    expect(ok.replaceWith).toBeUndefined();
    expect(compareCompatibilityWithTwins(['cpi'], 'cpi', has).reasonKey).toBe('compare.compat.alreadyAdded');
  });

  it('двойник называет понятие общего набора', () => {
    expect(macroTwinConcept('cpi')).toBe('hicp-index');
    expect(macroTwinConcept('unemployment')).toBe('unemployment-rate');
    expect(macroTwinConcept('key-rate')).toBeNull();
  });
});

describe('порядок выбора не важен (круг 10, Ср1)', () => {
  const has = (code) => code.startsWith('w:russia:');

  it('сначала США, потом ВВП России: берётся двойник из общего набора стран', () => {
    expect(compareCompatibility(['w:united-states:gdp-usd'], 'weo-gdp-usd').allowed).toBe(false);
    const result = compareCompatibilityWithTwins(['w:united-states:gdp-usd'], 'weo-gdp-usd', has);
    expect(result.allowed).toBe(true);
    expect(result.addCode).toBe('w:russia:gdp-usd');
    expect(result.swapNoteKey).toBe('c9d.compare.twinSwapped');
  });

  it('ВВП России в рублях рядом с США: добавляется ВВП в долларах, и об этом сказано отдельным текстом', () => {
    const result = compareCompatibilityWithTwins(['w:united-states:gdp-usd'], 'gdp-nominal', has);
    expect(result.allowed).toBe(true);
    expect(result.addCode).toBe('w:russia:gdp-usd');
    expect(result.swapNoteKey).toBe('c10k.compare.twinRubToUsd');
  });

  it('сначала ВВП России, потом США: российский ряд заменяется двойником', () => {
    const result = compareCompatibilityWithTwins(['gdp-nominal'], 'w:united-states:gdp-usd', has);
    expect(result.allowed).toBe(true);
    expect(result.replaceWith).toEqual(['w:russia:gdp-usd']);
    expect(result.swapNoteKey).toBe('c10k.compare.twinRubToUsd');
  });

  it('оба порядка дают один и тот же набор', () => {
    const forward = normalizeCompareCodes(['w:united-states:gdp-usd', 'gdp-nominal'], has);
    const backward = normalizeCompareCodes(['gdp-nominal', 'w:united-states:gdp-usd'], has);
    expect(new Set(forward)).toEqual(new Set(['w:united-states:gdp-usd', 'w:russia:gdp-usd']));
    expect(new Set(backward)).toEqual(new Set(forward));
  });

  it('двойник уже на графике: повторно не добавляется', () => {
    const result = compareCompatibilityWithTwins(['w:russia:gdp-usd', 'w:united-states:gdp-usd'], 'weo-gdp-usd', has);
    expect(result.allowed).toBe(false);
    expect(result.reasonKey).toBe('compare.compat.alreadyAdded');
  });

  it('показатель без двойника по-прежнему не сочетается с рядами стран', () => {
    expect(compareCompatibilityWithTwins(['w:united-states:gdp-usd'], 'key-rate', has).allowed).toBe(false);
    expect(compareCompatibilityWithTwins(['w:united-states:gdp-usd'], 'weo-gdp-usd', () => false).allowed).toBe(false);
    expect(normalizeCompareCodes(['key-rate', 'w:united-states:gdp-usd'], has)).toEqual(['key-rate']);
  });

  it('двойники ВВП на душу, баланса бюджета и госдолга названы', () => {
    expect(macroTwinConcept('weo-gdp-per-capita-usd')).toBe('gdp-per-capita-usd');
    expect(macroTwinConcept('weo-budget-balance-gdp')).toBe('budget-balance-gdp');
    expect(macroTwinConcept('weo-government-debt-gdp')).toBe('government-debt-gdp');
    expect(macroTwinCode('gdp-nominal')).toBe('w:russia:gdp-usd');
    expect(macroTwinCode('key-rate')).toBeNull();
  });
});
