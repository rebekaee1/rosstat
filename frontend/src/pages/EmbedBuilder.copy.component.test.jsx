// EmbedBuilder: превью с индикатором ожидания и копирование кода с видимым подтверждением.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import EmbedBuilder from './EmbedBuilder';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const INDICATORS = [
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2,
  },
];

function setup() {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators/, INDICATORS],
  ]);
  renderPage(<EmbedBuilder />, { path: '/embed-builder', route: '/embed-builder' });
}

describe('EmbedBuilder: превью и копирование', () => {
  it('пока iframe не загрузился, показывает ожидание; после onLoad убирает', async () => {
    setup();
    const frame = await screen.findByTitle('Превью виджета');
    expect(screen.getByText('Загружаем превью…')).toBeTruthy();
    act(() => { fireEvent.load(frame); });
    await waitFor(() => expect(screen.queryByText('Загружаем превью…')).toBeNull());
  });

  it('после копирования показывает «Скопировано» в зоне aria-live', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    setup();
    fireEvent.click(await screen.findByRole('button', { name: /Копировать код/ }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect((await screen.findAllByText('Скопировано')).length).toBeGreaterThan(0);
    const live = screen.getAllByRole('status').find((el) => el.getAttribute('aria-live') === 'polite');
    expect(live?.textContent).toBe('Скопировано');
  });

  it('выбор «что вставить» — карточки с подсказками; код спрятан под «Показать код»', async () => {
    setup();
    const ticker = await screen.findByRole('button', { name: /Бегущая строка/ });
    expect(ticker.getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByRole('button', { name: /График/ }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(ticker);
    expect(ticker.getAttribute('aria-pressed')).toBe('true');
    // Код — внутри свёрнутого <details>, не на виду; превью с адресом и «светофором» нет.
    const code = document.querySelector('.w5-embed-code details');
    expect(code).toBeTruthy();
    expect(code.hasAttribute('open')).toBe(false);
    expect(screen.getByText('Показать код')).toBeTruthy();
    expect(document.querySelector('.w5-embed-preview .rounded-full')).toBeNull();
  });

  it('форматы названы по-человечески, а не iframe / SVG / Badge', async () => {
    setup();
    await screen.findByRole('button', { name: /Копировать код/ });
    for (const name of ['Живой виджет', 'Картинка', 'Для блога', 'Мини-значок']) {
      expect(screen.getByRole('button', { name })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Картинка' }));
    expect(document.querySelector('.w5-embed-code pre').textContent).toContain('<img');
  });

  it('если буфер недоступен, говорит об этом', async () => {
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined });
    setup();
    fireEvent.click(await screen.findByRole('button', { name: /Копировать код/ }));
    expect(await screen.findByText(/Не удалось скопировать/)).toBeTruthy();
  });
});
