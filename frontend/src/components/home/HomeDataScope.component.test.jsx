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

describe('HomeDataScope — три живых числа платформы', () => {
  it('показывает показатели в тысячах, число стран и глубину истории; Россия не на первом плане', async () => {
    renderScope();

    expect(screen.getByRole('heading', { name: 'Платформа в цифрах' })).toBeTruthy();

    // Один раз «докручиваемое» число: без IntersectionObserver (тесты, печать) сразу итог.
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(screen.getByText('тыс.')).toBeTruthy();
    // Подписи — одно короткое слово над числом: три равные колонки, ни одна не переносится на вторую строку.
    expect(screen.getByText('Показатели')).toBeTruthy();
    expect(screen.getByText('55')).toBeTruthy();
    expect(screen.getByText('Страны')).toBeTruthy();
    expect(screen.getByText('1897')).toBeTruthy();
    expect(screen.getByText('Данные с')).toBeTruthy();
    const labels = [...document.querySelectorAll('.fe-scope-stat__label')];
    expect(labels).toHaveLength(3);
    expect(labels.every((el) => el.textContent.trim().split(/\s+/).length <= 2)).toBe(true);

    // Российские 145 и 495 — только внутри раскрывашки, не в основной сетке.
    const details = screen.getByText('Данные — только из официальных источников').closest('details');
    expect(details.contains(screen.getByText('145'))).toBe(true);
    expect(details.contains(screen.getByText('495'))).toBe(true);
    expect(screen.getByText(/региональных показателей России/)).toBeTruthy();
    expect(screen.queryByText(/2\s*377/)).toBeNull();
    expect(screen.queryByText(/США:.*штатам/)).toBeNull();
  });

  it('берёт число стран с API, а не устаревший фоллбэк', async () => {
    renderScope({ countries: COUNTRIES(57), total: 57 });
    await waitFor(() => expect(screen.getByText('57')).toBeTruthy());
    expect(screen.getByText('Страны')).toBeTruthy();
  });

  it('если в каталоге нет чисел, вместо них — честный прочерк, а не выдуманное значение', async () => {
    renderScope({ countries: [], total: 0 });
    await waitFor(() => expect(screen.getAllByLabelText('нет данных')).toHaveLength(2));
    expect(screen.queryByText('тыс.')).toBeNull();
  });

  it('официальные источники и режим обновления — в раскрывашке «Данные — только из официальных источников»', () => {
    renderScope();

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

  it('EN: без российских строк, источники международные', async () => {
    renderScope(undefined, 'en');

    expect(screen.getByRole('heading', { name: 'The platform in numbers' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(screen.getByText('K')).toBeTruthy();
    expect(screen.getByText('Indicators')).toBeTruthy();
    expect(screen.getByText('Countries')).toBeTruthy();
    // «Data since 1897», а не «since 1897 years of history».
    expect(screen.getByText('Data since')).toBeTruthy();
    expect(screen.getByText('1897')).toBeTruthy();
    expect(screen.queryByText(/years of history/)).toBeNull();
    expect(screen.queryByText(/Russian macro indicators/)).toBeNull();
    expect(screen.queryByText('495')).toBeNull();
    expect(screen.getByText(
      'Eurostat, IMF, U.S. Bureau of Labor Statistics, Bureau of Economic Analysis, Federal Reserve, national statistical offices and central banks',
    )).toBeTruthy();
    expect(screen.queryByText(/Rosstat/)).toBeNull();
  });
});
