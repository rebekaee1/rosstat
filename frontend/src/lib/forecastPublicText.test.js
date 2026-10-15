// Страж принципов владельца 7 и 8 на страницах прогноза world (круг 13): человеку не показывают название модели
// и MASE, а у прогноза нет диапазона. Читает исходники страниц и словари; падает, если жаргон вернулся.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import ru from '../i18n/messages.ru';
import en from '../i18n/messages.en';

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(join(here, '..', rel), 'utf8');

describe('публичный текст прогноза world', () => {
  it('страница показателя без MASE, названия модели и слов о качестве прогноза (круг 14)', () => {
    const page = read('pages/WorldIndicatorPage.jsx');
    const chart = read('components/WorldChartSection.jsx');
    expect(page).not.toMatch(/MASE/);
    expect(page).not.toMatch(/forecast\.model_name/);
    expect(page).not.toMatch(/c13f\.forecast\.checked|gate_status/);
    expect(chart).not.toMatch(/forecastPassed|forecastAdvisory|forecastGateStatus/);
    for (const dict of [ru, en]) {
      for (const key of ['c13f.forecast.checkedTitle', 'c13f.forecast.checkedBody', 'world.chart.forecastPassed', 'world.chart.forecastAdvisory']) {
        expect(dict[key]).toBeUndefined();
      }
    }
  });

  it('карточка прогноза региона без MASE и названия модели', () => {
    const page = read('pages/WorldRegionIndicatorPage.jsx');
    expect(page).not.toMatch(/MASE/);
    expect(page).not.toMatch(/forecastQ\.data\.model_name/);
  });

  it('в подписях официального прогноза нет диапазона и служебных слов', () => {
    for (const dict of [ru, en]) {
      for (const key of ['world.chart.forecastOfficial', 'world.forecast.officialTitle', 'world.forecast.officialBody']) {
        expect(dict[key]).toBeTruthy();
        expect(dict[key]).not.toMatch(/MASE|WEO|диапазон|коридор|range|interval|lower|upper/i);
      }
    }
  });
});
