const WORLD_PREFIX = 'w:';
const REGION_PREFIX = 'r:';

const BRIDGES = {
  'unemployment-rate': {
    macroCodes: new Set(['unemployment']),
    regionCodes: new Set(['2.10.1']),
    noteKey: 'compare.compat.note.unemployment',
  },
  population: {
    macroCodes: new Set(['population']),
    regionCodes: new Set(['1.1']),
    noteKey: 'compare.compat.note.population',
  },
};

// Российский показатель с главной витрины (`cpi`, `unemployment`…) и тот же показатель в общем наборе стран
// (`w:russia:{понятие}`): с рядами других стран сравнивается только второй.
// Круг 10 (Ср1): ВВП, ВВП на душу, баланс бюджета и госдолг тоже имеют двойников, поэтому порядок выбора
// «сначала США, потом Россия» и «сначала Россия, потом США» даёт один и тот же результат.
const MACRO_TWINS = {
  cpi: 'hicp-index',
  'cpi-yoy': 'hicp-index',
  unemployment: 'unemployment-rate',
  population: 'population',
  'gdp-nominal': 'gdp-usd',
  'weo-gdp-usd': 'gdp-usd',
  'weo-gdp-per-capita-usd': 'gdp-per-capita-usd',
  'weo-budget-balance-gdp': 'budget-balance-gdp',
  'weo-government-debt-gdp': 'government-debt-gdp',
};

/** Российские показатели в рублях, которые в общем наборе стран заменяются рядом в долларах США. */
const RUB_TO_USD_TWINS = new Set(['gdp-nominal']);

/** Понятие общего набора стран, которому соответствует российский показатель; нет двойника: null. */
export function macroTwinConcept(code) {
  return MACRO_TWINS[code] || null;
}

/** Код ряда России в общем наборе стран для российского показателя с двойником; нет двойника: null. */
export function macroTwinCode(code) {
  const concept = macroTwinConcept(code);
  return concept ? `${WORLD_PREFIX}russia:${concept}` : null;
}

export function parseWorldCompareCode(code) {
  const [kind, countrySlug, conceptSlug, ...rest] = String(code || '').split(':');
  if (kind !== 'w' || !countrySlug || !conceptSlug || rest.length) return null;
  return { countrySlug, conceptSlug };
}

/** Субнациональный ряд: `s:{страна}:{территория}:{показатель}`. */
export function parseSubnationalCompareCode(code) {
  const [kind, countrySlug, regionSlug, indicatorCode, ...rest] = String(code || '').split(':');
  if (kind !== 's' || !countrySlug || !regionSlug || !indicatorCode || rest.length) {
    return null;
  }
  return { countrySlug, regionSlug, indicatorCode };
}

function regionIndicatorCode(code) {
  if (!String(code || '').startsWith(REGION_PREFIX)) return null;
  const [, regionSlug, indicatorCode, ...rest] = code.split(':');
  if (!regionSlug || !indicatorCode || rest.length) return null;
  return indicatorCode;
}

function isAllowedNonWorld(code, bridge) {
  const regional = regionIndicatorCode(code);
  if (regional) return bridge.regionCodes.has(regional);
  return !String(code || '').startsWith(WORLD_PREFIX) && bridge.macroCodes.has(code);
}

export function compareCompatibility(existingCodes, candidateCode) {
  const existing = (existingCodes || []).filter(Boolean);
  if (!candidateCode || existing.includes(candidateCode)) {
    return { allowed: false, reasonKey: 'compare.compat.alreadyAdded', reason: 'compare.compat.alreadyAdded' };
  }
  if (!existing.length) return { allowed: true, note: null, noteKey: null };

  const candidateWorld = parseWorldCompareCode(candidateCode);
  const candidateSub = parseSubnationalCompareCode(candidateCode);
  const existingWorld = existing
    .map(parseWorldCompareCode)
    .filter(Boolean);
  const existingSub = existing
    .map(parseSubnationalCompareCode)
    .filter(Boolean);
  const worldConcepts = new Set(existingWorld.map((item) => item.conceptSlug));

  if (candidateWorld && existingWorld.length && (
    worldConcepts.size !== 1 || !worldConcepts.has(candidateWorld.conceptSlug)
  )) {
    return {
      allowed: false,
      reasonKey: 'compare.compat.sameConcept',
      reason: 'compare.compat.sameConcept',
    };
  }

  const subCountries = new Set(existingSub.map((item) => item.countrySlug));
  if (candidateSub) subCountries.add(candidateSub.countrySlug);
  if (subCountries.size > 1) {
    return {
      allowed: false,
      reasonKey: 'compare.compat.sameConcept',
      reason: 'compare.compat.sameConcept',
    };
  }

  const subCountry = candidateSub?.countrySlug || existingSub[0]?.countrySlug;
  const worldCountries = new Set(existingWorld.map((item) => item.countrySlug));
  if (candidateWorld) worldCountries.add(candidateWorld.countrySlug);
  if (subCountry && worldCountries.size && ![...worldCountries].every((slug) => slug === subCountry)) {
    return {
      allowed: false,
      reasonKey: 'compare.compat.noBridge',
      reason: 'compare.compat.noBridge',
    };
  }

  if (candidateSub && !existingWorld.length) {
    const foreign = existing.filter((code) => (
      !parseWorldCompareCode(code) && !parseSubnationalCompareCode(code)
    ));
    if (foreign.length) {
      return {
        allowed: false,
        reasonKey: 'compare.compat.noBridge',
        reason: 'compare.compat.noBridge',
      };
    }
    return { allowed: true, note: null, noteKey: null };
  }

  const conceptSlug = candidateWorld?.conceptSlug || existingWorld[0]?.conceptSlug;
  if (!conceptSlug) {
    if (existingSub.length && !candidateSub) {
      return {
        allowed: false,
        reasonKey: 'compare.compat.noBridge',
        reason: 'compare.compat.noBridge',
      };
    }
    return { allowed: true, note: null, noteKey: null };
  }

  const bridge = BRIDGES[conceptSlug];
  const nonWorldCodes = existing.filter((code) => (
    !parseWorldCompareCode(code) && !parseSubnationalCompareCode(code)
  ));
  if (!candidateWorld && !candidateSub) nonWorldCodes.push(candidateCode);

  if (!nonWorldCodes.length) return { allowed: true, note: null, noteKey: null };
  if (!bridge) {
    return {
      allowed: false,
      reasonKey: 'compare.compat.noBridge',
      reason: 'compare.compat.noBridge',
    };
  }
  if (!nonWorldCodes.every((code) => isAllowedNonWorld(code, bridge))) {
    return {
      allowed: false,
      reasonKey: 'compare.compat.notInGroup',
      reason: 'compare.compat.notInGroup',
    };
  }

  return {
    allowed: true,
    note: bridge.noteKey,
    noteKey: bridge.noteKey,
    conceptSlug,
  };
}

