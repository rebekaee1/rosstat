// Мелочи графика «Сравнение»: подписи концов линий, разрыв между двумя рядами словами,
// раскладка подписей без наложения. Чистые функции: ничего не знают про React.
import { formatAxisTick } from './format';

const PERCENT_LIKE = /%|п\.\s?п\.|p\.p\.|индекс|index/i;

/** Единица описывает абсолютную величину (млрд $, человек), а не долю, ставку или индекс. */
export function isAbsoluteUnit(unit) {
  const text = String(unit ?? '').trim();
  if (!text) return false;
  return !PERCENT_LIKE.test(text);
}

/** Последнее конечное значение ряда `[{ date, value }]` или null. */
export function lastFiniteValue(points) {
  for (let i = (points?.length || 0) - 1; i >= 0; i -= 1) {
    const raw = points[i]?.value;
    if (raw == null) continue;
    const v = Number(raw);
    if (Number.isFinite(v)) return v;
  }
  return null;
}

/**
 * Значение для подписи конца линии: без копеек и хвостов («28,1 млн», «30 767», «4,2 %»).
 * Миллионы и выше сокращаются словами по правилам языка, остальное идёт с разумным числом знаков.
 */
export function formatEndValue(value, { unit = '', locale = 'ru', indexed = false } = {}) {
  const num = Number(value);
  if (value == null || !Number.isFinite(num)) return '';
  if (indexed) return formatAxisTick(num, 0, locale);
  const abs = Math.abs(num);
  let text;
  if (abs >= 1e6) {
    try {
      text = new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU', {
        notation: 'compact',
        maximumFractionDigits: abs >= 1e8 ? 0 : 1,
      }).format(num);
    } catch {
      text = formatAxisTick(num, 0, locale);
    }
  } else if (abs >= 1000) {
    text = formatAxisTick(num, 0, locale);
  } else if (abs >= 100) {
    text = formatAxisTick(num, 1, locale);
  } else {
    text = formatAxisTick(num, 2, locale);
  }
  const unitText = String(unit ?? '').trim();
  return /^%$|^п\.\s?п\.$/i.test(unitText) ? `${text} ${unitText}` : text;
}

/**
 * Разрыв между двумя рядами: «США больше, чем Китай, в 1,6 раза».
 * items — ровно два элемента `{ label, value }` с положительными значениями; иначе null.
 * Возвращает `{ leader, other, ratio, text, plural }`: `ratio` округлён (1 знак до 10, дальше целое),
 * `plural` — категория слова «раз» для языка. Если ряды почти равны (меньше 5 %), `equal: true`.
 */
export function gapInsight(items, locale = 'ru') {
  if (!Array.isArray(items) || items.length !== 2) return null;
  const [a, b] = items;
  const va = Number(a?.value);
  const vb = Number(b?.value);
  if (!Number.isFinite(va) || !Number.isFinite(vb) || va <= 0 || vb <= 0) return null;
  const leader = va >= vb ? a : b;
  const other = va >= vb ? b : a;
  const raw = Math.max(va, vb) / Math.min(va, vb);
  if (raw < 1.05) return { equal: true, a: a.label, b: b.label };
  const ratioNumber = raw >= 10 ? Math.round(raw) : Math.round(raw * 10) / 10;
  const ratio = new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU', {
    maximumFractionDigits: raw >= 10 ? 0 : 1,
  }).format(ratioNumber);
  let plural = 'other';
  try {
    plural = new Intl.PluralRules(locale === 'en' ? 'en' : 'ru').select(ratioNumber);
  } catch {
    plural = 'other';
  }
  return {
    equal: false, leader: leader.label, other: other.label, ratio, plural,
  };
}

/**
 * Раскладывает подписи концов линий по высоте так, чтобы они не налезали друг на друга.
 * items: `[{ key, y }]` (y — желаемый центр подписи, px). Возвращает `{ key: y }` внутри [min, max].
 */
export function spreadLabels(items, { min = 0, max = Infinity, gap = 34 } = {}) {
  const sorted = [...items].sort((p, q) => p.y - q.y).map((item) => ({ ...item }));
  sorted.forEach((item, i) => {
    item.y = Math.max(min, item.y);
    if (i > 0) item.y = Math.max(item.y, sorted[i - 1].y + gap);
  });
  // Если вышли за нижний край, сдвигаем стопку вверх, не нарушая зазор.
  for (let i = sorted.length - 1; i >= 0; i -= 1) {
    const limit = i === sorted.length - 1 ? max : sorted[i + 1].y - gap;
    if (sorted[i].y > limit) sorted[i].y = limit;
  }
  const out = {};
  sorted.forEach((item) => { out[item.key] = Math.max(min, item.y); });
  return out;
}

/** Пиксель по вертикали для значения на оси с домeном [lo, hi] в области высотой `plotHeight` от `top`. */
export function yForValue(value, domain, { top = 0, plotHeight = 0 } = {}) {
  const [lo, hi] = domain || [];
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi === lo) return null;
  const share = (Number(value) - lo) / (hi - lo);
  return top + (1 - share) * plotHeight;
}
