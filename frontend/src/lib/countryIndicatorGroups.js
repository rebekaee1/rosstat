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
 * Ключ группы: начало названия до «по/by» или, если оно слишком короткое («Занятые»), всё название до первой запятой.
 * «Занятые по стажу на работе и виду деятельности, тысяч человек, мужчины» -> «Занятые по стажу на работе и виду деятельности»:
 * такие ряды складываются в одну свёрнутую строку, а не стоят стеной одинаковых карточек.
 * @returns {string} пусто, если по названию склеивать нельзя
 */
export function groupBaseName(name) {
  const short = indicatorBaseName(name);
  if (short.length >= 8) return short;
  const text = String(name || '').trim();
  const long = text.split(/\s*[:(,—–]\s*/)[0].trim();
  // «Занятые» (7 знаков) мало, «Занятые по стажу…» уже определяет разрез; «ВВП по расходам» и «ВВП по доходам» остаются раздельно.
  return long.length >= 12 && long.length < text.length ? long : '';
}

/**
 * Подпись члена группы: то, чем он отличается от остальных («мужчины», «15–24 лет»), без общего начала и единицы.
 * Если отличий нет (названия совпали), возвращается полное название.
 */
export function groupMemberLabel(name, base, unit) {
  const text = String(name || '').trim();
  const head = String(base || '').trim();
  if (!text || !head || !text.toLowerCase().startsWith(head.toLowerCase())) return text;
  let tail = text.slice(head.length);
  const u = String(unit || '').trim();
  if (u) {
    const escaped = u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    tail = tail.replace(new RegExp(`\\s*,\\s*${escaped}(?=\\s*(?:,|$))`, 'i'), '');
  }
  tail = tail.replace(/^[\s,:;—–-]+/, '').replace(/[\s,:;—–-]+$/, '').trim();
  if (!tail) return text;
  // Остаток, который сам является единицей («% of active population»), не название разреза: чип без названия хуже полного имени.
  if (/^%/.test(tail) || (u && tail.toLowerCase() === u.toLowerCase())) return text;
  return tail.charAt(0).toUpperCase() + tail.slice(1);
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
  const bases = list.map((item) => groupBaseName(nameOf(item)));
  const buckets = new Map();
  list.forEach((item, index) => {
    const base = bases[index];
    if (!base) return;
    const key = base.toLowerCase();
    if (!buckets.has(key)) buckets.set(key, { base, members: [] });
    buckets.get(key).members.push(item);
  });
  const out = [];
  const emitted = new Set();
  list.forEach((item, index) => {
    const base = bases[index];
    const key = base ? base.toLowerCase() : null;
    const bucket = key ? buckets.get(key) : null;
    if (!bucket || bucket.members.length < 2) {
      out.push({ kind: 'single', item });
      return;
    }
    if (emitted.has(key)) return;
    emitted.add(key);
    out.push({ kind: 'group', base: bucket.base, items: bucket.members });
  });
  return out;
}
