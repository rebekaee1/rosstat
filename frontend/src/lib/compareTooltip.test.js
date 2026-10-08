import { describe, expect, it } from 'vitest';
import { compareTooltipRows } from './compareTooltip';

const colors = { v0: '#2C4A8A', v1: '#238F9B' };

describe('compareTooltipRows', () => {
  it('оставляет по одной строке на страну и убирает «v0», «v1»', () => {
    const payload = [
      { dataKey: 'v0', name: 'v0', value: 30 },
      { dataKey: 'v1', name: 'v1', value: 19 },
      { dataKey: 'v0', name: 'США', value: 30 },
      { dataKey: 'v1', name: 'Китай', value: 19 },
      { dataKey: 'v0', name: 'v0', value: 30 },
      { dataKey: 'v1', name: 'v1', value: 19 },
    ];
    const rows = compareTooltipRows(payload, colors);
    expect(rows.map((r) => r.name)).toEqual(['США', 'Китай']);
  });

  it('не показывает ряды без значения и чужие ключи', () => {
    const rows = compareTooltipRows([
      { dataKey: 'v0', name: 'США', value: null },
      { dataKey: 'x', name: 'Лишнее', value: 1 },
      { dataKey: 'v1', name: 'Китай', value: 2 },
    ], colors);
    expect(rows.map((r) => r.name)).toEqual(['Китай']);
  });

  it('не падает на пустом вводе', () => {
    expect(compareTooltipRows(undefined)).toEqual([]);
  });
});
