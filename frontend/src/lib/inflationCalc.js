/**
 * Чистая математика калькулятора инфляции.
 * Россия: месячный ИПЦ (к предыдущему месяцу, 100 = без изменений).
 * Мир: годовое изменение потребительских цен (HICP/CPI YoY, %).
 */

export const RUSSIA_SLUG = 'russia';
export const HICP_CONCEPT = 'hicp-index';
export const RUSSIA_SOURCE = 'Росстат';

export function isRussiaCountry(slug) {
  return !slug || slug === RUSSIA_SLUG;
}

export function yearOf(dateStr) {
  return Number(String(dateStr || '').slice(0, 4));
}

export function toDateStr(year, month = 1) {
  return `${year}-${String(month).padStart(2, '0')}-01`;
}

export function computeCumulative(points, fromDate, toDate) {
  let product = 1;
  const series = [];
  let monthIdx = 0;

  for (const p of points) {
    if (p.date < fromDate || p.date > toDate) continue;
    product *= p.value / 100;
    monthIdx++;
    series.push({ date: p.date, product, monthIdx });
  }

  return { product, series, months: monthIdx };
}

export function buildPurchasingPowerSeries(amount, cpiPoints, fromDate, toDate) {
  const series = [];
  let cumProduct = 1;
  let prevYear = null;

  for (const p of cpiPoints) {
    if (p.date < fromDate || p.date > toDate) continue;
    cumProduct *= p.value / 100;
    const year = yearOf(p.date);

    series.push({
      date: p.date,
      purchasing: Math.round(amount / cumProduct),
      equivalent: Math.round(amount * cumProduct),
      year,
      isJanuary: prevYear !== year,
    });
    prevYear = year;
  }

  return series;
}

export function computeYearlyBreakdown(cpiPoints, fromDate, toDate, amount) {
  const yearBuckets = new Map();

  for (const p of cpiPoints) {
    if (p.date < fromDate || p.date > toDate) continue;
    const yr = yearOf(p.date);
    if (!yearBuckets.has(yr)) yearBuckets.set(yr, []);
    yearBuckets.get(yr).push(p.value);
  }

  const breakdown = [];
  let runningProduct = 1;
  let peakRate = -Infinity;
  let peakIdx = 0;
  let troughRate = Infinity;
  let troughIdx = 0;

  const sortedYears = [...yearBuckets.keys()].sort((a, b) => a - b);

  for (let i = 0; i < sortedYears.length; i++) {
    const year = sortedYears[i];
    const values = yearBuckets.get(year);

    let yearProduct = 1;
    for (const v of values) yearProduct *= v / 100;
    runningProduct *= yearProduct;

    const annualRate = (yearProduct - 1) * 100;

    if (annualRate > peakRate) { peakRate = annualRate; peakIdx = i; }
    if (annualRate < troughRate) { troughRate = annualRate; troughIdx = i; }

    breakdown.push({
      year,
      annualRate,
      months: values.length,
      cumulativeRate: (runningProduct - 1) * 100,
      purchasingPower: Math.round(amount / runningProduct),
      equivalent: Math.round(amount * runningProduct),
    });
  }

  if (breakdown.length) {
    breakdown[peakIdx].isPeak = true;
    breakdown[troughIdx].isTrough = true;
  }

  const peakYear = breakdown.length
    ? { year: breakdown[peakIdx].year, rate: peakRate }
    : null;
  const troughYear = breakdown.length
    ? { year: breakdown[troughIdx].year, rate: troughRate }
    : null;

  return { breakdown, peakYear, troughYear };
}

/** Последняя точка каждого календарного года — годовой уровень индекса. */
export function lastIndexByYear(points) {
  const map = new Map();
  for (const p of points || []) {
    if (p?.value == null || !Number.isFinite(Number(p.value))) continue;
    const y = yearOf(p.date);
    if (!Number.isFinite(y)) continue;
    map.set(y, { date: p.date, value: Number(p.value) });
  }
  return map;
}

/**
 * Годовое изменение из ряда индекса (HICP 2015=100 или национальный CPI).
 * YoY года t = I_t / I_{t-1} − 1, в процентах. Первый год ряда не даёт YoY.
 */
export function annualYoyFromIndexPoints(points) {
  const byYear = lastIndexByYear(points);
  const years = [...byYear.keys()].sort((a, b) => a - b);
  const out = [];
  for (let i = 1; i < years.length; i++) {
    const prev = byYear.get(years[i - 1]);
    const curr = byYear.get(years[i]);
    if (!prev?.value) continue;
    out.push({
      date: curr.date,
      year: years[i],
      value: (curr.value / prev.value - 1) * 100,
    });
  }
  return out;
}

