/**
 * Оси графика для человека: годы вместо «авг 2022, июн 2023, апр 2024» и «24 млн» вместо «24 000 000».
 */
import { formatAxisTick } from './format';

const YEAR_STEPS = [1, 2, 5, 10, 20, 25, 50];

function yearOf(iso) {
  const y = Number(String(iso).slice(0, 4));
  return Number.isFinite(y) ? y : null;
}

function monthOf(iso) {
  const m = Number(String(iso).slice(5, 7));
  return Number.isFinite(m) ? m : 1;
}

/** Окно длиннее двух лет: подписи по годам понятнее, чем по месяцам. */
export function spansManyYears(dates, minMonths = 30) {
  if (!Array.isArray(dates) || dates.length < 2) return false;
  const first = dates[0];
  const last = dates[dates.length - 1];
  const a = yearOf(first);
  const b = yearOf(last);
  if (a == null || b == null) return false;
  return (b - a) * 12 + (monthOf(last) - monthOf(first)) >= minMonths;
}

/**
 * Подписи оси X по календарным годам: берём первую точку каждого года (январь), шаг растёт 1, 2, 5, 10…,
 * пока подписи помещаются. Неполный первый год (начало после февраля) не подписываем, чтобы «2021» не стояло в марте.
 * @param {string[]} dates даты окна по возрастанию
 * @returns {string[]|null} значения для `ticks` или null, если годовую ось не построить
 */
export function yearAxisTicks(dates, plotWidthPx = 0) {
  if (!Array.isArray(dates) || dates.length < 2) return null;
  const firstByYear = new Map();
  for (const date of dates) {
    const y = yearOf(date);
    if (y != null && !firstByYear.has(y)) firstByYear.set(y, date);
  }
  const years = [...firstByYear.keys()].sort((a, b) => a - b);
  if (years.length < 2) return null;
  const firstYear = years[0];
  const startsEarly = monthOf(firstByYear.get(firstYear)) <= 2;
  const usable = startsEarly ? years : years.slice(1);
  if (usable.length < 2) return null;
  const budget = Math.max(2, plotWidthPx > 0 ? Math.floor(plotWidthPx / 58) : 6);
  for (const step of YEAR_STEPS) {
    const picked = usable.filter((y) => (step === 1 ? true : y % step === 0));
    if (picked.length >= 2 && picked.length <= budget) {
      return picked.map((y) => firstByYear.get(y));
    }
  }
  return null;
}

/**
 * Подпись деления оси Y: от миллиона — «24 млн», от миллиарда — «3 млрд». Меньшие числа как обычно.
 * `digits` — знаков для обычных чисел; для укрупнённых хватает одного.
 */
export function formatAxisTickCompact(val, digits = 2, locale) {
  const n = Number(val);
  if (val == null || !Number.isFinite(n)) return '';
  const abs = Math.abs(n);
  const en = locale === 'en';
  const rules = en
    ? [[1e12, 'T'], [1e9, 'B'], [1e6, 'M']]
    : [[1e12, ' трлн'], [1e9, ' млрд'], [1e6, ' млн']];
  for (const [div, suffix] of rules) {
    if (abs >= div) {
      const scaled = n / div;
      return `${formatAxisTick(scaled, Math.abs(scaled) >= 100 ? 0 : 1, locale)}${suffix}`;
    }
  }
  return formatAxisTick(n, digits, locale);
}

/** Нужна ли укрупнённая подпись: самое большое по модулю значение от миллиона. */
export function needsCompactAxis(maxAbs) {
  return Number.isFinite(maxAbs) && maxAbs >= 1e6;
}
