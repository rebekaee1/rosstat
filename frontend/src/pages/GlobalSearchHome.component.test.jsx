import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Dashboard from './Dashboard';
import HomeHero from '../components/home/HomeHero';
import { mockApiGet, renderPage } from '../test/renderPage';
import { track, events } from '../lib/track';

vi.mock('gsap', () => ({ default: { fromTo: () => ({ kill: () => {} }) } }));
vi.mock('../components/WorldMap', () => ({ default: () => <div data-testid="world-map" /> }));
vi.mock('../components/MapTimeline', () => ({ default: () => null }));
vi.mock('../lib/track', async importOriginal => ({ ...(await importOriginal()), track: vi.fn(), setTrackedIdentity: vi.fn() }));

beforeEach(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{ width: 100, height: 30 }]);
  track.mockClear();
});
afterEach(() => vi.restoreAllMocks());

const hits = [
  { key: 'ru:gdp', kind: 'russia', name: 'ВВП', name_en: 'GDP', country_slug: 'russia', country_name: 'Russia', path: '/russia/indicator/gdp' },
  { key: 'world:germany:de-cpi', kind: 'world', name: 'Инфляция', name_en: 'Inflation', country_slug: 'germany', country_name: 'Germany', path: '/germany/indicator/de-inflation' },
  { key: 'region:moskva:wages', kind: 'region_indicator', name: 'Зарплата', name_en: 'Pay', region_name: 'Moscow', country_slug: 'russia', country_name: 'Russia', path: '/russia/region/moskva/wages' },
  { key: 'subnational:united-states:california:population', kind: 'subnational_indicator', name: 'Население', name_en: 'Population', region_name: 'California', country_slug: 'united-states', country_name: 'United States', path: '/united-states/region/california/population' },
];
function Destination() {
  const location = useLocation();
  return <output data-testid="destination">{location.pathname}</output>;
}

function mount(locale, standaloneHero = false) {
  const get = mockApiGet([
    ['/auth/me', { user: null }], ['/indicators', []],
    ['/world/countries', { countries: [], total: 0 }],
    [/^\/world\/rating\/concepts/, { concepts: [] }],
    [/^\/world\/compare\/catalog/, { items: [] }],
    [/^\/world\/compare\/snapshot/, { items: [] }],
    [/^\/world\/compare\/map-series/, { years: [], values_by_year: {} }],
    ['/search', { results: hits, total: hits.length, has_more: false, version: 'federated-v2' }],
  ]);
  renderPage(<><Navbar />{standaloneHero ? <HomeHero /> : <Dashboard />}<Destination /></>, { path: '*', route: '/', locale });
  return get;
}

describe('Every homepage search entry uses global discovery', () => {
  it.each(['ru', 'en'])('hero and both Navbar variants preserve raw natural input and all four result planes in %s', async locale => {
    const get = mount(locale);
    const triggers = screen.getAllByRole('button', { name: locale === 'en' ? /^Open search/ : /^Открыть поиск/ });
    expect(triggers).toHaveLength(3);
    const query = locale === 'en' ? 'population in California in 2024' : 'население Калифорнии за 2024';
    for (const trigger of triggers) {
      fireEvent.click(trigger);
      expect(screen.getAllByRole('dialog')).toHaveLength(1);
      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: query } });
      await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(4));
      expect(get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: query, limit: 100 } }));
      expect(screen.getAllByRole('option').map(row => row.textContent).join(' ')).toContain('Germany');
      expect(screen.getAllByRole('option').map(row => row.textContent).join(' ')).toContain('California');
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(screen.queryByRole('dialog')).toBeNull();
    }
    // The same backend path is selected intact; the display plane does not
    // rewrite an international region result into a Russian destination.
    fireEvent.click(triggers[2]);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: query } });
    fireEvent.click((await screen.findAllByRole('option'))[3]);
    expect(screen.getByTestId('destination').textContent).toBe(hits[3].path);
    expect(track).toHaveBeenCalledWith(events.SEARCH_SELECT, expect.objectContaining({ path: hits[3].path, version: 'federated-v2', country: 'united-states' }));
  });

  it('the retained standalone HomeHero uses the same global endpoint', async () => {
    const get = mount('en', true);
    fireEvent.click(screen.getByRole('button', { name: 'Open search' }));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'inflation in Germany' } });
    await screen.findAllByRole('option');
    expect(get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: 'inflation in Germany', limit: 100 } }));
  });
});
