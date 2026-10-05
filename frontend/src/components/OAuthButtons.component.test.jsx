import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import OAuthButtons from './OAuthButtons';
import { fetchOAuthProviders } from '../lib/api';

vi.mock('../lib/api', () => ({
  fetchOAuthProviders: vi.fn(async () => ['yandex', 'vk', 'google']),
  oauthStartUrl: vi.fn(() => '/api/v1/auth/oauth/google/start'),
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useLocale: () => ({ locale: 'en', t: (key) => key }) }));

afterEach(cleanup);

describe('Google sign-in for the English site', () => {
  it('shows Google first; the newsletter box is preselected and can be switched off', async () => {
    render(<OAuthButtons />);
    const google = await screen.findByRole('button', { name: 'auth.oauth.google' });
    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toBe(google);
    fireEvent.click(google);
    expect(screen.getByText('auth.oauth.googleConsentIntro')).toBeTruthy();
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0].checked).toBe(false); // согласие с политикой — всегда явное
    expect(checkboxes[1].checked).toBe(true);  // рассылка — по умолчанию включена (решение владельца)
    fireEvent.click(checkboxes[1]);
    expect(checkboxes[1].checked).toBe(false);
    expect(screen.getByRole('button', { name: 'common.continue' }).disabled).toBe(true);
  });

  it.each([
    ['yandex', 'login'],
    ['yandex', 'register'],
    ['vk', 'login'],
    ['vk', 'register'],
    ['google', 'login'],
  ])('newsletter is preselected for %s (%s)', async (provider, intent) => {
    render(<OAuthButtons intent={intent} />);
    fireEvent.click(await screen.findByRole('button', { name: new RegExp(`auth\\.oauth\\.${provider}`) }));
    expect(screen.getAllByRole('checkbox')[1].checked).toBe(true);
  });

  it('opening another provider after switching the box off preselects it again', async () => {
    render(<OAuthButtons />);
    fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.yandex/ }));
    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    expect(screen.getAllByRole('checkbox')[1].checked).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'common.cancel' }));
    fireEvent.click(screen.getByRole('button', { name: /auth\.oauth\.vk/ }));
    expect(screen.getAllByRole('checkbox')[1].checked).toBe(true);
  });

  it('passes the chosen newsletter value to the provider redirect', async () => {
    const { oauthStartUrl } = await import('../lib/api');
    const original = window.location;
    delete window.location;
    window.location = { href: '' };
    try {
      render(<OAuthButtons intent="register" />);
      fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.vk/ }));
      fireEvent.click(screen.getAllByRole('checkbox')[0]);
      fireEvent.click(screen.getByRole('button', { name: 'common.continue' }));
      expect(oauthStartUrl).toHaveBeenLastCalledWith('vk', expect.objectContaining({ newsletter: true, consent: true }));
    } finally {
      window.location = original;
    }
  });

  it('keeps the Google signup button and sends an unconfigured provider to email registration', async () => {
    vi.mocked(fetchOAuthProviders).mockResolvedValue(['yandex', 'vk']);
    const onFallback = vi.fn();
    render(<OAuthButtons showGoogleEmailFallback onGoogleEmailFallback={onFallback} />);
    fireEvent.click(await screen.findByRole('button', { name: 'auth.oauth.googleRegister' }));
    expect(onFallback).toHaveBeenCalledOnce();
    expect(screen.queryByText('auth.oauth.googleConsentIntro')).toBeNull();
  });

  it('keeps registration on email even if Google appears in the provider list', async () => {
    vi.mocked(fetchOAuthProviders).mockResolvedValue(['yandex', 'vk', 'google']);
    const onFallback = vi.fn();
    render(<OAuthButtons showGoogleEmailFallback onGoogleEmailFallback={onFallback} />);
    fireEvent.click(await screen.findByRole('button', { name: 'auth.oauth.googleRegister' }));
    expect(onFallback).toHaveBeenCalledOnce();
    expect(screen.queryByText('auth.oauth.googleConsentIntro')).toBeNull();
  });
});
