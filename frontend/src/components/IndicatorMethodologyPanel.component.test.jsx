/** @vitest-environment jsdom */
import { expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import IndicatorMethodologyPanel from './IndicatorMethodologyPanel';

it('links a world indicator to its published source series', () => {
  const sourceUrl = 'https://fred.stlouisfed.org/series/LASST060000000000005';
  render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel
          indicator={{ name: 'Civilian employment', source: 'U.S. Bureau of Labor Statistics' }}
          content={{ description: 'Employed residents', methodology: 'Monthly LAUS series' }}
          sourcePath={sourceUrl}
        />
      </MemoryRouter>
    </LocaleProvider>,
  );
  expect(screen.getByRole('link', { name: /source|источник/i }).getAttribute('href')).toBe(sourceUrl);
});

function renderPanel(props) {
  return render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel content={{ description: 'd', methodology: 'm' }} {...props} />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

it('Russian indicator links to its external source_url in a new tab', () => {
  renderPanel({
    indicator: {
      code: 'cpi',
      name: 'ИПЦ',
      source: 'Росстат',
      source_url: 'https://rosstat.gov.ru/statistics/price',
    },
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('https://rosstat.gov.ru/statistics/price');
  expect(link.getAttribute('target')).toBe('_blank');
  expect(link.getAttribute('rel')).toMatch(/noopener/);
  expect(link.getAttribute('rel')).toMatch(/noreferrer/);
});

it('Bank of Russia indicator no longer links back to the key-rate card', () => {
  renderPanel({
    indicator: { code: 'key-rate', name: 'Ключевая ставка', source: 'Банк России', source_url: 'https://www.cbr.ru/hd_base/KeyRate/' },
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('https://www.cbr.ru/hd_base/KeyRate/');
});

it('world page: external source_url wins over an internal sourcePath fallback', () => {
  renderPanel({
    indicator: { code: 'us-gdp-real', name: 'GDP', source: 'Federal Reserve Bank of St. Louis', source_url: 'https://fred.stlouisfed.org/series/GDPC1' },
    sourcePath: '/united-states/indicator/us-gdp-real',
  });
  const link = screen.getByRole('link', { name: /источник|source/i });
  expect(link.getAttribute('href')).toBe('https://fred.stlouisfed.org/series/GDPC1');
  expect(link.getAttribute('target')).toBe('_blank');
});

it('shows a source badge without a misleading link when no source URL is known', () => {
  renderPanel({
    indicator: { code: 'some-series', name: 'X', source: 'Unknown agency' },
  });
  expect(screen.queryByRole('link', { name: /источник|source/i })).toBeNull();
  expect(screen.getByText(/^(источник|source):/i)).toBeTruthy();
});

it('shows a quiet «how to cite» line with name, source, date and page address (council 19.11.2026)', () => {
  renderPanel({
    indicator: { code: 'fuel-diesel', name: 'Дизельное топливо', source: 'Росстат', current_date: '2026-11-09' },
  });
  const line = document.querySelector('[data-block="cite"]');
  expect(line).toBeTruthy();
  expect(line.textContent).toMatch(/^(Как цитировать|How to cite):/);
  expect(line.textContent).toContain('Forecast Economy. Дизельное топливо');
  expect(line.textContent).toContain(`${window.location.origin}${window.location.pathname}`);
  expect(line.textContent).not.toContain('?');
});

it('«Как цитировать»: данные за квартал и дата обращения, кнопка копирования (круг наблюдателей, №2)', async () => {
  const writeText = vi.fn().mockResolvedValue();
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  renderPanel({
    indicator: { code: 'tour-outbound', name: 'Выезд', source: 'Росстат', frequency: 'quarterly', current_date: '2026-06-01' },
  });
  const line = document.querySelector('[data-block="cite"]');
  expect(line.textContent).toMatch(/данные за II кв\. 2026, дата обращения \d{2}\.\d{2}\.\d{4}/);
  expect(line.textContent).not.toMatch(/на 1 июня/);
  fireEvent.click(screen.getByTestId('cite-copy'));
  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
  expect(writeText.mock.calls[0][0]).toMatch(/^Forecast Economy\. Выезд: источник данных — Росстат, данные за II кв\. 2026/);
});

it('туристский ряд без описания: заглушки «показаны опубликованные наблюдения» нет; у остальных рядов она остаётся (№26)', () => {
  const { unmount } = render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel indicator={{ code: 'tour-outbound-egypt', name: 'Выезд: Египет', source: 'Росстат' }} content={{}} />
      </MemoryRouter>
    </LocaleProvider>,
  );
  expect(document.querySelector('[data-block="methodology"]').textContent).not.toMatch(/опубликованные наблюдения|Прогноз, если он доступен/);
  unmount();
  render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel indicator={{ code: 'cpi-x', name: 'ИПЦ', source: 'Росстат' }} content={{}} />
      </MemoryRouter>
    </LocaleProvider>,
  );
  expect(document.querySelector('[data-block="methodology"]').textContent).toMatch(/опубликованные наблюдения/);
});

it('туристский ряд с описанием от родителя показывает его текст', () => {
  render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel
          indicator={{ code: 'tour-outbound-egypt', name: 'Выезд: Египет', source: 'Росстат' }}
          content={{ description: 'Описание родителя.', methodology: 'Методика родителя.' }}
        />
      </MemoryRouter>
    </LocaleProvider>,
  );
  expect(document.querySelector('[data-block="methodology"]').textContent).toContain('Описание родителя.');
});
