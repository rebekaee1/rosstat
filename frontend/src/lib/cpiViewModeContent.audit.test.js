/**
 * Аудит 24 комбинаций: состав × активный режим.
 * Проверяет согласованность description + заголовков графика/таблицы.
 */
import { describe, it, expect } from 'vitest';
import {
  getViewModeContent,
  getCpiChartTitle,
  getCpiTableTitle,
} from './cpiViewModeContent.jsx';
import { dataModeForUrlMode } from './cpiViewModeResolve';
import { visibleCpiViewModes } from './cpiViewModeGroups';

/** Фразы чужого среза (не матчим «не»+продовольственные). */
const FOOD_ONLY = /на продовольственные товары|ИПЦ на продовольственные/i;
const NONFOOD_ONLY = /на непродовольственные товары|ИПЦ на непродовольственные/i;
const SERVICES_ONLY = /на услуги|ИПЦ на услуги/i;

const COMPOSITIONS = [
  {
    code: 'cpi',
    mustMatch: /потребительск|товаров и услуг/i,
    forbidden: [FOOD_ONLY, NONFOOD_ONLY, SERVICES_ONLY],
  },
  {
    code: 'cpi-food',
    mustMatch: /продовольственн/i,
    forbidden: [NONFOOD_ONLY, SERVICES_ONLY],
  },
  {
    code: 'cpi-nonfood',
    mustMatch: /непродовольственн/i,
    forbidden: [FOOD_ONLY, SERVICES_ONLY],
  },
  {
    code: 'cpi-services',
    mustMatch: /услуг/i,
    forbidden: [FOOD_ONLY, NONFOOD_ONLY],
  },
];

/** Режимы аудита — только видимые для данного состава (срезы — без недельных). */
function modesForCode(code) {
  return visibleCpiViewModes(code).map((m) => ({
    urlMode: m.mode,
    chartMode: dataModeForUrlMode(m.mode),
    label: m.label,
  }));
}

function bundle(code, urlMode, chartMode) {
  const indicator = { code };
  const content = getViewModeContent({
    chartMode,
    safeViewMode: urlMode,
    isPriceCategory: true,
    indicator,
  });
  const text = `${content.description} ${getCpiChartTitle(chartMode, code)} ${getCpiTableTitle(chartMode, code)}`;
  return { content, text, chartTitle: getCpiChartTitle(chartMode, code) };
}

describe('CPI состав × режим — аудит текстов', () => {
  for (const comp of COMPOSITIONS) {
    for (const mode of modesForCode(comp.code)) {
      const id = `${comp.code} × ${mode.urlMode}`;
      it(id, () => {
        const { content, text, chartTitle } = bundle(comp.code, mode.urlMode, mode.chartMode);

        expect(content.description.length, `${id}: пустое описание`).toBeGreaterThan(40);
        expect(content.methodology, `${id}: пустая методология`).toBeTruthy();

        expect(text, `${id}: нет маркера состава`).toMatch(comp.mustMatch);
        for (const re of comp.forbidden) {
          expect(text, `${id}: чужой состав (${re})`).not.toMatch(re);
        }

        if (mode.urlMode === 'inflation') {
          expect(content.description, id).toMatch(/соответствующ.+периоду предыдущего года/i);
          expect(chartTitle, id).toMatch(/предыдущего года/i);
        }
        if (mode.urlMode === 'inflation-quarter') {
          expect(content.description, id).toMatch(/квартал/i);
          expect(content.description, id).toMatch(/предыдущего года|год назад/i);
        }
        if (mode.urlMode === 'inflation-year') {
          expect(content.description, id).toMatch(/декабрь к декабрю/i);
        }
        if (mode.urlMode === 'step-weekly') {
          expect(content.description, id).toMatch(/недел/i);
        }
        if (mode.urlMode === 'step-monthly') {
          expect(content.description, id).toMatch(/месяц|м\/м|предыдущ/i);
        }
        if (mode.urlMode === 'period-monthly') {
          expect(content.description, id).toMatch(/месяц|недел/i);
        }
        if (mode.urlMode === 'period-weekly') {
          expect(content.description, id).toMatch(/недел/i);
        }
        if (mode.urlMode === 'yoy') {
          expect(content.description, id).toMatch(/Годовое изменение/i);
          expect(content.description, id).toMatch(/декабрь к декабрю/i);
        }
        if (mode.urlMode === 'qoq') {
          expect(content.description, id).toMatch(/квартал/i);
        }
        if (mode.urlMode === 'index') {
          expect(content.description, id).toMatch(/2000|накоплен/i);
          expect(chartTitle, id).toMatch(/2000=100|2000/);
        }
      });
    }
  }
});
