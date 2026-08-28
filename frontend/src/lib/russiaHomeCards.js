/**
 * Данные карточки страны /russia (ADR-0013).
 *
 * Слой данных — российский каталог (GET /api/v1/indicators, useIndicators),
 * не world-plane: группировка листинга по категориям CATEGORIES, сортировка
 * плиток и обзорные чипы. «Первая цифра» плитки/чипа — как на карточках
 * каталога (IndicatorTile): hero (г/г для индекс-рядов), для сырого ИПЦ —
 * «минус 100».
 */
import { isIndicatorListed, indicatorCategoryKey } from './categories';
import { isCpiIndex } from './format';

const NAME_COLLATOR = new Intl.Collator('ru');

/**
 * Порядок плитки внутри секции: ряды с текущим значением — выше (как в
 * листинге страны WorldCountry), внутри группы — по имени.
 */
export function sortRussiaTiles(items) {
  return [...(items || [])].sort((a, b) => {
    const aHas = a?.current_value != null ? 0 : 1;
    const bHas = b?.current_value != null ? 0 : 1;
    if (aHas !== bHas) return aHas - bHas;
    return NAME_COLLATOR.compare(a?.name || a?.code || '', b?.name || b?.code || '');
  });
}

/**
 * Листинг по категориям CATEGORIES (apiCategory — точное значение category
 * в БД). Категории без рядов не возвращаются; ряды вне CATEGORIES в листинг
 * не попадают (is_listed), поэтому просто не группируются.
 */
export function groupRussiaCategories(indicators, categories) {
  const byApi = new Map();
  for (const ind of indicators || []) {
    if (!isIndicatorListed(ind)) continue;
    const key = indicatorCategoryKey(ind);
    if (!key) continue;
    const bucket = byApi.get(key);
    if (bucket) bucket.push(ind);
    else byApi.set(key, [ind]);
  }
  const out = [];
  for (const category of categories || []) {
    const items = byApi.get(category.apiCategory);
    if (!items?.length) continue;
    byApi.delete(category.apiCategory);
    out.push({ category, indicators: sortRussiaTiles(items), count: items.length });
  }
  return out;
}

/**
 * Первая цифра плитки/чипа: hero (г/г %) либо уровень; для сырого ИПЦ-индекса
 * без hero — «минус 100», как в IndicatorTile. null — показывать нечего
 * (ряд без значения чип не образует).
 */
export function russiaIndicatorDisplay(indicator) {
  if (!indicator) return null;
  if (indicator.hero_value != null && Number.isFinite(Number(indicator.hero_value))) {
    return { value: Number(indicator.hero_value), unit: indicator.hero_unit || '%', isHero: true };
  }
  const raw = indicator.current_value;
  if (raw == null || !Number.isFinite(Number(raw))) return null;
  const value = isCpiIndex(indicator.code)
    ? +(Number(raw) - 100).toFixed(2)
    : Number(raw);
  return { value, unit: indicator.unit || '', isHero: false };
}

/** Бейдж изменения: hero_change у hero-рядов, иначе дельта уровня. */
export function russiaIndicatorChange(indicator) {
  if (!indicator) return null;
  const raw = indicator.hero_value != null ? indicator.hero_change : indicator.change;
  const n = raw == null ? Number.NaN : Number(raw);
  return Number.isFinite(n) && Math.abs(n) >= 1e-12 ? n : null;
}

/**
 * Обзорные чипы под H1: якорные индикаторы страны в порядке показа.
 * unemployment — код главного ряда безработицы РФ; unemployment-rate оставлен
 * запасным идентификатором на случай переименования ряда.
 */
export const RUSSIA_OVERVIEW_CHIP_CODES = Object.freeze([
  Object.freeze(['cpi']),
  Object.freeze(['key-rate']),
  Object.freeze(['unemployment', 'unemployment-rate']),
]);

export function russiaOverviewChips(indicators) {
  const byCode = new Map(
    (indicators || []).filter((ind) => ind?.code).map((ind) => [ind.code, ind]),
  );
  const chips = [];
  for (const codes of RUSSIA_OVERVIEW_CHIP_CODES) {
    const indicator = codes.map((code) => byCode.get(code)).find(Boolean);
    const display = russiaIndicatorDisplay(indicator);
    if (indicator && display) {
      chips.push({ code: indicator.code, indicator, ...display });
    }
  }
  return chips;
}
