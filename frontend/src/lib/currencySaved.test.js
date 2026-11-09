// @vitest-environment jsdom
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { readSavedRates, useSaveRates } from './currencySaved';

const ROW = (code, v) => ({ code, name: code, unit: 'руб.', current_value: v, current_date: '2026-11-07', change: 0.1, extra: 'не сохраняется' });

describe('курсы в памяти телефона (круг 8)', () => {
  beforeEach(() => window.localStorage.clear());

  it('ничего не сохранено: пусто', () => {
    expect(readSavedRates()).toBeNull();
  });

  it('список из трёх и больше рядов сохраняется без лишних полей и читается обратно', () => {
    renderHook(() => useSaveRates([ROW('usd-rub', 82), ROW('eur-rub', 92), ROW('cny-rub', 12)]));
    const saved = readSavedRates();
    expect(saved.items).toHaveLength(3);
    expect(saved.items[0]).toEqual(expect.objectContaining({ code: 'usd-rub', current_value: 82 }));
    expect(saved.items[0].extra).toBeUndefined();
    expect(typeof saved.at).toBe('string');
  });

  it('короткий или пустой ответ не затирает хорошие курсы', () => {
    renderHook(() => useSaveRates([ROW('usd-rub', 82), ROW('eur-rub', 92), ROW('cny-rub', 12)]));
    renderHook(() => useSaveRates([ROW('usd-rub', 1)]));
    renderHook(() => useSaveRates(null));
    expect(readSavedRates().items).toHaveLength(3);
  });

  it('испорченная запись не ломает страницу', () => {
    window.localStorage.setItem('fe.cur.saved.v1', '{oops');
    expect(readSavedRates()).toBeNull();
  });
});
