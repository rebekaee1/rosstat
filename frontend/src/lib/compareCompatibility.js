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
const MACRO_TWINS = {
  cpi: 'hicp-index',
  'cpi-yoy': 'hicp-index',
  unemployment: 'unemployment-rate',
  population: 'population',
};

/** Понятие общего набора стран, которому соответствует российский показатель; нет двойника: null. */
export function macroTwinConcept(code) {
  return MACRO_TWINS[code] || null;
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
 * То же, что compareCompatibility, но если выбранный российский показатель можно заменить на «двойника» в общем
 * наборе стран (ИПЦ России -> инфляция России рядом с инфляцией Турции), набор не отвергается, а перестраивается:
 * `replaceWith` — новый список уже выбранных кодов. `hasCode(code)` говорит, есть ли ряд в каталоге.
 */
export function compareCompatibilityWithTwins(existingCodes, candidateCode, hasCode = () => true) {
  const base = compareCompatibility(existingCodes, candidateCode);
  if (base.allowed) return base;
  const candidate = parseWorldCompareCode(candidateCode);
  const existing = (existingCodes || []).filter(Boolean);
  if (!candidate || !existing.length || base.reasonKey === 'compare.compat.alreadyAdded') return base;
  const swapped = existing.map((code) => {
    if (parseWorldCompareCode(code) || parseSubnationalCompareCode(code) || String(code).startsWith(REGION_PREFIX)) return code;
    const concept = macroTwinConcept(code);
    const twin = concept ? `${WORLD_PREFIX}russia:${concept}` : null;
    return twin && concept === candidate.conceptSlug && hasCode(twin) ? twin : code;
  });
  const replaced = swapped.some((code, i) => code !== existing[i]);
  const unique = swapped.filter((code, i) => swapped.indexOf(code) === i);
  if (!replaced) return base;
  const retry = compareCompatibility(unique, candidateCode);
  if (!retry.allowed) return base;
  return {
    allowed: true, note: null, noteKey: null, replaceWith: unique, swapNoteKey: 'c9d.compare.twinSwapped',
  };
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
