/**
 * Клиентский слой поиска ⌘K: нормализация, curated-синонимы, простой fuzzy.
 * Без внешних зависимостей — палитра фильтрует уже загруженный каталог.
 */

const TOKEN_RE = /[^a-z0-9а-я]+/g;
const TOKEN_CHAR_RE = /[a-z0-9а-я]/;

export function normalizeSearchQuery(raw) {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/\s+/g, ' ');
}

function unique(list) {
  return [...new Set(list)];
}

/**
 * Популярный запрос → префиксы кодов (Россия и мировые концепты).
 * Ключи нормализуются при сборке карты. Не копия seo_keywords — только ходовое.
 */
const SYNONYM_GROUPS = [
  { targets: ['cpi', 'inflation', 'hicp-index'], keys: ['ипц', 'cpi', 'ipc', 'инфляция', 'inflation', 'hicp', 'рост цен'] },
  { targets: ['gdp', 'gdp-volume-quarterly', 'gdp-volume-annual'], keys: ['ввп', 'gdp', 'валовой продукт'] },
  { targets: ['gdp-per-capita', 'gdp-per-capita-usd', 'gdp-per-capita-eu'], keys: ['ввп на душу', 'gdp per capita', 'per capita', 'на душу'] },
  { targets: ['key-rate'], keys: ['ставка цб', 'ключевая ставка', 'ключевая', 'key rate', 'cbr rate', 'ставка'] },
  { targets: ['fuel'], keys: ['бензин', 'gasoline', 'petrol', 'топливо', 'аи'] },
  { targets: ['fuel-ai95'], keys: ['бензин 95', 'аи-95', 'аи95', 'ai95', 'ai-95'] },
  { targets: ['fuel-ai92'], keys: ['бензин 92', 'аи-92', 'аи92', 'ai92', 'ai-92'] },
  { targets: ['fuel-diesel'], keys: ['дизель', 'солярка', 'diesel'] },
  { targets: ['unemployment', 'unemployment-rate'], keys: ['безработица', 'unemployment', 'безработ'] },
  { targets: ['wages'], keys: ['зарплата', 'заработная', 'wages', 'salary', 'зп', 'мрот', 'минимальная зарплата', 'minimum wage'] },
  { targets: ['usd-rub'], keys: ['курс доллара', 'доллар', 'usd', 'dollar', 'usdrub'] },
  { targets: ['eur-rub'], keys: ['курс евро', 'евро', 'eur', 'euro'] },
  { targets: ['cny-rub'], keys: ['курс юаня', 'юань', 'cny', 'yuan', 'renminbi'] },
  { targets: ['brent'], keys: ['нефть', 'oil', 'brent', 'crude'] },
  { targets: ['gold-price'], keys: ['золото', 'gold'] },
  { targets: ['btc-usd'], keys: ['биткоин', 'биткойн', 'bitcoin', 'btc'] },
  { targets: ['eth-usd'], keys: ['эфир', 'эфириум', 'ethereum', 'eth'] },
  { targets: ['mortgage-rate'], keys: ['ипотека', 'ипотечн', 'mortgage'] },
  { targets: ['pensioners'], keys: ['пенсии', 'пенсия', 'пенсионер', 'pension'] },
  { targets: ['ipi'], keys: ['ипп', 'промпроизводство', 'промышленность', 'industrial production', 'ipi'] },
  { targets: ['ppi'], keys: ['ицп', 'ppi', 'цены производителей'] },
  { targets: ['imoex'], keys: ['мосбиржа', 'imoex', 'индекс мосбиржи', 'micex'] },
  { targets: ['population'], keys: ['население', 'population', 'демография'] },
  { targets: ['budget'], keys: ['бюджет', 'дефицит', 'budget', 'deficit'] },
  { targets: ['government-debt', 'budget'], keys: ['госдолг', 'гос долг', 'government debt'] },
  { targets: ['retail-trade'], keys: ['розница', 'розничная', 'retail'] },
  { targets: ['natural-gas'], keys: ['газ', 'природный газ', 'gas', 'henry hub'] },
  { targets: ['housing'], keys: ['жилье', 'недвижимость', 'housing', 'квартир'] },
  { targets: ['ruonia'], keys: ['ruonia', 'руония', 'овернайт'] },
  { targets: ['m2', 'm0', 'm1'], keys: ['денежная масса', 'money supply', 'агрегат'] },
  { targets: ['deposit-rate'], keys: ['вклад', 'депозит', 'deposit'] },
];

function buildSynonymMap(groups) {
  const map = Object.create(null);
  for (const { targets, keys } of groups) {
    for (const key of keys) {
      const n = normalizeSearchQuery(key);
      if (!n) continue;
      map[n] = unique([...(map[n] || []), ...targets]);
    }
  }
  return map;
}

export const SEARCH_SYNONYMS = buildSynonymMap(SYNONYM_GROUPS);

const SYNONYM_KEYS = Object.keys(SEARCH_SYNONYMS).sort((a, b) => b.length - a.length);

