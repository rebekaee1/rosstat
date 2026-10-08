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

/** Главные показатели страны: в своей категории стоят первыми, остальное — по алфавиту (иначе «Индекс доступности жилья» шёл перед ИПЦ). */
const PRIORITY_CODES = ['cpi', 'key-rate', 'usd-rub', 'eur-rub', 'cny-rub'];
const priorityOf = (item) => {
  const i = PRIORITY_CODES.indexOf(item?.code);
  return i < 0 ? PRIORITY_CODES.length : i;
};

/**
 * Порядок плитки внутри секции: ряды с текущим значением — выше (как в
 * листинге страны WorldCountry), затем главные показатели (ИПЦ, ключевая ставка,
 * курсы), внутри группы — по имени.
 */
export function sortRussiaTiles(items) {
  return [...(items || [])].sort((a, b) => {
    const aHas = a?.current_value != null ? 0 : 1;
    const bHas = b?.current_value != null ? 0 : 1;
    if (aHas !== bHas) return aHas - bHas;
    const byPriority = priorityOf(a) - priorityOf(b);
    if (byPriority !== 0) return byPriority;
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

/**
 * «Главная пятёрка» страны: инфляция, ставка, курс доллара, ВВП, безработица.
 *
 * Инфляция всегда за год, и число, «год назад» и график идут из одного годового
 * ряда `cpi-yoy` (скрыт из каталога, но читается по коду). Источник числа:
 * 1) `cpi-yoy` в листинге (если вызван с includeUnlisted);
 * 2) `hero_value` у `cpi` (бэкенд берёт его из `cpi-yoy` того же месяца).
 * Месячный индекс `cpi` (около 100) в годовую карточку не подставляется ни как
 * число, ни как «год назад»: он остаётся только мелкой строкой «за месяц».
 * Годового значения нет вообще — карточка честно называется «за месяц».
 */
export const RUSSIA_MAIN_FIVE = Object.freeze([
  Object.freeze({ id: 'inflation', codes: Object.freeze(['cpi']) }),
  Object.freeze({ id: 'rate', codes: Object.freeze(['key-rate']) }),
  Object.freeze({ id: 'usd', codes: Object.freeze(['usd-rub']) }),
  Object.freeze({ id: 'gdp', codes: Object.freeze(['gdp-nominal']) }),
  Object.freeze({ id: 'unemployment', codes: Object.freeze(['unemployment', 'unemployment-rate']) }),
]);

const INFLATION_YOY_SERIES = 'cpi-yoy';

function finiteOrNull(value) {
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Годовая инфляция: { value, date } из листинга или null, если годового числа нет. */
function inflationYearly(cpi, yoy) {
  const yoyValue = finiteOrNull(yoy?.current_value);
  if (yoyValue != null) return { value: yoyValue, date: yoy.current_date || cpi?.current_date || null };
  const hero = finiteOrNull(cpi?.hero_value);
  if (hero != null) return { value: hero, date: cpi.current_date || null };
  return null;
}

/** Месячное изменение цен из индекса `cpi` (около 100): 99,92 -> -0,08. null, если индекса нет. */
function inflationMonthly(cpi, yearlyDate) {
  const raw = finiteOrNull(cpi?.current_value);
  if (raw == null) return null;
  // Показываем месяц только того же периода, что и годовое число, иначе строка соврёт.
  if (yearlyDate && cpi.current_date && String(cpi.current_date).slice(0, 7) !== String(yearlyDate).slice(0, 7)) return null;
  return { value: +(raw - 100).toFixed(2), unit: '%' };
}

/**
 * @returns {Array<{ id: string, code: string, seriesCode: string, indicator: object, value: number,
 *   unit: string, monthly: ?{ value: number, unit: string }, date: ?string, titleKey: ?string }>}
 */
export function russiaMainFive(indicators) {
  const byCode = new Map(
    (indicators || []).filter((ind) => ind?.code).map((ind) => [ind.code, ind]),
  );
  const out = [];
  for (const slot of RUSSIA_MAIN_FIVE) {
    const indicator = slot.codes.map((code) => byCode.get(code)).find(Boolean);
    if (slot.id === 'inflation') {
      if (!indicator) continue;
      const yearly = inflationYearly(indicator, byCode.get(INFLATION_YOY_SERIES));
      if (yearly) {
        out.push({
          id: slot.id,
          code: indicator.code,
          seriesCode: INFLATION_YOY_SERIES,
          indicator,
          value: yearly.value,
          unit: '%',
          monthly: inflationMonthly(indicator, yearly.date),
          date: yearly.date,
          titleKey: null,
        });
        continue;
      }
      // Годового числа нет: показываем месяц и называем его месяцем, а не годом.
      const month = inflationMonthly(indicator, null);
      if (month) {
        out.push({
          id: slot.id,
          code: indicator.code,
          seriesCode: indicator.code,
          indicator,
          value: month.value,
          unit: '%',
          monthly: null,
          date: indicator.current_date,
          titleKey: 'c8y.ru.main.inflationMonth',
          // «Год назад» из индексного ряда нельзя: вычитать 99,6 из -0,08 бессмысленно.
          noYearAgo: true,
        });
      }
      continue;
    }
    const display = russiaIndicatorDisplay(indicator);
    if (!indicator || !display) continue;
    out.push({
      id: slot.id,
      code: indicator.code,
      seriesCode: indicator.code,
      indicator,
      value: display.value,
      unit: display.unit,
      monthly: null,
      date: indicator.current_date,
      titleKey: null,
    });
  }
  return out;
}

/** Сколько строк категории видно сразу, остальное по кнопке «Показать ещё». Чётное число: плитки идут в две колонки без пустой ячейки. */
export const RUSSIA_CATEGORY_PREVIEW = 6;
