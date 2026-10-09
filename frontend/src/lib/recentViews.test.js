// @vitest-environment jsdom
import { renderHook, act } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  RECENT_VIEWS_KEY, RECENT_VIEWS_LIMIT, clearRecentViews, readRecentViews, recordView, titleFromDocument, useRecentViews,
} from './recentViews';

beforeEach(() => { window.localStorage.clear(); });

const view = (n) => ({ kind: 'indicator', key: `k${n}`, title: `Показатель ${n}`, path: `/russia/indicator/k${n}` });

describe('recordView', () => {
  it('держит новые первыми и не дублирует адрес', () => {
    recordView(view(1));
    recordView(view(2));
    recordView(view(1));
    expect(readRecentViews().map((v) => v.key)).toEqual(['k1', 'k2']);
  });

  it('хранит не больше предела', () => {
    for (let i = 0; i < RECENT_VIEWS_LIMIT + 5; i += 1) recordView(view(i));
    expect(readRecentViews()).toHaveLength(RECENT_VIEWS_LIMIT);
    expect(readRecentViews(3)).toHaveLength(3);
  });

  it('пропускает главную, служебные страницы и страницы без названия', () => {
    expect(recordView({ kind: 'home', title: 'Главная', path: '/' })).toBe(false);
    expect(recordView({ kind: 'page', title: 'Кабинет', path: '/account?tab=saved' })).toBe(false);
    expect(recordView({ kind: 'page', title: 'Вход', path: '/login' })).toBe(false);
    expect(recordView({ kind: 'indicator', title: '', path: '/russia/indicator/x' })).toBe(false);
    expect(recordView({ kind: 'indicator', title: 'X', path: '//evil.example' })).toBe(false);
    expect(readRecentViews()).toEqual([]);
  });

  it('якорь не создаёт новую запись', () => {
    recordView({ ...view(1), path: '/russia/indicator/k1#table' });
    recordView(view(1));
    expect(readRecentViews()).toHaveLength(1);
  });

  it('повреждённое хранилище даёт пустой список', () => {
    window.localStorage.setItem(RECENT_VIEWS_KEY, '{oops');
    expect(readRecentViews()).toEqual([]);
    window.localStorage.setItem(RECENT_VIEWS_KEY, JSON.stringify([{ kind: 'indicator', title: 'ok', path: '//evil' }, 5, null]));
    expect(readRecentViews()).toEqual([]);
  });

  it('очистка убирает всё', () => {
    recordView(view(1));
    clearRecentViews();
    expect(readRecentViews()).toEqual([]);
  });
});

describe('titleFromDocument', () => {
  it('убирает название сайта из заголовка вкладки', () => {
    expect(titleFromDocument('Инфляция в Турции — Forecast Economy')).toBe('Инфляция в Турции');
    expect(titleFromDocument('Inflation in Türkiye | Forecast Economy')).toBe('Inflation in Türkiye');
    expect(titleFromDocument('Без хвоста')).toBe('Без хвоста');
  });
});

describe('useRecentViews', () => {
  it('обновляется после записи', () => {
    const { result } = renderHook(() => useRecentViews(5));
    expect(result.current).toEqual([]);
    act(() => { recordView(view(7)); });
    expect(result.current.map((v) => v.key)).toEqual(['k7']);
  });
});
