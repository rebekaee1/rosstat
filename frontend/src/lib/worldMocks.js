/**
 * Dev-фикстуры мирового блока. Подключаются только когда live API
 * недоступен (404/сеть) в DEV — см. worldApi.js. Прод-сборку не трогают.
 *
 * Контракт: primary-карточка + frequencies + составные modes `{тип}-{частота}`.
 */

const HICP_POINTS = (() => {
  const out = [];
  let v = 72.3;
  for (let y = 1996; y <= 2026; y++) {
    const months = y === 2026 ? 6 : 12;
    for (let m = 1; m <= months; m++) {
      v = +(v * (1 + (0.0015 + ((y * 12 + m) % 7) * 0.0003))).toFixed(2);
      out.push({
        date: `${y}-${String(m).padStart(2, '0')}-01`,
        value: v,
      });
    }
  }
  return out;
})();

const UNE_M_POINTS = (() => {
  const out = [];
  for (let y = 2005; y <= 2026; y++) {
    const months = y === 2026 ? 5 : 12;
    for (let m = 1; m <= months; m++) {
      const i = (y - 2005) * 12 + m;
      out.push({
        date: `${y}-${String(m).padStart(2, '0')}-01`,
        value: +(3.2 + Math.sin(i / 8) * 0.4).toFixed(2),
      });
    }
  }
  return out;
})();

const UNE_Q_POINTS = UNE_M_POINTS.filter((_, i) => i % 3 === 2).map((p, i) => ({
  date: p.date,
  value: +(p.value + 0.05 * Math.sin(i)).toFixed(2),
}));

const UNE_A_POINTS = (() => {
  const byYear = new Map();
  for (const p of UNE_M_POINTS) {
    const y = p.date.slice(0, 4);
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y).push(p.value);
  }
  return [...byYear.entries()].map(([y, vals]) => ({
    date: `${y}-01-01`,
    value: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2),
  }));
})();

