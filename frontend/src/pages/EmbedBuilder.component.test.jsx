// Т-13: EmbedBuilder — конструктор embed-виджетов: монтируется, показывает
// типы виджетов и генерирует iframe-код с выбранным индикатором.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import EmbedBuilder from './EmbedBuilder';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2,
  },
];

describe('EmbedBuilder', () => {
  it('монтируется и показывает все типы виджетов', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
    ]);
    renderPage(<EmbedBuilder />, { path: '/embed-builder', route: '/embed-builder' });
    for (const label of ['График', 'Карточка', 'Таблица', 'Бегущая строка', 'Сравнение']) {
      expect((await screen.findAllByText(label)).length).toBeGreaterThan(0);
    }
    // Код для вставки содержит embed-URL с индикатором.
    const code = document.body.textContent;
    expect(code).toContain('forecasteconomy.com');
  });

  it('если превью не загрузилось за 12 секунд — понятная ошибка и «Повторить», а не пустой блок', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mockApiGet([
        ['/auth/me', { user: null }],
        [/^\/indicators/, INDICATORS],
      ]);
      renderPage(<EmbedBuilder />, { path: '/embed-builder', route: '/embed-builder' });
      await screen.findAllByText('График');
      expect(document.querySelector('.w5-embed-preview__state')).toBeTruthy();
      expect(document.body.textContent).toContain('Готовим превью');
      await act(async () => { vi.advanceTimersByTime(12100); });
      const alert = screen.getByRole('alert');
      expect(alert.textContent).toContain('Превью не загрузилось');
      fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
      expect(screen.queryByRole('alert')).toBeNull();
      expect(document.body.textContent).toContain('Готовим превью');
    } finally {
      vi.useRealTimers();
    }
  });
});
