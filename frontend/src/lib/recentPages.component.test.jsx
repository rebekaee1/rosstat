import { act, render } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RecentPagesTracker, { RECENT_SETTLE_MS } from '../components/RecentPagesTracker';
import {
  RECENT_PAGES_KEY, RECENT_PAGES_LIMIT, cleanRecentTitle, clearRecentPages, normalizeRecentPath, readRecentPages, recentPageKind, rememberPage,
} from './recentPages';

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { vi.useRealTimers(); document.title = ''; });

describe('recentPages (круг 11, G)', () => {
  it('адрес: служебные и главная не запоминаются, сравнение и калькулятор держат строку запроса без меток', () => {
    for (const p of ['/', '/login', '/register', '/account', '/admin/bi', '/embed/chart/cpi', '/widgets']) expect(normalizeRecentPath(p)).toBeNull();
    expect(normalizeRecentPath('/germany/')).toBe('/germany');
    expect(normalizeRecentPath('/germany/indicator/de-cpi', '?utm_source=x')).toBe('/germany/indicator/de-cpi');
    expect(normalizeRecentPath('/compare', '?codes=a,b&rep=yoy&utm_source=x&preview_locale=en')).toBe('/compare?codes=a%2Cb&rep=yoy');
    expect(normalizeRecentPath('/calculator/mortgage', '?amount=5000000')).toBe('/calculator/mortgage?amount=5000000');
  });

  it('вид страницы по адресу', () => {
    expect(recentPageKind('/compare?codes=a')).toBe('compare');
    expect(recentPageKind('/calculator')).toBe('calculator');
    expect(recentPageKind('/world/rating/gdp-usd')).toBe('rating');
    expect(recentPageKind('/germany')).toBe('country');
    expect(recentPageKind('/germany/indicator/de-cpi')).toBe('indicator');
    expect(recentPageKind('/currencies/indicator/usd-rub')).toBe('currency');
    expect(recentPageKind('/russia/region/moskva')).toBe('region');
    expect(recentPageKind('/russia/calendar')).toBe('calendar');
  });

  it('название без хвоста с именем сайта', () => {
    expect(cleanRecentTitle('Инфляция в Германии — Forecast Economy')).toBe('Инфляция в Германии');
    expect(cleanRecentTitle('Inflation | Forecast Economy')).toBe('Inflation');
    expect(cleanRecentTitle('  Курс   доллара ')).toBe('Курс доллара');
  });

  it('запись поднимает страницу наверх без дублей и держит не больше 12', () => {
    rememberPage({ path: '/a', title: 'Страница A', now: 1 });
    rememberPage({ path: '/b', title: 'Страница B', now: 2 });
    rememberPage({ path: '/a', title: 'Страница A, новое имя', now: 3 });
    expect(readRecentPages().map((x) => [x.path, x.title, x.kind])).toEqual([
      ['/a', 'Страница A, новое имя', 'country'],
      ['/b', 'Страница B', 'country'],
    ]);
    for (let i = 0; i < 20; i += 1) rememberPage({ path: `/p${i}`, title: `Страница ${i}`, now: 10 + i });
    expect(readRecentPages()).toHaveLength(RECENT_PAGES_LIMIT);
    expect(readRecentPages()[0].path).toBe('/p19');
    clearRecentPages();
    expect(readRecentPages()).toEqual([]);
  });

  it('пустое имя и чужие записи в хранилище не ломают чтение', () => {
    expect(rememberPage({ path: '/x', title: '' })).toBe(false);
    window.localStorage.setItem(RECENT_PAGES_KEY, JSON.stringify([{ path: 'javascript:1', title: 'x' }, { path: '/ok', title: 'Ок' }, 5]));
    expect(readRecentPages().map((x) => x.path)).toEqual(['/ok']);
    window.localStorage.setItem(RECENT_PAGES_KEY, '{oops');
    expect(readRecentPages()).toEqual([]);
  });
});

describe('RecentPagesTracker', () => {
  function Go({ to }) {
    const navigate = useNavigate();
    return <button type="button" onClick={() => navigate(to)}>go</button>;
  }

  it('через 1,5 с после открытия записывает страницу с названием вкладки; 404 и главную нет', () => {
    vi.useFakeTimers();
    document.title = 'Инфляция в Германии — Forecast Economy';
    const { unmount } = render(<MemoryRouter initialEntries={['/germany/indicator/de-cpi']}><RecentPagesTracker /></MemoryRouter>);
    expect(readRecentPages()).toEqual([]);
    act(() => { vi.advanceTimersByTime(RECENT_SETTLE_MS + 10); });
    expect(readRecentPages().map((x) => [x.path, x.title])).toEqual([['/germany/indicator/de-cpi', 'Инфляция в Германии']]);
    unmount();

    window.localStorage.clear();
    const nf = document.createElement('div');
    nf.className = 'z2-nf';
    document.body.appendChild(nf);
    render(<MemoryRouter initialEntries={['/nope']}><RecentPagesTracker /></MemoryRouter>);
    act(() => { vi.advanceTimersByTime(RECENT_SETTLE_MS + 10); });
    expect(readRecentPages()).toEqual([]);
    nf.remove();
  });

  it('быстрый проход по ссылкам записи не оставляет, а старое название вкладки чужой странице не достаётся', () => {
    vi.useFakeTimers();
    document.title = 'Страна A — Forecast Economy';
    const { getByText } = render(
      <MemoryRouter initialEntries={['/a-land']}><RecentPagesTracker /><Go to="/b-land" /></MemoryRouter>,
    );
    act(() => { vi.advanceTimersByTime(RECENT_SETTLE_MS + 10); });
    expect(readRecentPages().map((x) => x.path)).toEqual(['/a-land']);
    // Переход на другой адрес: название вкладки пока старое (страница грузится) — запись откладывается.
    act(() => { getByText('go').click(); });
    act(() => { vi.advanceTimersByTime(RECENT_SETTLE_MS + 10); });
    expect(readRecentPages().map((x) => x.path)).toEqual(['/a-land']);
    // Страница поставила своё название: следующая проверка записывает её.
    document.title = 'Страна B — Forecast Economy';
    act(() => { vi.advanceTimersByTime(RECENT_SETTLE_MS + 10); });
    expect(readRecentPages().map((x) => [x.path, x.title])).toEqual([['/b-land', 'Страна B'], ['/a-land', 'Страна A']]);
  });
});
