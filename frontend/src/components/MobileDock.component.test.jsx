import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import { OPEN_NAV_MENU_EVENT } from '../lib/navItems';
import MobileDock from './MobileDock';

async function scrollTo(y) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
  await act(async () => {
    window.dispatchEvent(new Event('scroll'));
    await new Promise((resolve) => { setTimeout(resolve, 40); });
  });
}

function renderDock(route = '/', locale = 'ru') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <LocaleProvider locale={locale}>
        <MobileDock />
      </LocaleProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
  document.documentElement.style.removeProperty('--fe-dock-h');
});

describe('MobileDock: нижняя док-панель телефона', () => {
  it('пять пунктов: Страны, Рейтинг, Сравнение, Прогнозы, Ещё; ссылки ведут на свои разделы', () => {
    renderDock();
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    const labels = [...dock.querySelectorAll('.fe-dock__label')].map((n) => n.textContent);
    expect(labels).toEqual(['Страны', 'Рейтинг', 'Сравнение', 'Прогнозы', 'Ещё']);
    const hrefs = [...dock.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/#countries', '/world/rating/gdp-usd', '/compare', '/forecasts']);
    expect(dock.querySelectorAll('button')).toHaveLength(1);
  });

  it('EN: подписи на английском', () => {
    renderDock('/', 'en');
    const dock = screen.getByRole('navigation', { name: 'Main sections' });
    expect([...dock.querySelectorAll('.fe-dock__label')].map((n) => n.textContent)).toEqual([
      'Countries', 'Rankings', 'Compare', 'Forecasts', 'More',
    ]);
  });

  it('до первой прокрутки панель спрятана, после прокрутки вниз ждёт остановки, при движении вверх появляется', async () => {
    renderDock();
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    expect(dock.getAttribute('data-visible')).toBe('false');
    await scrollTo(300);
    // Страница едет вниз: панель остаётся спрятанной.
    expect(dock.getAttribute('data-visible')).toBe('false');
    // Движение вверх: панель выплывает, резерв под ней записан в корень документа.
    await scrollTo(220);
    expect(dock.getAttribute('data-visible')).toBe('true');
    expect(document.documentElement.style.getPropertyValue('--fe-dock-h')).toBe('76px');
  });

  it('после остановки прокрутки панель появляется и без движения вверх', async () => {
    renderDock();
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    await scrollTo(400);
    expect(dock.getAttribute('data-visible')).toBe('false');
    await act(async () => { await new Promise((resolve) => { setTimeout(resolve, 800); }); });
    expect(dock.getAttribute('data-visible')).toBe('true');
  });

  it('текущий раздел отмечен: на сравнении активно «Сравнение»', () => {
    renderDock('/compare');
    const active = screen.getByRole('link', { name: 'Сравнение' });
    expect(active.getAttribute('aria-current')).toBe('page');
    expect(active.className).toContain('is-active');
    expect(screen.getByRole('link', { name: 'Прогнозы' }).getAttribute('aria-current')).toBeNull();
  });

  it('«Ещё» просит шапку открыть меню (событие), а не живёт своим состоянием', () => {
    renderDock();
    let fired = 0;
    const onOpen = () => { fired += 1; };
    window.addEventListener(OPEN_NAV_MENU_EVENT, onOpen);
    try {
      fireEvent.click(screen.getByRole('button', { name: 'Ещё' }));
    } finally {
      window.removeEventListener(OPEN_NAV_MENU_EVENT, onOpen);
    }
    expect(fired).toBe(1);
  });

  it('на служебных страницах /admin/* панели нет', () => {
    renderDock('/admin/bi');
    expect(screen.queryByRole('navigation')).toBeNull();
  });
});
