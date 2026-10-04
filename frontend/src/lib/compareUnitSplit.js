import { formatValueWithUnit } from './format';

/**
 * Делит длинную единицу показателя на короткую (идёт сразу за числом) и
 * поясняющий хвост («% от среднего по ЕС на душу населения» →
 * «%» + «от среднего по ЕС на душу населения»).
 * Хвост в крупное число не попадает: он выводится мелко отдельной строкой.
 */
export function splitUnit(unit) {
  const raw = String(unit ?? '').trim();
  if (!raw) return { short: '', tail: '' };
  const m = raw.match(/^(%|п\.\s?п\.|p\.p\.)\s+(.+)$/i);
  if (m) return { short: m[1], tail: m[2] };
  if (raw.length > 14 && /\s/.test(raw)) {
    // «млрд долл. США, постоянные цены» — короткая часть до первой запятой.
    const comma = raw.indexOf(',');
    if (comma > 0 && comma <= 14) return { short: raw.slice(0, comma), tail: raw.slice(comma + 1).trim() };
    return { short: '', tail: raw };
  }
  return { short: raw, tail: '' };
}

/** Число с короткой единицей + отдельный пояснительный хвост. */
export function formatValueSplit(value, unit, digits, locale) {
  const { short, tail } = splitUnit(unit);
  if (value == null || !Number.isFinite(Number(value))) return { main: '—', tail, unitShort: short };
  if (!short) {
    return { main: formatValueWithUnit(value, '', digits ?? 2, locale).trim(), tail, unitShort: '' };
  }
  return { main: formatValueWithUnit(value, short, digits, locale), tail, unitShort: short };
}
