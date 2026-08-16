import { afterEach, describe, expect, it, vi } from 'vitest';

describe('getSiteOrigin', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('uses build-time origin without window', async () => {
    vi.stubGlobal('window', undefined);
    const { getSiteOrigin, SITE_ORIGIN } = await import('./siteOrigin.js');
    expect(getSiteOrigin()).toBe(SITE_ORIGIN);
    expect(SITE_ORIGIN).toBe('https://forecasteconomy.com');
  });

  it('follows ru. host in the browser', async () => {
    vi.stubGlobal('window', {
      location: {
        hostname: 'ru.forecasteconomy.com',
        origin: 'https://ru.forecasteconomy.com',
      },
    });
    const { getSiteOrigin } = await import('./siteOrigin.js');
    expect(getSiteOrigin()).toBe('https://ru.forecasteconomy.com');
  });

  it('follows apex host in the browser', async () => {
    vi.stubGlobal('window', {
      location: {
        hostname: 'forecasteconomy.com',
        origin: 'https://forecasteconomy.com',
      },
    });
    const { getSiteOrigin } = await import('./siteOrigin.js');
    expect(getSiteOrigin()).toBe('https://forecasteconomy.com');
  });

  it('keeps build origin on localhost', async () => {
    vi.stubGlobal('window', {
      location: {
        hostname: 'localhost',
        origin: 'http://localhost:5173',
      },
    });
    const { getSiteOrigin, SITE_ORIGIN } = await import('./siteOrigin.js');
    expect(getSiteOrigin()).toBe(SITE_ORIGIN);
  });
});
