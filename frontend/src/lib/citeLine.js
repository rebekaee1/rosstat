import { formatDate } from './format';

/**
 * Строка «Как цитировать» (совет 19.11.2026). Тот же текст, что в SSR
 * (`backend/app/services/seo_cite.py`): человек и робот видят одно.
 * «Forecast Economy. {Название}: источник данных — {источник}, на {дата}. {адрес}».
 */
export function citeText({ name, source, url, asOf, locale }) {
  const en = locale === 'en';
  const tail = [];
  if (source) tail.push(en ? `data from ${source}` : `источник данных — ${source}`);
  const date = asOf ? formatDate(asOf, 'day', locale) : '';
  if (date && date !== '—') tail.push(en ? `as of ${date}` : `на ${date}`);
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
