/**
 * Режимы мировой карточки: составной токен `{тип}-{частота}` (как у ИПЦ),
 * нормализация легаси-токенов, группировка для двухуровневого переключателя.
 *
 * Тип ∈ level|step|yoy|yoyabs|index
 * Частота ∈ monthly|quarterly|annual
 *
 * Список modes приходит с API; при старом контракте — адаптер ниже.
 */

/** @typedef {'level'|'step'|'yoy'|'yoyabs'|'index'} WorldModeType */
/** @typedef {'monthly'|'quarterly'|'annual'|'weekly'|'daily'} WorldFreq */

/**
 * @typedef {{
 *   id: string,
 *   label: string,
 *   group: string,
 *   type?: WorldModeType,
 *   freq?: WorldFreq,
 *   unit?: string,
 *   available?: boolean,
 *   official?: boolean,
 * }} WorldMode
 */

/**
 * @typedef {{
 *   id: string,
 *   label: string,
 *   leafMode?: string,
 *   modes?: Array<{
 *     mode: string,
 *     label: string,
 *     unit?: string,
 *     available?: boolean,
 *     official?: boolean,
 *     disabled?: boolean,
 *     hint?: string,
 *   }>,
 * }} WorldModeGroup
 */

export const WORLD_MODE_TYPES = ['level', 'step', 'yoy', 'yoyabs', 'index'];
export const WORLD_MODE_FREQS = ['monthly', 'quarterly', 'annual'];

const TYPE_SET = new Set(WORLD_MODE_TYPES);
const FREQ_SET = new Set(WORLD_MODE_FREQS);

const COMPOSITE_RE = /^(level|step|yoy|yoyabs|index)-(monthly|quarterly|annual)$/;

const TYPE_GROUP_LABEL = {
  level: 'Уровень',
  step: 'К прошлому периоду',
  yoy: 'К году',
  yoyabs: 'К году',
  index: 'Индекс',
};

const FREQ_SUB_LABEL = {
  monthly: 'По месяцам',
  quarterly: 'По кварталам',
  annual: 'По годам',
  weekly: 'По неделям',
  daily: 'По дням',
};

const FREQUENCY_LONG = {
  daily: 'по дням',
  weekly: 'по неделям',
  monthly: 'помесячно',
  quarterly: 'поквартально',
  annual: 'по годам',
};

const FREQUENCY_LONG_EN = {
  daily: 'daily',
  weekly: 'weekly',
  monthly: 'monthly',
  quarterly: 'quarterly',
  annual: 'annual',
};

const FREQ_SUFFIX_RE = /(?:,\s*(помесячно|поквартально|за год|понедельно|по дням)|\s*[-–—]\s*(monthly|quarterly|annual|yearly|weekly|daily)\s+data)\s*$/i;

/** Убрать суффикс частоты из публичного имени (частота живёт в переключателе). */
export function stripFrequencySuffix(name) {
  if (!name) return name || '';
  return name.replace(FREQ_SUFFIX_RE, '').trim();
}

/** @param {string|null|undefined} token */
export function parseWorldModeToken(token) {
  if (!token) return null;
  const m = COMPOSITE_RE.exec(String(token).trim());
  if (!m) return null;
  return { type: /** @type {WorldModeType} */ (m[1]), freq: /** @type {WorldFreq} */ (m[2]) };
}

/** @param {WorldModeType} type @param {WorldFreq} freq */
export function buildWorldModeToken(type, freq) {
  return `${type}-${freq}`;
}

/**
 * Легаси API-токены → канонический составной.
 * @param {string|null|undefined} raw
 * @param {WorldFreq} [fallbackFreq='monthly']
 */
export function normalizeWorldModeToken(raw, fallbackFreq = 'monthly') {
  if (!raw) return buildWorldModeToken('level', fallbackFreq);
  const s = String(raw).trim();
  const parsed = parseWorldModeToken(s);
  if (parsed) return buildWorldModeToken(parsed.type, parsed.freq);

  const freq = FREQ_SET.has(fallbackFreq) ? fallbackFreq : 'monthly';
  const legacy = {
    level: () => buildWorldModeToken('level', freq),
    mom: () => 'step-monthly',
    qoq: () => 'step-quarterly',
    yoy: () => buildWorldModeToken('yoy', freq),
    yoy_abs: () => buildWorldModeToken('yoyabs', freq),
    yoyabs: () => buildWorldModeToken('yoyabs', freq),
    index_first: () => buildWorldModeToken('index', freq),
    index: () => buildWorldModeToken('index', freq),
    avg_quarter: () => 'level-quarterly',
    avg_year: () => 'level-annual',
    'avg-quarter': () => 'level-quarterly',
    'avg-year': () => 'level-annual',
  };
  const fn = legacy[s];
  if (fn) return fn();
  return buildWorldModeToken('level', freq);
}