export const WORLD_MOCK_COUNTRIES = {
  countries: [
    { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа', indicators_count: 412 },
    { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', region: 'Европа', indicators_count: 398 },
    { code: 'IT', slug: 'italy', name: 'Италия', name_en: 'Italy', region: 'Европа', indicators_count: 385 },
    { code: 'ES', slug: 'spain', name: 'Испания', name_en: 'Spain', region: 'Европа', indicators_count: 371 },
    { code: 'PL', slug: 'poland', name: 'Польша', name_en: 'Poland', region: 'Европа', indicators_count: 340 },
    { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States', region: 'Америка', indicators_count: 156 },
    { code: 'CA', slug: 'canada', name: 'Канада', name_en: 'Canada', region: 'Америка', indicators_count: 98 },
    { code: 'JP', slug: 'japan', name: 'Япония', name_en: 'Japan', region: 'Азия', indicators_count: 210 },
    { code: 'KR', slug: 'south-korea', name: 'Южная Корея', name_en: 'South Korea', region: 'Азия', indicators_count: 145 },
    { code: 'TR', slug: 'turkey', name: 'Турция', name_en: 'Turkey', region: 'Европа', indicators_count: 280 },
  ],
  total: 10,
};

const DE_COUNTRY = {
  code: 'DE',
  slug: 'germany',
  name: 'Германия',
  name_en: 'Germany',
  region: 'Европа',
};

export const WORLD_MOCK_COUNTRY = {
  germany: {
    country: DE_COUNTRY,
    categories: [
      {
        name: 'Цены',
        count: 2,
        indicators: [
          {
            code: 'de-prc_hicp_midx-cp00',
            name: 'Индекс потребительских цен',
            unit: 'индекс',
            frequencies: ['monthly', 'quarterly', 'annual'],
            last_value: HICP_POINTS[HICP_POINTS.length - 1].value,
            last_date: HICP_POINTS[HICP_POINTS.length - 1].date,
            history_start: HICP_POINTS[0].date,
            history_end: HICP_POINTS[HICP_POINTS.length - 1].date,
            points_count: HICP_POINTS.length,
          },
          {
            code: 'de-prc_hicp_manr-cp00',
            name: 'Гармонизированная инфляция',
            unit: '%',
            frequencies: ['monthly'],
            last_value: 2.1,
            last_date: '2026-06-01',
            history_start: '1997-01-01',
            history_end: '2026-06-01',
            points_count: 354,
          },
        ],
      },
      {
        name: 'Рынок труда',
        count: 2,
        indicators: [
          {
            code: 'de-une_rt_m-total-sa-t-pc-act',
            name: 'Безработица, % экономически активного населения',
            unit: '% экономически активного населения',
            frequencies: ['monthly', 'quarterly', 'annual'],
            last_value: UNE_M_POINTS[UNE_M_POINTS.length - 1].value,
            last_date: UNE_M_POINTS[UNE_M_POINTS.length - 1].date,
            history_start: UNE_M_POINTS[0].date,
            history_end: UNE_M_POINTS[UNE_M_POINTS.length - 1].date,
            points_count: UNE_M_POINTS.length,
          },
          {
            code: 'de-earn_mw_cur',
            name: 'Минимальная заработная плата',
            unit: 'евро',
            frequencies: ['annual'],
            last_value: 2151,
            last_date: '2026-01-01',
            history_start: '1999-01-01',
            history_end: '2026-01-01',
            points_count: 28,
          },
        ],
      },
    ],
  },
};

/** Полная матрица режимов для индексного месячного ряда. */
export const WORLD_MOCK_MODES_FULL = [
  { id: 'level-monthly', label: 'По месяцам', group: 'Уровень', type: 'level', freq: 'monthly', unit: 'индекс', available: true, official: true },
  { id: 'level-quarterly', label: 'По кварталам', group: 'Уровень', type: 'level', freq: 'quarterly', unit: 'индекс', available: true, official: true },
  { id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: 'индекс', available: true, official: true },
  { id: 'step-monthly', label: 'По месяцам', group: 'К прошлому периоду', type: 'step', freq: 'monthly', unit: '%', available: true, official: true },
  { id: 'step-quarterly', label: 'По кварталам', group: 'К прошлому периоду', type: 'step', freq: 'quarterly', unit: '%', available: true, official: true },
  { id: 'step-annual', label: 'По годам', group: 'К прошлому периоду', type: 'step', freq: 'annual', unit: '%', available: true, official: true },
  { id: 'yoy-monthly', label: 'По месяцам', group: 'К году', type: 'yoy', freq: 'monthly', unit: '%', available: true, official: true },
  { id: 'yoy-quarterly', label: 'По кварталам', group: 'К году', type: 'yoy', freq: 'quarterly', unit: '%', available: true, official: true },
  { id: 'yoy-annual', label: 'По годам', group: 'К году', type: 'yoy', freq: 'annual', unit: '%', available: true, official: true },
  { id: 'index-monthly', label: 'По месяцам', group: 'Индекс', type: 'index', freq: 'monthly', unit: 'индекс', available: true, official: true },
  { id: 'index-quarterly', label: 'По кварталам', group: 'Индекс', type: 'index', freq: 'quarterly', unit: 'индекс', available: true, official: true },
  { id: 'index-annual', label: 'По годам', group: 'Индекс', type: 'index', freq: 'annual', unit: 'индекс', available: true, official: true },
];

/** Режимы без «К прошлому периоду» (знакопеременный / годовой). */
export const WORLD_MOCK_MODES_NO_POP = [
  { id: 'level-monthly', label: 'По месяцам', group: 'Уровень', type: 'level', freq: 'monthly', unit: '%', available: true, official: true },
  { id: 'level-quarterly', label: 'По кварталам', group: 'Уровень', type: 'level', freq: 'quarterly', unit: '%', available: true, official: true },
  { id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: '%', available: true, official: true },
  { id: 'yoy-monthly', label: 'По месяцам', group: 'К году', type: 'yoy', freq: 'monthly', unit: 'п.п.', available: true, official: true },
  { id: 'yoy-quarterly', label: 'По кварталам', group: 'К году', type: 'yoy', freq: 'quarterly', unit: 'п.п.', available: true, official: true },
  { id: 'yoy-annual', label: 'По годам', group: 'К году', type: 'yoy', freq: 'annual', unit: 'п.п.', available: true, official: true },
];

/** Легаси-плоский список (для тестов адаптера). */
export const WORLD_MOCK_MODES_LEGACY = [
  { id: 'level', label: 'Уровень', group: 'Уровень', unit: 'индекс' },
  { id: 'mom', label: 'М/м, %', group: 'К прошлому периоду', unit: '%' },
  { id: 'qoq', label: 'Кв/Кв, %', group: 'К прошлому периоду', unit: '%' },
  { id: 'yoy', label: 'К году, %', group: 'К году', unit: '%' },
  { id: 'index', label: 'Индекс (база=100)', group: 'Индекс', unit: 'индекс' },
  { id: 'avg-year', label: 'Среднее за год', group: 'Средние', unit: 'индекс' },
];

const UNE_FREQS = [
  { freq: 'monthly', code: 'de-une_rt_m-total-sa-t-pc-act', points_count: UNE_M_POINTS.length, official: true },
  { freq: 'quarterly', code: 'de-une_rt_q-y15-74-sa-t-pc-act', points_count: UNE_Q_POINTS.length, official: true },
  { freq: 'annual', code: 'de-une_rt_a-y15-74-t-pc-act', points_count: UNE_A_POINTS.length, official: true },
];

export const WORLD_MOCK_INDICATOR = {
  'germany/de-prc_hicp_midx-cp00': {
    country: DE_COUNTRY,
    primary_code: 'de-prc_hicp_midx-cp00',
    indicator: {
      code: 'de-prc_hicp_midx-cp00',
      name: 'Индекс потребительских цен',
      name_en: 'Harmonised index of consumer prices',
      unit: 'индекс',
      frequency: 'monthly',
      category: 'Цены',
      source: 'Евростат',
      source_url: 'https://ec.europa.eu/eurostat',
      description:
        'Гармонизированный индекс потребительских цен Германии. Показывает изменение общего уровня цен на товары и услуги, приобретаемые домашними хозяйствами.',
      methodology:
        'Рассчитывается по единой методологии стран Европейского союза. База индекса — 2015 год. Публикуется ежемесячно.',
      history_start: HICP_POINTS[0].date,
      history_end: HICP_POINTS[HICP_POINTS.length - 1].date,
      points_count: HICP_POINTS.length,
    },
    frequencies: [
      { freq: 'monthly', code: 'de-prc_hicp_midx-cp00', points_count: HICP_POINTS.length, official: true },
      { freq: 'quarterly', code: 'de-prc_hicp_midx-cp00-q', points_count: 120, official: true },
      { freq: 'annual', code: 'de-prc_hicp_midx-cp00-a', points_count: 30, official: true },
    ],
    variants: [],
    modes: WORLD_MOCK_MODES_FULL,
  },
  'germany/de-une_rt_m-total-sa-t-pc-act': {
    country: DE_COUNTRY,
    primary_code: 'de-une_rt_m-total-sa-t-pc-act',
    indicator: {
      code: 'de-une_rt_m-total-sa-t-pc-act',
      name: 'Безработица, % экономически активного населения',
      name_en: 'Unemployment rate',
      unit: '% экономически активного населения',
      frequency: 'monthly',
      category: 'Рынок труда',
      source: 'Евростат',
      source_url: 'https://ec.europa.eu/eurostat',
      description:
        'Доля безработных в численности экономически активного населения Германии по гармонизированному определению.',
      methodology:
        'Показатель публикуется ежемесячно, ежеквартально и ежегодно. Методология согласована между странами Европейского союза.',
      history_start: UNE_M_POINTS[0].date,
      history_end: UNE_M_POINTS[UNE_M_POINTS.length - 1].date,
      points_count: UNE_M_POINTS.length,
    },
    frequencies: UNE_FREQS,
    variants: [
      { code: 'de-une_rt_m-total-sa-t-pc-act', label: 'Все возраста', current: true },
      { code: 'de-une_rt_m-y-lt25-sa-t-pc-act', label: '15–24 лет', current: false },
      { code: 'de-une_rt_m-y25-74-sa-t-pc-act', label: '25–74 лет', current: false },
    ],
    modes: WORLD_MOCK_MODES_NO_POP,
  },
};

function yoyFromLevel(points) {
  const byDate = new Map(points.map((p) => [p.date, p.value]));
  return points
    .map((p) => {
      const d = new Date(p.date);
      d.setUTCFullYear(d.getUTCFullYear() - 1);
      const prev = byDate.get(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-01`);
      if (prev == null || prev === 0) return null;
      return { date: p.date, value: +(((p.value / prev) - 1) * 100).toFixed(2) };
    })
    .filter(Boolean);
}

function momFromLevel(points) {
  return points
    .map((p, i) => {
      if (i === 0) return null;
      const prev = points[i - 1].value;
      if (prev == null || prev === 0) return null;
      return { date: p.date, value: +(((p.value / prev) - 1) * 100).toFixed(2) };
    })
    .filter(Boolean);
}

function pointsForCode(code) {
  if (code?.includes('une_rt_q')) return UNE_Q_POINTS;
  if (code?.includes('une_rt_a')) return UNE_A_POINTS;
  if (code?.includes('une')) return UNE_M_POINTS;
  return HICP_POINTS;
}

export function getWorldMockData(slug, code, mode = 'level-monthly') {
  const primaryKey = Object.keys(WORLD_MOCK_INDICATOR).find((k) => k.startsWith(`${slug}/`));
  const meta = WORLD_MOCK_INDICATOR[`${slug}/${code}`]
    || WORLD_MOCK_INDICATOR[primaryKey];
  if (!meta && !code) return null;

  let token = mode;
  // легаси
  if (!/-/.test(mode)) {
    const freq = code?.includes('_q') || code?.includes('-q')
      ? 'quarterly'
      : code?.includes('_a') || code?.endsWith('-a')
        ? 'annual'
        : 'monthly';
    const map = {
      level: `level-${freq}`,
      mom: 'step-monthly',
      qoq: 'step-quarterly',
      yoy: `yoy-${freq}`,
      yoy_abs: `yoyabs-${freq}`,
      index_first: `index-${freq}`,
      index: `index-${freq}`,
      'avg-year': 'level-annual',
      avg_year: 'level-annual',
    };
    token = map[mode] || `level-${freq}`;
  }

  const [type, freq] = token.split('-');
  let points = pointsForCode(code);
  let aggregated = false;

  if (freq === 'quarterly' && code?.includes('une_rt_m')) {
    points = UNE_Q_POINTS;
  } else if (freq === 'annual' && code?.includes('une_rt_m')) {
    points = UNE_A_POINTS;
  } else if (freq === 'quarterly' && !code?.includes('_q') && !code?.includes('une')) {
    // пересчёт от monthly HICP
    const byQ = new Map();
    for (const p of HICP_POINTS) {
      const y = +p.date.slice(0, 4);
      const m = +p.date.slice(5, 7);
      const q = Math.ceil(m / 3);
      const key = `${y}-Q${q}`;
      if (!byQ.has(key)) byQ.set(key, []);
      byQ.get(key).push(p.value);
    }
    points = [...byQ.entries()].map(([k, vals]) => {
      const [y, q] = k.split('-Q');
      return {
        date: `${y}-${String((+q - 1) * 3 + 1).padStart(2, '0')}-01`,
        value: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2),
      };
    });
    aggregated = true;
  } else if (freq === 'annual' && !code?.includes('_a') && !code?.includes('une')) {
    const byY = new Map();
    for (const p of HICP_POINTS) {
      const y = p.date.slice(0, 4);
      if (!byY.has(y)) byY.set(y, []);
      byY.get(y).push(p.value);
    }
    points = [...byY.entries()].map(([y, vals]) => ({
      date: `${y}-01-01`,
      value: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2),
    }));
    aggregated = true;
  }

  if (type === 'yoy' || type === 'yoyabs') points = yoyFromLevel(points);
  else if (type === 'step') points = momFromLevel(points);
  else if (type === 'index') {
    const base = points[0]?.value || 100;
    points = points.map((p) => ({ date: p.date, value: +((p.value / base) * 100).toFixed(2) }));
  }

  const modeMeta = (meta?.modes || []).find((m) => m.id === token);
  return {
    code,
    mode: token,
    source_code: code,
    unit: modeMeta?.unit || meta?.indicator?.unit || '',
    unit_ru: modeMeta?.unit || meta?.indicator?.unit || '',
    frequency: freq,
    aggregated,
    points,
    count: points.length,
  };
}

export function getWorldMockSearch(q, countrySlug, limit = 50) {
  const needle = (q || '').toLowerCase().replace(/ё/g, 'е');
  const results = [];
  for (const [key, meta] of Object.entries(WORLD_MOCK_INDICATOR)) {
    const [slug] = key.split('/');
    if (countrySlug && slug !== countrySlug) continue;
    const hay = `${meta.indicator.name} ${meta.indicator.name_en} ${meta.indicator.category}`.toLowerCase();
    if (!needle || hay.includes(needle)) {
      results.push({
        code: meta.indicator.code,
        name: meta.indicator.name,
        country_slug: slug,
        country_name: meta.country.name,
        category: meta.indicator.category,
        frequency: meta.indicator.frequency,
      });
    }
  }
  const cat = WORLD_MOCK_COUNTRY[countrySlug || 'germany'];
  if (cat) {
    for (const section of cat.categories) {
      for (const ind of section.indicators) {
        if (results.some((r) => r.code === ind.code)) continue;
        const hay = `${ind.name} ${section.name}`.toLowerCase();
        if (!needle || hay.includes(needle)) {
          results.push({
            code: ind.code,
            name: ind.name,
            country_slug: cat.country.slug,
            country_name: cat.country.name,
            category: section.name,
            frequency: ind.frequencies?.[0] || ind.frequency,
          });
        }
      }
    }
  }
  return { results: results.slice(0, limit), total: results.length };
}
