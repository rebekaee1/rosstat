import { describe, expect, it } from 'vitest';
import { buildGridPayload, safeFilename } from './gridExport';

describe('gridExport', () => {
  it('убирает lower/upper, нечисловые значения и лишние поля строк', () => {
    const payload = buildGridPayload({
      format: 'csv',
      filename: 'a.csv',
      columns: [{ key: 'date', label: 'Дата' }, { key: 'v0', label: 'ВВП', unit: 'млрд $' }, { key: 'lower', label: 'x' }, { key: 'Upper', label: 'y' }],
      rows: [{ date: '2020-01-01', v0: 1.5, lower: 1, extra: 3 }, { date: '2021-01-01', v0: Number.NaN }, { date: '2022-01-01' }],
    });
    expect(payload.columns.map((c) => c.key)).toEqual(['date', 'v0']);
    expect(payload.columns[1].unit).toBe('млрд $');
    expect(payload.rows).toEqual([
      { date: '2020-01-01', v0: 1.5 },
      { date: '2021-01-01', v0: null },
      { date: '2022-01-01', v0: null },
    ]);
    expect(JSON.stringify(payload)).not.toMatch(/lower|upper/i);
  });

  it('передаёт название, источник и параметры повтора, а пустое не добавляет', () => {
    const payload = buildGridPayload({
      format: 'xlsx', filename: 'a.xlsx', title: 'Сравнение', columns: [{ key: 'date', label: 'Дата' }], rows: [],
      meta: { source: 'МВФ' }, history: { source: 'compare', subject_key: 'a,b', params: { codes: ['a', 'b'] } },
    });
    expect(payload.title).toBe('Сравнение');
    expect(payload.meta.source).toBe('МВФ');
    expect(payload.history.params.codes).toEqual(['a', 'b']);
    expect(buildGridPayload({ format: 'csv', filename: 'a.csv', columns: [], rows: [] })).not.toHaveProperty('history');
  });

  it('имя файла безопасно', () => {
    expect(safeFilename('compare_w:united-states:gdp-usd', 'csv')).toBe('compare_w_united-states_gdp-usd.csv');
    expect(safeFilename('', 'xlsx')).toBe('data.xlsx');
    expect(safeFilename('x'.repeat(200), 'csv').length).toBeLessThanOrEqual(84);
  });
});
