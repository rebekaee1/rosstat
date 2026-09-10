// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { safeReturnTo, authLink, rememberExport, pendingExport, restoredAuthView, rememberAuthView } from './authReturn';
import { downloadCSV, resumeExport } from './excel';
import { exportTable } from './api';
vi.mock('./api', () => ({ exportTable: vi.fn() }));
vi.mock('./track', () => ({ trackFile: vi.fn(), track: vi.fn(), events: {} }));
beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); history.replaceState(null, '', '/indicator/cpi?mode=inflation#chart'); });
describe('safe auth return', () => {
  it.each(['https://evil.test', '//evil.test', '/\\evil.test', '/%2fevil.test', '/%5cevil.test', '/login', '/register?next=/x', '/\n/evil'])('rejects %s', value => expect(safeReturnTo(value)).toBe('/account'));
  it('preserves path, selection query and fragment across login/register links', () => {
    const path = '/indicator/cpi?mode=inflation&year=2025#chart';
    const next = new URLSearchParams(authLink('/register', path).split('?')[1]).get('next');
    expect(safeReturnTo(next)).toBe(path);
    expect(new URLSearchParams(authLink('/login', next).split('?')[1]).get('next')).toBe(path);
  });
  it('restores chart window only on the original page and mode', () => {
    rememberAuthView('cpi:inflation', { range: '5y', offset: 2 });
    expect(restoredAuthView('cpi:inflation')).toEqual({ range: '5y', offset: 2 });
    expect(restoredAuthView('cpi:index')).toBeNull();
    history.replaceState(null, '', '/indicator/gdp');
    expect(restoredAuthView('cpi:inflation')).toBeNull();
  });
  it('expires abandoned intents', () => {
    rememberExport({ format: 'csv' });
    const spy = vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 31 * 60 * 1000);
    expect(pendingExport()).toBeNull(); spy.mockRestore();
  });
  it('retries exact export payload after auth, clears only on success', async () => {
    exportTable.mockRejectedValueOnce({ code: 'download_limit' });
    expect(await downloadCSV([{ date: '2025-01-01', actual: 8.2 }], 'inflation', 'cpi', '2025')).toBe(false);
    const intent = pendingExport();
    expect(intent.path).toBe('/indicator/cpi?mode=inflation#chart');
    exportTable.mockRejectedValueOnce(new Error('network'));
    await expect(resumeExport(intent.payload)).rejects.toThrow('network');
    expect(pendingExport()).not.toBeNull();
    URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    exportTable.mockResolvedValueOnce({ blob: new Blob(['x']), remaining: null });
    await resumeExport(intent.payload);
    expect(exportTable.mock.calls[2][0]).toEqual(exportTable.mock.calls[0][0]);
    expect(pendingExport()).toBeNull();
  });
});
it('retains an explicit small return-to-chart fallback for oversized exports', () => {
  rememberExport({ filename: 'large.csv', points: 'x'.repeat(512001) });
  expect(pendingExport()).toMatchObject({ path: '/indicator/cpi?mode=inflation#chart', payload: null, filename: 'large.csv' });
});
