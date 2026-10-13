// @vitest-environment jsdom
// Круг 13 (R-CAB): история выгрузок знает страницу, с которой скачали, даже если вызывающий передал свою `history` без адреса.
import { afterEach, describe, expect, it, vi } from 'vitest';
import api, { exportGrid, exportTable } from './api';

afterEach(() => vi.restoreAllMocks());

const ok = () => vi.spyOn(api, 'post').mockResolvedValue({ data: new Blob(['a']), headers: {} });

describe('history.params.href', () => {
  it('своя history без адреса дополняется адресом текущей страницы', async () => {
    window.history.pushState({}, '', '/compare?codes=a');
    const post = ok();
    await exportGrid({
      format: 'csv', filename: 'a.csv', columns: [], rows: [],
      history: { source: 'compare', subject_key: 'a', params: { codes: ['a'] } },
    });
    const sent = post.mock.calls[0][1].history;
    expect(sent).toEqual({ source: 'compare', subject_key: 'a', params: { href: '/compare?codes=a', codes: ['a'] } });
  });

  it('уже заданный адрес не заменяется', async () => {
    window.history.pushState({}, '', '/somewhere');
    const post = ok();
    await exportTable({ format: 'csv', filename: 'a.csv', points: [], history: { source: 'table', params: { href: '/russia/indicator/x' } } });
    expect(post.mock.calls[0][1].history.params.href).toBe('/russia/indicator/x');
  });

  it('без history уходит адрес страницы и источник по умолчанию', async () => {
    window.history.pushState({}, '', '/world/rating/gdp-usd');
    const post = ok();
    await exportGrid({ format: 'csv', filename: 'a.csv', columns: [], rows: [] });
    expect(post.mock.calls[0][1].history).toEqual({ source: 'grid', params: { href: '/world/rating/gdp-usd' } });
  });
});