/**
 * Составной → легаси id для старого /data endpoint, пока backend не готов.
 * @param {string} token
 */
export function worldModeToLegacyDataToken(token) {
  const p = parseWorldModeToken(normalizeWorldModeToken(token));
  if (!p) return 'level';
  if (p.type === 'level') return 'level';
  if (p.type === 'step') {
    if (p.freq === 'monthly') return 'mom';
    if (p.freq === 'quarterly') return 'qoq';
    return 'yoy';
  }
  if (p.type === 'yoy') return 'yoy';
  if (p.type === 'yoyabs') return 'yoy_abs';
  if (p.type === 'index') return 'index_first';
  return 'level';
}

/** Нормализовать запись mode из API. */
function normalizeModeEntry(m, fallbackFreq = 'monthly') {
  if (!m?.id && !(m?.type && m?.freq)) return null;
  let type = m.type;
  let freq = m.freq;
  if (!type || !freq) {
    const p = parseWorldModeToken(normalizeWorldModeToken(m.id, fallbackFreq));
    type = p?.type;
    freq = p?.freq;
  }
  if (!type || !freq || !TYPE_SET.has(type) || !FREQ_SET.has(freq)) return null;
  const id = m.id && parseWorldModeToken(m.id)
    ? m.id
    : buildWorldModeToken(type, freq);
  return {
    id,
    label: m.label || FREQ_SUB_LABEL[freq] || freq,
    group: m.group || TYPE_GROUP_LABEL[type] || type,
    type,
    freq,
    unit: m.unit,
    available: m.available !== false,
    official: m.official !== false,
  };
}

/**
 * Частоты из meta: объекты или строки.
 * @param {unknown} frequencies
 * @param {string|undefined} indicatorFreq
 * @returns {Array<{ freq: string, code?: string, points_count?: number, official?: boolean }>}
 */
export function normalizeWorldFrequencies(frequencies, indicatorFreq) {
  if (Array.isArray(frequencies) && frequencies.length) {
    return frequencies.map((f) => {
      if (typeof f === 'string') return { freq: f, official: true };
      return {
        freq: f.freq || f.frequency,
        code: f.code,
        points_count: f.points_count,
        history_start: f.history_start,
        history_end: f.history_end,
        official: f.official !== false,
      };
    }).filter((f) => f.freq);
  }
  if (indicatorFreq) return [{ freq: indicatorFreq, official: true }];
  return [{ freq: 'monthly', official: true }];
}

/**
 * Адаптер: новый контракт или легаси modes × frequencies → плоский список WorldMode.
 * @param {{ modes?: WorldMode[], frequencies?: unknown, indicator?: { frequency?: string } }|null} meta
 * @returns {WorldMode[]}
 */
export function adaptWorldModes(meta) {
  const raw = meta?.modes;
  if (!Array.isArray(raw) || raw.length === 0) return [];

  const freqs = normalizeWorldFrequencies(meta.frequencies, meta.indicator?.frequency);
  const fallbackFreq = /** @type {WorldFreq} */ (freqs[0]?.freq || 'monthly');

  const looksComposite = raw.some(
    (m) => (m.type && m.freq) || parseWorldModeToken(m.id),
  );

  if (looksComposite) {
    const compositeOut = [];
    const compositeSeen = new Set();
    for (const entry of raw) {
      const normalized = normalizeModeEntry(entry, fallbackFreq);
      if (!normalized) continue;
      // Легаси-id и составные токены в одном списке схлопываются в один
      // канонический id (mom + step-monthly → step-monthly); приоритет у
      // записи, чей id совпал с API без трансформации, иначе — у первой.
      if (compositeSeen.has(normalized.id)) {
        const prevIdx = compositeOut.findIndex((m) => m.id === normalized.id);
        const prev = compositeOut[prevIdx];
        const prevIsTransformed = !parseWorldModeToken(prev.apiRawId);
        const curIsTransformed = !parseWorldModeToken(entry.id);
        if (prevIsTransformed && !curIsTransformed) {
          compositeOut[prevIdx] = { ...normalized, apiRawId: entry.id };
        }
        continue;
      }
      compositeSeen.add(normalized.id);
      compositeOut.push({ ...normalized, apiRawId: entry.id });
    }
    return compositeOut.map(({ apiRawId: _apiRawId, ...rest }) => rest);
  }

  const byId = Object.fromEntries(raw.map((m) => [m.id, m]));
  const out = [];
  const seen = new Set();

  const push = (type, freq, unit, official = true) => {
    const id = buildWorldModeToken(type, freq);
    if (seen.has(id)) return;
    seen.add(id);
    out.push({
      id,
      label: FREQ_SUB_LABEL[freq] || freq,
      group: TYPE_GROUP_LABEL[type],
      type,
      freq,
      unit,
      available: true,
      official,
    });
  };

  // Уровень — на все частоты карточки
  if (byId.level) {
    for (const f of freqs) {
      push('level', f.freq, byId.level.unit, f.official !== false);
    }
  }

  // К прошлому периоду — родная частота легаси-кнопки (+ год, если есть)
  if (byId.mom) push('step', 'monthly', byId.mom.unit);
  if (byId.qoq) push('step', 'quarterly', byId.qoq.unit);
  if (freqs.some((f) => f.freq === 'annual') && (byId.yoy || byId.mom || byId.qoq)) {
    push('step', 'annual', byId.yoy?.unit || '%');
  }

  // К году — один вариант: процент, а у знакопеременных рядов — единицы
  if (byId.yoy) {
    for (const f of freqs) push('yoy', f.freq, byId.yoy.unit, f.official !== false);
  } else if (byId.yoy_abs) {
    for (const f of freqs) push('yoyabs', f.freq, byId.yoy_abs.unit, f.official !== false);
  }
  const indexSrc = byId.index_first || byId.index;
  if (indexSrc) {
    for (const f of freqs) push('index', f.freq, indexSrc.unit, f.official !== false);
  }

  // avg_* легаси → уровень на агрегированной частоте (пометим official:false)
  if (byId.avg_quarter || byId['avg-quarter']) {
    push('level', 'quarterly', byId.level?.unit, false);
  }
  if (byId.avg_year || byId['avg-year']) {
    push('level', 'annual', byId.level?.unit, false);
  }

  return out;
}

