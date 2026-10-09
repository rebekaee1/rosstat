import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, within } from '@testing-library/react';
import HomeContinue from './HomeContinue';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());
beforeEach(() => window.localStorage.clear());

const ITEMS = [
  { path: '/turkey/indicator/tr-cpi', title: 'Инфляция в Турции', kind: 'indicator', ts: 9 },
  { path: '/germany', title: 'Германия', kind: 'country', ts: 8 },
  { path: '/compare?codes=a,b', title: 'Сравнение показателей', kind: 'compare', ts: 7 },
];
const USER = { id: 1, email: 'a@b.c', name: 'Тест' };

describe('HomeContinue: «Продолжить» и «Вы смотрели»', () => {
  it('для вошедшего: первая карточка «Продолжить», остальные с видом страницы, ссылки внутренние', async () => {
    window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify(ITEMS));
    mockApiGet([['/auth/me', { user: USER }]]);
    const { container } = renderPage(<HomeContinue />, { path: '/', route: '/' });
    const section = await screen.findByRole('region', { name: 'Вы смотрели' });
    const links = within(section).getAllByRole('link');
    expect(links).toHaveLength(3);
    expect(links[0].textContent).toContain('Продолжить');
    expect(links[0].textContent).toContain('Инфляция в Турции');
    expect(links[0].getAttribute('href')).toBe('/turkey/indicator/tr-cpi');
    expect(links[1].textContent).toContain('Страна');
    expect(links[2].textContent).toContain('Сравнение');
    expect(container.querySelector('[data-block="home-continue"]')).toBeTruthy();
  });

  it('у гостя блока нет, даже если страницы запомнены', async () => {
    window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify(ITEMS));
    mockApiGet([['/auth/me', { user: null }]]);
    const { container } = renderPage(<HomeContinue />, { path: '/', route: '/' });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
    expect(container.querySelector('[data-block="home-continue"]')).toBeNull();
  });

  it('у вошедшего без записей блок не занимает места', async () => {
    mockApiGet([['/auth/me', { user: USER }]]);
    const { container } = renderPage(<HomeContinue />, { path: '/', route: '/' });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
    expect(container.querySelector('[data-block="home-continue"]')).toBeNull();
  });

  it('«Очистить» стирает список в браузере, и блок исчезает', async () => {
    window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify(ITEMS));
    mockApiGet([['/auth/me', { user: USER }]]);
    const { container } = renderPage(<HomeContinue />, { path: '/', route: '/' });
    fireEvent.click(await screen.findByRole('button', { name: 'Очистить' }));
    expect(window.localStorage.getItem('fe:recent-pages:v1')).toBeNull();
    expect(container.querySelector('[data-block="home-continue"]')).toBeNull();
  });

  it('повреждённая запись не ломает главную', async () => {
    window.localStorage.setItem('fe:recent-pages:v1', '{oops');
    mockApiGet([['/auth/me', { user: USER }]]);
    const { container } = renderPage(<HomeContinue />, { path: '/', route: '/' });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
    expect(container.querySelector('[data-block="home-continue"]')).toBeNull();
  });
});
