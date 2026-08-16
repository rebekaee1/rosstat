/**
 * Locale-aware view-mode copy for indicator cards.
 *
 * RU stays in lib/*ViewModeContent (JSX formulas intact).
 * EN twins live in viewModeContent.en.js (plain strings).
 */
import {
  getViewModeContent,
  getCpiChartTitle,
  getCpiTableTitle,
} from '../lib/cpiViewModeContent';
import {
  getHousingChartTitle,
  getHousingTableTitle,
} from '../lib/housingViewModeContent';
import {
  getPpiChartTitle,
  getPpiTableTitle,
} from '../lib/ppiViewModeContent';
import {
  getCbrTermSliceChartTitle,
  getCbrTermSliceTableTitle,
} from '../lib/cbrTermSliceRateContent';
import {
  getUnemploymentChartTitle,
  getUnemploymentTableTitle,
} from '../lib/unemploymentViewModeContent';
import { unitSuffix } from '../lib/format';
import {
  getViewModeContentEn,
  getCpiChartTitleEn,
  getCpiTableTitleEn,
  getHousingChartTitleEn,
  getHousingTableTitleEn,
  getPpiChartTitleEn,
  getPpiTableTitleEn,
  getUnemploymentChartTitleEn,
  getUnemploymentTableTitleEn,
  getCbrTermSliceChartTitleEn,
  getCbrTermSliceTableTitleEn,
} from './viewModeContent.en';

const FREQUENCY_LONG_RU = {
  daily: 'днев.',
  weekly: 'недельная',
  monthly: 'помесячно',
  quarterly: 'квартально',
  annual: 'годовая',
};

const FREQUENCY_LONG_EN = {
  daily: 'daily',
  weekly: 'weekly',
  monthly: 'monthly',
  quarterly: 'quarterly',
  annual: 'annual',
};

function genericChartTitle(indicator, locale) {
  const suffix = unitSuffix(indicator?.unit);
  const freqMap = locale === 'en' ? FREQUENCY_LONG_EN : FREQUENCY_LONG_RU;
  const freq = freqMap[indicator?.frequency] || '';
  const fallback = locale === 'en' ? 'Indicator' : 'Показатель';
  const baseTitle = `${indicator?.name || fallback}${suffix ? ` (${suffix})` : ''}`;
  return freq ? `${baseTitle} — ${freq}` : baseTitle;
}

function genericTableTitle(indicator, locale) {
  const fallback = locale === 'en' ? 'series' : 'ряд';
  const prefix = locale === 'en' ? 'Historical data' : 'Исторические данные';
  return `${prefix} — ${indicator?.name || fallback}`;
}

/**
 * Methodology / description for the card panel.
 */
export function resolveViewModeContent(locale, args) {
  if (locale === 'en') return getViewModeContentEn(args);
  return getViewModeContent(args);
}

/**
 * Chart H2 for bespoke families + generic fallback (API name already localized).
 */
export function resolveChartTitle(locale, {
  chartMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  indicator,
  safeViewMode,
}) {
  const en = locale === 'en';
  if (isUnemploymentFamily) {
    return en
      ? getUnemploymentChartTitleEn(chartMode)
      : getUnemploymentChartTitle(chartMode);
  }
  if (isPpiFamily) {
    return en
      ? getPpiChartTitleEn(chartMode, safeViewMode)
      : getPpiChartTitle(chartMode, safeViewMode);
  }
  if (isCbrTermSliceFamily) {
    return en
      ? getCbrTermSliceChartTitleEn(chartMode, indicator?.code)
      : getCbrTermSliceChartTitle(chartMode, indicator?.code);
  }
  if (isHousingFamily && indicator?.code) {
    return en
      ? getHousingChartTitleEn(chartMode, indicator.code, safeViewMode)
      : getHousingChartTitle(chartMode, indicator.code, safeViewMode);
  }
  if (isPriceCategory && indicator?.code) {
    return en
      ? getCpiChartTitleEn(chartMode, indicator.code, safeViewMode)
      : getCpiChartTitle(chartMode, indicator.code, safeViewMode);
  }
  return genericChartTitle(indicator, locale);
}

/**
 * Data-table section title.
 */
export function resolveTableTitle(locale, {
  chartMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  indicator,
  safeViewMode,
}) {
  const en = locale === 'en';
  if (isUnemploymentFamily) {
    return en
      ? getUnemploymentTableTitleEn(chartMode)
      : getUnemploymentTableTitle(chartMode);
  }
  if (isPpiFamily) {
    return en
      ? getPpiTableTitleEn(chartMode, safeViewMode)
      : getPpiTableTitle(chartMode, safeViewMode);
  }
  if (isCbrTermSliceFamily) {
    return en
      ? getCbrTermSliceTableTitleEn(chartMode, indicator?.code)
      : getCbrTermSliceTableTitle(chartMode, indicator?.code);
  }
  if (isHousingFamily && indicator?.code) {
    return en
      ? getHousingTableTitleEn(chartMode, indicator.code, safeViewMode)
      : getHousingTableTitle(chartMode, indicator.code, safeViewMode);
  }
  if (isPriceCategory && indicator?.code) {
    return en
      ? getCpiTableTitleEn(chartMode, indicator.code, safeViewMode)
      : getCpiTableTitle(chartMode, indicator.code, safeViewMode);
  }
  return genericTableTitle(indicator, locale);
}
