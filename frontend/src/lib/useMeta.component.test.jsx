import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter, useLocation } from 'react-router-dom';
import useDocumentMeta from './useMeta';

vi.mock('./siteOrigin', () => ({ getSiteOrigin: () => 'https://ru.forecasteconomy.com' }));
vi.mock('../i18n/locale', () => ({ resolveBrowserLocale: () => 'ru' }));

const origin = 'https://ru.forecasteconomy.com';
const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content;
const property = (name) => document.querySelector(`meta[property="${name}"]`)?.content;
const canonical = () => document.querySelector('link[rel="canonical"]')?.href;

function Page({ pages }) {
  const { pathname } = useLocation();
  useDocumentMeta(pages[pathname]);
  return <>{Object.keys(pages).map((path) => <Link key={path} to={path}>{path}</Link>)}
    <Link to="?preview_locale=ru">preview ru</Link>
  </>;
}
const app = (pages, route) => <MemoryRouter initialEntries={[route]}><Page pages={pages} /></MemoryRouter>;

beforeEach(() => {
  document.head.innerHTML = '';
});

describe('useDocumentMeta navigation contracts', () => {
  it('uses Router pathname for US canonical and OG without a manually supplied path', () => {
    const path = '/united-states/region/california/building-permits';
    render(app({ [path]: { title: 'Permits', description: 'California data' } }, `${path}?utm_source=test#chart`));
    expect(canonical()).toBe(`${origin}${path}`);
    expect(property('og:url')).toBe(canonical());
    expect(property('og:image')).toBe(`${origin}/og/world/united-states/region/california/building-permits.png`);
  });

  it('clears private robots and updates Twitter metadata when login opens a public page', () => {
    render(app({
      '/login': { title: 'Вход', robots: 'noindex, nofollow' },
      '/about': { title: 'О проекте', description: 'Официальные данные' },
    }, '/login'));
    expect(meta('robots')).toBe('noindex, nofollow');
    fireEvent.click(screen.getByText('/about'));
    expect(meta('robots')).toContain('index, follow');
    expect(meta('robots')).not.toContain('noindex');
    expect(meta('twitter:title')).toBe('О проекте');
    expect(meta('twitter:description')).toBe('Официальные данные');
    expect(meta('twitter:image:alt')).toBe('О проекте');
    expect(document.querySelectorAll('meta[name="robots"]')).toHaveLength(1);
  });

  it('replaces a previous indicator graph with v3 on a static page', () => {
    render(app({ '/russia/indicator/cpi': { title: 'ИПЦ' }, '/about': { title: 'О проекте' } }, '/russia/indicator/cpi'));
    expect(property('og:image')).toBe(`${origin}/og/russia/cpi.png`);
    fireEvent.click(screen.getByText('/about'));
    expect(property('og:image')).toBe(`${origin}/og-image-v3.png`);
    expect(meta('twitter:image')).toBe(property('og:image'));
  });

  it('keeps explicit canonical years and selected map years without tracking params', () => {
    const path = '/world/rating/gdp-usd';
    render(app({ [path]: { title: 'GDP in 2024', path } }, `${path}?year=2024&utm_source=test`));
    expect(canonical()).toBe(`${origin}${path}`);
    expect(property('og:image')).toBe(`${origin}/og/world/rating/gdp-usd/2024.png`);
  });

  it('preserves explicit canonical override and image override', () => {
    render(app({ '/old': {
      title: 'Historical data', path: '/russia/indicator/cpi/2024', image: 'https://cdn.example.test/preview.png',
    } }, '/old'));
    expect(canonical()).toBe(`${origin}/russia/indicator/cpi/2024`);
    expect(property('og:image')).toBe('https://cdn.example.test/preview.png');
  });

  it('does not overwrite SSR head while options are null, then publishes loaded metadata', () => {
    document.head.innerHTML = '<title>SSR title</title><meta name="robots" content="index, follow"><meta property="og:image" content="https://example.test/ssr.png">';
    const before = document.head.innerHTML;
    const view = render(app({ '/germany': null }, '/germany'));
    expect(document.head.innerHTML).toBe(before);
    view.rerender(app({ '/germany': { title: 'Germany' } }, '/germany'));
    expect(document.title).toBe('Germany');
    expect(property('og:image')).toBe(`${origin}/og/world/germany.png`);
  });

  it('keeps nofollow on private previews and updates locale when only Router query changes', () => {
    render(app({ '/login': { title: 'Sign in', robots: 'noindex, nofollow' } }, '/login?preview_locale=en'));
    expect(meta('robots')).toBe('noindex, nofollow');
    expect(property('og:locale')).toBe('en_US');
    fireEvent.click(screen.getByText('preview ru'));
    expect(property('og:locale')).toBe('ru_RU');
    expect(meta('robots')).toBe('noindex, nofollow');
  });
});