/**
 * Собрать двухуровневые группы: верх = тип (group), низ = частоты.
 * Ячейки available:false остаются видимыми, но disabled — как у ИПЦ.
 *
 * @param {WorldMode[]|null|undefined} modes
 * @returns {WorldModeGroup[]}
 */
export function groupModesFromApi(modes) {
  if (!Array.isArray(modes) || modes.length === 0) return [];

  const order = [];
  const buckets = new Map();

  for (const m of modes) {
    if (!m?.id || !m?.group) continue;
    if (!buckets.has(m.group)) {
      buckets.set(m.group, []);
      order.push(m.group);
    }
    const available = m.available !== false;
    buckets.get(m.group).push({
      mode: m.id,
      label: m.label || FREQ_SUB_LABEL[m.freq] || m.id,
      unit: m.unit,
      available,
      official: m.official !== false,
      disabled: !available,
      hint: !available ? 'нет официального ряда' : (!m.official ? 'расчётный ряд' : undefined),
    });
  }

  return order.map((groupName) => {
    const items = buckets.get(groupName);
    const availableItems = items.filter((i) => !i.disabled);
    // Одна доступная частота и нет disabled-соседей → leaf на верхнем ряду
    if (items.length === 1 && availableItems.length === 1) {
      return {
        id: groupName,
        label: groupName,
        leafMode: items[0].mode,
        modes: items,
      };
    }
    return {
      id: groupName,
      label: groupName,
      modes: items,
    };
  });
}

/**
 * @param {WorldMode[]|null|undefined} modes
 * @param {string|null|undefined} urlMode
 * @param {WorldFreq} [fallbackFreq]
 */
export function resolveWorldMode(modes, urlMode, fallbackFreq = 'monthly') {
  if (!Array.isArray(modes) || modes.length === 0) return null;
  const canonical = normalizeWorldModeToken(urlMode, fallbackFreq);
  const exact = modes.find((m) => m.id === canonical && m.available !== false);
  if (exact) return exact.id;
  // URL указывает на недоступную ячейку — взять первую доступную того же типа
  const parsed = parseWorldModeToken(canonical);
  if (parsed) {
    const sameType = modes.find(
      (m) => m.type === parsed.type && m.available !== false,
    );
    if (sameType) return sameType.id;
  }
  const first = modes.find((m) => m.available !== false) || modes[0];
  return first?.id ?? null;
}

/** @param {WorldMode[]|null|undefined} modes @param {string|null|undefined} modeId */
export function findWorldMode(modes, modeId) {
  if (!Array.isArray(modes) || !modeId) return null;
  const canonical = normalizeWorldModeToken(modeId);
  return modes.find((m) => m.id === modeId)
    || modes.find((m) => m.id === canonical)
    || null;
}

export function expandedGroupForWorldMode(groups, modeId) {
  if (!groups?.length || !modeId) return groups?.[0]?.id ?? null;
  for (const g of groups) {
    if (g.leafMode === modeId) return g.id;
    if (g.modes?.some((m) => m.mode === modeId)) return g.id;
  }
  return groups[0]?.id ?? null;
}

