// Недельные цены на топливо по региону (ЕМИСС 37426, с 2022 года; 18.11.2026).
// Люди спрашивают цену «на 01.01.2026»: Росстат записывает цену раз в неделю, поэтому на выбранный день
// показываем последнюю запись не позже него. Отдельного адреса на дату нет: дата выбирается на странице.
import { NBSP } from './regionUi';

/** Точка на день `iso` (YYYY-MM-DD): последняя запись не позже дня; раньше первой — первая; пусто — последняя. */
export function pointOn(series, iso) {
  if (!series?.length) return null;
  if (!iso) return series[series.length - 1];
  let best = null;
  for (const p of series) {
    if (p.date <= iso) best = p;
    else break;
  }
  return best || series[0];
}

/** «75,83 ₽» — недельная цена с копейками: от недели к неделе она меняется на копейки. */
export function kopText(value, locale = 'ru') {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${n}${NBSP}₽`;
}

/** Строки таблицы: новые сверху, с ценой России на тот же день (если есть). */
export function weeklyRows(series, russia) {
  const rf = new Map((russia || []).map((p) => [p.date, p.value]));
  return [...(series || [])].reverse().map((p) => ({ ...p, russia: rf.has(p.date) ? rf.get(p.date) : null }));
}
