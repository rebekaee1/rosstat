/**
 * English twins for bespoke view-mode description / methodology blocks.
 *
 * Plain strings only — keeps RU JSX formula components untouched.
 * Symbols such as CPIᵢ are fine in methodology text.
 * Wire-up belongs to the locale layer; this module is content-only.
 */

const CPI_SLICE = {
  cpi: {
    prices: 'consumer prices',
    pricesGen: 'consumer prices',
    ipcMonthly: 'monthly CPI readings',
    ipcMonthlyNom: 'monthly CPI readings',
    ipcFoot: 'consumer price index',
    indexLevel: 'the overall consumer price level',
    weeklyBasket: 'the full consumer basket',
  },
  'cpi-food': {
    prices: 'food prices',
    pricesGen: 'food prices',
    ipcMonthly: 'monthly food CPI readings',
    ipcMonthlyNom: 'monthly food CPI readings',
    ipcFoot: 'food consumer price index',
    indexLevel: 'the food price level',
    weeklyBasket: 'food items in the basket',
  },
  'cpi-nonfood': {
    prices: 'non-food goods prices',
    pricesGen: 'non-food goods prices',
    ipcMonthly: 'monthly non-food CPI readings',
    ipcMonthlyNom: 'monthly non-food CPI readings',
    ipcFoot: 'non-food consumer price index',
    indexLevel: 'the non-food goods price level',
    weeklyBasket: 'non-food items in the basket',
  },
  'cpi-services': {
    prices: 'services prices',
    pricesGen: 'services prices',
    ipcMonthly: 'monthly services CPI readings',
    ipcMonthlyNom: 'monthly services CPI readings',
    ipcFoot: 'services consumer price index',
    indexLevel: 'the services price level',
    weeklyBasket: 'services items in the weekly basket',
  },
};

function cpiSlice(code) {
  return CPI_SLICE[code] ?? CPI_SLICE.cpi;
}

export function getCpiChartTitleEn(chartMode, code, urlMode = null) {
  const s = cpiSlice(code);
  const mode = urlMode ?? chartMode;
  if (mode === 'period-weekly') {
    return `Month-to-date growth — ${s.prices} (%)`;
  }
  switch (chartMode) {
    case 'inflation': {
      const period = mode === 'inflation-quarter' ? ' (by quarter)'
        : mode === 'inflation-year' ? ' (by year)' : '';
      return code === 'cpi'
        ? `Inflation vs same period previous year (all goods and services, %)${period}`
        : `Inflation vs same period previous year (${s.prices}, %)${period}`;
    }
    case 'quarterly':
      return `Quarterly inflation — ${s.prices} (%)`;
    case 'annual':
      return `Year-on-year change (Dec–Dec) — ${s.prices} (%)`;
    case 'period-monthly':
      return `Month growth from weekly readings — ${s.prices} (%)`;
    case 'yoy':
      return `Year on year — ${s.prices} (%)`;
    case 'qoq':
      return `Quarter on quarter — ${s.prices} (%)`;
    case 'weekly':
      return mode === 'period-weekly'
        ? `Month-to-date growth — ${s.prices} (%)`
        : `Week-on-week change in ${s.pricesGen} (%)`;
    case 'index': {
      const period = mode === 'index-quarterly' ? ' at quarter-end'
        : mode === 'index-annual' ? ' at year-end' : '';
      return code === 'cpi'
        ? `Cumulative CPI${period} (level, 2000 = 100)`
        : `Cumulative index${period} — ${s.prices} (2000 = 100)`;
    }
    case 'cpi':
      return `Month-on-month change in ${s.pricesGen} (%)`;
    default:
      return `${s.prices} dynamics (%)`;
  }
}

