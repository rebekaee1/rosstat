// «О проекте» и «Методология»: короткий лид, карточки-разделы, жаргон только под «Подробнее».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import About from './About';
import Methodology from './Methodology';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

// \b не работает с кириллицей, поэтому границы слова — явные.
const JARGON_ROW = /(^|[^а-яёa-z])ряд(ы|ов|ам|ами|е|а)?([^а-яёa-z]|$)/i;
const JARGON_SLICE = /(^|[^а-яё])срез/i;

/** Видимый человеку текст: всё, кроме содержимого закрытых <details> (кроме summary). */
function visibleText(root) {
  const clone = root.cloneNode(true);
  clone.querySelectorAll('details:not([open])').forEach((d) => {
    [...d.children].forEach((child) => { if (child.tagName !== 'SUMMARY') child.remove(); });
  });
  return clone.textContent;
}

describe('About', () => {
  it('короткий лид и карточки с заголовками разделов, без «рядов» на виду', async () => {
    mockApiGet([['/auth/me', { user: null }]]);
    const { container } = renderPage(<About />, { path: '/about', route: '/about' });

    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy();
    for (const name of ['Откуда данные', 'Что внутри', 'Прогнозы', 'Для кого', 'Бесплатно', 'Чего мы не делаем']) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeTruthy();
    }
    const text = visibleText(container);
    expect(text).not.toMatch(JARGON_ROW);
    expect(text).not.toMatch(JARGON_SLICE);
    // Лид — 2–3 предложения.
    const lead = container.querySelector('.x4-lead').textContent;
    expect(lead.split(/(?<=[.!?])\s+/).length).toBeLessThanOrEqual(3);
    // Благодарности свёрнуты и не мешают странице.
    expect(container.querySelector('details.x4-credits').hasAttribute('open')).toBe(false);
    // Почта — кнопкой, а не строкой в тексте.
    const mail = screen.getByRole('link', { name: /Написать письмо/ });
    expect(mail.getAttribute('href')).toMatch(/^mailto:/);
  });
});

describe('Methodology', () => {
  it('шесть карточек, техника спрятана под «Подробнее»', async () => {
    mockApiGet([['/auth/me', { user: null }]]);
    const { container } = renderPage(<Methodology />, { path: '/methodology', route: '/methodology' });

    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy();
    for (const name of ['Откуда данные', 'Как мы считаем', 'Прогнозы', 'Другие страны', 'Что мы не делаем', 'Важно знать']) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeTruthy();
    }
    const text = visibleText(container);
    expect(text).not.toMatch(JARGON_ROW);
    expect(text).not.toMatch(/стационарн/i);
    expect(text).not.toMatch(JARGON_SLICE);
    // Четыре коротких шага вместо стены текста.
    const steps = within(container.querySelector('.x4-mini-steps')).getAllByRole('listitem');
    expect(steps).toHaveLength(4);
    // У каждой карточки с деталями есть «Подробнее».
    expect(container.querySelectorAll('details.w5-more-inline').length).toBeGreaterThanOrEqual(5);
  });
});
