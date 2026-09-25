import { afterEach, describe, expect, it, vi } from 'vitest';

import { completeDataset, datasetLicenseUrl } from './datasetJsonLd';

describe('completeDataset', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('points license at the host terms page', () => {
    vi.stubGlobal('window', {
      location: {
        hostname: 'ru.forecasteconomy.com',
        origin: 'https://ru.forecasteconomy.com',
      },
    });
    expect(datasetLicenseUrl()).toBe('https://ru.forecasteconomy.com/terms');
    const node = completeDataset({
      name: 'ИПЦ',
      creator: { '@type': 'Organization', name: 'Росстат' },
    }, 'ru');
    expect(node.license).toBe('https://ru.forecasteconomy.com/terms');
    expect(node.creator).toEqual({ '@type': 'Organization', name: 'Росстат' });
    expect(node.description.length).toBeGreaterThanOrEqual(50);
    expect(node.description).toContain('Росстат');
  });

  it('uses the apex terms URL on the English host', () => {
    vi.stubGlobal('window', {
      location: {
        hostname: 'forecasteconomy.com',
        origin: 'https://forecasteconomy.com',
      },
    });
    const node = completeDataset({
      name: 'CPI',
      description: 'Consumer price index for Russia, monthly, official series from Rosstat.',
    }, 'en');
    expect(node.license).toBe('https://forecasteconomy.com/terms');
    expect(node.description).toBe(
      'Consumer price index for Russia, monthly, official series from Rosstat.',
    );
    expect(node.creator.name).toBe('Forecast Economy');
  });
});