/**
 * То же, что compareCompatibility, но российский показатель с «двойником» в общем наборе стран не отвергается,
 * а заменяется на двойника, где бы он ни стоял:
 *  - уже выбранный (ИПЦ или ВВП России -> тот же показатель России рядом с другой страной): `replaceWith` — новый
 *    список уже выбранных кодов;
 *  - добавляемый (ВВП России к уже выбранному ВВП США): `addCode` — код, который нужно добавить вместо выбранного.
 * `swapNoteKey` — что сказать человеку. `hasCode(code)` говорит, есть ли ряд в каталоге.
 */
export function compareCompatibilityWithTwins(existingCodes, candidateCode, hasCode = () => true) {
  const base = compareCompatibility(existingCodes, candidateCode);
  if (base.allowed || base.reasonKey === 'compare.compat.alreadyAdded') return base;
  const existing = (existingCodes || []).filter(Boolean);
  if (!existing.length) return base;

  const candidate = parseWorldCompareCode(candidateCode);
  if (!candidate) {
    // Российский показатель добавляется к рядам других стран: берём его двойника из общего набора.
    const twin = macroTwinCode(candidateCode);
    if (!twin || !hasCode(twin)) return base;
    if (existing.includes(twin)) {
      return { allowed: false, reasonKey: 'compare.compat.alreadyAdded', reason: 'compare.compat.alreadyAdded' };
    }
    const viaTwin = compareCompatibilityWithTwins(existing, twin, hasCode);
    if (!viaTwin.allowed) return base;
    return {
      ...viaTwin,
      addCode: twin,
      swapNoteKey: RUB_TO_USD_TWINS.has(candidateCode) ? 'c10k.compare.twinRubToUsd' : 'c9d.compare.twinSwapped',
    };
  }

  if (base.reasonKey !== 'compare.compat.sameConcept' && base.reasonKey !== 'compare.compat.noBridge'
    && base.reasonKey !== 'compare.compat.notInGroup') return base;
  const replacedMacros = [];
  const swapped = existing.map((code) => {
    if (parseWorldCompareCode(code) || parseSubnationalCompareCode(code) || String(code).startsWith(REGION_PREFIX)) return code;
    const twin = macroTwinCode(code);
    if (twin && macroTwinConcept(code) === candidate.conceptSlug && hasCode(twin)) {
      replacedMacros.push(code);
      return twin;
    }
    return code;
  });
  if (!replacedMacros.length) return base;
  const unique = swapped.filter((code, i) => swapped.indexOf(code) === i);
  const retry = compareCompatibility(unique, candidateCode);
  if (!retry.allowed) return base;
  return {
    allowed: true,
    note: null,
    noteKey: null,
    replaceWith: unique,
    swapNoteKey: replacedMacros.some((code) => RUB_TO_USD_TWINS.has(code))
      ? 'c10k.compare.twinRubToUsd'
      : 'c9d.compare.twinSwapped',
  };
}

/**
 * Коды из адреса или готовой подборки приводим к совместимому набору: российский показатель с двойником
 * превращается в двойника, если иначе он не сочетался бы со странами; несочетаемое отбрасывается.
 */
export function normalizeCompareCodes(codes, hasCode = () => true) {
  let accepted = [];
  for (const code of codes || []) {
    if (!accepted.length) {
      accepted.push(code);
      continue;
    }
    const result = compareCompatibilityWithTwins(accepted, code, hasCode);
    if (!result.allowed) continue;
    accepted = [...(result.replaceWith || accepted), result.addCode || code];
    accepted = accepted.filter((item, i) => accepted.indexOf(item) === i);
  }
  return accepted;
}

export function sanitizeCompareCodes(codes) {
  const accepted = [];
  for (const code of codes || []) {
    if (!accepted.length || compareCompatibility(accepted, code).allowed) {
      accepted.push(code);
    }
  }
  return accepted;
}

export function activeCompatibilityNote(codes) {
  const world = (codes || []).map(parseWorldCompareCode).find(Boolean);
  if (!world) return null;
  const bridge = BRIDGES[world.conceptSlug];
  if (!bridge) return null;
  const hasNonWorld = codes.some((code) => (
    !parseWorldCompareCode(code) && !parseSubnationalCompareCode(code)
  ));
  return hasNonWorld ? bridge.noteKey : null;
}
