/**
 * Список показателей страны для человека: почти-дубли свёрнуты в одну строку («Число родившихся: 3 разреза»),
 * а единица измерения не повторяется ни в названии, ни под ним.
 */

/** Начало названия до первого разделителя: «Число родившихся по возрасту матери» -> «Число родившихся». */
export function indicatorBaseName(name) {
  const text = String(name || '').trim();
  if (!text) return '';
  const first = text.split(/\s+(?:по|by|of|for)\s+|\s*[:(,—–]\s*/i)[0];
  return first.trim();
}

/**
 * Убирает единицу из хвоста названия, если она уже показана отдельно:
 * «Число умерших, человек» + единица «человек» -> «Число умерших».
 */
export function dropRepeatedUnit(name, unit) {
  const text = String(name || '').trim();
  const u = String(unit || '').trim();
  if (!text || !u) return text;
  const escaped = u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const stripped = text.replace(new RegExp(`\\s*(?:,|\\u2014|\\u2013|-)\\s*${escaped}\\s*$`, 'i'), '')
    .replace(new RegExp(`\\s*\\(${escaped}\\)\\s*$`, 'i'), '');
  return stripped || text;
}

/**
 * Склеивает подряд идущие и разбросанные показатели с одним началом названия (две и больше штуки) в группу.
 * Группа встаёт на место первого члена. Одиночные показатели остаются как есть.
 * @param {Array<object>} items показатели категории
 * @param {(item: object) => string} nameOf публичное название показателя
 * @returns {Array<{ kind: 'single', item: object } | { kind: 'group', base: string, items: object[] }>}
 */
export function groupNearDuplicates(items, nameOf) {
  const list = Array.isArray(items) ? items : [];
  const buckets = new Map();
  for (const item of list) {
    const base = indicatorBaseName(nameOf(item));
    // Короткое начало («ВВП», «Цены») слишком общее: склеивать по нему разные показатели нельзя.
    const key = base.length >= 8 ? base.toLowerCase() : null;
    if (!key) continue;
    if (!buckets.has(key)) buckets.set(key, { base, members: [] });
    buckets.get(key).members.push(item);
  }
  const out = [];
  const emitted = new Set();
  for (const item of list) {
    const base = indicatorBaseName(nameOf(item));
    const key = base.length >= 8 ? base.toLowerCase() : null;
    const bucket = key ? buckets.get(key) : null;
    if (!bucket || bucket.members.length < 2) {
      out.push({ kind: 'single', item });
      continue;
    }
    if (emitted.has(key)) continue;
    emitted.add(key);
    out.push({ kind: 'group', base: bucket.base, items: bucket.members });
  }
  return out;
}
