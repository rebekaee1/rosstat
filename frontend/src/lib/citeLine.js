import { formatDate } from './format';

/** Дата обращения в виде ДД.ММ.ГГГГ (местное время читателя). */
export function formatAccessDate(date) {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/**
 * Строка «Как цитировать» (совет 19.11.2026). Тот же текст, что в SSR
 * (`backend/app/services/seo_cite.py`): человек и робот видят одно.
 * «Forecast Economy. {Название}: источник данных — {источник}, на {дата}. {адрес}».
 */
export function citeText({
  name, source, url, asOf, period, accessDate, locale,
}) {
  const en = locale === 'en';
  const tail = [];
  if (source) tail.push(en ? `data from ${source}` : `источник данных — ${source}`);
  if (period) {
    // Круг наблюдателей 20.11.2026, №2: период данных словами («данные за II кв. 2026») и дата обращения, а не код периода как дата.
    tail.push(en ? `data ${period}` : `данные ${period}`);
    const access = accessDate ? formatAccessDate(accessDate) : '';
    if (access) tail.push(en ? `accessed ${access}` : `дата обращения ${access}`);
  } else {
    const date = asOf ? formatDate(asOf, 'day', locale) : '';
    if (date && date !== '—') tail.push(en ? `as of ${date}` : `на ${date}`);
  }
  // Название с точкой на конце не даёт двух точек подряд (как в seo_cite.py).
  const clean = String(name).trim().replace(/\.+$/, '');
  const head = `Forecast Economy. ${clean}${tail.length ? `: ${tail.join(', ')}` : ''}`;
  return `${head}. ${url}`;
}

/** Адрес страницы без параметров — как canonical. */
export function citeUrl(loc = typeof window !== 'undefined' ? window.location : null) {
  if (!loc) return '';
  return `${loc.origin}${loc.pathname}`;
}
