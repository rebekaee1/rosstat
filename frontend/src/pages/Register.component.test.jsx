import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';

import Register from './Register';

vi.mock('../context/authContext', () => ({ useAuth: () => ({ setUser: vi.fn() }) }));
vi.mock('../lib/api', () => ({
  registerUser: vi.fn(),
  fetchOAuthProviders: vi.fn(async () => ['yandex', 'vk']),
  oauthStartUrl: vi.fn(() => '/oauth'),
}));
vi.mock('../lib/useMeta', () => ({ default: vi.fn() }));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key) => key,
  useLocale: () => ({ locale: 'en', t: (key) => key }),
}));

afterEach(cleanup);

function CurrentLocation() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>;
}

describe('email fallback from unavailable Google signup', () => {
  it('keeps next, explains the temporary fallback in English, and focuses email', async () => {
    render(
      <MemoryRouter initialEntries={['/register?next=%2Fworld%2Findicator%2Fgdp-usd']}>
        <CurrentLocation />
        <Routes><Route path="/register" element={<Register />} /></Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'auth.oauth.googleRegister' }));

    expect(await screen.findByText('auth.register.googleUnavailable')).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('google_unavailable=1'));
    expect(screen.getByTestId('location').textContent).toContain('next=%2Fworld%2Findicator%2Fgdp-usd');
    expect(screen.getByTestId('location').textContent).toContain('#email');
    expect(document.activeElement).toBe(screen.getByLabelText('common.email'));
  });
});
