// Круг 5, R5-C: курс на выбранный день, выгрузка курсов ЦБ в таблицу (CSV для Excel), копирование строки для документа. Чистая логика.
import { nominalFor, unitMeta } from './currencyRates';
import { unitName } from './currencyChart';

const DAY = 86_400_000;
const ms = (date) => Date.parse(`${String(date || '').slice(0, 10)}T12:00:00Z`);

/** Курс «из → в» за одну единицу на выбранный день (последняя точка не позже дня); день вне ряда: null. */
export function rateOnDate(rows, iso, { invert = false, units = 1 } = {}) {
  const points = (rows || [])
    .map((row) => ({ date: String(row?.date || '').slice(0, 10), value: Number(row?.value) }))
    .filter((p) => p.date && Number.isFinite(p.value) && p.value > 0)
    .sort((a, b) => (a.date < b.date ? -1 : 1));
  if (!points.length || !iso) return null;
  const target = ms(iso);
  if (!Number.isFinite(target) || target < ms(points[0].date) || target > ms(points[points.length - 1].date) + 3 * DAY) return null;
  let found = null;
  for (const p of points) { if (ms(p.date) <= target) found = p; else break; }
  if (!found) return null;
  const perOne = found.value / (units || 1);
  return { date: found.date, rate: invert ? 1 / perOne : perOne, first: points[0].date, last: points[points.length - 1].date };
}

/** Опорные дни для кнопок «Конец прошлого месяца», «1 число», «Неделю назад» от последней даты ряда. */
export function dateShortcuts(lastIso) {
  const base = new Date(`${String(lastIso).slice(0, 10)}T12:00:00Z`);
  if (Number.isNaN(base.getTime())) return [];
  const iso = (d) => d.toISOString().slice(0, 10);
  const y = base.getUTCFullYear();
  const m = base.getUTCMonth();
  return [
    { key: 'prevMonthEnd', iso: iso(new Date(Date.UTC(y, m, 0, 12))) },
    { key: 'monthStart', iso: iso(new Date(Date.UTC(y, m, 1, 12))) },
    { key: 'weekAgo', iso: iso(new Date(base.getTime() - 7 * DAY)) },
  ];
}

/** Строки таблицы «курсы к рублю»: валюта, код, за сколько единиц, курс, дата. */
export function rateTableRows(edges, locale = 'ru') {
  return (edges || [])
    .filter((edge) => edge.to === 'RUB' && !unitMeta(edge.from)?.crypto && edge.rate > 0)
    .map((edge) => {
      const nominal = nominalFor(edge.from, edge.rate);
      return {
        name: unitName(edge.from, locale), code: edge.from, nominal, value: edge.rate * nominal, date: String(edge.date || '').slice(0, 10),
      };
    });
}

/** Текст CSV: разделитель «;», запятая в дробях (Excel на русской раскладке открывает без мастера), BOM для кириллицы. */
export function ratesCsv(rows, locale = 'ru') {
  const head = locale === 'en' ? ['Currency', 'Code', 'Units', 'Rate, RUB', 'Date'] : ['Валюта', 'Код', 'Номинал', 'Курс, ₽', 'Дата'];
  const num = (v) => (locale === 'en' ? String(Number(v.toFixed(4))) : String(Number(v.toFixed(4))).replace('.', ','));
  const lines = rows.map((r) => [r.name, r.code, r.nominal, num(r.value), r.date].join(';'));
  return `\uFEFF${[head.join(';'), ...lines].join('\r\n')}\r\n`;
}

export function downloadText(filename, text, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand('copy');
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}
