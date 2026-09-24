import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import HomeDataScope from './HomeDataScope';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function renderScope(countriesPayload, locale) {
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
      world_indicators_count: 38146,
      russia_macro_indicators_count: 145,
      regional_indicators_count: 2377,
      us_state_indicators_count: 1882,
      us_states_count: 50,
    }],
  ]);
  return renderPage(<HomeDataScope />, { path: '/', route: '/', locale });
}

describe('HomeDataScope — состав платформы в hero главной', () => {
  it('рендерится с заголовком блока и общеплатформенными цифрами', async () => {
    renderScope();

    expect(screen.getByRole('heading', { name: 'Что внутри платформы' })).toBeTruthy();

    await waitFor(() => expect(screen.getByText('145')).toBeTruthy());
    expect(screen.getByText(/макроиндикаторов России/)).toBeTruthy();

    expect(screen.getByText(/38\s*146/)).toBeTruthy();
    expect(screen.getByText(/показателей по странам мира/)).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText('55')).toBeTruthy();
    });
    expect(screen.getByText(/стран мира/)).toBeTruthy();

    expect(screen.getByText(/2\s*377/)).toBeTruthy();
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
      'Евростат, МВФ, Бюро экономического анализа США, Бюро трудовой статистики США, ФРС, Росстат, Банк России, Минфин России',
    )).toBeTruthy();
    expect(screen.getByText(/обновляются автоматически/)).toBeTruthy();
  });

  it('нет текста-заглушки и запрещённого разделителя mid-dot', () => {
    renderScope();

    const block = screen.getByLabelText('Что внутри платформы');
    expect(block.textContent).not.toMatch(/lorem|заглушк|mock/i);
    // U+00B7 в литерале запрещён даже в тестовых .jsx — эскейп, см. noMiddleDot.test.js.
    expect(block.textContent).not.toContain('\u00B7');
  });

  it('EN: без российских плиток, источники международные', async () => {
    renderScope(undefined, 'en');

    expect(screen.getByRole('heading', { name: 'Inside the platform' })).toBeTruthy();
    expect(screen.getByText(/indicators across world countries/)).toBeTruthy();
    expect(screen.getByText(/countries worldwide/)).toBeTruthy();
    expect(screen.queryByText(/Russian macro indicators/)).toBeNull();
    expect(screen.queryByText('100+')).toBeNull();
    expect(screen.queryByText(/regional indicators/)).toBeNull();
    expect(screen.queryByText('2,377')).toBeNull();
    expect(screen.getByText(/observation period/)).toBeTruthy();
    expect(screen.getByText(
      'Eurostat, IMF, U.S. Bureau of Labor Statistics, Bureau of Economic Analysis, Federal Reserve, national statistical offices and central banks',
    )).toBeTruthy();
    expect(screen.queryByText(/Rosstat/)).toBeNull();
  });
});
