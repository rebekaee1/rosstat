// @vitest-environment jsdom
// Раздел «Туризм» (20.11.2026): этажи «Регионы России» и «Мир», навигация по этажам, пустые этажи не рисуются.
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TourismFloors, { TourismJump } from './TourismFloors';

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
    count: 2,
    items: [
      {
        code: 'kollektivnye-sredstva', name: 'Коллективные средства размещения', unit: 'единица', year: 2024,
        period: 2024, rating_path: '/russia/region-rating/kollektivnye-sredstva',
        map_path: '/russia/region/map/kollektivnye-sredstva',
        leaders: [
          { slug: 'krasnodarskiy-kray', name: 'Краснодарский край', value: 2600, path: '/russia/region/krasnodarskiy-kray/kollektivnye-sredstva' },
          { slug: 'moskva', name: 'г. Москва', value: 1500.4, path: '/russia/region/moskva/kollektivnye-sredstva' },
        ],
      },
      { code: 'turfirmy', name: 'Туристские фирмы', unit: 'единица', year: 2023, rating_path: '/russia/region-rating/turfirmy', map_path: '/russia/region/map/turfirmy' },
    ],
  },
  world: {
    count: 1,
    concepts: [{ slug: 'tourist-arrivals', name: 'Прибытия туристов', path: '/world/rating/tourist-arrivals' }],
    countries: [{ slug: 'turkey', name: 'Турция', path: '/turkey', count: 4, series: [{ code: 'tr-arr', name: 'Прибытия иностранных туристов', path: '/turkey/indicator/tr-arr' }] }],
  },
};

function mount() {
  return render(<MemoryRouter><TourismJump /><TourismFloors /></MemoryRouter>);
}

it('показывает три первых региона в карточке и остальные показатели строками', () => {
  state.data = FULL;
  mount();
  const regions = document.getElementById('tourism-regions');
  const card = regions.querySelector('.t6-card');
  expect(within(card).getByRole('link', { name: 'Коллективные средства размещения' }).getAttribute('href'))
    .toBe('/russia/region-rating/kollektivnye-sredstva');
  const leaders = [...card.querySelectorAll('.t6-rank__name')].map((a) => a.textContent);
  expect(leaders).toEqual(['Краснодарский край', 'г. Москва']);
  expect(card.querySelector('.t6-rank__v').textContent.replace(/\s/g, '')).toBe('2600');
  expect(within(card).getByRole('link', { name: 'tourism.regions.map' }).getAttribute('href'))
    .toBe('/russia/region/map/kollektivnye-sredstva');
  const rest = regions.querySelector('.t6-rows');
  expect(within(rest).getByRole('link', { name: /Туристские фирмы/ }).getAttribute('href')).toBe('/russia/region-rating/turfirmy');
});

it('мир: рейтинги стран и страны с прямыми ссылками на ряды', () => {
  state.data = FULL;
  mount();
  const world = document.getElementById('tourism-world');
  expect(within(world).getByRole('link', { name: 'Прибытия туристов' }).getAttribute('href')).toBe('/world/rating/tourist-arrivals');
  expect(within(world).getByRole('link', { name: 'Турция' }).getAttribute('href')).toBe('/turkey');
  expect(within(world).getByRole('link', { name: 'Прибытия иностранных туристов' }).getAttribute('href')).toBe('/turkey/indicator/tr-arr');
});

it('навигация по этажам ведёт к якорям и прячется, если этаж один', () => {
  state.data = FULL;
  mount();
  const nav = screen.getByRole('navigation', { name: 'tourism.nav.label' });
  expect([...nav.querySelectorAll('a')].map((a) => a.getAttribute('href')))
    .toEqual(['#category-list', '#tourism-regions', '#tourism-world']);
  cleanup();
  state.data = { russia: { count: 3 }, regions: { count: 0, items: [] }, world: { count: 0, countries: [], concepts: [] } };
  mount();
  expect(screen.queryByRole('navigation')).toBeNull();
  expect(document.getElementById('tourism-regions')).toBeNull();
  expect(document.getElementById('tourism-world')).toBeNull();
});
