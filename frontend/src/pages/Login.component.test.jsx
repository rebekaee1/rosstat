// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Login from './Login';
import { loginUser } from '../lib/api';

vi.mock('../context/authContext', () => ({ useAuth: () => ({ setUser: vi.fn() }) }));
vi.mock('../lib/api', () => ({
  loginUser: vi.fn(),
  fetchOAuthProviders: vi.fn(async () => []),
  oauthStartUrl: vi.fn(() => '/oauth'),
}));
vi.mock('../lib/useMeta', () => ({ default: vi.fn() }));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key) => key,
  useLocale: () => ({ locale: 'ru', t: (key) => key }),
}));

afterEach(cleanup);

const renderLogin = () => render(
  <MemoryRouter initialEntries={['/login']}>
    <Routes><Route path="/login" element={<Login />} /></Routes>
  </MemoryRouter>,
);

describe('Login form states', () => {
  it('marks the submit button busy while the request is pending', async () => {
    let resolve;
    vi.mocked(loginUser).mockReturnValue(new Promise((r) => { resolve = r; }));
    renderLogin();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByRole('button', { name: 'auth.login.submit' }));
    const busyButton = await screen.findByRole('button', { name: 'auth.login.busy' });
    expect(busyButton.getAttribute('aria-busy')).toBe('true');
    expect(busyButton.disabled).toBe(true);
    expect(screen.getByRole('status').textContent).toBe('auth.login.busy');
    resolve({});
  });

  it('announces wrong credentials and highlights both fields with the error token', async () => {
    vi.mocked(loginUser).mockRejectedValue(new Error('401'));
    renderLogin();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: 'auth.login.submit' }));
    const alert = screen.getByRole('alert');
    await waitFor(() => expect(alert.textContent).toBe('auth.login.errorCredentials'));
    await waitFor(() => expect(screen.getByLabelText('common.email').getAttribute('aria-invalid')).toBe('true'));
    expect(screen.getByLabelText('common.password').className).toContain('border-negative');
    expect(screen.getByLabelText('common.email').getAttribute('aria-describedby')).toBe(alert.id);
  });
});
