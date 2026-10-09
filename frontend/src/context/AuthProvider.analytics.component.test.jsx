// @vitest-environment jsdom
import { cleanup, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from './AuthProvider';
import { fetchMe } from '../lib/api';
import { track } from '../lib/track';
import { markOAuthPending } from '../lib/authTrigger';

vi.mock('../lib/api', () => ({ fetchMe: vi.fn() }));
vi.mock('../lib/track', () => ({
  track: vi.fn(),
  setTrackedIdentity: vi.fn(),
  events: {
    AUTH_SIGNUP: 'signup', AUTH_LOGIN: 'login_success', NEWSLETTER_OPT_IN: 'newsletter_opt_in',
  },
}));

beforeEach(() => {
  vi.mocked(track).mockClear();
  window.sessionStorage.clear();
  window.localStorage.clear();
  document.documentElement.lang = 'en';
});
afterEach(cleanup);

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthProvider><span /></AuthProvider></QueryClientProvider>);
}

const tracked = () => vi.mocked(track).mock.calls.map(([name, params]) => [name, params]);

describe('signup и login_success после возврата с провайдера', () => {
  it('новый аккаунт: signup с методом, языком и рассылкой, затем newsletter_opt_in', async () => {
    markOAuthPending('yandex', 'login', { newsletter: true });
    vi.mocked(fetchMe).mockResolvedValue({ id: 'u1', is_new: true });
    mount();
    await waitFor(() => expect(tracked().length).toBeGreaterThan(0));
    expect(tracked()[0][0]).toBe('signup');
    expect(tracked()[0][1]).toMatchObject({ method: 'yandex', newsletter: 1, site_locale: 'en', trigger: 'direct' });
    expect(tracked()[1]).toEqual(['newsletter_opt_in', { channel: 'yandex' }]);
  });

  it('старый аккаунт: login_success', async () => {
    markOAuthPending('vk', 'login', { newsletter: false });
    vi.mocked(fetchMe).mockResolvedValue({ id: 'u1', is_new: false });
    mount();
    await waitFor(() => expect(tracked().length).toBe(1));
    expect(tracked()[0]).toEqual(['login_success', { method: 'vk', site_locale: 'en' }]);
  });

  it('без флага возврата (обычная загрузка страницы) событий нет', async () => {
    vi.mocked(fetchMe).mockResolvedValue({ id: 'u1', is_new: false });
    mount();
    await waitFor(() => expect(vi.mocked(fetchMe)).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(tracked()).toEqual([]);
  });

  it('привязка соцсети (intent=link) не считается входом', async () => {
    markOAuthPending('vk', 'link');
    vi.mocked(fetchMe).mockResolvedValue({ id: 'u1', is_new: false });
    mount();
    await waitFor(() => expect(vi.mocked(fetchMe)).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(tracked()).toEqual([]);
  });

  it('гость: флаг не расходуется на событие', async () => {
    markOAuthPending('vk', 'login');
    vi.mocked(fetchMe).mockRejectedValue({ response: { status: 401 } });
    mount();
    await new Promise((r) => setTimeout(r, 30));
    expect(tracked()).toEqual([]);
  });
});
