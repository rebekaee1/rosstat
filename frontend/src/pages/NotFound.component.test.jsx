// 404: заголовок документа, noindex, поиск и ссылки на главные разделы.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import NotFound from './NotFound';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

describe('NotFound', () => {
  it('показывает понятный текст, поиск и ссылки на разделы', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
    ]);
    renderPage(<NotFound />, { path: '*', route: '/net-takoy-stranitsy' });

    expect(await screen.findByRole('heading', { level: 1, name: 'Такой страницы нет' })).toBeTruthy();
    // Поиск: кнопка-триггер с подсказкой в тексте.
    expect(screen.getByText('Показатель, страна или регион')).toBeTruthy();
    for (const name of ['Рейтинг стран', 'Сравнение', 'Регионы России', 'Сегодня', 'Календарь', 'Калькуляторы']) {
      expect(screen.getByRole('link', { name: new RegExp(`^${name}`) }).getAttribute('href')).toBeTruthy();
    }
    expect(screen.getByRole('link', { name: 'На главную' }).getAttribute('href')).toBe('/');
    expect(document.title).toContain('Такой страницы нет');
    // Дружелюбный текст и подсказки у разделов.
    expect(screen.getByText('Популярные разделы')).toBeTruthy();
  });

  it('«404» с планетой вместо нуля, золотая «На главную» и вторая кнопка «Вернуться назад»', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/indicators/, []]]);
    const { container } = renderPage(<NotFound />, { path: '*', route: '/net-takoy-stranitsy' });
    await screen.findByRole('heading', { level: 1 });
    const code = container.querySelector('.z2-nf-code');
    expect(code.getAttribute('aria-hidden')).toBe('true');
    expect([...code.querySelectorAll('.z2-nf-digit')].map((d) => d.textContent)).toEqual(['4', '4']);
    // Планета стоит между цифрами и вращается: поверхность и орбита — отдельные анимируемые группы.
    expect(code.children[1].tagName.toLowerCase()).toBe('svg');
    expect(code.querySelector('.z2-nf-surface')).toBeTruthy();
    expect(code.querySelector('.z2-nf-orbit')).toBeTruthy();
    const home = screen.getByRole('link', { name: 'На главную' });
    expect(home.className).toContain('z2-nf-home');
    expect(screen.getByRole('button', { name: 'Вернуться назад' })).toBeTruthy();
    // Золотая кнопка идёт сразу под поиском, раньше списков разделов.
    const actions = container.querySelector('.z2-nf-actions');
    const popular = screen.getByText('Популярные разделы');
    expect(actions.compareDocumentPosition(popular) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('/forecasts: подсказка «Возможно, вы искали» предлагает «Прогнозы» первой', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/indicators/, []]]);
    const { container } = renderPage(<NotFound />, { path: '*', route: '/forecasts' });
    await screen.findByRole('heading', { level: 1 });
    const guess = container.querySelector('[data-nf-guess]');
    expect(guess).toBeTruthy();
    const first = guess.querySelector('a');
    expect(first.textContent).toBe('Прогнозы');
    expect(first.getAttribute('href')).toBe('/forecasts');
  });
});
