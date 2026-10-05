import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import Navbar from './Navbar';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('./IndicatorSearch', () => ({
  default: () => <div data-testid="indicator-search-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

function renderNav(locale) {
  mockApiGet([['/auth/me', { user: null }]]);
  return renderPage(<Navbar />, { path: '*', route: '/', locale });
}

describe('Navbar: появление и закрытие панелей', () => {
  it('шапка видна сразу: появление задаётся классом CSS, а не скрытием до старта JS-твина', () => {
    renderNav();
    const nav = screen.getByRole('navigation');
    expect(nav.className).toContain('fe-reveal');
    // начальное состояние не прячет шапку инлайном
    expect(nav.style.opacity).toBe('');
  });

  it('мобильное меню: появляется с классом панели, закрывается по Esc и возвращает фокус на кнопку', () => {
    renderNav();
    const toggle = screen.getByRole('button', { name: 'Открыть меню' });
    fireEvent.click(toggle);

    const menu = document.getElementById('fe-nav-mobile-menu');
    expect(menu).toBeTruthy();
    expect(menu.className).toContain('fe-reveal--panel');
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(toggle.getAttribute('aria-controls')).toBe('fe-nav-mobile-menu');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Открыть меню' }));
  });

  it('мобильное меню: «Войти» и «Регистрация» закреплены внизу вне прокручиваемого списка и выровнены одинаково', async () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const scroll = menu.querySelector('.fe-mnav-scroll');
    const foot = menu.querySelector('.fe-mnav-foot');
    expect(scroll).toBeTruthy();
    expect(foot).toBeTruthy();
    await waitFor(() => expect(foot.querySelectorAll('a').length).toBe(2));
    const login = [...foot.querySelectorAll('a')].find((a) => a.getAttribute('href') === '/login');
    const register = [...foot.querySelectorAll('a')].find((a) => a.getAttribute('href')?.startsWith('/register'));
    expect(login).toBeTruthy();
    expect(register).toBeTruthy();
    // Кнопки не внутри прокручиваемой части — видны сразу.
    expect(scroll.contains(login)).toBe(false);
    expect(scroll.contains(register)).toBe(false);
    // Текст у обеих по центру: раньше «Войти» прижималось влево из-за display:flex.
    expect(login.className).toContain('justify-center');
    expect(register.className).toContain('justify-center');
  });

  it('мобильное меню: у трёх калькуляторов разные значки, а «Валюты» есть в основном разделе', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const calcLinks = ['Калькулятор инфляции', 'Ипотечный калькулятор', 'Сложные проценты']
      .map((name) => [...menu.querySelectorAll('a')].find((a) => a.textContent.trim() === name));
    expect(calcLinks.every(Boolean)).toBe(true);
    const icons = calcLinks.map((a) => a.querySelector('svg').getAttribute('class'));
    expect(new Set(icons).size).toBe(3);
    expect([...menu.querySelectorAll('a')].some((a) => a.getAttribute('href') === '/currencies')).toBe(true);
  });

  it('выпадашка инструментов: три калькулятора и виджеты, у каждого пометка, для кого он', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    const menu = screen.getByRole('menu');
    const hrefs = [...menu.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/calculator', '/calculator/mortgage', '/calculator/compound', '/widgets']);
    expect(menu.textContent).toContain('Россия и страны мира');
    expect(menu.textContent).toContain('Для рублёвых кредитов');
    expect(menu.textContent).toContain('Для любой валюты');
    expect(menu.textContent).toContain('Встроить график на сайт');
  });

  it('мобильное меню: «Виджеты» лежат в группе «Инструменты» вместе с калькуляторами', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const widgets = [...menu.querySelectorAll('a')].find((a) => a.getAttribute('href') === '/widgets');
    expect(widgets).toBeTruthy();
    expect(widgets.textContent.trim()).toBe('Виджеты');
    expect(widgets.closest('.fe-mnav-group').textContent).toContain('Инструменты');
  });

  it('мобильное меню закрывается тапом вне панели, но не тапом внутри неё', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');

    fireEvent.mouseDown(menu);
    expect(document.getElementById('fe-nav-mobile-menu')).toBeTruthy();

    fireEvent.mouseDown(document.body);
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
  });

  it('выпадашка инструментов: панель с классом появления, Esc закрывает и возвращает фокус на кнопку', () => {
    renderNav();
    const btn = screen.getByRole('button', { name: /Инструменты/i });
    fireEvent.click(btn);

    const menu = screen.getByRole('menu');
    expect(menu.className).toContain('fe-reveal--panel');
    expect(btn.getAttribute('aria-expanded')).toBe('true');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(btn);
  });

  it('выпадашка инструментов закрывается тапом вне (pointerdown)', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    expect(screen.getByRole('menu')).toBeTruthy();

    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('menu')).toBeNull();
  });
});
