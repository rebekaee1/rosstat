// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
vi.mock('./api', () => ({ exportTable: vi.fn(async () => ({ blob: new Blob(['data']), remaining: null })) }));
vi.mock('./track', () => ({ trackFile: vi.fn(), track: vi.fn(), events: {} }));
vi.mock('./authReturn', () => ({ rememberExport: vi.fn(), clearPendingExport: vi.fn() }));
import { exportTable } from './api';
import { downloadCSV, downloadExcel } from './excel';
import { cpiProvenance } from './cpiProvenance';
it('both file formats carry calculation provenance and units alongside numeric data', async () => {
  URL.createObjectURL = vi.fn(() => 'blob:test');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  const provenance = cpiProvenance('cpi', 'inflation');
  const meta = { name: 'Годовое изменение', unit: '%', source: 'Росстат', provenance };
  for (const download of [downloadCSV, downloadExcel]) {
    await download([{ date: '2026-07-01', actual: 6 }], 'inflation', 'cpi', 'all', meta);
    expect(exportTable).toHaveBeenLastCalledWith(expect.objectContaining({
      points: [{ date: '2026-07-01', actual: 6, forecast: null }],
      meta: expect.objectContaining({ unit: '%', source: 'Росстат', provenance }),
    }));
  }
});
