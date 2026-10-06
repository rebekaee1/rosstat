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

describe('AdminBI блок «Приложение»', () => {
  const snapshot = (pwa) => ({
    generated_at: '2026-10-06T00:00:00',
    period: { label: '7 дней', from: '2026-09-30', to: '2026-10-06' },
    cache_meta: { built_at: '2026-10-06T00:00:00', age_sec: 10, stale: false, refreshing: false },
    metric_tree: { north_star: {}, drivers: [] },
    ...(pwa ? { pwa } : {}),
  });

  it('показывает установки, конверсию и запуски из иконки', async () => {
    mockApiGet([
      ['/auth/me', { user: { id: 1, email: 'admin@x.ru', is_admin: true } }],
      [/\/admin\/bi\/dashboard/, snapshot({
        period: { label: '7 дней', from: '2026-09-30', to: '2026-10-06' },
        totals: {
          prompt_views: 40, prompt_viewers: 30, ios_hint_views: 5, entry_clicks: 2,
          prompt_accepts: 6, native_accepted: 4, installed_events: 4, installs: 3,
          dismissals: 12, launch_visitors: 7, launch_sessions: 9, conversion_pct: 10,
        },
        daily: [
          { date: '2026-10-05', prompt_views: 20, installs: 1, dismissals: 6, launch_visitors: 3, launch_sessions: 4 },
          { date: '2026-10-06', prompt_views: 20, installs: 2, dismissals: 6, launch_visitors: 4, launch_sessions: 5 },
        ],
      })],
    ]);
    renderPage(<AdminBI />, { path: '/admin/bi', route: '/admin/bi' });
    expect(await screen.findByText('Приложение: установки и запуски')).toBeTruthy();
    expect(screen.getByText('Установили')).toBeTruthy();
    expect(screen.getByText('10%')).toBeTruthy();
    expect(screen.getByText('Запуски из иконки')).toBeTruthy();
    expect(screen.getByText(/отказов: 12/)).toBeTruthy();
  });

  it('старый снимок без витрины pwa не ломает страницу', async () => {
    mockApiGet([
      ['/auth/me', { user: { id: 1, email: 'admin@x.ru', is_admin: true } }],
      [/\/admin\/bi\/dashboard/, snapshot(null)],
    ]);
    renderPage(<AdminBI />, { path: '/admin/bi', route: '/admin/bi' });
    expect(await screen.findByText('Приложение: установки и запуски')).toBeTruthy();
    expect(screen.getByText(/Появится после пересчёта/)).toBeTruthy();
  });
});
