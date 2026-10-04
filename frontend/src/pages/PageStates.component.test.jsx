// Ожидание и ошибка на страницах регионов / Today / мирового индикатора:
// скелетон объявляется скринридеру, на сбое — понятный текст и кнопка «Повторить».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import RegionProfile from './RegionProfile';
import RegionRatingsHub from './RegionRatingsHub';
import RegionComparePage from './RegionComparePage';
import TodayIndicatorPage from './TodayIndicatorPage';
import api from '../lib/api';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function failEverything() {
  mockApiGet([['/auth/me', { user: null }]]);
}

describe('состояния ошибки на страницах данных', () => {
  it('профиль региона: текст ошибки и «Повторить»', async () => {
    failEverything();
    renderPage(<RegionProfile />, { path: '/russia/region/:slug', route: '/russia/region/moskva' });
    expect(await screen.findByText('Не удалось загрузить страницу региона.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
  });

  it('каталог рейтингов: текст ошибки и «Повторить»', async () => {
    failEverything();
    renderPage(<RegionRatingsHub />, { path: '/russia/region-rating', route: '/russia/region-rating' });
    expect(await screen.findByText('Не удалось загрузить каталог показателей.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
  });

  it('сравнение регионов: текст ошибки и «Повторить»', async () => {
    failEverything();
    renderPage(<RegionComparePage />, { path: '/russia/region-vs/:pair', route: '/russia/region-vs/moskva-vs-spb' });
    expect(await screen.findByText('Не удалось загрузить сравнение регионов.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
  });

  it('Today-страница: текст ошибки и «Повторить»', async () => {
    failEverything();
    renderPage(<TodayIndicatorPage />, { path: '/today/:code', route: '/today/usd-rub' });
    expect(await screen.findByText(/Не удалось загрузить данные/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
  });

  it('пока данные грузятся, скелетон объявлен как «ожидание»', async () => {
    vi.spyOn(api, 'get').mockImplementation(() => new Promise(() => {}));
    renderPage(<RegionProfile />, { path: '/russia/region/:slug', route: '/russia/region/moskva' });
    const busy = await screen.findAllByRole('status');
    expect(busy.some((el) => el.getAttribute('aria-busy') === 'true')).toBe(true);
  });
});
