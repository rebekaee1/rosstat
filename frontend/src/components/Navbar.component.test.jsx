import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import Navbar from './Navbar';
import { switchLanguage } from '../i18n/locale';
import { resolveActiveNavId } from '../lib/navItems';
import Footer from './Footer';
import { renderPage, mockApiGet } from '../test/renderPage';
import {
  demographicsPath,
  regionHubPath,
  russiaHomePath,
} from '../lib/sitePaths';

vi.mock('gsap', () => ({
  default: {
    fromTo: () => ({ kill: () => {} }),
  },
}));

vi.mock('../i18n/locale', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, switchLanguage: vi.fn() };
});

vi.mock('./IndicatorSearch', () => ({
  default: () => <div data-testid="indicator-search-stub" />,
}));

afterEach(() => {
  switchLanguage.mockClear();
  vi.restoreAllMocks();
});

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
  it('десктоп: Главная, Россия, Рейтинг стран, Сравнение и Калькуляторы — без витрины мира', () => {
    renderShell();

    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: /Регионы/i })).toBeNull();
    expect(within(nav).queryByText('Категории')).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Демография' })).toBeNull();
    // Витрина «Мировая экономика» снята: её содержимое переехало на главную.
    expect(within(nav).queryByRole('link', { name: 'Мировая экономика' })).toBeNull();

    const rating = within(nav).getByRole('link', { name: 'Рейтинг стран' });
    expect(rating.getAttribute('href')).toBe('/world/rating/gdp-usd');

    expect(within(nav).getByRole('link', { name: 'Главная' }).getAttribute('href')).toBe('/');
    expect(within(nav).getByRole('link', { name: 'Россия' }).getAttribute('href')).toBe(russiaHomePath());
    // До xl подпись короткая, с xl — полная: в DOM обе, имя ссылки склеенное.
    expect(within(nav).getByRole('link', { name: /Сравнение/ }).getAttribute('href')).toBe('/compare');
    expect(within(nav).getByRole('button', { name: /Калькуляторы/i })).toBeTruthy();
  });

  it('мобильное меню синхронизировано с десктопом: те же primary-пункты, без демографии', () => {
    renderShell();

    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));

    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: /Регионы/i })).toBeNull();
    expect(within(nav).queryByText('Категории')).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Демография' })).toBeNull();

    // Desktop + mobile дубли в DOM (Tailwind hidden не режет a11y в jsdom).
    for (const name of ['Главная', 'Россия', 'Рейтинг стран']) {
      const links = within(nav).getAllByRole('link', { name });
      expect(links.length).toBe(2);
    }
    const ratingLinks = within(nav).getAllByRole('link', { name: 'Рейтинг стран' });
    expect(ratingLinks.every((a) => a.getAttribute('href') === '/world/rating/gdp-usd')).toBe(true);
    expect(within(nav).getAllByRole('link', { name: /Сравнение/ }).length).toBe(2);

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

  it('карточка России доступна из футера, «Сегодня» скрыт', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByRole('link', { name: 'Россия' }).getAttribute('href'))
      .toBe(russiaHomePath());
    expect(within(footer).queryByRole('link', { name: 'Сегодня' })).toBeNull();
  });

  it('демография не осиротела: ссылка есть в футере', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    const demo = within(footer).getByRole('link', { name: 'Демография' });
    expect(demo.getAttribute('href')).toBe(demographicsPath());
  });

  it('каталог стран не осиротел: футер ведёт на список стран главной', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByRole('link', { name: 'Страны' }).getAttribute('href'))
      .toBe('/#countries');
  });

  it('на /world/rating/* подсвечен «Рейтинг стран», не «Главная»', () => {
    renderShell('/world/rating/unemployment-rate');

    const nav = screen.getByRole('navigation');
    const rating = within(nav).getAllByRole('link', { name: 'Рейтинг стран' })[0];
    const home = within(nav).getAllByRole('link', { name: 'Главная' })[0];
    expect(rating.getAttribute('aria-current')).toBe('page');
    expect(home.getAttribute('aria-current')).toBeNull();
  });

  it('на карточке показателя России подсвечена «Россия»', () => {
    renderShell('/russia/indicator/cpi');

    const nav = screen.getByRole('navigation');
    const russia = within(nav).getAllByRole('link', { name: 'Россия' })[0];
    const home = within(nav).getAllByRole('link', { name: 'Главная' })[0];
    expect(russia.getAttribute('aria-current')).toBe('page');
    expect(home.getAttribute('aria-current')).toBeNull();
  });

  it('EN-версия: пункта «Россия»/«Russia» в навигации нет', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('preview_locale', 'en');
    window.history.pushState({}, '', url.toString());
    try {
      renderShell('/russia/indicator/cpi');

      const nav = screen.getByRole('navigation');
      // Пункт скрыт даже на страницах русского раздела...
      expect(within(nav).queryByRole('link', { name: 'Россия' })).toBeNull();
      expect(within(nav).queryByRole('link', { name: 'Russia' })).toBeNull();
      // ...но подсветка активной страницы /russia не ломается (resolveActiveNavId
      // считает по полному массиву; сам пункт ни на что не указывает).
      expect(within(nav).queryAllByRole('link', { name: 'Home' }).length).toBeGreaterThan(0);
      expect(within(nav).queryByRole('link', { name: 'Country rankings' })).toBeTruthy();
      for (const link of within(nav).queryAllByRole('link')) {
        expect(link.getAttribute('aria-current')).toBeNull();
      }

      const triggers = within(nav).getAllByRole('button', { name: 'Language: English' });
      expect(triggers.length).toBeGreaterThan(0);
      expect(within(nav).queryByRole('button', { name: 'Язык: Русский' })).toBeNull();
      expect(within(nav).queryByText('Русская версия')).toBeNull();

      fireEvent.click(triggers[0]);
      fireEvent.click(within(nav).getByRole('menuitem', { name: 'Русский' }));
      expect(switchLanguage).toHaveBeenCalledWith('ru');
    } finally {
      const reset = new URL(window.location.href);
      reset.searchParams.delete('preview_locale');
      window.history.pushState({}, '', reset.toString());
    }
  });

  it('RU: в header флаг текущего языка, список — оба языка, English вызывает switchLanguage(en)', () => {
    renderShell();

    const nav = screen.getByRole('navigation');
    const triggers = within(nav).getAllByRole('button', { name: 'Язык: Русский' });
    expect(triggers.length).toBeGreaterThan(0);
    expect(within(nav).queryByRole('button', { name: 'English' })).toBeNull();
    expect(within(nav).queryByText('English')).toBeNull();

    fireEvent.click(triggers[0]);
    expect(within(nav).getByRole('menuitem', { name: 'Русский' }).getAttribute('aria-current')).toBe('true');
    expect(within(nav).getByRole('menuitem', { name: 'English' })).toBeTruthy();

    fireEvent.click(within(nav).getByRole('menuitem', { name: 'Русский' }));
    expect(switchLanguage).not.toHaveBeenCalled();

    fireEvent.click(triggers[0]);
    fireEvent.click(within(nav).getByRole('menuitem', { name: 'English' }));
    expect(switchLanguage).toHaveBeenCalledTimes(1);
    expect(switchLanguage).toHaveBeenCalledWith('en');
  });
});

describe('resolveActiveNavId', () => {
  it('выбирает самый длинный совпавший префикс', () => {
    expect(resolveActiveNavId('/world/rating/unemployment-rate')).toBe('world-rating');
    expect(resolveActiveNavId('/world/rating/gdp-per-capita')).toBe('world-rating');
    expect(resolveActiveNavId('/russia')).toBe('russia');
    expect(resolveActiveNavId('/russia/region/moskva')).toBe('russia');
    expect(resolveActiveNavId('/compare')).toBe('compare');
    expect(resolveActiveNavId('/')).toBe('home');
    // Карточка страны — не пункт меню: подсветки быть не должно.
    expect(resolveActiveNavId('/sweden')).toBeNull();
  });

  it('главная матчится точно, иначе «/» подсветил бы весь сайт', () => {
    expect(resolveActiveNavId('/sweden/indicator/se-cpi')).toBeNull();
  });
});
