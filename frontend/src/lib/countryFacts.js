/**
 * Короткие факты о стране для карточки каталога: размер экономики, инфляция, безработица и линия истории ВВП.
 * Всё берётся из тех же ответов, что рейтинг и карта главной (снимки по понятиям и ряд карты), отдельных запросов
 * по странам нет. Форматирование по локали, крупные суммы в «трлн $».
 */
import { formatValue } from './format';

/** Сумма в миллиардах долларов по числу и подписи единицы («млрд $», «млн $», «трлн $»). */
export function billionsOf(value, unit = '') {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const u = String(unit).toLowerCase();
  if (/трлн|trillion/.test(u)) return n * 1000;
  if (/млрд|billion/.test(u)) return n;
  if (/млн|million/.test(u)) return n / 1000;
  return n;
}

/** «3,5 трлн $», «820 млрд $», «450 млн $»; EN: «$3.5 trillion». Нет значения — пустая строка. */
export function formatEconomySize(valueBn, locale = 'ru') {
  const bn = Number(valueBn);
  if (!Number.isFinite(bn) || bn <= 0) return '';
  const en = locale === 'en';
  const nbsp = '\u00a0';
  if (bn >= 1000) {
    const tn = bn / 1000;
    const text = formatValue(tn, 1, locale);
    return en ? `$${text} trillion` : `${text}${nbsp}трлн${nbsp}$`;
  }
  if (bn >= 1) {
    const text = formatValue(bn, bn >= 10 ? 0 : 1, locale);
    return en ? `$${text} billion` : `${text}${nbsp}млрд${nbsp}$`;
  }
  const text = formatValue(bn * 1000, 0, locale);
  return en ? `$${text} million` : `${text}${nbsp}млн${nbsp}$`;
}

/** «4,0 %» по-русски (неразрывный пробел), «4.0%» по-английски. */
export function formatPercentValue(value, locale = 'ru') {
  const n = Number(value);
  if (!Number.isFinite(n)) return '';
  const text = formatValue(n, 1, locale);
  return locale === 'en' ? `${text}%` : `${text}\u00a0%`;
}

/** Последние `limit` значений страны по годам из ряда карты (`values_by_year[год][код].value`). */
export function sparkValuesForCountry(mapSeries, code, limit = 20) {
  const byYear = mapSeries?.values_by_year;
  if (!byYear || !code) return [];
  const years = Object.keys(byYear).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  const out = [];
  for (const year of years) {
    const value = Number(byYear[String(year)]?.[code]?.value);
    if (Number.isFinite(value)) out.push(value);
  }
  return out.slice(-limit);
}

function itemsByCode(snapshot) {
  const map = new Map();
  for (const item of snapshot?.items || []) {
    if (item?.country_code && item.value != null) map.set(item.country_code, item);
  }
  return map;
}

/**
 * Словарь «код страны → факты». `economyBn` нужен и для сортировки «по размеру экономики».
 * Любой из источников может отсутствовать (ещё грузится или не ответил): тогда нет и соответствующего поля.
 */
export function buildCountryFacts({ gdp, inflation, unemployment, gdpSeries } = {}) {
  const gdpMap = itemsByCode(gdp);
  const infMap = itemsByCode(inflation);
  const unMap = itemsByCode(unemployment);
  const codes = new Set([...gdpMap.keys(), ...infMap.keys(), ...unMap.keys()]);
  const facts = new Map();
  for (const code of codes) {
    const g = gdpMap.get(code);
    facts.set(code, {
      economyBn: g ? billionsOf(g.value, g.unit) : null,
      inflation: infMap.has(code) ? Number(infMap.get(code).value) : null,
      unemployment: unMap.has(code) ? Number(unMap.get(code).value) : null,
      spark: sparkValuesForCountry(gdpSeries, code),
    });
  }
  return facts;
}