export function getCpiTableTitleEn(chartMode, code, urlMode = null) {
  const s = cpiSlice(code);
  const mode = urlMode ?? chartMode;
  if (mode === 'period-weekly') {
    return `Historical data — month-to-date growth (${s.pricesGen})`;
  }
  switch (chartMode) {
    case 'inflation': {
      const period = mode === 'inflation-quarter' ? ' (by quarter)'
        : mode === 'inflation-year' ? ' (by year)' : '';
      return code === 'cpi'
        ? `Historical data — inflation vs same period previous year (all goods and services)${period}`
        : `Historical data — inflation vs same period previous year (${s.prices})${period}`;
    }
    case 'quarterly':
      return `Historical data — quarterly inflation (${s.prices})`;
    case 'annual':
      return `Historical data — year-on-year change, Dec–Dec (${s.prices})`;
    case 'period-monthly':
      return `Historical data — month growth from weekly readings (${s.prices})`;
    case 'yoy':
      return `Historical data — year on year (${s.prices})`;
    case 'qoq':
      return `Historical data — quarter on quarter (${s.prices})`;
    case 'weekly':
      return mode === 'period-weekly'
        ? `Historical data — month-to-date growth (${s.pricesGen})`
        : `Historical data — weekly change (${s.pricesGen})`;
    case 'index': {
      const period = mode === 'index-quarterly' ? ' at quarter-end'
        : mode === 'index-annual' ? ' at year-end' : '';
      return code === 'cpi'
        ? `Historical data — cumulative CPI${period} (2000 = 100)`
        : `Historical data — cumulative index${period} (${s.prices}, 2000 = 100)`;
    }
    case 'cpi':
      return `Historical data — month-on-month (${s.pricesGen})`;
    default:
      return 'Historical data';
  }
}

const ANNUAL_INFLATION_FORMULA =
  '∏ᵢ₌₁¹² (CPIᵢ / 100) × 100 − 100';

function inflationFootnote(ipcFoot) {
  return `CPIᵢ — ${ipcFoot} for month i (% vs previous month).`;
}

function buildInflation(code, period = null) {
  const s = cpiSlice(code);
  if (period === 'quarter') {
    return {
      description:
        `Inflation versus the same quarter a year earlier: by how many percent ${s.prices} `
        + 'changed relative to that quarter twelve months ago. The monthly year-on-year series '
        + 'is shown at quarterly frequency — the reading at each quarter-end.',
      methodology:
        `Formula (quarter-end): ${ANNUAL_INFLATION_FORMULA}. ${inflationFootnote(s.ipcFoot)}`,
    };
  }
  if (period === 'year') {
    return {
      description:
        `Calendar-year inflation: by how many percent ${s.prices} changed by year-end `
        + 'versus the previous year-end (December to December). One point per completed year.',
      methodology:
        `Formula (December to December): ${ANNUAL_INFLATION_FORMULA}. ${inflationFootnote(s.ipcFoot)}`,
    };
  }
  return {
    description:
      `Inflation versus the same period a year earlier: by how many percent ${s.prices} `
      + 'changed relative to the same month last year. Computed as the product of twelve '
      + `consecutive ${s.ipcMonthly} divided by 100, minus 100%.`,
    methodology:
      `Formula: ${ANNUAL_INFLATION_FORMULA}. ${inflationFootnote(s.ipcFoot)}`,
  };
}

const WEEKLY = {
  description:
    'Weekly CPI — week-on-week change in consumer prices from Rosstat. '
    + 'Published weekly as a high-frequency inflation gauge.',
  methodology:
    'Source: Rosstat weekly consumer price estimates for the full basket. '
    + 'A value of 100 means no price change.',
};

const WEEKLY_FOOD = {
  description:
    'Weekly change in food prices — a high-frequency cut of Rosstat’s weekly basket, '
    + 'comparable with the monthly food CPI.',
  methodology:
    'Weighted average of weekly indices for food items (weights from Rosstat household '
    + 'expenditure structure). Rosstat does not publish a separate official weekly food bulletin; '
    + 'headline weekly estimates cover the full basket.',
};

const WEEKLY_NONFOOD = {
  description:
    'Weekly change in non-food goods prices — a high-frequency cut of Rosstat’s weekly basket, '
    + 'comparable with the monthly non-food CPI.',
  methodology:
    'Weighted average of weekly indices for non-food items (weights from Rosstat household '
    + 'expenditure structure). No separate official weekly bulletin for this group alone.',
};

const WEEKLY_SERVICES = {
  description:
    'Weekly change in services prices — a high-frequency cut of services items in Rosstat’s '
    + 'weekly basket, comparable with the monthly services CPI.',
  methodology:
    'Weighted average of weekly services indices (weights from Rosstat household expenditure '
    + 'structure). No separate official weekly bulletin for services alone.',
};

const WEEKLY_BY_CODE = {
  cpi: WEEKLY,
  'cpi-food': WEEKLY_FOOD,
  'cpi-nonfood': WEEKLY_NONFOOD,
  'cpi-services': WEEKLY_SERVICES,
};

