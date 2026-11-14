// @vitest-environment jsdom
// Содержание скачиваний доходит до событий через общие выгрузки (14.11.2026).
import { beforeEach, expect, it, vi } from 'vitest';

const limitError = Object.assign(new Error('download_limit'), { code: 'download_limit' });
vi.mock('./api', () => ({
  exportTable: vi.fn(async () => ({ blob: new Blob(['data']), remaining: 2 })),
  exportGrid: vi.fn(async () => ({ blob: new Blob(['data']), remaining: 2 })),
}));
vi.mock('./track', () => ({
  trackFile: vi.fn(), track: vi.fn(),
  events: { DOWNLOAD_CSV: 'download_csv', DOWNLOAD_EXCEL: 'download_excel', DOWNLOAD_LIMIT_HIT: 'download_limit' },
}));
vi.mock('./authReturn', () => ({ rememberExport: vi.fn(), clearPendingExport: vi.fn() }));
vi.mock('./chunkRecovery', () => ({ trackBusy: (p) => p }));

import { exportGrid, exportTable } from './api';
import { track } from './track';
import { downloadGrid } from './gridExport';
import { downloadExcel, resumeExport } from './excel';

beforeEach(() => {
  vi.clearAllMocks();
  URL.createObjectURL = vi.fn(() => 'blob:test');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

const grid = { format: 'xlsx', filename: 'a.xlsx', columns: [{ key: 'date', label: 'Дата' }], rows: [] };

it('table download carries code and country; the limit hit too', async () => {
  await downloadGrid(grid, { source: 'table-range', subject: { indicator: 'de-gdp', code: 'de-gdp', country: 'germany' } });
  expect(track).toHaveBeenLastCalledWith('download_excel',
    { source: 'table-range', indicator: 'de-gdp', code: 'de-gdp', country: 'germany' });

  exportGrid.mockRejectedValueOnce(limitError);
  await downloadGrid(grid, { source: 'table-range', subject: { indicator: 'cpi', code: 'cpi', country: 'russia' } });
  expect(track).toHaveBeenLastCalledWith('download_limit', { source: 'table-range', indicator: 'cpi', code: 'cpi' });
});

it('grid download without a subject stays as before', async () => {
  await downloadGrid({ ...grid, format: 'csv' }, { source: 'calc' });
  expect(track).toHaveBeenLastCalledWith('download_csv', { source: 'calc' });
});

it('excel limit and the resumed download after sign-in keep the code and country', async () => {
  exportTable.mockRejectedValueOnce(limitError);
  const ok = await downloadExcel([{ date: '2026-01-01', actual: 1 }], 'level', 'de-gdp', 'all', { name: 'ВВП', country: 'germany' });
  expect(ok).toBe(false);
  expect(track).toHaveBeenLastCalledWith('download_limit', { indicator: 'de-gdp', code: 'de-gdp', country: 'germany' });

  await resumeExport({ format: 'csv', filename: 'x.csv', points: [], subject: { code: 'cpi' } });
  expect(track).toHaveBeenLastCalledWith('download_csv', { resumed_after_auth: true, indicator: 'cpi', code: 'cpi' });
  // Поле subject не уходит на сервер: exportTable берёт только свои поля.
  expect(exportTable).toHaveBeenLastCalledWith(expect.objectContaining({ filename: 'x.csv' }));
});
