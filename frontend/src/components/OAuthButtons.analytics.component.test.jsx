// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import OAuthButtons from './OAuthButtons';
import { track } from '../lib/track';
import { consumeOAuthPending } from '../lib/authTrigger';

vi.mock('../lib/api', () => ({
  fetchOAuthProviders: vi.fn(async () => ['yandex', 'vk']),
  oauthStartUrl: vi.fn(() => '/api/v1/auth/oauth/yandex/start'),
}));
vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: {
    OAUTH_START: 'oauth_start',
    OAUTH_CONSENT_OPEN: 'oauth_consent_open',
    OAUTH_CONSENT_CANCEL: 'oauth_consent_cancel',
    NEWSLETTER_OPT_IN: 'newsletter_opt_in',
  },
}));
vi.mock('../i18n', () => ({ useLocale: () => ({ locale: 'ru', t: (key) => key }) }));

beforeEach(() => { vi.mocked(track).mockClear(); window.sessionStorage.clear(); });
afterEach(cleanup);

const calls = () => vi.mocked(track).mock.calls.map(([name, params]) => [name, params]);

describe('воронка окна согласия перед входом через соцсеть', () => {
  it('открытие окна и отмена дают события с провайдером и намерением', async () => {
    render(<OAuthButtons intent="login" />);
    fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.yandex/ }));
    expect(calls()).toContainEqual(['oauth_consent_open', { provider: 'yandex', intent: 'login' }]);
    fireEvent.click(screen.getByRole('button', { name: 'common.cancel' }));
    expect(calls()).toContainEqual(['oauth_consent_cancel', { provider: 'yandex', intent: 'login' }]);
  });

  it('Escape тоже считается отменой', async () => {
    render(<OAuthButtons intent="login" />);
    fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.vk/ }));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(calls()).toContainEqual(['oauth_consent_cancel', { provider: 'vk', intent: 'login' }]);
  });

  it('продолжение: oauth_start есть, подписка считается не на старте, а запоминается до возврата', async () => {
    const original = window.location;
    delete window.location;
    window.location = { href: '' };
    try {
      render(<OAuthButtons intent="login" />);
      fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.yandex/ }));
      fireEvent.click(screen.getAllByRole('checkbox')[0]);
      fireEvent.click(screen.getByRole('button', { name: 'common.continue' }));
    } finally {
      window.location = original;
    }
    const names = calls().map(([name]) => name);
    expect(names).toContain('oauth_start');
    expect(names).not.toContain('newsletter_opt_in');
    expect(names).not.toContain('oauth_consent_cancel');
    expect(consumeOAuthPending()).toEqual({ provider: 'yandex', intent: 'login', newsletter: true });
  });
});