export function defaultModeForWorldGroup(groups, groupId) {
  const g = groups?.find((x) => x.id === groupId);
  if (!g) return null;
  if (g.leafMode) return g.leafMode;
  const firstOk = g.modes?.find((m) => !m.disabled);
  return firstOk?.mode ?? g.modes?.[0]?.mode ?? null;
}

export function isEmptySeries(points) {
  return !Array.isArray(points) || points.length === 0;
}

/** Minimal RU→EN for chart title groups (mirrors viewModeLabels). */
const LABELS_EN_INLINE = {
  'Уровень': 'Level',
  'К прошлому периоду': 'Vs previous period',
  'К году': 'Year on year',
  'Индекс': 'Index',
  'По месяцам': 'Monthly',
  'По кварталам': 'Quarterly',
  'По годам': 'Annual',
  'М/м': 'MoM',
  'Кв/кв': 'QoQ',
  'Кв/Кв': 'QoQ',
  'Г/г': 'YoY',
};

/**
 * Заголовок графика: имя (без частоты) + режим + частота активного ряда.
 * @param {{ name?: string, frequency?: string }|null} indicator
 * @param {WorldMode|null} mode
 * @param {string} [activeFreq]
 * @param {'ru'|'en'} [locale='ru']
 */
export function worldChartTitle(indicator, mode, activeFreq, locale = 'ru') {
  const fallback = locale === 'en' ? 'Indicator' : 'Показатель';
  const name = stripFrequencySuffix(indicator?.name || fallback);
  const modeLabelRaw = mode?.group || mode?.label;
  const modeLabel = locale === 'en' && modeLabelRaw
    ? (LABELS_EN_INLINE[modeLabelRaw] || modeLabelRaw)
    : modeLabelRaw;
  const freqKey = activeFreq || mode?.freq || indicator?.frequency;
  const freqMap = locale === 'en' ? FREQUENCY_LONG_EN : FREQUENCY_LONG;
  const freq = freqMap[freqKey] || '';
  const parts = [name];
  if (modeLabel) parts.push(modeLabel);
  const base = parts.join(' — ');
  return freq ? `${base} (${freq})` : base;
}

/** @param {string|undefined} frequency */
export function worldRangePreset(frequency) {
  if (frequency === 'quarterly') return 'quarterly';
  if (frequency === 'annual') return 'annual';
  if (frequency === 'weekly') return 'weekly';
  if (frequency === 'daily') return 'daily';
  return 'default';
}

const FREQ_RANK = { monthly: 0, quarterly: 1, annual: 2, weekly: 3, daily: 4 };

/**
 * Схлопнуть листинг страны: одна плитка на показатель, если API ещё отдаёт ряды.
 * Если у элементов уже есть frequencies[] — считаем, что backend схлопнул.
 *
 * @param {Array<Record<string, unknown>>} indicators
 */
export function collapseCountryIndicators(indicators) {
  if (!Array.isArray(indicators) || indicators.length === 0) return [];
  if (indicators.some((i) => Array.isArray(i.frequencies))) {
    // Prefer locale-facing `name` (API already resolved RU/EN). Never fall
    // back to name_ru first — that forced Russian titles under preview_locale=en.
    return indicators.map((i) => ({
      ...i,
      name: stripFrequencySuffix(i.name || i.name_ru),
      name_ru: undefined,
    }));
  }

  const groups = new Map();
  for (const item of indicators) {
    const baseName = stripFrequencySuffix(item.name);
    const key = `${baseName}||${item.unit || ''}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }

  const out = [];
  for (const members of groups.values()) {
    members.sort((a, b) => {
      const ra = FREQ_RANK[a.frequency] ?? 9;
      const rb = FREQ_RANK[b.frequency] ?? 9;
      if (ra !== rb) return ra - rb;
      return (b.points_count || 0) - (a.points_count || 0);
    });
    const primary = members[0];
    const freqs = [...new Set(members.map((m) => m.frequency).filter(Boolean))];
    out.push({
      ...primary,
      name: stripFrequencySuffix(primary.name),
      frequencies: freqs,
      _freqMembers: members.map((m) => ({
        freq: m.frequency,
        code: m.code,
        points_count: m.points_count,
        official: true,
      })),
    });
  }
  return out;
}

/**
 * VariantGroupPicker shape из API variants.
 * @param {Array<{ code: string, label: string, current?: boolean }>|null|undefined} variants
 * @param {string} [groupLabel='Срез']
 */
export function worldVariantsToPickerGroup(variants, groupLabel = 'Срез') {
  if (!Array.isArray(variants) || variants.length < 2) return null;
  return {
    label: groupLabel,
    codes: variants.map((v) => ({ code: v.code, label: v.label })),
  };
}
