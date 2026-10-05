/**
 * Calendar event grouping.
 *
 * ЦБ публикует одну ведомость («Внешняя торговля товарами»), а backend
 * раскладывает её на 3 события — по одному на каждый индикатор-наследник
 * (exports / imports / trade-balance) с разными `event_key`. Бэк не может
 * слить их обратно (event_key должен оставаться уникальным per indicator,
 * иначе разлетится whole calendar invariant о (source × code × period) →
 * один event), поэтому group-by делаем на фронте перед рендером.
 *
 * Ключ группировки = `${date}|${time||'00:00'}|${source}|${title}` +
 *                    `source_event_uid` без code-суффикса (см. ниже).
 * Если ключ совпадает у ≥2 событий — мерджим в одну карточку с массивом
 * `indicators: [{code, name}, ...]`. Поля события (description, importance,
 * forecast_value/actual_value/...) берём из первого элемента группы.
 *
 * Один event возвращается as-is (без поля `indicators`).
 */

import { groupDescription } from './calendarText';

// source_event_uid обычно имеет вид `cbr-<indicator>-<date>` (см. backend
// calendar generator). Чтобы события одной публикации совпадали по
// grouping key, отрезаем индикатор-суффикс: всё что лежит между source-
// префиксом и финальной date. Например:
//   cbr-exports-2026-05-14         → cbr--2026-05-14
//   cbr-services-imports-2026-05-18 → cbr--2026-05-18
// Если формат не соответствует ожидаемому — возвращаем uid без изменений
// (грубая защита от мисс-grouping).
const UID_DATE_RE = /-(\d{4}-\d{2}-\d{2})$/;
const UID_SOURCE_RE = /^([a-z]+)-/;

export function normalizeEventUid(uid) {
  if (!uid || typeof uid !== 'string') return uid || '';
  const date = uid.match(UID_DATE_RE)?.[1];
  const source = uid.match(UID_SOURCE_RE)?.[1];
  if (!date || !source) return uid;
  return `${source}--${date}`;
}

function buildKey(event) {
  const date = event.scheduled_date || '';
  const time = event.scheduled_time || '';
  const source = event.source || '';
  const title = (event.title || '').trim();
  const uid = normalizeEventUid(event.source_event_uid);
  return `${date}|${time}|${source}|${title}|${uid}`;
}

/**
 * Group calendar events with the same (date, time, source, title, uid-without-code).
 *
 * @param {Array<object>} events — список событий от API.
 * @returns {Array<object>} — события с возможным полем `indicators: [{code, name}, ...]`.
 *   Если у группы только 1 элемент — возвращается as-is, без `indicators`.
 *   Если ≥2 — берётся первый event с дополнительным `indicators` массивом
 *   (deduped по code, отсортирован по code).
 */
export function groupSimilarEvents(events) {
  if (!Array.isArray(events) || events.length === 0) return [];

  const groups = new Map();
  const order = [];
  for (const ev of events) {
    if (!ev) continue;
    const key = buildKey(ev);
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key).push(ev);
  }

  return order.map((key) => {
    const arr = groups.get(key);
    if (arr.length === 1) return arr[0];

    const seenCodes = new Set();
    const indicators = [];
    for (const ev of arr) {
      const code = ev.indicator_code;
      if (!code || seenCodes.has(code)) continue;
      seenCodes.add(code);
      indicators.push({
        code,
        name: ev.indicator_name || code,
      });
    }
    indicators.sort((a, b) => a.code.localeCompare(b.code));

    // Берём первый event как основу, чтобы остальные поля (importance,
    // values, description, source_url, id) пришли консистентно.
    // Описание — у «головного» показателя группы (индекс цен, а не его услуговая часть).
    return { ...arr[0], description: groupDescription(arr), indicators };
  });
}

/**
 * Повторяющиеся каждый день события («Ставка RUONIA», курсы ЦБ) не должны занимать место в каждом дне
 * месяца: их выносят в одну строку «Каждый рабочий день». Повтор = одно и то же название и источник
 * минимум в `minDays` разных датах месяца (недельные публикации сюда не попадают).
 *
 * @param {Array<object>} monthEvents — все события месяца (для подсчёта повторов).
 * @returns {{ keys: Set<string>, items: Array<{key:string,title:string,time:string,source:string,days:number}>, everyDay: boolean }}
 */
export function findDailyRecurring(monthEvents, { minDays = 8 } = {}) {
  const byKey = new Map();
  for (const ev of Array.isArray(monthEvents) ? monthEvents : []) {
    if (!ev?.title || !ev.scheduled_date) continue;
    const key = recurringKeyOf(ev);
    let entry = byKey.get(key);
    if (!entry) {
      entry = { key, title: ev.title.trim(), time: ev.scheduled_time || '', source: ev.source || '', dates: new Set() };
      byKey.set(key, entry);
    }
    entry.dates.add(ev.scheduled_date);
  }
  const items = [];
  let everyDay = false;
  for (const entry of byKey.values()) {
    if (entry.dates.size < minDays) continue;
    for (const d of entry.dates) {
      const dow = new Date(`${d}T12:00:00`).getDay();
      if (dow === 0 || dow === 6) everyDay = true;
    }
    items.push({ key: entry.key, title: entry.title, time: entry.time, source: entry.source, days: entry.dates.size });
  }
  items.sort((a, b) => (a.time || '').localeCompare(b.time || '') || a.title.localeCompare(b.title, 'ru'));
  return { keys: new Set(items.map((i) => i.key)), items, everyDay };
}

export function recurringKeyOf(event) {
  return `${event?.source || ''}|${String(event?.title || '').trim()}`;
}

/**
 * Какой день открыть в календаре по умолчанию: сегодня, если в нём есть разовые события; иначе ближайший
 * день с важным событием (важность 2 и выше); иначе ближайший день с любым разовым событием.
 * Ежедневные публикации (курсы, ставки) в расчёт не берутся: они есть в каждый будний день и ничего не говорят.
 *
 * @param {Array<object>} monthEvents — события месяца.
 * @param {string} todayStr — сегодня в виде YYYY-MM-DD.
 * @param {Set<string>} recurringKeys — ключи ежедневных событий (`findDailyRecurring(...).keys`).
 * @returns {string|null}
 */
export function pickDefaultDay(monthEvents, todayStr, recurringKeys = new Set()) {
  const own = (Array.isArray(monthEvents) ? monthEvents : []).filter(
    (ev) => ev?.scheduled_date && !recurringKeys.has(recurringKeyOf(ev)),
  );
  if (own.some((ev) => ev.scheduled_date === todayStr)) return todayStr;
  const future = own
    .filter((ev) => ev.scheduled_date > todayStr)
    .sort((a, b) => a.scheduled_date.localeCompare(b.scheduled_date));
  const important = future.find((ev) => (ev.importance || 0) >= 2);
  return (important || future[0])?.scheduled_date || null;
}
