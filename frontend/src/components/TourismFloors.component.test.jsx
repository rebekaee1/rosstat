// @vitest-environment jsdom
// Раздел «Туризм» (20.11.2026): этажи «Регионы России» и «Мир», навигация по этажам, пустые этажи не рисуются.
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TourismFloors, { TourismJump, TourismRussiaCatalog } from './TourismFloors';

const state = vi.hoisted(() => ({ data: null }));
vi.mock('../lib/hooks', () => ({ useTourismOverview: () => ({ data: state.data }) }));
vi.mock('../i18n', () => ({
  useT: () => (key, vars) => (vars ? `${key}:${Object.values(vars).join(',')}` : key),
  useLocale: () => ({ locale: 'ru' }),
}));

afterEach(() => { cleanup(); state.data = null; });

const FULL = {
  russia: { count: 3, path: '/russia/category/tourism' },
  regions: {
    count: 3,
    groups: ['flows', 'stay', 'business'],
    items: [
      { code: 'kollektivnye-sredstva', name: 'Коллективные средства размещения', unit: 'единица', year: 2024, group: 'stay', path: '/russia/region-rating/kollektivnye-sredstva' },
      { code: 'turfirmy', name: 'Туристские фирмы', unit: 'единица', year: 2023, group: 'business', path: '/russia/region-rating/turfirmy' },
      { code: 'gosti-mes', name: 'Гости гостиниц за месяц', unit: 'тыс.', year: 2026, group: 'flows', path: '/russia/region/russia/gosti-mes' },
    ],
  },
  world: {
    count: 1,
    concepts: [{ slug: 'tourist-arrivals', name: 'Прибытия туристов', path: '/world/rating/tourist-arrivals' }],
    countries: [{ slug: 'turkey', name: 'Турция', path: '/turkey', count: 4, series: [] }],
    outbound: {
      year: 2025, unit: 'тыс.',
      items: [
        { slug: 'turkey', name: 'Турция', path: '/russia/indicator/tour-outbound-turkey', value: 5123.4, period: 2025 },
        { slug: 'egypt', name: 'Египет', path: '/russia/indicator/tour-outbound-egypt', value: 1947.8, period: 2025 },
      ],
    },
  },
};

function mount() {
  return render(<MemoryRouter><TourismJump /><TourismFloors /></MemoryRouter>);
}

it('регионы: только свёрнутые группы, карточек «топ-3» и тройки лидеров нет', () => {
  state.data = FULL;
  mount();
  const regions = document.getElementById('tourism-regions');
  expect(regions.querySelector('.t6-card')).toBeNull();
  expect(regions.querySelector('.t6-rank')).toBeNull();
  const groups = [...regions.querySelectorAll('details.t6-group')];
  expect(groups.map((g) => g.querySelector('.t6-group__title').textContent))
    .toEqual(['tourism.group.flows', 'tourism.group.stay', 'tourism.group.business']);
  expect(groups.every((g) => !g.open)).toBe(true);
  expect(within(regions).getByRole('link', { name: /Туристские фирмы/, hidden: true }).getAttribute('href'))
    .toBe('/russia/region-rating/turfirmy');
  expect(regions.textContent).not.toMatch(/показ\./);
});

it('мир: рейтинги и один список «Куда ездят россияне» из строк «страна, период, число», ссылка «все страны»', () => {
  state.data = FULL;
  mount();
  const world = document.getElementById('tourism-world');
  expect(within(world).getByRole('link', { name: 'Прибытия туристов' }).getAttribute('href')).toBe('/world/rating/tourist-arrivals');
  const rows = [...world.querySelectorAll('.t6-trip')];
  expect(rows).toHaveLength(2);
  expect(rows[0].getAttribute('href')).toBe('/russia/indicator/tour-outbound-turkey');
  expect(rows[0].querySelector('.t6-trip__name').textContent).toBe('Турция');
  expect(rows[0].querySelector('.t6-trip__period').textContent).toBe('2025');
  expect(rows[0].querySelector('.t6-trip__v').textContent.replace(/\s/g, '')).toBe('5123тыс.');
  expect(world.querySelector('.t6-country')).toBeNull();
  expect(within(world).getByRole('link', { name: /kt3_allCountries:1/ }).getAttribute('href')).toBe('/');
});

it('подпись «все страны»: число из countries_count; без него — длина списка; без России — пометка', () => {
  state.data = { ...FULL, world: { ...FULL.world, countries_count: 54 } };
  mount();
  expect(screen.getByRole('link', { name: /^kt3_allCountries:54$/ })).toBeTruthy();
  cleanup();
  state.data = { ...FULL, world: { ...FULL.world, countries_count: 54, russia_included: false } };
  mount();
  expect(screen.getByRole('link', { name: /^kt3_allCountriesEx:54,страны$/ })).toBeTruthy();
  cleanup();
  state.data = FULL;
  mount();
  expect(screen.getByRole('link', { name: /^kt3_allCountries:1$/ })).toBeTruthy();
});

it('остальные ряды России — пять свёрнутых групп по смыслу', () => {
  const mk = (code, extra = {}) => ({ code, name: code, frequency: 'annual', current_date: '2023-12-31', ...extra });
  render(<MemoryRouter><TourismRussiaCatalog indicators={[
    mk('tour-hist-outbound'), mk('tour-agencies'), mk('tour-package-price'), mk('tour-air-passengers'), mk('tour-tax'),
  ]} /></MemoryRouter>);
  const titles = [...document.querySelectorAll('.t6-group__title')].map((h) => h.textContent);
  expect(titles).toEqual(['kt3_group_trips', 'kt3_group_stay', 'kt3_group_prices', 'kt3_group_transport', 'kt3_group_money']);
  expect(document.querySelector('details').open).toBe(false);
});

it('навигация по этажам ведёт к якорям и прячется, если этаж один', () => {
  state.data = FULL;
  mount();
  const nav = screen.getByRole('navigation', { name: 'tourism.nav.label' });
  expect([...nav.querySelectorAll('a')].map((a) => a.getAttribute('href')))
    .toEqual(['#category-list', '#tourism-regions', '#tourism-world']);
  expect([...nav.querySelectorAll('a')].map((a) => a.textContent)).toEqual(['kt3_navRussia', 'kt3_navRegions', 'kt3_navWorld']);
  cleanup();
  state.data = { russia: { count: 3 }, regions: { count: 0, items: [] }, world: { count: 0, countries: [], concepts: [] } };
  mount();
  expect(screen.queryByRole('navigation')).toBeNull();
  expect(document.getElementById('tourism-regions')).toBeNull();
  expect(document.getElementById('tourism-world')).toBeNull();
});
