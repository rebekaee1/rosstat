import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import Navbar from './Navbar';
import { resolveActiveNavId } from '../lib/navItems';
import Footer from './Footer';
import { renderPage, mockApiGet } from '../test/renderPage';
import {
  demographicsPath,
  regionHubPath,
} from '../lib/sitePaths';

vi.mock('gsap', () => ({
  default: {
    fromTo: () => ({ kill: () => {} }),
  },
}));

vi.mock('./IndicatorSearch', () => ({
  default: () => <div data-testid="indicator-search-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

function renderShell(route = '/') {
  mockApiGet([['/auth/me', { user: null }]]);
  return renderPage(
    <>
      <Navbar />
      <Footer />
    </>,
    { path: '*', route },
  );
}

describe('Navbar H-4 menu', () => {
  it('не содержит /regions, Категории и Демографию; содержит рейтинг стран', () => {
    renderShell();

    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: /Регионы/i })).toBeNull();
    expect(within(nav).queryByRole('link', { name: /^Категории$/i })).toBeNull();
    expect(within(nav).queryByText('Категории')).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Демография' })).toBeNull();

    const rating = within(nav).getByRole('link', { name: 'Рейтинг стран' });
    expect(rating.getAttribute('href')).toBe('/world/rating/unemployment-rate');

    expect(within(nav).getByRole('link', { name: 'Мировая экономика' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Сравнение' })).toBeTruthy();
    expect(within(nav).getByRole('button', { name: /Калькуляторы/i })).toBeTruthy();

    // «Главная» на десктопе намеренно скрыта — в закрытом мобильном меню её нет.
    expect(within(nav).queryByRole('link', { name: 'Главная' })).toBeNull();
  });

  it('мобильное меню синхронизировано с десктопом: те же primary-пункты, без демографии', () => {
    renderShell();

    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));

    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: /Регионы/i })).toBeNull();
    expect(within(nav).queryByText('Категории')).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Демография' })).toBeNull();

    // Desktop + mobile дубли в DOM (Tailwind hidden не режет a11y в jsdom).
    const ratingLinks = within(nav).getAllByRole('link', { name: 'Рейтинг стран' });
    expect(ratingLinks.length).toBe(2);
    expect(ratingLinks.every((a) => a.getAttribute('href') === '/world/rating/unemployment-rate')).toBe(true);

    expect(within(nav).getByRole('link', { name: 'Главная' })).toBeTruthy();
    expect(within(nav).getAllByRole('link', { name: 'Мировая экономика' }).length).toBe(2);
    expect(within(nav).getAllByRole('link', { name: 'Сравнение' }).length).toBe(2);
    expect(within(nav).getByRole('link', { name: 'Калькулятор инфляции' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Ипотечный калькулятор' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Сложные проценты' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'О проекте' })).toBeTruthy();
  });

  it('раздел /regions не осиротел: ссылка есть в футере', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    const regions = within(footer).getByRole('link', { name: 'Регионы России' });
    expect(regions.getAttribute('href')).toBe(regionHubPath());
  });

  it('демография не осиротела: ссылка есть в футере', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    const demo = within(footer).getByRole('link', { name: 'Демография' });
    expect(demo.getAttribute('href')).toBe(demographicsPath());
  });

  it('на /world/rating/* подсвечен «Рейтинг стран», не «Мировая экономика»', () => {
    renderShell('/world/rating/unemployment-rate');

    const nav = screen.getByRole('navigation');
    const rating = within(nav).getAllByRole('link', { name: 'Рейтинг стран' })[0];
    const world = within(nav).getAllByRole('link', { name: 'Мировая экономика' })[0];
    expect(rating.getAttribute('aria-current')).toBe('page');
    expect(world.getAttribute('aria-current')).toBeNull();
  });

  it('на /world подсвечена «Мировая экономика»', () => {
    renderShell('/world');

    const nav = screen.getByRole('navigation');
    const rating = within(nav).getAllByRole('link', { name: 'Рейтинг стран' })[0];
    const world = within(nav).getAllByRole('link', { name: 'Мировая экономика' })[0];
    expect(world.getAttribute('aria-current')).toBe('page');
    expect(rating.getAttribute('aria-current')).toBeNull();
  });
});

describe('resolveActiveNavId', () => {
  it('выбирает самый длинный совпавший префикс', () => {
    expect(resolveActiveNavId('/world/rating/unemployment-rate')).toBe('world-rating');
    expect(resolveActiveNavId('/world/rating/gdp-per-capita')).toBe('world-rating');
    expect(resolveActiveNavId('/world')).toBe('world');
    expect(resolveActiveNavId('/world/united-states')).toBe('world');
    expect(resolveActiveNavId('/compare')).toBe('compare');
    expect(resolveActiveNavId('/russia/demographics')).toBeNull();
    expect(resolveActiveNavId('/')).toBeNull();
  });
});
