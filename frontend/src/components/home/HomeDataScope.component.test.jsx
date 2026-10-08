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

    // Круг 8: полоса из трёх чисел и больше ничего: ни строки «обновляется», ни раскрывающегося абзаца об источниках.
    expect(document.querySelector('details')).toBeNull();
    expect(screen.queryByText('Только официальные источники')).toBeNull();
    expect(screen.queryByText(/обновляются автоматически/)).toBeNull();
    expect(screen.queryByText('145')).toBeNull();
    expect(screen.queryByText('495')).toBeNull();
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
    expect(screen.queryByText(/Rosstat/)).toBeNull();
    expect(screen.getByText('268').closest('a').getAttribute('href')).toBe('/world/rating/gdp-usd');
  });

  it('полоса «Платформа в цифрах» не обещает «ежедневно» и не несёт лишних строк', async () => {
    renderScope();
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(document.querySelector('.fe-scope-update')).toBeNull();
    expect(document.querySelector('[data-block="home-data-scope"]').textContent).not.toMatch(/ежедневн/i);
  });

  it('счёт цифр: если число в экране, набегает от нуля один раз и приходит к итоговому; итог всегда в разметке', async () => {
    const frames = [];
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { frames.push(callback); return frames.length; });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 60, height: 30, top: 120, bottom: 150, left: 0, right: 60, x: 0, y: 120, toJSON: () => ({}),
    });
    renderScope();
    const number = await screen.findByText('0', { selector: '.fe-scope-stat__link span, dd span' });
    expect(number).toBeTruthy();
    // Кадр за кадром до итога.
    const run = (time) => { const next = frames.splice(0); next.forEach((callback) => callback(time)); };
    run(0);
    run(1000);
    run(2000);
    await waitFor(() => expect(screen.getByText('268')).toBeTruthy());
    expect(screen.getByText('55')).toBeTruthy();
  });
});
