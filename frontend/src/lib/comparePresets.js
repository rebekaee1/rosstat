// Готовые сравнения для страницы «Сравнение»: открываются сразу живым графиком и быстрыми кнопками.
// Все пары — «один показатель, две страны»: гость может сравнивать до двух рядов, а страны
// разрешено ставить рядом только по одному и тому же показателю (см. compareCompatibility).
// Инфляция берётся по Германии и Франции: у обеих один и тот же индекс цен с одной базой,
// поэтому «рост цен за год» считается честно (у США этот ряд приходит уже в процентах).

export const COMPARE_PRESETS = [
  {
    id: 'gdp',
    labelKey: 'w6g.compare.preset.gdp',
    codes: ['w:united-states:gdp-usd', 'w:china:gdp-usd'],
    reps: {},
  },
  {
    id: 'unemployment',
    labelKey: 'w6g.compare.preset.unemployment',
    codes: ['w:germany:unemployment-rate', 'w:france:unemployment-rate'],
    reps: {},
  },
  {
    id: 'inflation',
    labelKey: 'w6g.compare.preset.inflation',
    codes: ['w:germany:hicp-index', 'w:france:hicp-index'],
    reps: { 'w:germany:hicp-index': 'yoy', 'w:france:hicp-index': 'yoy' },
  },
  {
    id: 'population',
    labelKey: 'w6g.compare.preset.population',
    codes: ['w:india:population', 'w:china:population'],
    reps: {},
  },
  // Круг 9 (P2): готовые пары «Россия и другая страна». У Турции индекс цен приходит уровнем, у России уже в процентах
  // за год, поэтому турецкий ряд сразу берётся как «% к прошлому году».
  {
    id: 'ru-tr-inflation',
    labelKey: 'c9d.compare.preset.ruTrInflation',
    codes: ['w:russia:hicp-index', 'w:turkey:hicp-index'],
    reps: { 'w:turkey:hicp-index': 'yoy' },
  },
  {
    id: 'ru-tr-gdp',
    labelKey: 'c9d.compare.preset.ruTrGdp',
    codes: ['w:russia:gdp-usd', 'w:turkey:gdp-usd'],
    reps: {},
  },
  {
    id: 'ru-tr-unemployment',
    labelKey: 'c9d.compare.preset.ruTrUnemployment',
    codes: ['w:russia:unemployment-rate', 'w:turkey:unemployment-rate'],
    reps: {},
  },
];

export const DEFAULT_COMPARE_PRESET = COMPARE_PRESETS[0];

/** Параметры адреса для набора: `codes=…` и, если нужно, `rep=код:вид,…`. */
export function presetParams(preset, base) {
  const params = new URLSearchParams(base || '');
  params.delete('a');
  params.delete('b');
  params.set('codes', preset.codes.join(','));
  const reps = Object.entries(preset.reps || {});
  if (reps.length) params.set('rep', reps.map(([code, rep]) => `${code}:${rep}`).join(','));
  else params.delete('rep');
  return params;
}

/** Совпадает ли текущий набор рядов с готовым (порядок не важен). */
export function presetIsActive(preset, codes) {
  if (!codes || codes.length !== preset.codes.length) return false;
  return preset.codes.every((code) => codes.includes(code));
}
