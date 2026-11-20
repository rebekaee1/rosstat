/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import IndicatorSeoBlocks from './IndicatorSeoBlocks';

afterEach(cleanup);

const BLOCKS = [
  { title: 'Что показывает эта карточка', body: 'Повтор описания.' },
  { title: 'Какой режим на графике', body: 'Уровень.' },
  { title: 'Как читать график', body: 'Сравнивайте одинаковые кварталы.' },
  { title: 'Откуда берутся данные и чего ряд не показывает', body: 'Повтор источника.' },
];

describe('IndicatorSeoBlocks: «О показателе» свёрнут и без повторов (№35)', () => {
  it('вопросы про описание и источник убраны, остальные в закрытом блоке, ответы остаются в DOM', () => {
    const { container } = render(<LocaleProvider locale="ru"><IndicatorSeoBlocks blocks={BLOCKS} indicatorCode="tour-x" /></LocaleProvider>);
    const details = container.querySelector('details[data-testid="about-details"]');
    expect(details).toBeTruthy();
    expect(details.open).toBe(false);
    const text = container.textContent;
    expect(text).toContain('Какой режим на графике');
    expect(text).toContain('Сравнивайте одинаковые кварталы.');
    expect(text).not.toContain('Что показывает эта карточка');
    expect(text).not.toContain('Откуда берутся данные');
  });

  it('разметка FAQPage остаётся для оставшихся вопросов', () => {
    render(<LocaleProvider locale="ru"><IndicatorSeoBlocks blocks={BLOCKS} indicatorCode="tour-x" /></LocaleProvider>);
    const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map((n) => n.textContent).join('');
    expect(ld).toContain('FAQPage');
    expect(ld).toContain('Какой режим на графике');
  });

  it('все вопросы были повторами: блока нет', () => {
    const { container } = render(<LocaleProvider locale="ru"><IndicatorSeoBlocks blocks={[BLOCKS[0], BLOCKS[3]]} indicatorCode="x" /></LocaleProvider>);
    expect(container.firstChild).toBeNull();
  });
});
