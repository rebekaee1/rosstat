// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import api from './api';
import { downloadGrid, gridColumnKey, gridFilename } from './gridDownload';

afterEach(() => vi.restoreAllMocks());

describe('gridColumnKey и gridFilename', () => {
  it('ключ колонки латиницей, имя файла без слэшей и пробелов', () => {
    expect(gridColumnKey('x_unemployment-rate')).toBe('x_unemployment-rate');
    expect(gridColumnKey('Среднее значение')).toBe('col');
    expect(gridColumnKey('a b/c')).toBe('a_b_c');
    expect(gridFilename('rating gdp/usd 2025', 'csv')).toBe('rating_gdp_usd_2025.csv');
    expect(gridFilename('', 'xlsx')).toBe('table.xlsx');
  });
});

describe('downloadGrid', () => {
  it('отправляет сетку на /export/grid и возвращает остаток гостевых выгрузок', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: new Blob(['a']), headers: { 'x-download-remaining': '2' } });
    const payload = { format: 'csv', filename: 'a.csv', title: 'T', columns: [{ key: 'a', label: 'A' }], rows: [{ a: 1 }] };
    const result = await downloadGrid(payload);
    expect(post).toHaveBeenCalledWith('/export/grid', payload, { responseType: 'blob' });
    expect(result.remaining).toBe(2);
  });

  it('403 с кодом download_limit превращается в ошибку с кодом', async () => {
    // jsdom не знает Blob.text(): подставляем объект с тем же методом.
    const blob = { text: async () => JSON.stringify({ detail: { code: 'download_limit', message: 'лимит' } }) };
    vi.spyOn(api, 'post').mockRejectedValue({ response: { status: 403, data: blob } });
    await expect(downloadGrid({})).rejects.toMatchObject({ code: 'download_limit' });
  });

  it('прочие ошибки сети пробрасываются как есть', async () => {
    const boom = new Error('network');
    vi.spyOn(api, 'post').mockRejectedValue(boom);
    await expect(downloadGrid({})).rejects.toBe(boom);
  });
});
