import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import HomeDataScope from './HomeDataScope';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const COUNTRIES = (n) => Array.from({ length: n }, (_, i) => ({
  code: `C${i}`,
  slug: `c-${i}`,
  name: `Страна ${i}`,
  name_en: `Country ${i}`,
  indicators_count: 1,
}));

function renderScope(countriesPayload, locale) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries', countriesPayload || {
      countries: COUNTRIES(55),
      total: 55,
      world_indicators_count: 268003,
      russia_macro_indicators_count: 145,
      russia_regional_indicators_count: 495,
      regional_indicators_count: 2377,
      us_state_indicators_count: 1882,
      us_states_count: 50,
    }],
  ]);
  return renderPage(<HomeDataScope />, { path: '/', route: '/', locale });
}

const YEARS = new Date().getFullYear() - 1897;

describe('HomeDataScope: три числа платформы', () => {
  it('сразу итоговые числа и пояснения фразами: показатели, страны (и список растёт), история до N лет', async () => {
    renderScope();

    expect(screen.getByRole('heading', { name: 'Платформа в цифрах' })).toBeTruthy();

    // Без «бега»: число сразу итоговое (в первом кадре нет промежуточных 169 / 35 / 1956).
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(screen.getByText('тыс.')).toBeTruthy();
    expect(screen.getByText('показателей')).toBeTruthy();
    expect(screen.getByText('55')).toBeTruthy();
    expect(screen.getByText('стран, и список растёт')).toBeTruthy();
    // Глубина истории: «до 129 лет» и пояснение, с какого года.
    expect(screen.getByText(String(YEARS))).toBeTruthy();
    expect(screen.getByText('до')).toBeTruthy();
    expect(screen.getByText('лет истории, с 1897 года')).toBeTruthy();
    expect(screen.queryByText('1897')).toBeNull();
    expect(document.querySelectorAll('.fe-scope-stat')).toHaveLength(3);

    // Российские 145 и 495 — только внутри раскрывашки, не в основной сетке.
    const details = screen.getByText('Только официальные источники').closest('details');
    expect(details.contains(screen.getByText('145'))).toBe(true);
    expect(details.contains(screen.getByText('495'))).toBe(true);
    expect(screen.getByText(/региональных показателей России/)).toBeTruthy();
    expect(screen.queryByText(/2\s*377/)).toBeNull();
    expect(screen.queryByText(/США:.*штатам/)).toBeNull();
  });

  it('плитки нажимаются: показатели ведут ко всем темам, страны к каталогу; история без ссылки', async () => {
    renderScope();
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(screen.getByText('268').closest('a').getAttribute('href')).toBe('/russia/category');
    expect(screen.getByText('55').closest('a').getAttribute('href')).toBe('/#countries');
    expect(screen.getByText(String(YEARS)).closest('a')).toBeNull();
  });

  it('пока каталог грузится, вместо чисел «…», а не устаревший запасной набор', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries', () => new Promise(() => {})],
    ]);
    renderPage(<HomeDataScope />, { path: '/', route: '/' });
    expect(document.querySelectorAll('.fe-stat-wait')).toHaveLength(2);
    const text = document.querySelector('[data-block="home-data-scope"]').textContent;
    expect(text).not.toMatch(/169|35|1956|1954|174/);
  });

  it('берёт число стран с API, а не устаревший фоллбэк', async () => {
    renderScope({ countries: COUNTRIES(57), total: 57 });
    await waitFor(() => expect(screen.getByText('57')).toBeTruthy());
    expect(screen.getByText('стран, и список растёт')).toBeTruthy();
  });

  it('если в каталоге нет чисел, вместо них честный прочерк, а не выдуманное значение', async () => {
    renderScope({ countries: [], total: 0 });
    await waitFor(() => expect(screen.getAllByLabelText('нет данных')).toHaveLength(2));
    expect(screen.queryByText('тыс.')).toBeNull();
  });

  it('свёрнутая строка сразу называет источники; полный список и режим обновления в раскрывашке', () => {
    renderScope();

    expect(screen.getByText('Росстат, Евростат, МВФ и другие')).toBeTruthy();
    expect(screen.getByText(
      'Евростат, МВФ, Бюро экономического анализа США, Бюро трудовой статистики США, ФРС, Росстат, Банк России, Минфин России',
    )).toBeTruthy();
    expect(screen.getByText(/обновляются автоматически/)).toBeTruthy();
  });

  it('нет текста-заглушки и запрещённого разделителя mid-dot', () => {
    renderScope();

    const block = screen.getByLabelText('Платформа в цифрах');
    expect(block.textContent).not.toMatch(/lorem|заглушк|mock/i);
    // U+00B7 в литерале запрещён даже в тестовых .jsx — эскейп, см. noMiddleDot.test.js.
    expect(block.textContent).not.toContain('\u00B7');
  });

  it('EN: без российских строк, источники международные, история «up to N years»', async () => {
    renderScope(undefined, 'en');

    expect(screen.getByRole('heading', { name: 'The platform in numbers' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(screen.getByText('K')).toBeTruthy();
    expect(screen.getByText('indicators')).toBeTruthy();
    expect(screen.getByText('countries and counting')).toBeTruthy();
    expect(screen.getByText('up to')).toBeTruthy();
    expect(screen.getByText('years of history, since 1897')).toBeTruthy();
    expect(screen.queryByText(/Russian macro indicators/)).toBeNull();
    expect(screen.queryByText('495')).toBeNull();
    expect(screen.getByText('Eurostat, IMF, BLS and others')).toBeTruthy();
    expect(screen.getByText(
      'Eurostat, IMF, U.S. Bureau of Labor Statistics, Bureau of Economic Analysis, Federal Reserve, national statistical offices and central banks',
    )).toBeTruthy();
    expect(screen.queryByText(/Rosstat/)).toBeNull();
    expect(screen.getByText('268').closest('a').getAttribute('href')).toBe('/world/rating/gdp-usd');
  });
});
