// Т-13: AdminBI — гейт доступа. Аноним видит форму входа, зарегистрированный
// не-админ — «404», и только is_admin получает дашборд (данные мокаются).
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import AdminBI from './AdminBI';
import { renderPage, mockApiGet } from '../test/renderPage';

// ECharts требует canvas — в jsdom его нет; вкладки дашборда рендерим без графиков.
vi.mock('../components/EChart', () => ({ default: () => <div data-testid="echart" /> }));

afterEach(() => vi.restoreAllMocks());

describe('AdminBI access gate', () => {
  it('аноним видит форму входа, не дашборд', async () => {
    mockApiGet([['/auth/me', { user: null }]]);
    renderPage(<AdminBI />, { path: '/admin/bi', route: '/admin/bi' });
    expect(await screen.findByRole('button', { name: /войти/i })).toBeTruthy();
    expect(screen.queryByText(/404/)).toBeNull();
  });

  it('зарегистрированный не-админ видит 404', async () => {
    mockApiGet([['/auth/me', { user: { id: 1, email: 'u@x.ru', is_admin: false } }]]);
    renderPage(<AdminBI />, { path: '/admin/bi', route: '/admin/bi' });
    expect(await screen.findByText(/404/)).toBeTruthy();
  });
});

describe('AdminBI фоновая сборка', () => {
  // Инцидент 2026-09-04: бэкенд на холодном кэше отвечает 202 «считаем»,
  // фронт опрашивает и не рвёт сборку 15-секундным таймаутом.
  it('202 building → опрос → снимок с пометкой возраста', async () => {
    let calls = 0;
    mockApiGet([
      ['/auth/me', { user: { id: 1, email: 'admin@x.ru', is_admin: true } }],
      [/\/admin\/bi\/dashboard/, () => {
        calls += 1;
        if (calls === 1) return { status: 'building', elapsed_sec: 4, queued_builds: 1 };
        return {
          generated_at: '2026-09-04T00:00:00',
          period: { label: '7 дней', from: '2026-08-28', to: '2026-09-03' },
          cache_meta: { built_at: '2026-09-03T22:00:00', age_sec: 10, stale: false, refreshing: false },
          metric_tree: { north_star: {}, drivers: [] },
        };
      }],
    ]);
    renderPage(<AdminBI />, { path: '/admin/bi', route: '/admin/bi' });
    expect(await screen.findByText(/Считаем витрины — 4 с/)).toBeTruthy();
    expect(await screen.findByText(/снимок \d{2}:\d{2}/, {}, { timeout: 6000 })).toBeTruthy();
    expect(calls).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/Считаем витрины/)).toBeNull();
  }, 10000);
});
