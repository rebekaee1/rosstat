import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderPage } from '../test/renderPage';
import FreshnessNote from './FreshnessNote';
import ru from '../i18n/messages.ru';
import en from '../i18n/messages.en';

const STALE = {
  level: 'stale',
  last_period: '2023-07-01',
  age_days: 1108,
  reason: 'series_lag',
  source_updated_at: '2026-10-01',
  lead: 'Источник обновляет набор, но по этому ряду данных позже III квартала 2023 нет.',
  message: 'Источник обновляет набор, но по этому ряду данных позже III квартала 2023 нет. Ближайший актуальный показатель: Производство в сфере услуг, индекс (2021 = 100).',
  nearest: {
    code: 'bg-services', name: 'Производство в сфере услуг, индекс (2021 = 100)',
    url: '/bulgaria/indicator/bg-services', last_period: '2026-04-01', frequency: 'quarterly',
  },
};

describe('FreshnessNote (круг 13, D2)', () => {
  it('устаревший ряд: причина, дата обновления источника и ссылка на ближайший актуальный показатель', () => {
    renderPage(<FreshnessNote freshness={STALE} />);
    const block = screen.getByTestId('freshness-note');
    expect(block.getAttribute('data-reason')).toBe('series_lag');
    expect(screen.getByRole('heading', { name: 'Актуальные данные' })).toBeTruthy();
    // Первая фраза — причина; предложение про ближайший показатель из общей строки не повторяется рядом со ссылкой.
    expect(screen.getByTestId('freshness-note-lead').textContent).toBe(STALE.lead);
    expect(block.textContent).not.toContain('Ближайший актуальный показатель:');
    expect(block.textContent.replace(/ /g, ' ')).toContain('Источник обновлял набор: 1 октября 2026.');
    const link = screen.getByTestId('freshness-note-link');
    expect(link.getAttribute('href')).toBe('/bulgaria/indicator/bg-services');
    expect(link.textContent.replace(/ /g, ' ')).toContain('Производство в сфере услуг, индекс (2021 = 100)');
    // Дата ближайшего показателя говорит на его частоте (квартал), а не частоте устаревшего ряда.
    expect(link.textContent.replace(/ /g, ' ')).toContain('данные до II кв. 2026');
  });

  it('старый ответ сервера без поля lead: из сообщения убирается предложение про ближайший показатель', () => {
    const { lead, ...legacy } = STALE; // eslint-disable-line no-unused-vars
    renderPage(<FreshnessNote freshness={legacy} />);
    expect(screen.getByTestId('freshness-note-lead').textContent).toBe(STALE.lead);
  });

  it('без ближайшего показателя остаётся причина без ссылки; английский текст показывается как пришёл', () => {
    renderPage(<FreshnessNote freshness={{
      ...STALE, nearest: null, source_updated_at: null, reason: 'source_stopped',
      lead: 'The source has not updated this series since July 2023.', message: 'The source has not updated this series since July 2023.',
    }} />, { locale: 'en' });
    expect(screen.queryByTestId('freshness-note-link')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Up-to-date data' })).toBeTruthy();
    expect(screen.getByTestId('freshness-note-lead').textContent).toBe('The source has not updated this series since July 2023.');
  });

  it('свежий ряд, пустой ответ и ответ без текста ничего не рисуют', () => {
    const { container, unmount } = renderPage(<FreshnessNote freshness={null} />);
    expect(container.querySelector('[data-testid="freshness-note"]')).toBeNull();
    unmount();
    const second = renderPage(<FreshnessNote freshness={{ level: 'aging', message: 'x' }} />);
    expect(second.container.querySelector('[data-testid="freshness-note"]')).toBeNull();
    second.unmount();
    const third = renderPage(<FreshnessNote freshness={{ level: 'stale', reason: 'retired' }} />);
    expect(third.container.querySelector('[data-testid="freshness-note"]')).toBeNull();
  });

  it('ключи c13d. есть в обоих словарях и не пропущены', () => {
    const keys = Object.keys(ru).filter((k) => k.startsWith('c13d.'));
    expect(keys.length).toBeGreaterThanOrEqual(4);
    expect(Object.keys(en).filter((k) => k.startsWith('c13d.')).sort()).toEqual(keys.sort());
  });
});
