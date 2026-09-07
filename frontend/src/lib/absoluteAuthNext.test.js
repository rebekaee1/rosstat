import { afterEach, describe, expect, it, vi } from 'vitest';
import { absoluteAuthNext, oauthStartUrl } from './api.js';

describe('absoluteAuthNext', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps relative path without window', () => {
    vi.stubGlobal('window', undefined);
    expect(absoluteAuthNext('/account')).toBe('/account');
    expect(absoluteAuthNext('/register')).toBe('/register');
  });

  it('prefixes current origin on ru host', () => {
    vi.stubGlobal('window', {
      location: { origin: 'https://ru.forecasteconomy.com' },
    });
    expect(absoluteAuthNext('/account')).toBe('https://ru.forecasteconomy.com/account');
    expect(absoluteAuthNext('/account#feedback')).toBe(
      'https://ru.forecasteconomy.com/account#feedback',
    );
  });

  it('rejects protocol-relative and empty', () => {
    vi.stubGlobal('window', {
      location: { origin: 'https://ru.forecasteconomy.com' },
    });
    expect(absoluteAuthNext('//evil.example/x')).toBe(
      'https://ru.forecasteconomy.com/account',
    );
    expect(absoluteAuthNext('')).toBe('https://ru.forecasteconomy.com/account');
  });

  it('oauthStartUrl encodes absolute next from current host', () => {
    vi.stubGlobal('window', {
      location: { origin: 'https://ru.forecasteconomy.com' },
    });
    const url = oauthStartUrl('yandex', { intent: 'login', next: '/account' });
    expect(url).toContain('/api/v1/auth/oauth/yandex/start?');
    expect(url).toContain(
      encodeURIComponent('https://ru.forecasteconomy.com/account'),
    );
  });
});
