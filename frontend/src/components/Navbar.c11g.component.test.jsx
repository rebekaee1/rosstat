import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import Navbar from './Navbar';
import { accountInitial } from '../lib/accountInitial';
import { mockApiGet, renderPage } from '../test/renderPage';

vi.mock('gsap', () => ({ default: { fromTo: () => ({ kill: () => {} }) } }));
vi.mock('./IndicatorSearch', () => ({ default: () => <div data-testid="indicator-search-stub" /> }));

afterEach(() => { vi.restoreAllMocks(); });

const ME = { id: 7, email: 'ivan@example.com', display_name: 'Иван' };

describe('Navbar, круг 11 G (U2): вошедший виден в шапке', () => {
  it('accountInitial: первая буква имени, иначе почты, иначе пусто', () => {
    expect(accountInitial({ display_name: 'иван', email: 'a@b.c' })).toBe('И');
    expect(accountInitial({ display_name: '', email: 'zed@b.c' })).toBe('Z');
    expect(accountInitial({ display_name: '  ', email: '' })).toBe('');
    expect(accountInitial(null)).toBe('');
  });

  it('кнопка кабинета несёт кружок с буквой имени и не золотой primary', async () => {
    mockApiGet([['/auth/me', { user: ME }]]);
    renderPage(<Navbar />, { path: '*', route: '/compare' });
    const nav = screen.getByRole('navigation');
    const link = await waitFor(() => {
      const found = within(nav).getAllByRole('link').find((a) => a.getAttribute('href') === '/account');
      if (!found) throw new Error('кнопка кабинета ещё не появилась');
      return found;
    });
    expect(link.className).toContain('fe-nav-account');
    expect(link.className).not.toContain('fe-button-primary');
    expect(link.querySelector('.fe-avatar').textContent).toBe('И');
    expect(link.getAttribute('aria-current')).toBeNull();
  });

  it('на /account кнопка помечена текущей', async () => {
    mockApiGet([['/auth/me', { user: ME }]]);
    renderPage(<Navbar />, { path: '*', route: '/account' });
    const nav = screen.getByRole('navigation');
    const link = await waitFor(() => {
      const found = within(nav).getAllByRole('link').find((a) => a.getAttribute('href') === '/account');
      if (!found) throw new Error('нет кнопки');
      return found;
    });
    expect(link.getAttribute('aria-current')).toBe('page');
    expect(link.className).toContain('is-current');
  });

  it('на калькуляторе пункт «Инструменты» подсвечен, на сравнении нет; «Страны» подсвечены по #countries', () => {
    mockApiGet([['/auth/me', { user: null }]]);
    const { unmount } = renderPage(<Navbar />, { path: '*', route: '/calculator/mortgage' });
    expect(screen.getByRole('button', { name: /Инструменты/i }).getAttribute('data-active')).toBe('true');
    unmount();
    const second = renderPage(<Navbar />, { path: '*', route: '/compare' });
    expect(screen.getByRole('button', { name: /Инструменты/i }).getAttribute('data-active')).toBeNull();
    second.unmount();
    renderPage(<Navbar />, { path: '*', route: '/#countries' });
    const countries = screen.getAllByRole('link').find((a) => a.getAttribute('href') === '/#countries' && a.className.includes('fe-nav-link'));
    expect(countries.getAttribute('aria-current')).toBe('page');
  });
});
