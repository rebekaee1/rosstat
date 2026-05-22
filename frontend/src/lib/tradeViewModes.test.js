import { describe, it, expect } from 'vitest';
import {
  TRADE_VIEW_MODE_FAMILIES,
  findTradeViewModeFamily,
  applyMoMTransform,
} from './tradeViewModes';

describe('TRADE_VIEW_MODE_FAMILIES — schema', () => {
  it('каждая семья содержит непустой modes[] и валидный level-режим', () => {
    for (const [parent, family] of Object.entries(TRADE_VIEW_MODE_FAMILIES)) {
      expect(family.label).toBeTruthy();
      expect(Array.isArray(family.modes)).toBe(true);
      expect(family.modes.length).toBeGreaterThan(0);
      const levels = family.modes.filter((m) => m.mode === 'level');
      expect(levels).toHaveLength(1);
      expect(levels[0].code).toBe(parent);
    }
  });

  it('monthly counterparts отмечены transform="mom" на non-level режиме', () => {
    const monthlyKeys = Object.keys(TRADE_VIEW_MODE_FAMILIES).filter((k) =>
      k.endsWith('-monthly'),
    );
    expect(monthlyKeys.length).toBeGreaterThan(0);
    for (const key of monthlyKeys) {
      const nonLevel = TRADE_VIEW_MODE_FAMILIES[key].modes.filter(
        (m) => m.mode !== 'level',
      );
      expect(nonLevel.length).toBeGreaterThan(0);
      for (const m of nonLevel) {
        expect(m.transform).toBe('mom');
        expect(m.unit).toBe('%');
      }
    }
  });
});

describe('findTradeViewModeFamily', () => {
  it('возвращает семью для родительского кода', () => {
    expect(findTradeViewModeFamily('exports')).toBeTruthy();
    expect(findTradeViewModeFamily('trade-balance')).toBeTruthy();
    expect(findTradeViewModeFamily('exports-monthly')).toBeTruthy();
  });

  it('возвращает null для несвязанного кода', () => {
    expect(findTradeViewModeFamily('cpi')).toBeNull();
    expect(findTradeViewModeFamily('unknown')).toBeNull();
  });
});

describe('applyMoMTransform', () => {
  it('пустой ряд → пустой ряд', () => {
    expect(applyMoMTransform([])).toEqual([]);
    expect(applyMoMTransform(null)).toEqual([]);
    expect(applyMoMTransform([{ date: '2026-01-01', value: 100 }])).toEqual([]);
  });

  it('последовательные месяцы — корректный % к предшественнику', () => {
    const points = [
      { date: '2026-01-01', value: 100 },
      { date: '2026-02-01', value: 110 },
      { date: '2026-03-01', value: 99 },
    ];
    const out = applyMoMTransform(points);
    expect(out).toEqual([
      { date: '2026-02-01', value: 10 },
      { date: '2026-03-01', value: -10 },
    ]);
  });

  it('точки приводятся к хронологическому порядку перед расчётом', () => {
    const shuffled = [
      { date: '2026-03-01', value: 99 },
      { date: '2026-01-01', value: 100 },
      { date: '2026-02-01', value: 110 },
    ];
    const out = applyMoMTransform(shuffled);
    expect(out.map((p) => p.date)).toEqual(['2026-02-01', '2026-03-01']);
  });

  it('точка с нулевым знаменателем отбрасывается', () => {
    const points = [
      { date: '2026-01-01', value: 0 },
      { date: '2026-02-01', value: 50 },
      { date: '2026-03-01', value: 75 },
    ];
    const out = applyMoMTransform(points);
    expect(out).toEqual([{ date: '2026-03-01', value: 50 }]);
  });

  it('округляется до 2 знаков', () => {
    const points = [
      { date: '2026-01-01', value: 3 },
      { date: '2026-02-01', value: 7 },
    ];
    const out = applyMoMTransform(points);
    expect(out[0].value).toBe(133.33);
  });
});