function isTokenChar(ch) {
  return Boolean(ch) && TOKEN_CHAR_RE.test(ch);
}

function hasPhrase(text, phrase) {
  let from = 0;
  while (from <= text.length) {
    const idx = text.indexOf(phrase, from);
    if (idx === -1) return false;
    const before = idx === 0 || !isTokenChar(text[idx - 1]);
    const afterEnd = idx + phrase.length;
    const after = afterEnd === text.length || !isTokenChar(text[afterEnd]);
    if (before && after) return true;
    from = idx + 1;
  }
  return false;
}

export function resolveSynonymTargets(raw) {
  const q = normalizeSearchQuery(raw);
  if (!q) return [];
  if (SEARCH_SYNONYMS[q]) return SEARCH_SYNONYMS[q];
  const hits = [];
  for (const key of SYNONYM_KEYS) {
    if (q.length >= 3 && key.startsWith(q)) {
      hits.push(...SEARCH_SYNONYMS[key]);
      continue;
    }
    if (q.length >= 3 && key.length >= 3 && hasPhrase(q, key)) {
      hits.push(...SEARCH_SYNONYMS[key]);
    }
  }
  return unique(hits);
}

export function damerauLevenshtein(a, b) {
  if (a === b) return 0;
  const n = a.length;
  const m = b.length;
  if (Math.abs(n - m) > 1) return 2;
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1));
  for (let i = 0; i <= n; i += 1) dp[i][0] = i;
  for (let j = 0; j <= m; j += 1) dp[0][j] = j;
  for (let i = 1; i <= n; i += 1) {
    for (let j = 1; j <= m; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        dp[i][j] = Math.min(dp[i][j], dp[i - 2][j - 2] + 1);
      }
    }
  }
  return dp[n][m];
}

function tokenize(text) {
  return normalizeSearchQuery(text).split(TOKEN_RE).filter((t) => t.length >= 3);
}

function tokenFuzzy(queryToken, hayToken) {
  if (hayToken.startsWith(queryToken) && queryToken.length >= 3) return true;
  if (queryToken.startsWith(hayToken) && hayToken.length >= 3) return true;
  if (queryToken.length >= 4 && hayToken.length >= 4) {
    return damerauLevenshtein(queryToken, hayToken) <= 1;
  }
  return false;
}

function haystackOf(ind) {
  return normalizeSearchQuery(
    `${ind.name || ''} ${ind.name_en || ''} ${ind.category || ''} ${ind.category_ru || ''} ${ind.code || ''} ${ind.seo_keywords || ''} ${ind.concept_slug || ''}`,
  );
}

function itemCodes(ind) {
  return [ind.code, ind.concept_slug, ind.concept].filter(Boolean).map((c) => String(c).toLowerCase());
}

export function codeMatchesTargets(codeOrItem, targets) {
  if (!targets?.length) return false;
  const codes = typeof codeOrItem === 'string' || codeOrItem == null
    ? [String(codeOrItem || '').toLowerCase()]
    : itemCodes(codeOrItem);
  return codes.some((c) => c && targets.some((t) => c === t || c.startsWith(`${t}-`)));
}

function fuzzyMatch(ind, q) {
  const qTokens = tokenize(q);
  if (!qTokens.length) return false;
  const hayTokens = tokenize(haystackOf(ind));
  if (!hayTokens.length) return false;
  return qTokens.every((qt) => hayTokens.some((ht) => tokenFuzzy(qt, ht)));
}

/**
 * Ранжированный фильтр: точная подстрока → синонимы → fuzzy.
 * Fuzzy включается только если точных подстрочных совпадений нет.
 */
export function filterSearchIndicators(indicators, rawQuery, { limit = 600 } = {}) {
  const q = normalizeSearchQuery(rawQuery);
  if (!q) return [];
  const list = Array.isArray(indicators) ? indicators : [];
  const targets = resolveSynonymTargets(q);

  const exact = [];
  const synonym = [];
  for (const ind of list) {
    if (haystackOf(ind).includes(q)) {
      exact.push(ind);
      continue;
    }
    if (codeMatchesTargets(ind, targets)) synonym.push(ind);
  }

  const seen = new Set();
  const out = [];
  const push = (ind) => {
    const key = ind.code || ind.key || ind.concept_slug;
    if (!key || seen.has(key)) return;
    seen.add(key);
    out.push(ind);
  };
  exact.forEach(push);
  synonym.forEach(push);

  if (exact.length === 0) {
    for (const ind of list) {
      const key = ind.code || ind.key || ind.concept_slug;
      if (!key || seen.has(key)) continue;
      if (fuzzyMatch(ind, q)) push(ind);
    }
  }

  return limit > 0 ? out.slice(0, limit) : out;
}

/** Для мирового /world/search: короткий синоним раскрываем в латинский код. */
export function expandSearchQuery(raw) {
  const q = normalizeSearchQuery(raw);
  if (!q) return '';
  const direct = SEARCH_SYNONYMS[q];
  if (direct?.length) return direct[0];
  return String(raw || '').trim();
}
