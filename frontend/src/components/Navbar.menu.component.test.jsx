import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
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

  it('мобильное меню закрывается тапом вне панели, но не тапом внутри неё', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');

    fireEvent.mouseDown(menu);
    expect(document.getElementById('fe-nav-mobile-menu')).toBeTruthy();

    fireEvent.mouseDown(document.body);
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
  });

  it('выпадашка калькуляторов: панель с классом появления, Esc закрывает и возвращает фокус на кнопку', () => {
    renderNav();
    const btn = screen.getByRole('button', { name: /Калькуляторы/i });
    fireEvent.click(btn);

    const menu = screen.getByRole('menu');
    expect(menu.className).toContain('fe-reveal--panel');
    expect(btn.getAttribute('aria-expanded')).toBe('true');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(btn);
  });

  it('выпадашка калькуляторов закрывается тапом вне (pointerdown)', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Калькуляторы/i }));
    expect(screen.getByRole('menu')).toBeTruthy();

    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('menu')).toBeNull();
  });
});
