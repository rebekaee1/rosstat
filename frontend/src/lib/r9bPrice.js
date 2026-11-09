import { formatValue } from './format';

/** «рублей за литр» -> { sign: '₽', per: 'за литр' } */
export function splitPriceUnit(unit) {
  const u = String(unit || '');
  const m = u.match(/^(?:рублей|рубля|рубль|roubles|rubles)\s*(.*)$/i);
  if (!m) return { sign: '', per: u };
  const per = m[1]
    .replace(/килограмм(?![\p{L}])/iu, 'кг')
    .replace(/штук(?![\p{L}])/iu, 'шт.')
    .replace(/литр(?![\p{L}])/iu, 'л');
  return { sign: '₽', per };
}

export function signed(p, locale) {
  const s = formatValue(Math.abs(p), Math.abs(p) < 100 ? 1 : 0, locale);
  return `${p > 0 ? '+' : p < 0 ? '−' : ''}${s}\u00a0%`;
}

export function money(v, unit, locale) {
  if (v == null) return '';
  const { sign } = splitPriceUnit(unit);
  return `${formatValue(v, v >= 1000 ? 0 : 2, locale)}${sign ? `\u00a0${sign}` : ''}`;
}

/** Текст для цитаты: имя, цена, год назад, изменение, источник. */
export function quoteLine(it, t, locale) {
  const { per } = splitPriceUnit(it.unit);
  return t('r9b.quote', {
    name: it.short_name || it.name,
    per: per ? `, ${per}` : '',
    now: money(it.value, it.unit, locale),
    then: money(it.year_ago_value, it.unit, locale),
    pct: signed(it.yoy_pct, locale),
    month: it.period_label || '',
  });
}

export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}