function buildStepMonthly(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Month-on-month change — by how many percent ${s.prices} moved versus the previous `
      + 'month. Positive values are increases; negative values are declines.',
    methodology:
      `Formula: CPIᵢ − 100, where CPIᵢ is the ${s.ipcFoot} for month i `
      + `as % of the previous month. Source: Rosstat ${s.ipcMonthlyNom}.`,
  };
}

function buildStepWeekly(code) {
  const s = cpiSlice(code);
  const weekly = WEEKLY_BY_CODE[code] ?? WEEKLY;
  return {
    description:
      `Week-on-week change — by how many percent ${s.prices} moved versus the previous week. `
      + 'Positive values are increases; negative values are declines.',
    methodology: weekly.methodology,
  };
}

function buildPeriodWeekly(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Cumulative change in ${s.pricesGen} since the start of the calendar month `
      + 'as of each reporting week. Differs from week-on-week, which shows only the latest week.',
    methodology:
      'Formula on week t of month M: (∏ weekly CPIᵢ / 100) × 100 − 100, '
      + 'where i runs over all weeks of month M from the first through t. '
      + 'Source: Rosstat weekly estimates.',
  };
}

function buildPeriodMonthly(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Growth in ${s.pricesGen} over the calendar month from operational weekly estimates: `
      + 'all weekly indices belonging to that month are multiplied. May differ slightly from '
      + 'the official monthly index (month-on-month mode), which is published separately.',
    methodology:
      'Formula for month M: (∏ weekly CPIᵢ / 100) × 100 − 100, where i covers all '
      + `weeks of calendar month M for the “${s.prices}” slice. The point is dated to the `
      + 'last week of the month.',
  };
}

function buildYoy(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Year-on-year change — by how many percent ${s.prices} moved versus the previous year. `
      + 'Positive values are increases; negative values are declines. Computed on calendar years '
      + '— December to December, one point per completed year.',
    methodology:
      `Formula (calendar year, January–December): ${ANNUAL_INFLATION_FORMULA}. `
      + `CPIᵢ — ${s.ipcFoot} for month i of the year (% vs previous month). `
      + 'Forecast uses the same product on monthly forecast points.',
  };
}

