// Точность чисел ряда (круг «Туризм», правки 22 и 38): без «1 847,69 тыс.» и «16,112.00».
// Прогноз берёт точность у факта, поэтому здесь значения — только фактические точки.
import { chartValueDigits, unitDigitsKnown } from './format';

// Счётные единицы без своей настройки: «тыс. поездок», «тыс. прибытий», «people», «thousand trips».
const COUNT_UNIT_RE = /^(?:(?:тыс\.?|млн|млрд)\s+)?(?:поездок|прибытий|выездов|въездов|ночёвок|ночевок|размещённых|размещенных|человек|чел\.?|посещений|единиц|мест|номеров)\b|^(?:thousand|million|billion)?\s*(?:people|persons|trips|arrivals|visits|nights)\b/i;
const SCALE_COUNT_RE = /^(?:тыс\.?|млн|млрд|thousand|million|billion)\s+\S/i;

function isCountUnit(unit) {
  const text = String(unit ?? '').trim();
  if (!text || /%|₽|руб|\$|€|\/|индекс|index|п\.\s?п\./i.test(text)) return false;
  return COUNT_UNIT_RE.test(text) || SCALE_COUNT_RE.test(text);
}

/**
 * Знаков после запятой для значений ряда.
 * Для известных единиц и всех не счётных рядов — прежняя настройка сайта (ничего не меняется).
 * Для счётных единиц без настройки: целые числа без дроби, иначе по величине (от 100 — целые, от 10 — один знак, меньше — два).
 */
export function valueDigitsFor(unit, values, mode) {
  const base = chartValueDigits(unit, mode);
  if (unitDigitsKnown(unit) || !isCountUnit(unit)) return base;
  const nums = (values || []).map(Number).filter(Number.isFinite);
  if (!nums.length) return base;
  if (nums.every((n) => Number.isInteger(n))) return 0;
  const sorted = nums.map(Math.abs).sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  if (median >= 100) return 0;
  if (median >= 10) return 1;
  return 2;
}

/** Ширина оси Y по самой длинной подписи среди всех делений (а не только верхнего): «10 000» над «−2» не обрезается до «0,000». */
export function yAxisLabelWidth(labels) {
  const longest = (labels || []).reduce((len, text) => Math.max(len, String(text ?? '').length), 0);
  return Math.max(40, Math.min(120, longest * 7.5 + 12));
}
