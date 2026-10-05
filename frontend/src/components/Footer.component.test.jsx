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

  it('компьютер: источники данных одной строкой над колонками, каждый ведёт на официальный сайт в новой вкладке', () => {
    asDesktop();
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    const strip = footer.querySelector('.fe-foot-sources');
    expect(strip).toBeTruthy();
    expect(strip.querySelector('.fe-foot-sources__label').textContent).toBe('Источники');
    const names = [...strip.querySelectorAll('li')].map((li) => li.textContent);
    expect(names).toEqual(['Евростат', 'МВФ', 'Росстат', 'Банк России', 'Минфин России']);
    const links = [...strip.querySelectorAll('a')];
    expect(links.every((a) => a.getAttribute('target') === '_blank')).toBe(true);
    // Строка стоит в верхнем ряду, а не внутри сетки колонок.
    expect(footer.querySelector('.fe-foot-top').contains(strip)).toBe(true);
    expect(footer.querySelector('.fe-footer-grid').contains(strip)).toBe(false);
  });

  it('компьютер: «Прогнозы», «Курсы валют» и «Конвертер валют» есть в подвале', () => {
    asDesktop();
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByRole('link', { name: 'Прогнозы' }).getAttribute('href')).toBe('/forecasts');
    expect(within(footer).getByRole('link', { name: 'Курсы валют' }).getAttribute('href')).toBe('/currencies');
    const converter = within(footer).getByRole('link', { name: 'Конвертер валют' });
    expect(converter.getAttribute('href')).toBe('/currencies');
    // Конвертер первый в колонке «Инструменты».
    const tools = converter.closest('ul');
    expect(tools.querySelector('a').textContent).toBe('Конвертер валют');
  });

  it('компьютер: длинные списки занимают две дорожки и идут в два столбца', () => {
    asDesktop();
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    const categories = within(footer).getByRole('heading', { name: 'Категории' }).closest('section');
    expect(categories.className).toContain('fe-foot-span-2');
    const list = categories.querySelector('ul');
    expect(list.className).toContain('fe-foot-list--cols2');
    expect(list.style.getPropertyValue('--fe-foot-rows')).toBe(String(Math.ceil(list.children.length / 2)));
  });

  it('EN: колонки Countries и World двухстолбцовые, источники тоже одной строкой', () => {
    asDesktop();
    renderFooter('en');
    const footer = screen.getByRole('contentinfo');
    expect(footer.querySelector('.fe-foot-sources')).toBeTruthy();
    expect(within(footer).getByRole('link', { name: 'Forecasts' })).toBeTruthy();
    expect(within(footer).getByRole('link', { name: 'Exchange rates' })).toBeTruthy();
    expect(within(footer).getByRole('link', { name: 'Currency converter' })).toBeTruthy();
    expect(footer.querySelectorAll('.fe-foot-list--cols2').length).toBe(2);
  });

  it('телефон: источники остались сворачиваемой группой, строки-ленты нет', () => {
    renderFooter();
    const footer = screen.getByRole('contentinfo');
    expect(footer.querySelector('.fe-foot-sources')).toBeNull();
    expect(within(footer).getByRole('button', { name: 'Источники' })).toBeTruthy();
  });
});