function buildQoq(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Quarter-on-quarter change — by how many percent ${s.prices} moved versus the previous `
      + 'quarter. Positive values are increases; negative values are declines.',
    methodology:
      'Formula at quarter ends: (LEVEL end Q / LEVEL end Q−1 − 1) × 100, '
      + `where LEVEL is the cumulative price index built from ${s.ipcMonthly}.`,
  };
}

function buildIndex(code, bucket = null) {
  const s = cpiSlice(code);
  const intro = code === 'cpi'
    ? 'The cumulative consumer price index — the overall consumer price level relative to the base.'
    : `The cumulative index reflects ${s.indexLevel} relative to the base.`;
  if (bucket) {
    const periodWord = bucket === 'year' ? 'year' : 'quarter';
    const periodAdj = bucket === 'year' ? 'annual' : 'quarterly';
    return {
      description:
        `${intro} ${periodAdj.charAt(0).toUpperCase() + periodAdj.slice(1)} view: one point is the `
        + `cumulative index at the end of each completed ${periodWord}. Base is January 2000 `
        + `(100 = the January 2000 price level). Useful for comparing the level of ${s.pricesGen} `
        + `across ${bucket === 'year' ? 'years' : 'quarters'} without monthly noise.`,
      methodology:
        `Monthly cumulative index INDEXₜ = 100 × (CPI₁/100) × … × (CPIₜ/100), where CPIᵢ is the `
        + `monthly ${s.ipcFoot} vs the previous month. Then take the last value of each completed `
        + `${periodWord}. History covers the full series from 1991; readings before January 2000 `
        + 'are well below 100 — prices then were far below the base. Forecast continues the '
        + `cumulative curve from the monthly forecast to each completed ${periodWord} on the horizon.`,
    };
  }
  return {
    description:
      `${intro} Base is January 2000 (100 = the January 2000 price level). Each value is the `
      + `chained product of ${s.ipcMonthly} onto that base. The curve shows how ${s.prices} `
      + 'have evolved since 1991.',
    methodology:
      `Formula: INDEXₜ = 100 × (CPI₁/100) × (CPI₂/100) × … × (CPIₜ/100), where CPIᵢ is the `
      + `monthly ${s.ipcFoot} vs the previous month. History from 1991; pre-2000 readings are `
      + 'well below 100. Forecast continues the cumulative curve from the 12-month forecast of '
      + `${s.ipcMonthly}.`,
  };
}

export function getCpiViewModeContentEn({
  chartMode,
  safeViewMode,
  code = 'cpi',
}) {
  if (chartMode === 'inflation') {
    if (safeViewMode === 'inflation-quarter') return buildInflation(code, 'quarter');
    if (safeViewMode === 'inflation-year') return buildInflation(code, 'year');
    return buildInflation(code);
  }
  if (safeViewMode === 'period-weekly') return buildPeriodWeekly(code);
  if (safeViewMode === 'period-monthly') return buildPeriodMonthly(code);
  if (safeViewMode === 'step-weekly') return buildStepWeekly(code);
  if (safeViewMode === 'step-monthly') return buildStepMonthly(code);
  if (safeViewMode === 'yoy') return buildYoy(code);
  if (safeViewMode === 'qoq') return buildQoq(code);
  if (safeViewMode === 'index') return buildIndex(code);
  if (safeViewMode === 'index-quarterly') return buildIndex(code, 'quarter');
  if (safeViewMode === 'index-annual') return buildIndex(code, 'year');
  if (chartMode === 'weekly') return WEEKLY_BY_CODE[code] ?? WEEKLY;
  if (chartMode === 'cpi') return buildStepMonthly(code);
  return { description: '', methodology: '' };
}

/* ---- Housing ---- */

const HOUSING_SLICE = {
  'housing-price-primary': {
    marketShort: 'primary housing',
    marketGen: 'the primary housing market',
    marketWhat: 'new-build apartments',
    sample: 'developers and shared-construction contracts',
    drivers: 'construction costs, project finance, subsidised mortgages and the pace of housing completions',
  },
  'housing-price-secondary': {
    marketShort: 'secondary housing',
    marketGen: 'the secondary housing market',
    marketWhat: 'resale apartments',
    sample: 'household-to-household transactions and realtor observations',
    drivers: 'secondary supply, mortgage conditions, demand shifting from new-builds, and household incomes',
  },
};

function housingSlice(code) {
  return HOUSING_SLICE[code] ?? HOUSING_SLICE['housing-price-primary'];
}

function housingIndexPeriodSuffix(safeViewMode) {
  return safeViewMode === 'index-annual' ? ' at year-end' : '';
}

export function getHousingChartTitleEn(chartMode, code, safeViewMode) {
  const s = housingSlice(code);
  switch (chartMode) {
    case 'yoy':
      return `Vs same period previous year — ${s.marketShort} (%)`;
    case 'annual':
      return `Year on year — ${s.marketShort} (%)`;
    case 'qoq':
      return `Quarter on quarter — ${s.marketShort} (%)`;
    case 'index':
      return `Price index — ${s.marketShort} (2010 = 100)${housingIndexPeriodSuffix(safeViewMode)}`;
    default:
      return `Price dynamics — ${s.marketShort}`;
  }
}

export function getHousingTableTitleEn(chartMode, code, safeViewMode) {
  const s = housingSlice(code);
  switch (chartMode) {
    case 'yoy':
      return `Historical data — vs same period previous year (${s.marketGen})`;
    case 'annual':
      return `Historical data — year on year by calendar year (${s.marketGen})`;
    case 'qoq':
      return `Historical data — quarter on quarter (${s.marketGen})`;
    case 'index':
      return safeViewMode === 'index-annual'
        ? `Historical data — index at year-end (${s.marketWhat}, 2010 = 100)`
        : `Historical data — index (${s.marketWhat}, 2010 = 100)`;
    default:
      return `Historical data — ${s.marketGen}`;
  }
}

function housingYoy(code) {
  const s = housingSlice(code);
  return {
    description:
      `Pace of change in prices of ${s.marketWhat} versus the same quarter a year earlier, `
      + 'in percent. Four points a year — each quarter compared with the matching quarter '
      + 'twelve months before.',
    methodology:
      'Mode “vs same period previous year”: how much the quarterly price index for '
      + `${s.marketGen} changed relative to the same quarter last year. Built from the `
      + 'cumulative index with base 2010 = 100, updated quarterly by Rosstat. Positive '
      + 'values are price increases; negative values are declines.',
  };
}

function housingAnnual(code) {
  const s = housingSlice(code);
  return {
    description:
      `Calendar-year change in prices of ${s.marketWhat}: the year-end price level versus `
      + 'the previous year-end, in percent. One point per completed year.',
    methodology:
      'Mode “period-on-period — year on year”: annual price growth for '
      + `${s.marketGen}, computed as the year-end index divided by the previous year-end. `
      + 'Unlike the quarterly same-period comparison (four points a year), this view has '
      + 'one point per year. Positive values are increases; negative values are declines.',
  };
}

function housingQoq(code) {
  const s = housingSlice(code);
  return {
    description:
      `Pace of change in prices of ${s.marketWhat} versus the previous quarter `
      + '(quarter on quarter), in percent.',
    methodology:
      'Mode “period-on-period — quarter on quarter”: growth versus the immediately preceding '
      + `quarter. Rosstat’s quarterly growth rates for ${s.marketGen} are used to rebuild the `
      + `quarterly index. Sample: ${s.sample}. The chart shows the reconstructed quarterly path `
      + 'aligned with the official publication.',
  };
}

function housingIndex(code, safeViewMode) {
  const s = housingSlice(code);
  const primaryExtra = code === 'housing-price-primary'
    ? ' Coverage includes shared-construction contracts for new builds; assignments and early-stage off-plan deals are outside the official sample.'
    : ' Reflects transactions in the existing housing stock, not developer list prices.';
  if (safeViewMode === 'index-annual') {
    return {
      description:
        `Price level for ${s.marketWhat} at each year-end on base 2010 = 100. `
        + 'The quarterly series is thinned to annual frequency: the last quarter of each year, '
        + 'convenient for long-run comparisons.',
      methodology:
        'Mode “Index — by year”: quarterly price level on base 2010 = 100, shown as the '
        + `year-end (final quarter) reading. Rosstat weights observations by region and dwelling characteristics.${primaryExtra} `
        + `Drivers of the level include ${s.drivers}.`,
    };
  }
  return {
    description:
      `Cumulative price index for ${s.marketWhat} with 2010 = 100: `
      + 'shows how many times the price level has changed since the base year.',
    methodology:
      'Mode “Index”: quarterly price level on base 2010 = 100. '
      + 'Rosstat weights observations by region and dwelling characteristics; '
      + `the historical series from 1998 uses reconstructed archival figures.${primaryExtra} `
      + `Drivers of the level include ${s.drivers}.`,
  };
}

export function getHousingViewModeContentEn({ chartMode, safeViewMode, code = 'housing-price-primary' }) {
  if (chartMode === 'yoy') return housingYoy(code);
  if (chartMode === 'annual') return housingAnnual(code);
  if (chartMode === 'qoq') return housingQoq(code);
  if (chartMode === 'index') return housingIndex(code, safeViewMode);
  return { description: '', methodology: '' };
}

/* ---- PPI ---- */

function ppiIndexPeriodSuffix(safeViewMode) {
  if (safeViewMode === 'index-quarterly') return ' at quarter-end';
  if (safeViewMode === 'index-annual') return ' at year-end';
  return '';
}

function ppiYoyPeriodSuffix(safeViewMode) {
  if (safeViewMode === 'yoy-quarter') return ' (by quarter)';
  if (safeViewMode === 'yoy-year') return ' (by year)';
  return '';
}

export function getPpiChartTitleEn(chartMode, safeViewMode) {
  switch (chartMode) {
    case 'yoy':
      return `Inflation vs same period previous year — producer prices (%)${ppiYoyPeriodSuffix(safeViewMode)}`;
    case 'mom':
      return 'Month on month — producer price index (%)';
    case 'qoq':
      return 'Quarter on quarter — producer price index (%)';
    case 'annual':
      return 'Year-on-year change — producer prices (%)';
    case 'index':
      return `Producer price index (2010 = 100)${ppiIndexPeriodSuffix(safeViewMode)}`;
    default:
      return 'Producer price index dynamics';
  }
}

export function getPpiTableTitleEn(chartMode, safeViewMode) {
  switch (chartMode) {
    case 'yoy':
      return `Historical data — inflation vs same period previous year (%)${ppiYoyPeriodSuffix(safeViewMode)}`;
    case 'mom':
      return 'Historical data — month on month (%)';
    case 'qoq':
      return 'Historical data — quarter on quarter (%)';
    case 'annual':
      return 'Historical data — year-on-year change (%)';
    case 'index': {
      if (safeViewMode === 'index-quarterly') return 'Historical data — index at quarter-end';
      if (safeViewMode === 'index-annual') return 'Historical data — index at year-end';
      return 'Historical data — index (2010 = 100)';
    }
    default:
      return 'Historical data — PPI';
  }
}

function ppiYoy() {
  return {
    description:
      'Producer-price inflation versus the same period a year earlier: by how many percent '
      + 'wholesale prices of industrial products changed relative to the same month last year. '
      + 'The reading is recomputed every month, so the line shows the current annual pace on '
      + 'each date, not a calendar-year total.',
    methodology:
      'Percent change in industrial producer prices versus the same month twelve months earlier. '
      + 'Monthly series. Source: Rosstat. Covers mining, manufacturing, energy and water supply.',
  };
}

function ppiYoyQuarter() {
  return {
    description:
      'Producer-price inflation versus the same quarter a year earlier: by how many percent '
      + 'wholesale prices changed relative to that quarter twelve months ago. The monthly '
      + 'year-on-year series is shown at quarterly frequency — the reading at each quarter-end.',
    methodology:
      'Percent change in industrial producer prices versus the same quarter a year earlier. '
      + 'Takes the last month of each completed quarter from the monthly year-on-year path. '
      + 'Source: Rosstat.',
  };
}

function ppiYoyYear() {
  return {
    description:
      'Calendar-year producer-price inflation: by how many percent wholesale prices changed '
      + 'by year-end versus the previous year-end (December to December). One point per '
      + 'completed year.',
    methodology:
      'December producer price level divided by the previous December, in percent. '
      + 'One point per completed calendar year. Source: Rosstat.',
  };
}

function ppiMom() {
  return {
    description:
      'Month-on-month change — by how many percent producer prices moved versus the previous '
      + 'month. Positive values are increases; negative values are declines.',
    methodology:
      'Percent change in wholesale industrial prices versus the preceding month. Monthly series. '
      + 'Source: Rosstat. Month-on-month changes accumulate into the producer price index level.',
  };
}

function ppiQoq() {
  return {
    description:
      'Quarter-on-quarter change — by how many percent producer prices moved versus the previous '
      + 'quarter. Positive values are increases; negative values are declines.',
    methodology:
      'Producer price level is taken at quarter-end, then the percent change versus the previous '
      + 'quarter is computed. Source: Rosstat.',
  };
}

function ppiAnnual() {
  return {
    description:
      'Year-on-year change — by how many percent producer prices moved versus the previous year. '
      + 'Positive values are increases; negative values are declines. Calendar years — December '
      + 'to December, one point per completed year.',
    methodology:
      'December producer price level divided by the previous December, in percent. '
      + 'One point per completed calendar year. Forecast uses the same rule on monthly forecast '
      + 'points. Source: Rosstat.',
  };
}

function ppiIndex(safeViewMode) {
  if (safeViewMode === 'index-quarterly') {
    return {
      description:
        'Producer price level at each quarter-end relative to base year 2010 (2010 = 100). '
        + 'The monthly series is shown at quarterly frequency: the last month of each quarter.',
      methodology:
        'Cumulative industrial producer price index, base 2010 = 100. Quarterly view uses the '
        + 'index level at the end of each completed quarter. Source: Rosstat.',
    };
  }
  if (safeViewMode === 'index-annual') {
    return {
      description:
        'Producer price level at each year-end relative to base year 2010 (2010 = 100). '
        + 'Shows the December reading of each year — convenient for long-run comparisons.',
      methodology:
        'Cumulative industrial producer price index, base 2010 = 100. Annual view uses the '
        + 'December level of each completed year. Source: Rosstat.',
    };
  }
  return {
    description:
      'Cumulative industrial producer price index (2010 = 100): the wholesale price level '
      + 'relative to the base year. The line shows the level itself, which rises as monthly '
      + 'inflation accumulates — not a growth rate.',
    methodology:
      'Monthly producer price level on the 2010 = 100 system. Built from a sample of enterprises '
      + 'and products; monthly increases chain into the level. Source: Rosstat.',
  };
}

export function getPpiViewModeContentEn({ chartMode, safeViewMode }) {
  if (chartMode === 'yoy') {
    if (safeViewMode === 'yoy-quarter') return ppiYoyQuarter();
    if (safeViewMode === 'yoy-year') return ppiYoyYear();
    return ppiYoy();
  }
  if (chartMode === 'mom') return ppiMom();
  if (chartMode === 'qoq') return ppiQoq();
  if (chartMode === 'annual') return ppiAnnual();
  if (chartMode === 'index') return ppiIndex(safeViewMode);
  return { description: '', methodology: '' };
}

/* ---- Unemployment ---- */

export function getUnemploymentChartTitleEn(chartMode) {
  switch (chartMode) {
    case 'quarterly':
      return 'Unemployment rate — quarterly average (%)';
    case 'annual':
      return 'Unemployment rate — 12-month average (%)';
    default:
      return 'Unemployment rate — monthly (%)';
  }
}

export function getUnemploymentTableTitleEn(chartMode) {
  switch (chartMode) {
    case 'quarterly':
      return 'Historical data — unemployment, quarterly average';
    case 'annual':
      return 'Historical data — unemployment, 12-month average';
    default:
      return 'Historical data — unemployment (monthly)';
  }
}

export function getUnemploymentViewModeContentEn({ chartMode = 'level' } = {}) {
  if (chartMode === 'quarterly') {
    return {
      description:
        'Chart shows the average monthly unemployment rate within each calendar quarter (%). '
        + 'The three months of the quarter are averaged so a noisy single month does not dominate. '
        + 'This is neither calendar-year unemployment nor the quarter-on-quarter change — only '
        + 'an averaged level in percent.',
      methodology:
        'Mode “by quarter” — derived series: simple average of three monthly Rosstat readings '
        + 'inside the quarter. Rosstat does not publish a separate “quarterly unemployment” '
        + 'release; the average is computed for display from the official monthly path. '
        + 'Compare with the monthly mode when you need within-year detail.',
    };
  }
  if (chartMode === 'annual') {
    return {
      description:
        'Chart shows the trailing twelve-month average of the unemployment rate (%). '
        + 'Each point is the mean over a one-year window ending in that month — smoother than '
        + 'individual months. This is not the average inside a calendar year and not a peak '
        + 'unemployment reading — it is 12-month smoothing of the level.',
      methodology:
        'Mode “12M average” — derived series: for each month, average the previous twelve '
        + 'monthly levels including the current one. The date grid stays monthly, but values '
        + 'are less noisy. Do not confuse with the quarterly-average mode or with point changes '
        + '— the chart still shows the unemployment rate in percent.',
    };
  }
  return {
    description:
      'Chart shows the share of unemployed in the labour force in percent at each month-end '
      + 'from Rosstat’s labour force survey. Covers persons aged 15 and over who are without '
      + 'work, actively seeking work and available to start, under International Labour '
      + 'Organization definitions. This is a level on the date, not the month-on-month change '
      + 'in percentage points. Compare with employment and labour force in the same category.',
    methodology:
      'Mode “monthly” — the underlying monthly unemployment rate (history on the platform from '
      + 'the 1990s). Value is the unemployed share of the labour force in percent for the month. '
      + 'A forecast may be available for this mode. For smoothing, open “Smoothing”: quarterly '
      + 'average or trailing 12-month average — those are separate series with different meaning.',
  };
}

/* ---- CBR term-slice rates ---- */

const CBR_SLICE_META = {
  'credit-rate-corp-short': {
    kind: 'corp',
    chart: 'up to 1 year',
    table: 'up to 1 year',
    phrase: 'with maturity up to 1 year, including demand facilities',
    variant: 'short-term slice',
  },
  'credit-rate-corp-1to3y': {
    kind: 'corp',
    chart: '1 to 3 years',
    table: '1 to 3 years',
    phrase: 'with maturity from 1 to 3 years',
    variant: 'medium-term slice',
  },
  'credit-rate-corp-over3y': {
    kind: 'corp',
    chart: 'over 3 years',
    table: 'over 3 years',
    phrase: 'with maturity over 3 years',
    variant: 'long-term slice',
  },
  'credit-rate-ind-short': {
    kind: 'ind',
    chart: 'up to 1 year',
    table: 'up to 1 year',
    phrase: 'with maturity up to 1 year, including demand facilities',
    variant: 'short-term slice',
  },
  'credit-rate-ind-1to3y': {
    kind: 'ind',
    chart: '1 to 3 years',
    table: '1 to 3 years',
    phrase: 'with maturity from 1 to 3 years',
    variant: 'medium-term slice',
  },
  'credit-rate-ind-over3y': {
    kind: 'ind',
    chart: 'over 3 years',
    table: 'over 3 years',
    phrase: 'with maturity over 3 years',
    variant: 'long-term slice',
  },
  'deposit-rate': {
    kind: 'deposit',
    chart: 'up to 1 year',
    table: 'up to 1 year',
    phrase: 'with maturity up to 1 year, including demand deposits',
    variant: 'short-term slice',
  },
  'deposit-rate-medium': {
    kind: 'deposit',
    chart: '1 to 3 years',
    table: '1 to 3 years',
    phrase: 'with maturity from 1 to 3 years',
    variant: 'medium-term slice',
  },
  'deposit-rate-long': {
    kind: 'deposit',
    chart: 'over 3 years',
    table: 'over 3 years',
    phrase: 'with maturity over 3 years',
    variant: 'long-term slice',
  },
};

function cbrMeta(code) {
  return CBR_SLICE_META[code] ?? CBR_SLICE_META['credit-rate-corp-short'];
}

function cbrProductLabel(kind) {
  if (kind === 'deposit') return 'household deposits';
  if (kind === 'ind') return 'household loans';
  return 'corporate loans';
}

function cbrSubjectPhrase(kind) {
  if (kind === 'deposit') {
    return 'on ruble household deposits';
  }
  if (kind === 'ind') {
    return 'on ruble consumer loans to households';
  }
  return 'on ruble loans to non-financial organisations';
}

export function getCbrTermSliceChartTitleEn(chartMode, code) {
  void chartMode;
  const m = cbrMeta(code);
  return `Rate on ${cbrProductLabel(m.kind)} — ${m.chart} (%)`;
}

export function getCbrTermSliceTableTitleEn(chartMode, code) {
  void chartMode;
  const m = cbrMeta(code);
  if (m.kind === 'deposit') {
    return `Historical data — deposits, ${m.table}`;
  }
  if (m.kind === 'ind') {
    return `Historical data — household loans, ${m.table}`;
  }
  return `Historical data — corporate loans, ${m.table}`;
}

export function getCbrTermSliceViewModeContentEn({ chartMode = 'level', code = 'credit-rate-corp-short' } = {}) {
  void chartMode;
  const m = cbrMeta(code);
  const subject = cbrSubjectPhrase(m.kind);
  const depositNote = m.kind === 'deposit'
    ? 'This is the rate at which banks attract depositor funds, not the yield of a single bank product. '
    : '';
  return {
    description:
      `Chart shows the weighted-average annual rate ${subject} `
      + `${m.phrase}: ${depositNote}`
      + 'the reporting-month value from bank reporting. '
      + 'This is a rate level, not the change versus the previous month.',
    methodology:
      `Mode “rate level” for the ${m.variant}. The Bank of Russia publishes `
      + 'weighted-average rates by maturity; the term is chosen with the switcher above the '
      + 'chart (“Up to 1 year / 1 to 3 years / Over 3 years”). Monthly data with about a '
      + 'one-month lag; the latest point appears on the card and in the history table.',
  };
}

/**
 * Dispatcher mirroring getViewModeContent() family flags.
 */
export function getViewModeContentEn({
  chartMode,
  safeViewMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  indicator,
}) {
  if (isUnemploymentFamily) {
    return getUnemploymentViewModeContentEn({ chartMode });
  }
  if (isPpiFamily) {
    return getPpiViewModeContentEn({ chartMode, safeViewMode });
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceViewModeContentEn({
      chartMode,
      code: indicator?.code,
    });
  }
  if (isHousingFamily) {
    return getHousingViewModeContentEn({
      chartMode,
      safeViewMode,
      code: indicator?.code,
    });
  }
  if (isPriceCategory) {
    return getCpiViewModeContentEn({
      chartMode,
      safeViewMode,
      code: indicator?.code ?? 'cpi',
    });
  }
  return {
    description: indicator?.description ?? '',
    methodology: indicator?.methodology ?? '',
  };
}
