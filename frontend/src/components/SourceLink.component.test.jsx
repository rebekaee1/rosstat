/** @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SourceLink from './SourceLink';
import { FOOTER_SOURCE_LINKS_BY_LOCALE } from '../lib/footerNav';
import { isExternalHref, pickExternalHref } from '../lib/sourceLink';

describe('SourceLink', () => {
  it('external URL opens the source in a new tab', () => {
    render(<MemoryRouter><SourceLink href="https://fred.stlouisfed.org/series/GDPC1" fallbackTo="/united-states">FRED</SourceLink></MemoryRouter>);
    const a = screen.getByRole('link', { name: 'FRED' });
    expect(a.getAttribute('href')).toBe('https://fred.stlouisfed.org/series/GDPC1');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('no URL: internal fallback without target', () => {
    render(<MemoryRouter><SourceLink href="" fallbackTo="/germany">Eurostat</SourceLink></MemoryRouter>);
    const a = screen.getByRole('link', { name: 'Eurostat' });
    expect(a.getAttribute('href')).toBe('/germany');
    expect(a.getAttribute('target')).toBeNull();
  });

  it('works outside a router and renders text when nothing to link', () => {
    render(<><SourceLink fallbackTo="/#countries">A</SourceLink><SourceLink>B</SourceLink></>);
    expect(screen.getByRole('link', { name: 'A' }).getAttribute('href')).toBe('/#countries');
    expect(screen.queryByRole('link', { name: 'B' })).toBeNull();
    expect(screen.getByText('B')).toBeTruthy();
  });

  it('helpers detect http(s) only', () => {
    expect(isExternalHref('https://rosstat.gov.ru')).toBe(true);
    expect(isExternalHref('/russia')).toBe(false);
    expect(pickExternalHref('/x', null, 'http://a.b')).toBe('http://a.b');
  });
});

describe('footer/About agency links', () => {
  it('point to official agency sites, not site sections', () => {
    for (const items of Object.values(FOOTER_SOURCE_LINKS_BY_LOCALE)) {
      for (const item of items) expect(isExternalHref(item.href)).toBe(true);
    }
  });
});
