import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import HomeDataScope from './HomeDataScope';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function renderScope(countriesPayload) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries', countriesPayload || {
      countries: Array.from({ length: 55 }, (_, i) => ({
        code: `C${i}`,
        slug: `c-${i}`,
        name: `Страна ${i}`,
        name_en: `Country ${i}`,
        indicators_count: 1,
      })),
      total: 55,
    }],
  ]);
  return renderPage(<HomeDataScope />, { path: '/', route: '/' });
}

describe('HomeDataScope — состав платформы в hero главной', () => {
  it('рендерится с заголовком блока и общеплатформенными цифрами', async () => {
    renderScope();

    expect(screen.getByRole('heading', { name: 'Что внутри платформы' })).toBeTruthy();

    expect(screen.getByText('100+')).toBeTruthy();
    expect(screen.getByText(/макроиндикаторов России/)).toBeTruthy();

    expect(screen.getByText('36 000+')).toBeTruthy();
    expect(screen.getByText(/показателей по странам мира/)).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText('55')).toBeTruthy();
    });
    expect(screen.getByText(/стран мира/)).toBeTruthy();

    expect(screen.getByText('495')).toBeTruthy();
    expect(screen.getByText(/региональных показателей/)).toBeTruthy();
    expect(screen.queryByText(/42\s*075/)).toBeNull();
    expect(screen.queryByText(/495\s*[×x]/)).toBeNull();

    expect(screen.getByText('1897–2026')).toBeTruthy();
    expect(screen.getByText(/период наблюдений/)).toBeTruthy();
  });

  it('берёт число стран с API, а не устаревший фоллбэк', async () => {
    renderScope({
      countries: Array.from({ length: 57 }, (_, i) => ({
        code: `C${i}`,
        slug: `c-${i}`,
        name: `Страна ${i}`,
        name_en: `Country ${i}`,
        indicators_count: 1,
      })),
      total: 57,
    });

    await waitFor(() => {
      expect(screen.getByText('57')).toBeTruthy();
    });
  });

  it('показывает официальные источники в порядке международные — российские и режим обновления', () => {
    renderScope();

    expect(screen.getByText(
      'Евростат, МВФ, национальные статистические ведомства, Росстат, Банк России, Минфин России',
    )).toBeTruthy();
    expect(screen.getByText(/06:00 и 20:00 МСК/)).toBeTruthy();
  });

  it('нет текста-заглушки и запрещённого разделителя mid-dot', () => {
    renderScope();

    const block = screen.getByLabelText('Что внутри платформы');
    expect(block.textContent).not.toMatch(/lorem|заглушк|mock/i);
    // U+00B7 в литерале запрещён даже в тестовых .jsx — эскейп, см. noMiddleDot.test.js.
    expect(block.textContent).not.toContain('\u00B7');
  });
});
