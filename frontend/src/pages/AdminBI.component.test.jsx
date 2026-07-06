// Т-13: AdminBI — гейт доступа. Аноним видит форму входа, зарегистрированный
// не-админ — «404», и только is_admin получает дашборд (данные мокаются).
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import AdminBI from './AdminBI';
import { renderPage, mockApiGet } from '../test/renderPage';

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
