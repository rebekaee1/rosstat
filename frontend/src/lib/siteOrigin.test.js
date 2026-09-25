import { afterEach, describe, expect, it, vi } from 'vitest';
import { publicPageUrl } from './siteOrigin';

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

  it('canonicalizes www and en. onto the apex origin', async () => {
    vi.stubGlobal('window', {
      location: {
        hostname: 'www.forecasteconomy.com',
        origin: 'https://www.forecasteconomy.com',
      },
    });
    const www = await import('./siteOrigin.js');
    expect(www.getSiteOrigin()).toBe('https://forecasteconomy.com');
    vi.resetModules();
    vi.stubGlobal('window', {
      location: {
        hostname: 'en.forecasteconomy.com',
        origin: 'https://en.forecasteconomy.com',
      },
    });
    const en = await import('./siteOrigin.js');
    expect(en.getSiteOrigin()).toBe('https://forecasteconomy.com');
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

describe('publicPageUrl', () => {
  it('serializes the root without a trailing slash and keeps other paths', () => {
    expect(publicPageUrl('https://forecasteconomy.com/', '/')).toBe('https://forecasteconomy.com');
    expect(publicPageUrl('https://ru.forecasteconomy.com', '/about')).toBe(
      'https://ru.forecasteconomy.com/about',
    );
    expect(publicPageUrl('https://forecasteconomy.com', '/russia/indicator/cpi/')).toBe(
      'https://forecasteconomy.com/russia/indicator/cpi',
    );
  });
});
