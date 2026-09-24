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
  it('shows Google first and allows opting out of the preselected newsletter', async () => {
    render(<OAuthButtons />);
    const google = await screen.findByRole('button', { name: 'auth.oauth.google' });
    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toBe(google);
    fireEvent.click(google);
    expect(screen.getByText('auth.oauth.googleConsentIntro')).toBeTruthy();
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0].checked).toBe(false);
    expect(checkboxes[1].checked).toBe(true);
    fireEvent.click(checkboxes[1]);
    expect(checkboxes[1].checked).toBe(false);
    expect(screen.getByRole('button', { name: 'common.continue' }).disabled).toBe(true);
  });

  it('keeps the existing newsletter default for other providers', async () => {
    render(<OAuthButtons />);
    fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.yandex/ }));
    expect(screen.getAllByRole('checkbox')[1].checked).toBe(false);
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
