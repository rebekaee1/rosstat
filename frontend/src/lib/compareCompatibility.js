const WORLD_PREFIX = 'w:';
const REGION_PREFIX = 'r:';

const BRIDGES = {
  'unemployment-rate': {
    macroCodes: new Set(['unemployment']),
    regionCodes: new Set(['2.10.1']),
    note: 'Уровень безработицы сопоставляется с оговоркой о различиях сезонной корректировки и возрастных границ.',
  },
  population: {
    macroCodes: new Set(['population']),
    regionCodes: new Set(['1.1']),
    note: 'Численность населения сопоставляется по официальным годовым уровням.',
  },
};

export function parseWorldCompareCode(code) {
  const [kind, countrySlug, conceptSlug, ...rest] = String(code || '').split(':');
  if (kind !== 'w' || !countrySlug || !conceptSlug || rest.length) return null;
  return { countrySlug, conceptSlug };
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
    return { allowed: false, reason: 'Этот ряд уже добавлен.' };
  }
  if (!existing.length) return { allowed: true, note: null };

  const candidateWorld = parseWorldCompareCode(candidateCode);
  const existingWorld = existing
    .map(parseWorldCompareCode)
    .filter(Boolean);
  const worldConcepts = new Set(existingWorld.map((item) => item.conceptSlug));

  if (candidateWorld && existingWorld.length && (
    worldConcepts.size !== 1 || !worldConcepts.has(candidateWorld.conceptSlug)
  )) {
    return {
      allowed: false,
      reason: 'Страны можно добавлять только для одного и того же показателя.',
    };
  }

  const conceptSlug = candidateWorld?.conceptSlug || existingWorld[0]?.conceptSlug;
  if (!conceptSlug) return { allowed: true, note: null };

  const bridge = BRIDGES[conceptSlug];
  const nonWorldCodes = existing.filter((code) => !parseWorldCompareCode(code));
  if (!candidateWorld) nonWorldCodes.push(candidateCode);

  if (!nonWorldCodes.length) return { allowed: true, note: null };
  if (!bridge) {
    return {
      allowed: false,
      reason: 'Для этого показателя пока нет доказанной сопоставимости с российскими или региональными рядами.',
    };
  }
  if (!nonWorldCodes.every((code) => isAllowedNonWorld(code, bridge))) {
    return {
      allowed: false,
      reason: 'Выбранный ряд не входит в курируемую сопоставимую группу.',
    };
  }

  return { allowed: true, note: bridge.note, conceptSlug };
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
  const hasNonWorld = codes.some((code) => !parseWorldCompareCode(code));
  return hasNonWorld ? bridge.note : null;
}
