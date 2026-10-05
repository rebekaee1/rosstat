// Население человеческими числами: «28,1 млн человек», «+0,35 млн (+1,3 %)», «5-е место среди стран».
// Вместо «28 076 986 человек, +346 630,00» и «среднего за 47 лет».

/** Множитель единицы ряда: «млн чел.» -> 1e6, «тыс. человек» -> 1e3, иначе люди. */
export function peopleScale(unit) {
  const text = String(unit || '').toLowerCase();
  if (/млрд|billion/.test(text)) return 1e9;
  if (/млн|million/.test(text)) return 1e6;
  if (/тыс|thousand|ths/.test(text)) return 1e3;
  return 1;
}

/** Похож ли показатель на численность людей (единица в людях или тысячах/миллионах людей). */
export function isPeopleUnit(unit) {
  return /чел|people|persons|person/i.test(String(unit || ''));
}

const nf = (locale, digits) => new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU', {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
});

/**
 * Число людей кратко: 28 076 986 -> «28,1 млн», 812 400 -> «812 тыс.», 1,41 млрд -> «1,41 млрд».
 * Знаков столько, чтобы число читалось, но не врало точностью оценки.
 */
export function compactPeople(count, locale = 'ru') {
  const n = Math.abs(Number(count));
  if (!Number.isFinite(n)) return '—';
  const words = locale === 'en'
    ? { b: 'billion', m: 'million', k: 'thousand' }
    : { b: 'млрд', m: 'млн', k: 'тыс.' };
  const sp = String.fromCharCode(160);
  if (n >= 1e9) return `${nf(locale, 2).format(n / 1e9)}${sp}${words.b}`;
  if (n >= 1e7) return `${nf(locale, 1).format(n / 1e6)}${sp}${words.m}`;
  if (n >= 1e6) return `${nf(locale, 2).format(n / 1e6)}${sp}${words.m}`;
  if (n >= 1e4) return `${nf(locale, 0).format(n / 1e3)}${sp}${words.k}`;
  return nf(locale, 0).format(n);
}

/** Знаковая прибавка: «+0,35 млн». Ноль и «почти ноль» -> null (вызывающий пишет «без изменений»). */
export function signedPeople(delta, locale = 'ru') {
  const n = Number(delta);
  if (!Number.isFinite(n) || n === 0) return null;
  const sign = n > 0 ? '+' : '−';
  return `${sign}${compactPeople(Math.abs(n), locale)}`;
}

export function signedPercent(pct, locale = 'ru') {
  const n = Number(pct);
  if (!Number.isFinite(n)) return null;
  if (Math.abs(n) < 0.05) return '0 %';
  const sign = n > 0 ? '+' : '−';
  return `${sign}${nf(locale, 1).format(Math.abs(n))}${String.fromCharCode(160)}%`;
}

/** Порядковое «5-е» / «5th». */
export function placeOrdinal(n, locale = 'ru') {
  const num = Math.round(Number(n));
  if (!Number.isFinite(num) || num < 1) return '—';
  if (locale !== 'en') return `${num}-е`;
  const v = num % 100;
  if (v >= 11 && v <= 13) return `${num}th`;
  return `${num}${['th', 'st', 'nd', 'rd'][num % 10 > 3 ? 0 : num % 10]}`;
}

/** Место страны среди стран снимка: { rank, total } или null, если страны в снимке нет. */
export function populationRank(items, countrySlug) {
  const list = (items || []).filter((item) => Number.isFinite(Number(item?.value)));
  const mine = list.find((item) => item.country_slug === countrySlug);
  if (!mine) return null;
  const rank = 1 + list.filter((item) => Number(item.value) > Number(mine.value)).length;
  return { rank, total: list.length };
}

/**
 * Сводка по точкам ряда населения (годовые): последнее значение, прирост за год, рост за десять лет.
 * points: [{ date, value }] по возрастанию даты; unit — единица ряда.
 */
export function populationSummary(points, unit, { now = new Date() } = {}) {
  const scale = peopleScale(unit);
  const list = (points || [])
    .filter((p) => p?.date && Number.isFinite(Number(p.value)))
    .map((p) => ({ year: Number(String(p.date).slice(0, 4)), date: p.date, value: Number(p.value) * scale }))
    .sort((a, b) => a.year - b.year);
  if (!list.length) return null;
  const last = list[list.length - 1];
  const prev = list.length > 1 ? list[list.length - 2] : null;
  const decade = list.find((p) => p.year === last.year - 10) || null;
  return {
    year: last.year,
    value: last.value,
    // Значения за текущий и будущие годы — оценка, а не измерение.
    estimate: last.year >= now.getUTCFullYear(),
    delta: prev ? last.value - prev.value : null,
    deltaPct: prev && prev.value ? ((last.value / prev.value) - 1) * 100 : null,
    decadePct: decade && decade.value ? ((last.value / decade.value) - 1) * 100 : null,
  };
}
