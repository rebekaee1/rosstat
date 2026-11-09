import { isPercentUnit, NBSP } from './regionUi';

const MINUS = '−';

export function isYearsUnit(unit) {
  return /^(число лет|лет|years?)$/i.test((unit || '').trim());
}

function dec(locale) { return locale === 'en' ? '.' : ','; }

function yearsWord(abs, locale) {
  if (locale === 'en') return abs === 1 ? 'year' : 'years';
  if (!Number.isInteger(abs)) return 'года';
  const n = abs % 100;
  const d = n % 10;
  if (n > 10 && n < 20) return 'лет';
  if (d === 1) return 'год';
  if (d >= 2 && d <= 4) return 'года';
  return 'лет';
}

/** Разница a − b словами единицы: «+0,04 года», «−1,2 п. п.», «+8,3 %» (для уровней — относительная). */
export function gapText(a, b, unit, locale = 'ru', { signed = true } = {}) {
  const x = Number(a);
  const y = Number(b);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const diff = x - y;
  const abs = Math.abs(diff);
  const sign = !signed ? '' : abs < 0.005 ? '' : diff > 0 ? '+' : MINUS;
  const d = dec(locale);
  if (isYearsUnit(unit)) {
    const digits = abs < 1 ? 2 : 1;
    const n = abs.toFixed(digits).replace('.', d);
    return { diff, text: `${sign}${n}${NBSP}${yearsWord(Number(abs.toFixed(digits)), locale)}` };
  }
  if (isPercentUnit(unit)) {
    const n = abs.toFixed(1).replace('.', d);
    return { diff, text: `${sign}${n}${NBSP}${locale === 'en' ? 'p.p.' : 'п.п.'}` };
  }
  if (!y) return null;
  const pct = (diff / Math.abs(y)) * 100;
  const ap = Math.abs(pct);
  const n = (ap < 10 ? ap.toFixed(1) : String(Math.round(ap))).replace('.', d);
  return { diff, pct, text: `${sign}${n}${NBSP}%` };
}

