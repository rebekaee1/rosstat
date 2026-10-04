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

    expect(await screen.findByRole('heading', { level: 1, name: 'Страница не найдена' })).toBeTruthy();
    // Поиск: кнопка-триггер с подсказкой в тексте.
    expect(screen.getByText('Найти показатель, страну или регион')).toBeTruthy();
    for (const name of ['Рейтинг стран', 'Сравнение показателей', 'Календарь публикаций статистики']) {
      expect(screen.getByRole('link', { name }).getAttribute('href')).toBeTruthy();
    }
    expect(screen.getByRole('link', { name: 'На главную' }).getAttribute('href')).toBe('/');
    expect(document.title).toContain('Страница не найдена');
  });
});
