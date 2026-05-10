import { describe, it, expect } from 'vitest';
import { buildShareUrl } from './utm';

describe('buildShareUrl', () => {
  it('appends utm_source/medium/campaign to absolute URL', () => {
    const url = buildShareUrl('https://forecasteconomy.com/calculator', {
      source: 'self',
      medium: 'share-link',
      campaign: 'calc-share',
    });
    expect(url).toBe('https://forecasteconomy.com/calculator?utm_source=self&utm_medium=share-link&utm_campaign=calc-share');
  });

  it('appends utm_content / utm_term when provided', () => {
    const url = buildShareUrl('https://forecasteconomy.com/indicator/cpi', {
      source: 'self',
      medium: 'share-link',
      campaign: 'indicator-share',
      content: 'cpi',
      term: 'monthly',
    });
    expect(url).toContain('utm_content=cpi');
    expect(url).toContain('utm_term=monthly');
  });

  it('overwrites existing utm_* params', () => {
    const url = buildShareUrl('https://forecasteconomy.com/?utm_source=ad&utm_medium=cpc&utm_campaign=old', {
      source: 'self',
      medium: 'share-link',
      campaign: 'calc-share',
    });
    expect(url).toContain('utm_source=self');
    expect(url).toContain('utm_medium=share-link');
    expect(url).toContain('utm_campaign=calc-share');
    expect(url).not.toContain('utm_source=ad');
    expect(url).not.toContain('utm_medium=cpc');
    expect(url).not.toContain('utm_campaign=old');
  });

  it('preserves non-utm query parameters', () => {
    const url = buildShareUrl('https://forecasteconomy.com/calculator?amount=100000&from=2014&to=2026', {
      source: 'self',
      medium: 'share-link',
      campaign: 'calc-share',
    });
    expect(url).toContain('amount=100000');
    expect(url).toContain('from=2014');
    expect(url).toContain('to=2026');
    expect(url).toContain('utm_source=self');
  });

  it('throws on missing required fields', () => {
    expect(() => buildShareUrl('https://forecasteconomy.com/', { source: 'self', medium: 'x' })).toThrow();
    expect(() => buildShareUrl('https://forecasteconomy.com/', { source: 'self', campaign: 'c' })).toThrow();
    expect(() => buildShareUrl('https://forecasteconomy.com/', { medium: 'x', campaign: 'c' })).toThrow();
  });

  it('handles relative URLs by anchoring to forecasteconomy.com fallback', () => {
    const url = buildShareUrl('/calculator?amount=1000', {
      source: 'self',
      medium: 'share-link',
      campaign: 'calc-share',
    });
    expect(url).toContain('forecasteconomy.com/calculator');
    expect(url).toContain('amount=1000');
    expect(url).toContain('utm_source=self');
  });
});
