/** @vitest-environment jsdom */
import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import IndicatorMethodologyPanel from './IndicatorMethodologyPanel';

it('links a world indicator to its published source series', () => {
  const sourceUrl = 'https://fred.stlouisfed.org/series/LASST060000000000005';
  render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel
          indicator={{ name: 'Civilian employment', source: 'U.S. Bureau of Labor Statistics' }}
          content={{ description: 'Employed residents', methodology: 'Monthly LAUS series' }}
          sourcePath={sourceUrl}
        />
      </MemoryRouter>
    </LocaleProvider>,
  );
  expect(screen.getByRole('link', { name: /source|источник/i }).getAttribute('href')).toBe(sourceUrl);
});

function renderPanel(props) {
  return render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel content={{ description: 'd', methodology: 'm' }} {...props} />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

it('Russian indicator links to its external source_url in a new tab', () => {
  renderPanel({
    indicator: {
      code: 'cpi',
      name: 'ИПЦ',
      source: 'Росстат',
      source_url: 'https://rosstat.gov.ru/statistics/price',
    },
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('https://rosstat.gov.ru/statistics/price');
  expect(link.getAttribute('target')).toBe('_blank');
  expect(link.getAttribute('rel')).toMatch(/noopener/);
  expect(link.getAttribute('rel')).toMatch(/noreferrer/);
});

it('Bank of Russia indicator no longer links back to the key-rate card', () => {
  renderPanel({
    indicator: { code: 'key-rate', name: 'Ключевая ставка', source: 'Банк России', source_url: 'https://www.cbr.ru/hd_base/KeyRate/' },
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('https://www.cbr.ru/hd_base/KeyRate/');
});

it('world page: external source_url wins over an internal sourcePath fallback', () => {
  renderPanel({
    indicator: { code: 'us-gdp-real', name: 'GDP', source: 'Federal Reserve Bank of St. Louis', source_url: 'https://fred.stlouisfed.org/series/GDPC1' },
    sourcePath: '/united-states/indicator/us-gdp-real',
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('https://fred.stlouisfed.org/series/GDPC1');
  expect(link.getAttribute('target')).toBe('_blank');
});

it('falls back to an internal link only when no source URL is known', () => {
  renderPanel({
    indicator: { code: 'some-series', name: 'X', source: 'Unknown agency' },
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('/russia/indicator/some-series');
  expect(link.getAttribute('target')).toBeNull();
});
