// Волна 6, G: конструктор виджетов: понятный пример по умолчанию, предпросмотр закреплён, показатель из «Встроить».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import EmbedBuilder from './EmbedBuilder';
import EmbedLink from '../components/EmbedLink';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  { code: 'usd-rub', name: 'Курс доллара США', unit: 'руб.', category: 'Валюты', category_ru: 'Валюты', frequency: 'daily', is_active: true, is_listed: true, current_value: 83.4 },
  { code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены', category_ru: 'Цены', frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2 },
];

function setup(route = '/widgets') {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators/, INDICATORS],
  ]);
  return renderPage(<EmbedBuilder />, { path: '/widgets', route });
}

describe('EmbedBuilder: волна 6', () => {
  it('по умолчанию виджет «Курс доллара США», а не нулевая инфляция', async () => {
    setup();
    const frame = await screen.findByTitle('Превью виджета');
    expect(frame.getAttribute('src')).toContain('/embed/chart/usd-rub');
    expect(document.querySelector('.w5-embed-code pre').textContent).toContain('/embed/chart/usd-rub');
  });

  it('показатель с карточки приходит через ?code= («Встроить»)', async () => {
    setup('/widgets?code=cpi');
    const frame = await screen.findByTitle('Превью виджета');
    expect(frame.getAttribute('src')).toContain('/embed/chart/cpi');
  });

  it('мусор в ?code= не попадает в код виджета', async () => {
    setup('/widgets?code=%22%3E%3Cscript%3E');
    const frame = await screen.findByTitle('Превью виджета');
    expect(frame.getAttribute('src')).toContain('/embed/chart/usd-rub');
  });

  it('слова без жаргона и одно написание бренда', async () => {
    setup();
    await screen.findByTitle('Превью виджета');
    expect(screen.getByText('Показатель')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Индикатор/);
    const crumbs = document.querySelector('.fe-crumbs');
    expect(crumbs.textContent).toContain('Виджеты forecasteconomy');
    expect(crumbs.textContent).not.toContain('Forecast Economy');
    expect(document.querySelector('.w5-embed-code pre').textContent).toContain('forecasteconomy');
  });

  it('предпросмотр закреплён и стоит выше настроек; код развёрнут, «Копировать код» одна и главная', async () => {
    const { container } = setup();
    await screen.findByTitle('Превью виджета');
    const grid = container.querySelector('.fe-w6g-embed-grid');
    const kids = [...grid.children].map((node) => node.className);
    expect(kids[0]).toContain('fe-w6g-embed-preview');
    expect(kids[1]).toContain('fe-w6g-embed-settings');
    expect(kids[2]).toContain('fe-w6g-embed-code');
    const copy = screen.getAllByRole('button', { name: /Копировать код/ });
    expect(copy).toHaveLength(1);
    expect(copy[0].className).toContain('fe-btn--primary');
    expect(container.querySelector('.w5-embed-code details').hasAttribute('open')).toBe(true);
    // Переключение типа не ломает раскладку.
    fireEvent.click(screen.getByRole('button', { name: /Таблица/ }));
    expect(container.querySelector('.fe-w6g-embed-preview')).toBeTruthy();
  });
});

describe('EmbedLink («Встроить»)', () => {
  it('ведёт в конструктор с выбранным показателем', () => {
    mockApiGet([['/auth/me', { user: null }]]);
    renderPage(<EmbedLink code="usd-rub" />);
    const link = screen.getByRole('link', { name: 'Встроить' });
    expect(link.getAttribute('href')).toBe('/widgets?code=usd-rub');
  });
  it('волна 7: предпросмотр сворачивается кнопкой', async () => {
    setup();
    await screen.findByTitle('Превью виджета');
    const toggle = screen.getByRole('button', { name: 'Свернуть предпросмотр' });
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(toggle);
    const section = document.querySelector('.fe-w6g-embed-preview');
    expect(section.className).toContain('is-collapsed');
    expect(screen.getByRole('button', { name: 'Развернуть предпросмотр' }).getAttribute('aria-expanded')).toBe('false');
  });
});
