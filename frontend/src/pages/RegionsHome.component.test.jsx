import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import RegionsHome from './RegionsHome';
import { mockApiGet, renderPage } from '../test/renderPage';

vi.mock('../components/RegionsMap', () => ({ default: () => <div data-testid="regions-map" /> }));
vi.mock('../components/MapTimeline', () => ({ default: () => null }));
afterEach(() => vi.restoreAllMocks());

const landing = {
  totals: { points: 2, indicators: 2, regions: 2 },
  districts: [{ slug: 'dfo', name: 'Дальневосточный округ', regions: [
    { slug: 'khabarovskiy-kray', name: 'Хабаровский край', name_en: 'Khabarovsk Krai', stats: {} },
    { slug: 'primorskiy-kray', name: 'Приморский край', name_en: 'Primorsky Krai', stats: {} },
  ] }],
};
const catalog = { sections: [{ name: 'Производство', indicators: [
  { code: 'bread', name: 'Производство хлебных изделий', name_en: 'Bread production', frequency: 'annual', unit: 'тонны' },
  { code: 'wages', name: 'Средняя зарплата', name_en: 'Average wage', frequency: 'annual', unit: 'рубли' },
  { code: 'road-density', name: 'Плотность автомобильных дорог общего пользования с твердым покрытием', frequency: 'annual', unit: 'км на 1000 км²' },
] }] };

function mount(route, locale = 'ru') {
  const get = mockApiGet([
    ['/auth/me', { user: null }], ['/regions', landing], ['/regions/catalog', catalog],
    [/^\/regions\/heatmap/, { values: [] }],
  ]);
  renderPage(<RegionsHome />, { path: '*', route, locale });
  return get;
}

describe('RegionsHome scoped keyboard correction', () => {
  it('preserves keyboard punctuation when matching the supplied region list', async () => {
    const get = mount('/russia/region');
    const input = await screen.findByRole('searchbox', { name: 'Поиск региона' });
    await screen.findByRole('link', { name: 'Хабаровский край' });
    fireEvent.change(input, { target: { value: '[f,fhjdcrbq rhfq' } });
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Приморский край' })).toBeNull());
    expect(screen.getByRole('link', { name: 'Хабаровский край' }).getAttribute('href')).toBe('/russia/region/khabarovskiy-kray');
    fireEvent.change(input, { target: { value: 'California' } });
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Хабаровский край' })).toBeNull());
    expect(get.mock.calls.some(([url]) => url === '/search')).toBe(false);
  });

  it.each([
    ['ru', 'Найти показатель для карты'], ['en', 'Find an indicator for the map'],
  ])('matches punctuation-layout metric input in the %s map catalogue without dropping frequency or unit', async (locale, label) => {
    const get = mount('/russia/region/map/overview', locale);
    const input = await screen.findByRole('combobox', { name: label });
    await waitFor(() => expect(get).toHaveBeenCalledWith('/regions/catalog', expect.anything()));
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '[kt,ys[' } });
    expect(await screen.findByRole('button', { name: /Производство хлебных изделий/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Средняя зарплата/ })).toBeNull();
    fireEvent.change(input, { target: { value: '[kt,ys[ vtczwfv' } });
    await waitFor(() => expect(screen.queryByRole('button', { name: /Производство хлебных изделий/ })).toBeNull());
    fireEvent.change(input, { target: { value: '[kt,ys[ %' } });
    expect(screen.queryByRole('button', { name: /Производство хлебных изделий/ })).toBeNull();
    expect(get.mock.calls.some(([url]) => url === '/search')).toBe(false);
  });

  it('keeps a partially typed native metric title discoverable without dropping added facets', async () => {
    mount('/russia/region/map/overview');
    const input = await screen.findByRole('combobox', { name: 'Найти показатель для карты' });
    fireEvent.focus(input);
    const q = 'Плотность автомобильных дорог общего пользования с твердым п';
    fireEvent.change(input, { target: { value: q } });
    expect(await screen.findByRole('button', { name: /Плотность автомобильных дорог общего пользования с твердым покрытием/ })).toBeTruthy();
    fireEvent.change(input, { target: { value: `${q} %` } });
    expect(screen.queryByRole('button', { name: /Плотность автомобильных дорог/ })).toBeNull();
    fireEvent.change(input, { target: { value: `${q} ежемесячно` } });
    expect(screen.queryByRole('button', { name: /Плотность автомобильных дорог/ })).toBeNull();
  });
});
