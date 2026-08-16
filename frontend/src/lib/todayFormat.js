/**
 * Форматирование чисел и дат для страниц «на сегодня».
 * Зеркало backend/app/services/seo_today.py::_format_number / _ru_date.
 * Не подставлять formatValue из format.js — там другая точность и хвостовые нули.
 */

const MONTHS_GEN = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

const STALE_AFTER_DAYS = {
  daily: 7,
  weekly: 21,
  monthly: 75,
  quarterly: 150,
  annual: 500,
};

/** Русская типографика: пробел-разряды, запятая-дробь; хвостовые нули снимаются. */
export function formatTodayNumber(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) return '';
  const digits = Math.abs(v) >= 1000 ? 0 : (Math.abs(v) >= 100 ? 1 : 2);
  let text = v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: true,
  }).replace(/,/g, '\u202f').replace('.', ',');
  if (text.includes(',')) {
    text = text.replace(/0+$/, '').replace(/,$/, '');
  }
  return text;
}

/** «16 августа 2026 года» — как seo_today._ru_date. */
export function formatTodayRuDate(input = new Date()) {
  let d;
  if (input instanceof Date) {
    d = input;
  } else if (typeof input === 'string' && /^\d{4}-\d{2}-\d{2}/.test(input)) {
    const [y, m, day] = input.slice(0, 10).split('-').map(Number);
    d = new Date(Date.UTC(y, m - 1, day));
  } else {
    d = new Date(input);
  }
  if (Number.isNaN(d.getTime())) return '';
  const day = input instanceof Date || typeof input !== 'string'
    ? d.getDate()
    : d.getUTCDate();
  const month = input instanceof Date || typeof input !== 'string'
    ? d.getMonth()
    : d.getUTCMonth();
  const year = input instanceof Date || typeof input !== 'string'
    ? d.getFullYear()
    : d.getUTCFullYear();
  return `${day} ${MONTHS_GEN[month]} ${year} года`;
}

/** Московское «сегодня» для заголовков (как display.today_msk). */
export function todayMsk() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const get = (type) => parts.find((p) => p.type === type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export function isTodayStale(frequency, lastDateIso, todayIso = todayMsk()) {
  if (!lastDateIso) return true;
  const last = new Date(`${String(lastDateIso).slice(0, 10)}T00:00:00Z`);
  const today = new Date(`${todayIso}T00:00:00Z`);
  const limit = STALE_AFTER_DAYS[(frequency || '').toLowerCase()] ?? 75;
  return Math.floor((today - last) / 86400000) > limit;
}

/** Фраза изменения — как seo_today._change_phrase. */
export function todayChangePhrase(cur, prev, unit) {
  const diff = Number(cur) - Number(prev);
  if (!Number.isFinite(diff) || Math.abs(diff) < 1e-12) {
    return 'без изменений к предыдущему значению';
  }
  const verb = diff > 0 ? 'выше' : 'ниже';
  const u = (unit || '').trim();
  if (u === '%') {
    return `${verb} предыдущего значения на ${formatTodayNumber(Math.abs(diff))} п. п.`;
  }
  let text = `на ${formatTodayNumber(Math.abs(diff))} ${u}`.trim();
  if (prev) {
    const pct = Math.abs(diff) / Math.abs(Number(prev)) * 100;
    text += ` (${formatTodayNumber(Math.round(pct * 100) / 100)}%)`;
  }
  return `${verb} предыдущего значения ${text}`;
}

/**
 * Title + description страницы /today/{code} — как render_today_indicator_html.
 * Вызывать только когда есть last + indicator.source.
 */
export function buildTodayIndicatorMeta({
  query,
  value,
  prevValue,
  unit,
  lastDate,
  frequency,
  source,
}) {
  const unitPart = (unit || '').trim();
  const valueText = `${formatTodayNumber(value)}${unitPart ? ` ${unitPart}` : ''}`.trim();
  const today = todayMsk();
  const stale = isTodayStale(frequency, lastDate, today);
  const lastRu = formatTodayRuDate(lastDate);
  const todayRu = formatTodayRuDate(today);
  const changePhrase = todayChangePhrase(value, prevValue, unitPart);
  const title = stale
    ? `${query} — последнее значение на ${lastRu}: ${valueText}`
    : `${query} сегодня, ${todayRu} — ${valueText}`;
  const freshFrame = stale
    ? `последнее доступное значение на ${lastRu}`
    : `данные на ${lastRu}`;
  const description = (
    `${query}${stale ? ' — последнее доступное значение' : ' на сегодня'}: `
    + `${valueText} (${freshFrame}, ${changePhrase}). Источник — ${source}. `
    + 'График, таблица последних значений и прогноз.'
  );
  return { title, description, valueText };
}
