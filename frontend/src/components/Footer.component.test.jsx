import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import Footer from './Footer';
import { mockApiGet, renderPage } from '../test/renderPage';

const realMatchMedia = window.matchMedia;
afterEach(() => {
  window.matchMedia = realMatchMedia;
  vi.restoreAllMocks();
});

const asDesktop = () => {
  window.matchMedia = (query) => ({
    matches: /min-width:\s*640px/.test(query), media: query, addEventListener() {}, removeEventListener() {},
  });
};

function renderFooter(locale) {
  mockApiGet([['/auth/me', { user: null }]]);
  return renderPage(<Footer />, { path: '*', route: '/', locale });
}

describe('Footer', () => {
  it('телефон: группы ссылок — аккордеон, свёрнуты по умолчанию и раскрываются по нажатию', () => {
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    const toggles = within(footer).getAllByRole('button', { expanded: false });
    const names = toggles.map((b) => b.textContent);
    expect(names).toEqual(expect.arrayContaining(['Источники', 'Россия', 'Инструменты', 'Информация']));
    // «Категории» и «Мир» раскрыты сразу и показаны чипами-ссылками, а не спрятаны за стрелкой.
    expect(names).not.toContain('Категории');
    expect(names).not.toContain('Мир');
    for (const title of ['Категории', 'Мир']) {
      const group = within(footer).getByRole('heading', { name: title }).closest('section');
      expect(group.className).toContain('fe-foot-group--chips');
      expect(group.querySelectorAll('.fe-foot-chip').length).toBeGreaterThanOrEqual(3);
    }

    const sources = within(footer).getByRole('button', { name: 'Источники' });
    const panel = document.getElementById(sources.getAttribute('aria-controls'));
    expect(panel.hasAttribute('inert')).toBe(true);
    fireEvent.click(sources);
    expect(sources.getAttribute('aria-expanded')).toBe('true');
    expect(panel.hasAttribute('inert')).toBe(false);
    fireEvent.click(sources);
    expect(sources.getAttribute('aria-expanded')).toBe('false');
  });

  it('телефон: заголовки всех групп — одного вида, обычным регистром, без служебных плашек', () => {
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    const titles = [...footer.querySelectorAll('.fe-foot-title')];
    expect(titles.length).toBeGreaterThanOrEqual(6);
    for (const title of titles) {
      expect(title.className).toMatch(/^fe-foot-title( fe-foot-title--static)?$/);
      expect(title.textContent).not.toBe(title.textContent.toUpperCase());
    }
    expect(within(footer).queryByText('Система работает')).toBeNull();
    expect(footer.querySelector('.pulse-dot')).toBeNull();
    expect(within(footer).getByText(/Данные обновляются по мере публикации/)).toBeTruthy();
  });

  it('почта подписана по-человечески, адрес — в подсказке и в ссылке', () => {
    renderFooter();
    const mail = within(screen.getByRole('contentinfo')).getByRole('link', { name: 'Написать нам' });
    expect(mail.getAttribute('href')).toBe('mailto:rebeka.ee@yandex.ru');
    expect(within(screen.getByRole('contentinfo')).queryByText('rebeka.ee@yandex.ru')).toBeNull();
  });

  it('телефон: реквизиты компании свёрнуты в «Реквизиты»', () => {
    renderFooter();
    const summary = screen.getByText('Реквизиты');
    expect(summary.closest('details').open).toBe(false);
  });

  it('телефон: у «Реквизитов» есть стрелка раскрытия, ссылки групп — в тёмном списке (контраст)', () => {
    renderFooter();
    const summary = screen.getByText('Реквизиты').closest('summary');
    expect(summary.querySelector('svg.fe-foot-requisites__chevron')).toBeTruthy();
    expect(document.querySelectorAll('ul.fe-foot-list').length).toBeGreaterThanOrEqual(4);
    expect(document.querySelectorAll('ul.fe-foot-chips').length).toBe(2);
  });

  it('компьютер: колонки с обычными заголовками, без кнопок-аккордеонов, реквизиты на виду', () => {
    asDesktop();
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    expect(within(footer).queryAllByRole('button', { expanded: false })).toHaveLength(0);
    expect(within(footer).getByRole('heading', { name: 'Мир' })).toBeTruthy();
    expect(within(footer).queryByText('Реквизиты')).toBeNull();
    expect(footer.querySelectorAll('[inert]')).toHaveLength(0);
  });

  it('«Сравнение» в подвале одно (в «Мир»), а не дубль в «Инструментах»; имена страниц единые', () => {
    asDesktop();
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getAllByRole('link', { name: 'Сравнение' })).toHaveLength(1);
    expect(within(footer).queryByRole('link', { name: 'Сравнение индикаторов' })).toBeNull();
    expect(within(footer).getByRole('link', { name: 'Как мы считаем прогнозы' }).getAttribute('href')).toBe('/methodology');
    expect(within(footer).getByRole('link', { name: 'Условия использования' }).getAttribute('href')).toBe('/terms');
    expect(within(footer).getByRole('link', { name: 'Источники данных и изображений' }).getAttribute('href')).toBe('/about#credits');
    expect(within(footer).queryByRole('link', { name: 'Благодарности' })).toBeNull();
  });
});
