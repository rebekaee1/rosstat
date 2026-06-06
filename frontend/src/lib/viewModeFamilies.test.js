import { describe, it, expect } from 'vitest';
import {
  VIEW_MODE_FAMILIES,
  DAILY_AGG_FREQUENCY,
  findViewModeFamily,
  viewModeCode,
  viewModeCanonicalTarget,
  applyMoMTransform,
  applyAggregateTransform,
} from './viewModeFamilies';

describe('VIEW_MODE_FAMILIES — schema', () => {
  it('каждая семья содержит непустой modes[] и валидный level-режим', () => {
    for (const [parent, family] of Object.entries(VIEW_MODE_FAMILIES)) {
      expect(family.label).toBeTruthy();
      expect(Array.isArray(family.modes)).toBe(true);
      expect(family.modes.length).toBeGreaterThan(0);
      const levels = family.modes.filter((m) => m.mode === 'level');
      expect(levels).toHaveLength(1);
      expect(levels[0].code).toBe(parent);
    }
  });

  it('monthly trade counterparts отмечены transform="mom" на non-level режиме', () => {
    const monthlyKeys = Object.keys(VIEW_MODE_FAMILIES).filter((k) =>
      k.endsWith('-monthly'),
    );
    expect(monthlyKeys.length).toBeGreaterThan(0);
    for (const key of monthlyKeys) {
      const nonLevel = VIEW_MODE_FAMILIES[key].modes.filter(
        (m) => m.mode !== 'level',
      );
      expect(nonLevel.length).toBeGreaterThan(0);
      for (const m of nonLevel) {
        expect(m.transform).toBe('mom');
        expect(m.unit).toBe('%');
      }
    }
  });

  // Инвариант ADR-0006 «Subsequent additions» (downstream metadata leak fix):
  // у каждого не-level mode должен быть задан либо `frequency` (для real
  // siblings), либо `transform` (для virtual transforms — frequency
  // остаётся родительская). Без этого pill/title протекают от родителя.
  it('каждый не-level mode имеет frequency или transform (anti-leak invariant)', () => {
    for (const [parent, family] of Object.entries(VIEW_MODE_FAMILIES)) {
      for (const m of family.modes) {
        if (m.mode === 'level') continue;
        const hasFreq = typeof m.frequency === 'string' && m.frequency.length > 0;
        const hasTransform = typeof m.transform === 'string' && m.transform.length > 0;
        expect(
          hasFreq || hasTransform,
          `Family "${parent}" mode "${m.mode}" должен иметь frequency или transform`,
        ).toBe(true);
      }
    }
  });

  it('DAILY_AGG_FREQUENCY покрывает 4 granularity (Phase 5)', () => {
    expect(DAILY_AGG_FREQUENCY).toEqual({
      week: 'weekly',
      month: 'monthly',
      quarter: 'quarterly',
      year: 'annual',
    });
  });
});

describe('findViewModeFamily / viewModeCode', () => {
  it('возвращает семью для родительского кода', () => {
    expect(findViewModeFamily('exports')).toBeTruthy();
    expect(findViewModeFamily('wages-nominal')).toBeNull();
    expect(findViewModeFamily('housing-price-primary')).toBeNull();
  });

  it('возвращает null для несвязанного кода', () => {
    expect(findViewModeFamily('cpi')).toBeNull();
    expect(findViewModeFamily('unknown')).toBeNull();
  });

  it('viewModeCode маппит (parent, mode) → derived code', () => {
    expect(viewModeCode('exports', 'yoy')).toBe('exports-yoy');
    expect(viewModeCode('exports', 'unknown')).toBe('exports'); // fallback
  });
});

describe('applyMoMTransform', () => {
  it('пустой ряд → пустой ряд', () => {
    expect(applyMoMTransform([])).toEqual([]);
    expect(applyMoMTransform(null)).toEqual([]);
    expect(applyMoMTransform([{ date: '2026-01-01', value: 100 }])).toEqual([]);
  });

  it('последовательные месяцы — корректный % к предшественнику', () => {
    const out = applyMoMTransform([
      { date: '2026-01-01', value: 100 },
      { date: '2026-02-01', value: 110 },
      { date: '2026-03-01', value: 99 },
    ]);
    expect(out).toEqual([
      { date: '2026-02-01', value: 10 },
      { date: '2026-03-01', value: -10 },
    ]);
  });

  it('сортирует точки хронологически перед расчётом', () => {
    const out = applyMoMTransform([
      { date: '2026-03-01', value: 99 },
      { date: '2026-01-01', value: 100 },
      { date: '2026-02-01', value: 110 },
    ]);
    expect(out.map((p) => p.date)).toEqual(['2026-02-01', '2026-03-01']);
  });

  it('нулевой знаменатель отбрасывается', () => {
    const out = applyMoMTransform([
      { date: '2026-01-01', value: 0 },
      { date: '2026-02-01', value: 50 },
      { date: '2026-03-01', value: 75 },
    ]);
    expect(out).toEqual([{ date: '2026-03-01', value: 50 }]);
  });

  it('округляется до 2 знаков', () => {
    const out = applyMoMTransform([
      { date: '2026-01-01', value: 3 },
      { date: '2026-02-01', value: 7 },
    ]);
    expect(out[0].value).toBe(133.33);
  });
});

describe('applyAggregateTransform', () => {
  it('пустой ряд / неизвестная granularity', () => {
    expect(applyAggregateTransform([], 'month')).toEqual([]);
    expect(applyAggregateTransform(null, 'month')).toEqual([]);
    const orig = [{ date: '2026-01-01', value: 1 }];
    expect(applyAggregateTransform(orig, 'unknown')).toBe(orig);
  });

  it('monthly aggregation: avg по месяцам, дата — конец месяца', () => {
    const out = applyAggregateTransform([
      { date: '2026-01-05', value: 10 },
      { date: '2026-01-20', value: 20 },
      { date: '2026-02-10', value: 30 },
      { date: '2026-02-15', value: 40 },
    ], 'month');
    expect(out).toEqual([
      { date: '2026-01-31', value: 15 },
      { date: '2026-02-28', value: 35 },
    ]);
  });

  it('quarterly aggregation: 3 месяца → одно среднее', () => {
    const out = applyAggregateTransform([
      { date: '2026-01-15', value: 10 },
      { date: '2026-02-15', value: 20 },
      { date: '2026-03-15', value: 30 },
      { date: '2026-04-15', value: 100 },
    ], 'quarter');
    expect(out.length).toBe(2);
    expect(out[0].value).toBe(20); // (10+20+30)/3
    expect(out[1].value).toBe(100);
    expect(out[0].date).toBe('2026-03-31');
    expect(out[1].date).toBe('2026-06-30');
  });

  it('annual aggregation: точки в один год → одно среднее на 31 декабря', () => {
    const out = applyAggregateTransform([
      { date: '2026-01-01', value: 100 },
      { date: '2026-07-01', value: 200 },
      { date: '2027-03-01', value: 300 },
    ], 'year');
    expect(out).toEqual([
      { date: '2026-12-31', value: 150 },
      { date: '2027-12-31', value: 300 },
    ]);
  });

  it('null-value точки игнорируются', () => {
    const out = applyAggregateTransform([
      { date: '2026-01-15', value: 10 },
      { date: '2026-01-20', value: null },
      { date: '2026-02-15', value: 30 },
    ], 'month');
    expect(out).toEqual([
      { date: '2026-01-31', value: 10 },
      { date: '2026-02-28', value: 30 },
    ]);
  });
});
