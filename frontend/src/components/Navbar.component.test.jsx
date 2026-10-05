import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import Navbar from './Navbar';
import { switchLanguage, buildLanguageSwitchUrl } from '../i18n/locale';
import { resolveActiveNavId } from '../lib/navItems';
import Footer from './Footer';
import { renderPage, mockApiGet } from '../test/renderPage';
import {
  calendarPath,
  demographicsPath,
  regionHubPath,
  regionRatingHubPath,
  russiaHomePath,
  todayPath,
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

function renderShell(route = '/', locale) {
  mockApiGet([['/auth/me', { user: null }]]);
  return renderPage(
    <>
      <Navbar />
      <Footer />
    </>,
    { path: '*', route, locale },
  );
}

describe('Navbar H-4 menu', () => {
  it('десктоп: Страны, Рейтинг, Сравнение, Прогнозы, Россия и Инструменты; на главную ведёт логотип', () => {
    renderShell();

    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: /Регионы/i })).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Демография' })).toBeNull();
    // Витрина «Мировая экономика» снята: её содержимое переехало на главную.
    expect(within(nav).queryByRole('link', { name: 'Мировая экономика' })).toBeNull();
    // «Главная» не пункт меню: сайт мировой, а не про одну страну.
    expect(within(nav).queryByRole('link', { name: 'Главная' })).toBeNull();
    expect(within(nav).getByRole('link', { name: 'Forecast Economy — на главную' }).getAttribute('href')).toBe('/');

    // До xl подпись короткая, с xl — полная: в DOM обе, имя ссылки склеенное.
    expect(within(nav).getByRole('link', { name: /Страны/ }).getAttribute('href')).toBe('/#countries');
    expect(within(nav).getByRole('link', { name: /Рейтинг/ }).getAttribute('href')).toBe('/world/rating/gdp-usd');
    expect(within(nav).getByRole('link', { name: 'Сравнение' }).getAttribute('href')).toBe('/compare');
    expect(within(nav).getByRole('link', { name: 'Прогнозы' }).getAttribute('href')).toBe('/forecasts');
    expect(within(nav).getByRole('link', { name: 'Россия' }).getAttribute('href')).toBe(russiaHomePath());
    expect(within(nav).getByRole('button', { name: /Инструменты/i })).toBeTruthy();
  });

  it('мобильное меню: мировые разделы сверху с подписями, «Россия» одной раскрывающейся строкой', () => {
    renderShell();

    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));

    const menu = document.getElementById('fe-nav-mobile-menu');
    const hrefs = (root) => [...root.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    const links = hrefs(menu);
    // Порядок: страны, рейтинг, сравнение, прогнозы, категории, валюты, «Как мы считаем».
    const order = ['/#countries', '/world/rating/gdp-usd', '/compare', '/forecasts', '/russia/category', '/currencies', '/methodology'];
    expect(order.map((href) => links.indexOf(href))).toEqual([...order.keys()]);
    expect(within(menu).queryByRole('link', { name: 'Демография' })).toBeNull();

    // Подпись к каждому пункту: что внутри.
    const rating = [...menu.querySelectorAll('a')].find((a) => a.getAttribute('href') === '/world/rating/gdp-usd');
    expect(rating.querySelector('.fe-mnav-label').textContent).toBe('Рейтинг стран');
    expect(rating.querySelector('.fe-mnav-hint').textContent).toMatch(/впереди/);
    expect(menu.querySelectorAll('.fe-mnav-hint').length).toBeGreaterThanOrEqual(8);
    // Одно название «Сравнение» вместо «Сравнение индикаторов».
    expect(within(menu).queryByText('Сравнение индикаторов')).toBeNull();

    // Россия: одна строка-кнопка, пока закрыта пунктов России не видно.
    const russia = within(menu).getByRole('button', { name: /^Россия/ });
    expect(russia.getAttribute('aria-expanded')).toBe('false');
    expect(links).not.toContain(todayPath());
    fireEvent.click(russia);
    expect(russia.getAttribute('aria-expanded')).toBe('true');
    const opened = hrefs(menu);
    expect(opened).toEqual(expect.arrayContaining([russiaHomePath(), todayPath(), regionHubPath(), calendarPath()]));
    expect(within(menu).getByRole('link', { name: 'Экономика России' })).toBeTruthy();
    expect(within(menu).getByRole('link', { name: 'Новые данные сегодня' })).toBeTruthy();

    // «О проекте» и «Написать нам» рядом, в конце списка.
    const tail = hrefs(menu).slice(-2);
    expect(tail).toEqual(['/about', 'mailto:rebeka.ee@yandex.ru']);
    expect(within(menu).getByRole('link', { name: 'Калькулятор инфляции' })).toBeTruthy();
    expect(within(menu).getByRole('link', { name: 'Ипотечный калькулятор' })).toBeTruthy();
    expect(within(menu).getByRole('link', { name: 'Сложные проценты' })).toBeTruthy();
  });

  it('мобильное меню: на страницах России группа «Россия» раскрыта сама', () => {
    renderShell('/russia/indicator/cpi');
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    expect(within(menu).getByRole('button', { name: /^Россия/ }).getAttribute('aria-expanded')).toBe('true');
    expect(within(menu).getByRole('link', { name: 'Новые данные сегодня' }).getAttribute('href')).toBe(todayPath());
  });

  it('EN: в меню телефона те же мировые разделы, Russia раскрывающейся строкой', () => {
    renderShell('/', 'en');

    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const menu = document.getElementById('fe-nav-mobile-menu');
    const links = [...menu.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    for (const href of ['/#countries', '/world/rating/gdp-usd', '/compare', '/forecasts', '/russia/category', '/currencies', '/methodology']) {
      expect(links).toContain(href);
    }
    const russia = within(menu).getByRole('button', { name: /^Russia/ });
    fireEvent.click(russia);
    expect(within(menu).getByRole('link', { name: 'New data today' })).toBeTruthy();
    expect(within(menu).getByRole('link', { name: 'Regions' })).toBeTruthy();
    expect(within(menu).getByRole('link', { name: 'Calendar' })).toBeTruthy();
    expect(within(menu).getByRole('link', { name: /^Compare/ })).toBeTruthy();
  });

  it('раздел /regions не осиротел: ссылка есть в футере', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    const regions = within(footer).getByRole('link', { name: 'Регионы России' });
    expect(regions.getAttribute('href')).toBe(regionHubPath());
  });

  it('карточка России и хаб «Экономика сегодня» доступны из футера', () => {
    renderShell();

    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByRole('link', { name: 'Россия' }).getAttribute('href'))
      .toBe(russiaHomePath());
    // Одно слово «Сегодня» слишком общее для анкора. Хаб — отдельная ссылка.
    expect(within(footer).queryByRole('link', { name: 'Сегодня', exact: true })).toBeNull();
    expect(within(footer).getByRole('link', { name: 'Экономика сегодня' }).getAttribute('href'))
      .toBe(todayPath());
    expect(within(footer).getByRole('link', { name: 'Рейтинги регионов' }).getAttribute('href'))
      .toBe(regionRatingHubPath());
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

  it('на /world/rating/* подсвечен «Рейтинг стран»', () => {
    renderShell('/world/rating/unemployment-rate');

    const nav = screen.getByRole('navigation');
    const rating = within(nav).getAllByRole('link', { name: /Рейтинг/ })[0];
    expect(rating.getAttribute('aria-current')).toBe('page');
    expect(within(nav).getByRole('link', { name: 'Сравнение' }).getAttribute('aria-current')).toBeNull();
  });

  it('на карточке показателя России подсвечена «Россия»', () => {
    renderShell('/russia/indicator/cpi');

    const nav = screen.getByRole('navigation');
    const russia = within(nav).getAllByRole('link', { name: 'Россия' })[0];
    expect(russia.getAttribute('aria-current')).toBe('page');
  });

  it('EN-версия: пункта «Россия»/«Russia» в шапке нет, вместо него США; в меню телефона Russia есть', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('preview_locale', 'en');
    window.history.pushState({}, '', url.toString());
    try {
      renderShell('/russia/indicator/cpi');

      const nav = screen.getByRole('navigation');
      // Пункт скрыт в шапке даже на страницах русского раздела...
      expect(within(nav).queryByRole('link', { name: 'Россия' })).toBeNull();
      expect(within(nav).queryByRole('link', { name: 'Russia' })).toBeNull();
      expect(within(nav).queryByRole('link', { name: 'Country rankings' })).toBeNull();
      expect(within(nav).queryByRole('link', { name: /Rankings/ })).toBeTruthy();
      expect(within(nav).queryByRole('link', { name: /United States|USA/ })).toBeTruthy();
      const usLinks = within(nav).queryAllByRole('link', { name: /United States|USA/ });
      expect(usLinks.every((a) => a.getAttribute('href') === '/united-states')).toBe(true);
      // ...но подсветка активной страницы /russia не ломается: сам пункт ни на что не указывает.
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

  it('EN: пункт United States в шапке, колонка United States в футере, без Росстата в Sources', () => {
    renderShell('/', 'en');

    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: 'Россия' })).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Russia' })).toBeNull();
    const usNav = within(nav).getAllByRole('link', { name: /United States|USA/ });
    expect(usNav[0].getAttribute('href')).toBe('/united-states');

    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByRole('heading', { name: 'United States' })).toBeTruthy();
    expect(within(footer).getByRole('link', { name: 'Unemployment rate' }).getAttribute('href'))
      .toBe('/united-states/indicator/us-unemployment-rate');
    expect(within(footer).getByRole('link', { name: 'Consumer Price Index' }).getAttribute('href'))
      .toBe('/united-states/indicator/us-cpi-all');
    expect(within(footer).getByRole('link', { name: 'Real GDP' }).getAttribute('href'))
      .toBe('/united-states/indicator/us-gdp-real');
    expect(within(footer).getByRole('link', { name: 'Federal funds rate' }).getAttribute('href'))
      .toBe('/united-states/indicator/us-policy-rate');
    expect(within(footer).getByRole('link', { name: 'All countries' }).getAttribute('href'))
      .toBe('/#countries');
    expect(within(footer).queryByRole('link', { name: 'Rosstat' })).toBeNull();
    expect(within(footer).queryByRole('link', { name: 'Bank of Russia' })).toBeNull();
    expect(within(footer).getByRole('link', { name: 'Eurostat' })).toBeTruthy();
    expect(within(footer).getByRole('link', { name: 'U.S. Bureau of Labor Statistics' })).toBeTruthy();
    expect(footer.textContent).not.toMatch(/especially deep/i);
  });

  it('EN: на /united-states подсвечен United States', () => {
    renderShell('/united-states', 'en');

    const nav = screen.getByRole('navigation');
    const us = within(nav).getAllByRole('link', { name: /United States|USA/ })[0];
    expect(us.getAttribute('aria-current')).toBe('page');
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

  it('до cutover English с localhost не уходит на прод-apex и ставит preview_locale=en', () => {
    const next = buildLanguageSwitchUrl('en', {
      href: 'http://localhost:3000/',
      hostname: 'localhost',
      apexLocaleEn: false,
    });
    const url = new URL(next);
    expect(url.origin).toBe('http://localhost:3000');
    expect(url.hostname).not.toBe('forecasteconomy.com');
    expect(url.searchParams.get('preview_locale')).toBe('en');
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
    expect(resolveActiveNavId('/united-states')).toBe('united-states');
    expect(resolveActiveNavId('/united-states/indicator/us-cpi-all')).toBe('united-states');
    // Другая страна — не пункт меню.
    expect(resolveActiveNavId('/sweden')).toBeNull();
  });

  it('главная матчится точно, иначе «/» подсветил бы весь сайт', () => {
    expect(resolveActiveNavId('/sweden/indicator/se-cpi')).toBeNull();
  });
});
