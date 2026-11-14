// Вкладка «Почта» админ-BI (ADR-0032): своя загрузка /admin/bi/mail, только числа.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import AdminBI from './AdminBI';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/EChart', () => ({ default: () => <div data-testid="echart" /> }));

afterEach(() => vi.restoreAllMocks());

describe('AdminBI вкладка «Почта»', () => {
  it('показывает флаги, итоги, виды писем и выпуски', async () => {
    mockApiGet([
      ['/auth/me', { user: { id: 1, email: 'admin@x.ru', is_admin: true } }],
      [/\/admin\/bi\/dashboard/, {
        generated_at: '2026-11-14T00:00:00',
        period: { label: '7 дней', from: '2026-11-08', to: '2026-11-14' },
        cache_meta: { built_at: '2026-11-14T00:00:00', age_sec: 1, stale: false, refreshing: false },
        metric_tree: { north_star: {}, drivers: [] },
      }],
      [/\/admin\/bi\/mail/, {
        days: 30,
        config: { enabled: true, allowlist_only: true, bulk_profile: false, bounce_poll: false, watch_digest: false },
        by_kind: { verify_email: { sent: 3, blocked: 5 }, newsletter: { sent: 10, bounced: 1 } },
        daily: { '2026-11-14': { sent: 13, blocked: 5 } },
        campaigns: [{ key: '2026-11-reconfirm', statuses: { sent: 40, failed: 2 }, last: '2026-11-14T10:00:00' }],
        audience: { newsletter_subscribers: 122, password_verified: 4, password_unverified: 107 },
        consent_events: { newsletter_revoked: 2, watch_mail_revoked: 1 },
        suppressions: { bounce: 3, complaint: 1 },
      }],
    ]);
    renderPage(<AdminBI />, { path: '/admin/bi', route: '/admin/bi' });
    fireEvent.click(await screen.findByRole('button', { name: /Почта/ }));
    expect(await screen.findByTestId('bi-mail')).toBeTruthy();
    expect(screen.getByText('Почта включена')).toBeTruthy();
    expect(screen.getByText('Только список допуска')).toBeTruthy();
    expect(screen.getByText('122')).toBeTruthy();
    expect(screen.getByText('2026-11-reconfirm')).toBeTruthy();
    expect(screen.getByText('Подтверждение адреса')).toBeTruthy();
    expect(screen.getByText(/рассылка 2, «колокольчик» 1/)).toBeTruthy();
  });
});