function markPeaks(breakdown) {
  if (!breakdown.length) {
    return { breakdown, peakYear: null, troughYear: null };
  }
  let peakIdx = 0;
  let troughIdx = 0;
  for (let i = 1; i < breakdown.length; i++) {
    if (breakdown[i].annualRate > breakdown[peakIdx].annualRate) peakIdx = i;
    if (breakdown[i].annualRate < breakdown[troughIdx].annualRate) troughIdx = i;
  }
  const next = breakdown.map((row, i) => ({
    ...row,
    isPeak: i === peakIdx,
    isTrough: i === troughIdx,
  }));
  return {
    breakdown: next,
    peakYear: { year: next[peakIdx].year, rate: next[peakIdx].annualRate },
    troughYear: { year: next[troughIdx].year, rate: next[troughIdx].annualRate },
  };
}

/**
 * Накопленный множитель = ∏(1 + yoy/100) по годам [fromYear, toYear].
 * Пропуски в середине не заполняются (не экстраполируем).
 */
export function computeFromAnnualYoy(yoyPoints, fromYear, toYear, amount) {
  const byYear = new Map();
  for (const p of yoyPoints || []) {
    if (p?.value == null || !Number.isFinite(Number(p.value))) continue;
    const y = p.year != null ? Number(p.year) : yearOf(p.date);
    if (!Number.isFinite(y)) continue;
    byYear.set(y, { date: p.date, value: Number(p.value) });
  }

  const years = [...byYear.keys()].sort((a, b) => a - b);
  if (!years.length) {
    return {
      product: 1,
      months: 0,
      series: [],
      breakdown: [],
      peakYear: null,
      troughYear: null,
      effectiveFrom: fromYear,
      effectiveTo: toYear,
      clamped: false,
      minYear: fromYear,
      maxYear: toYear,
    };
  }

  const minYear = years[0];
  const maxYear = years[years.length - 1];
  const effectiveFrom = Math.max(fromYear, minYear);
  const effectiveTo = Math.min(toYear, maxYear);
  const clamped = effectiveFrom !== fromYear || effectiveTo !== toYear;

  if (effectiveFrom > effectiveTo) {
    return {
      product: 1,
      months: 0,
      series: [],
      breakdown: [],
      peakYear: null,
      troughYear: null,
      effectiveFrom,
      effectiveTo,
      clamped: true,
      minYear,
      maxYear,
    };
  }

  let product = 1;
  const breakdown = [];
  const series = [];

  for (let y = effectiveFrom; y <= effectiveTo; y++) {
    const pt = byYear.get(y);
    if (!pt) continue;
    product *= 1 + pt.value / 100;
    breakdown.push({
      year: y,
      annualRate: pt.value,
      months: 12,
      cumulativeRate: (product - 1) * 100,
      purchasingPower: Math.round(amount / product),
      equivalent: Math.round(amount * product),
    });
    series.push({
      date: pt.date || toDateStr(y, 12),
      purchasing: Math.round(amount / product),
      equivalent: Math.round(amount * product),
      year: y,
      isJanuary: true,
    });
  }

  const peaks = markPeaks(breakdown);
  return {
    product,
    months: breakdown.length * 12,
    series,
    ...peaks,
    effectiveFrom,
    effectiveTo,
    clamped,
    minYear,
    maxYear,
  };
}

export function emptyRussiaResult(amount, effectiveFrom, effectiveTo, clamped) {
  return {
    equivalent: amount,
    purchasing: amount,
    totalInflation: 0,
    avgAnnual: 0,
    multiplier: 1,
    series: [],
    months: 0,
    food: 0,
    nonfood: 0,
    services: 0,
    yearlyBreakdown: [],
    peakYear: null,
    troughYear: null,
    doublingYears: null,
    effectiveFrom,
    effectiveTo,
    clamped,
    hasCategories: true,
    kind: 'russia',
  };
}

