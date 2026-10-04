import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import RegionRatingsHub from './RegionRatingsHub';
import { mockApiGet, renderPage } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const CATALOG = {
  sections: [
    { name: 'Труд', indicators: [
      { code: 'uroven-bezrabotitsy', name: 'Уровень безработицы' },
      { code: 'chislo-zanyatyh', name: 'Число занятых' },
    ] },
    { name: 'Здоровье', indicators: [
      { code: 'chislo-vrachey', name: 'Число врачей' },
    ] },
  ],
};
const HEAT = {
  indicator: { code: 'x', name: 'Показатель', unit: 'рублей' },
  year: 2024,
  default_sort: 'desc',
  values: [
    { slug: 'a', name: 'Чукотка', value: 188561, raw: 188561 },
    { slug: 'b', name: 'Ямал', value: 150000, raw: 150000 },
    { slug: 'c', name: 'Москва', value: 120000, raw: 120000 },
    { slug: 'd', name: 'Ингушетия', value: 40588, raw: 40588 },
  ],
};

function mount() {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/regions/catalog', CATALOG],
    [/^\/regions\/heatmap\//, HEAT],
  ]);
  renderPage(<RegionRatingsHub />, { path: '/russia/region-rating', route: '/russia/region-rating' });
}

describe('RegionRatingsHub', () => {
  it('сверху поиск, ниже популярные рейтинги с тройкой лидеров', async () => {
    mount();
    expect(await screen.findByRole('searchbox', { name: 'Поиск рейтинга по показателю' })).toBeTruthy();
    const popular = await screen.findByRole('heading', { name: 'Популярные рейтинги' });
    expect(popular).toBeTruthy();
    const card = (await screen.findAllByRole('link', { name: /Зарплата/ }))[0];
    await waitFor(() => expect(within(card).getByText('Чукотка')).toBeTruthy());
    expect(within(card).getByText('Ямал')).toBeTruthy();
    expect(within(card).getByText('Москва')).toBeTruthy();
    expect(within(card).queryByText('Ингушетия')).toBeNull();
    expect(card.getAttribute('href')).toBe('/russia/region-rating/srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy');
  });

  it('остальные показатели свёрнуты по темам: названия видны только в раскрытой теме', async () => {
    mount();
    await screen.findByRole('heading', { name: 'Остальные показатели по темам' });
    expect(screen.queryByRole('link', { name: 'Число врачей' })).toBeNull();
    fireEvent.click(screen.getByText('Здоровье'));
    expect(await screen.findByRole('link', { name: 'Число врачей' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Число занятых' })).toBeNull();
  });

  it('поиск показывает плоский список совпадений вместо групп, а пустой — предлагает сбросить', async () => {
    mount();
    const input = await screen.findByRole('searchbox', { name: 'Поиск рейтинга по показателю' });
    await screen.findByRole('heading', { name: 'Популярные рейтинги' });
    fireEvent.change(input, { target: { value: 'врач' } });
    expect(await screen.findByRole('link', { name: /Число врачей/ })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Популярные рейтинги' })).toBeNull();
    fireEvent.change(input, { target: { value: 'zzzzzz' } });
    expect(await screen.findByRole('button', { name: 'Сбросить поиск' })).toBeTruthy();
  });
});