export function buildRussiaResult({
  amount, fromYear, toYear, cpiAll, cpiFood, cpiNonfood, cpiServices,
  minYear, lastAvailableYear, lastAvailableDate,
}) {
  const effectiveFrom = Math.max(fromYear, minYear);
  const effectiveTo = Math.min(toYear, lastAvailableYear);
  const clamped = effectiveFrom !== fromYear || effectiveTo !== toYear;
  if (effectiveFrom > effectiveTo) {
    return emptyRussiaResult(amount, effectiveFrom, effectiveTo, clamped);
  }

  const fromDate = toDateStr(effectiveFrom, 1);
  const toDate = lastAvailableDate && effectiveTo === lastAvailableYear
    ? lastAvailableDate
    : toDateStr(effectiveTo, 12);

  const { product, months } = computeCumulative(cpiAll, fromDate, toDate);
  const series = buildPurchasingPowerSeries(amount, cpiAll, fromDate, toDate);
  const totalInflation = (product - 1) * 100;
  const years = months / 12;
  const avgAnnual = years > 0 ? (product ** (1 / years) - 1) * 100 : 0;
  const foodCum = computeCumulative(cpiFood, fromDate, toDate);
  const nonfoodCum = computeCumulative(cpiNonfood, fromDate, toDate);
  const servicesCum = computeCumulative(cpiServices, fromDate, toDate);
  const { breakdown, peakYear, troughYear } = computeYearlyBreakdown(
    cpiAll, fromDate, toDate, amount,
  );
  const doublingYears = avgAnnual > 0.5 ? Math.round(72 / avgAnnual) : null;

  return {
    equivalent: Math.round(amount * product),
    purchasing: Math.round(amount / product),
    totalInflation,
    avgAnnual,
    multiplier: product,
    series,
    months,
    food: (foodCum.product - 1) * 100,
    nonfood: (nonfoodCum.product - 1) * 100,
    services: (servicesCum.product - 1) * 100,
    yearlyBreakdown: breakdown,
    peakYear,
    troughYear,
    doublingYears,
    effectiveFrom,
    effectiveTo,
    clamped,
    periodFrom: fromDate,
    periodTo: toDate,
    hasCategories: true,
    kind: 'russia',
  };
}

export function buildWorldResult({
  amount, fromYear, toYear, indexPoints, seriesStartYear,
}) {
  const yoyPoints = annualYoyFromIndexPoints(indexPoints);
  const computed = computeFromAnnualYoy(yoyPoints, fromYear, toYear, amount);
  const yearsCount = computed.months / 12;
  const avgAnnual = yearsCount > 0
    ? (computed.product ** (1 / yearsCount) - 1) * 100
    : 0;
  const doublingYears = avgAnnual > 0.5 ? Math.round(72 / avgAnnual) : null;
  const lastPoint = computed.series[computed.series.length - 1];
  const firstPoint = computed.series[0];

  return {
    equivalent: Math.round(amount * computed.product),
    purchasing: Math.round(amount / computed.product),
    totalInflation: (computed.product - 1) * 100,
    avgAnnual,
    multiplier: computed.product,
    series: computed.series,
    months: computed.months,
    food: 0,
    nonfood: 0,
    services: 0,
    yearlyBreakdown: computed.breakdown,
    peakYear: computed.peakYear,
    troughYear: computed.troughYear,
    doublingYears,
    effectiveFrom: computed.effectiveFrom,
    effectiveTo: computed.effectiveTo,
    clamped: computed.clamped,
    periodFrom: firstPoint?.date || toDateStr(computed.effectiveFrom, 1),
    periodTo: lastPoint?.date || toDateStr(computed.effectiveTo, 12),
    hasCategories: false,
    kind: 'world',
    seriesStartYear: seriesStartYear ?? (indexPoints?.length
      ? yearOf(indexPoints[0].date)
      : computed.minYear),
    minYear: computed.minYear,
    maxYear: computed.maxYear,
  };
}

/**
 * Страны с инфляционным рядом из /world/compare/catalog.
 * Россия в world-каталоге отсутствует — её подмешивает UI.
 */
export function inflationCountriesFromCatalog(catalog, { locale = 'ru' } = {}) {
  const items = catalog?.items || [];
  const map = new Map();
  for (const item of items) {
    if (item.concept_slug !== HICP_CONCEPT) continue;
    if (!item.country_slug || item.country_slug === RUSSIA_SLUG) continue;
    if (map.has(item.country_slug)) continue;
    map.set(item.country_slug, {
      slug: item.country_slug,
      name: item.country_name,
      indicatorCode: item.indicator_code,
    });
  }
  const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
  return [...map.values()].sort((a, b) => collator.compare(a.name || '', b.name || ''));
}

export function formatCalcAmount(n, { withRuble = true } = {}) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(Math.round(n));
  const sign = n < 0 ? '-' : '';
  const body = sign + abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
  return withRuble ? `${body}\u00A0₽` : body;
}
