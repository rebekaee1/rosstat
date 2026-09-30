/**
 * Общий deterministic ranking для уже допустимого набора результатов.
 * Все значимые слова обязательны: alias не стирает страну, вариант или частоту.
 * Веса exact/prefix/alias/edit-distance не требуют внешней модели/запроса.
 */

const TOKEN_RE = /[^a-z0-9а-я]+/g;
const TOKEN_CHAR_RE = /[a-z0-9а-я]/;

export function normalizeSearchQuery(raw) {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .normalize('NFC')
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
  { targets: ['gdp', 'gdp-nominal', 'gdp-real', 'gdp-volume-quarterly', 'gdp-volume-annual'], keys: ['ввп', 'gdp', 'валовой продукт'] },
  { targets: ['valovoy-regionalnyy-produkt', 'real-gdp'], keys: ['врп', 'grp', 'gross regional product'] },
  { targets: ['gdp-per-capita', 'gdp-per-capita-usd', 'gdp-per-capita-eu', 'weo-gdp-per-capita-usd'], keys: ['ввп на душу', 'gdp per capita', 'per capita', 'на душу'] },
  { targets: ['key-rate'], keys: ['ставка цб', 'ключевая ставка', 'ключевая', 'key rate', 'cbr rate', 'ставка'] },
  { targets: ['fuel'], keys: ['бензин', 'gasoline', 'petrol', 'топливо', 'аи'] },
  { targets: ['fuel-ai95'], keys: ['бензин 95', 'аи-95', 'аи95', 'ai95', 'ai-95'] },
  { targets: ['fuel-ai92'], keys: ['бензин 92', 'аи-92', 'аи92', 'ai92', 'ai-92'] },
  { targets: ['fuel-diesel'], keys: ['дизель', 'солярка', 'diesel'] },
  { targets: ['unemployment', 'unemployment-rate', 'uroven-bezrabotitsy'], keys: ['безработица', 'unemployment', 'безработ'] },
  { targets: ['wages', 'wages-nominal', 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy'], keys: ['зарплата', 'зпл', 'з/п', 'заработная', 'wages', 'salary', 'зп'] },
  { targets: ['minimum-wage', 'mrot'], keys: ['мрот', 'минимальная зарплата', 'minimum wage'] },
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
  { targets: ['government-debt', 'weo-government-debt-gdp', 'budget'], keys: ['госдолг', 'гос долг', 'government debt'] },
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

function itemCodes(ind) {
  const raw = [ind.code, ind.concept_slug, ind.concept, ind.value, ind.slug, ...(Array.isArray(ind.search_codes) ? ind.search_codes : [])]
    .filter((c) => typeof c === 'string').map(normalizeSearchQuery);
  // National passports prefix the statistical code with a two-letter country
  // code. Require supplied country identity before interpreting that prefix.
  return ind.country_slug
    ? unique([...raw, ...raw.filter((code) => /^[a-z]{2}-/.test(code)).map((code) => code.slice(3))])
    : raw;
}

export function codeMatchesTargets(codeOrItem, targets) {
  if (!targets?.length) return false;
  const codes = typeof codeOrItem === 'string' || codeOrItem == null
    ? [String(codeOrItem || '').toLowerCase()]
    : itemCodes(codeOrItem);
  return codes.some((c) => c && targets.some((t) => c === t || c.startsWith(`${t}-`)));
}

const STOP_WORDS = new Set(['в', 'во', 'на', 'по', 'к', 'и', 'с', 'со', 'за', 'для', 'the', 'of', 'in', 'on', 'at', 'and', 'a', 'an', 'to', 'for']);
const FREQUENCY_TERMS = {
  daily: 'daily day days ежедневно дневной день дням',
  weekly: 'weekly week weeks еженедельно недельный неделя неделям',
  monthly: 'monthly month months ежемесячно месячный месяц месяцам',
  quarterly: 'quarterly quarter quarters квартально квартальный квартал кварталам',
  annual: 'annual annually yearly year years ежегодно годовой год годам',
};
// Aliases extend identity fields only. A metric name mentioning a country is
// not sufficient to claim that identity. Unknown countries still match their
// own supplied bilingual labels/slugs without requiring this convenience map.
const GEO_ALIASES = {
  russia: 'Россия России Russian Federation РФ RF RU',
  'united-states': 'United States United States of America USA US США Соединенные Штаты Америки',
  'united-kingdom': 'United Kingdom UK GB Britain Великобритания Великобритании Британия Англия',
  germany: 'Germany Deutschland Германия Германии DE',
  france: 'France Франция Франции FR',
  austria: 'Austria Австрия Австрии AT',
  italy: 'Italy Италия Италии IT',
  spain: 'Spain Испания Испании ES',
  poland: 'Poland Польша Польши PL',
  sweden: 'Sweden Швеция Швеции SE',
  norway: 'Norway Норвегия Норвегии NO',
  finland: 'Finland Финляндия Финляндии FI',
  netherlands: 'Netherlands Holland Нидерланды Нидерландов Голландия NL',
  belgium: 'Belgium Бельгия Бельгии BE',
  switzerland: 'Switzerland Швейцария Швейцарии CH',
  canada: 'Canada Канада Канады CA',
  australia: 'Australia Австралия Австралии AU',
  japan: 'Japan Япония Японии JP',
  'south-korea': 'South Korea Южная Корея Южной Кореи KR',
  brazil: 'Brazil Бразилия Бразилии BR',
  mexico: 'Mexico Мексика Мексики MX',
  china: 'China Китай Китая CN',
  india: 'India Индия Индии IN',
  moskva: 'Москва Москвы Moscow',
  'sankt-peterburg': 'Санкт-Петербург Санкт-Петербурга СПб Петербург Saint Petersburg St Petersburg',
  'respublika-tatarstan': 'Татарстан Татарстана Tatarstan',
  'krasnodarskiy-kray': 'Краснодарский край Краснодарского края Krasnodar Krai',
  california: 'California Калифорния Калифорнии CA',
  'new-york': 'New York Нью-Йорк Нью-Йорка NY',
  texas: 'Texas Техас Техаса TX',
  florida: 'Florida Флорида Флориды FL',
  'district-of-columbia': 'District of Columbia Washington DC Округ Колумбия Округа Колумбия',
};
const LAYOUT_LATIN = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`";
const LAYOUT_CYRILLIC = 'йцукенгшщзхъфывапролджэячсмитьбюе';

export function correctSearchKeyboardLayout(raw) {
  const text = normalizeSearchQuery(raw);
  const from = /[а-я]/.test(text) ? LAYOUT_CYRILLIC : LAYOUT_LATIN;
  const to = from === LAYOUT_LATIN ? LAYOUT_CYRILLIC : LAYOUT_LATIN;
  return [...text].map((ch) => {
    const index = from.indexOf(ch);
    return index < 0 ? ch : to[index];
  }).join('');
}

function tokenize(text) {
  return normalizeSearchQuery(text).split(TOKEN_RE).filter(Boolean);
}

function oneEdit(a, b) {
  return a.length >= 4 && b.length >= 4
    && Math.abs(a.length - b.length) <= 1 && damerauLevenshtein(a, b) <= 1;
}

function russianStem(token) {
  // Inflection only, no generic semantic substitutions. Keep at least five
  // letters so short abbreviations and different statistical terms stay exact.
  if (!/^[а-я]{6,}$/.test(token)) return token;
  const stem = token.replace(/(?:иями|ями|ами|ого|ему|ому|иях|ах|ях|ов|ев|ий|ый|ая|яя|ое|ее|ые|ие|ам|ям|ом|ем|ой|ей|ы|и|а|я|у|ю|е)$/u, '');
  return stem.length >= 5 ? stem : token;
}

const COUNT_WORDS = new Set(['количество', 'численность', 'число', 'count', 'number']);

// Longest intents consume their own words; remaining qualifiers are separate
// required terms. "GDP per capita Germany" cannot fall back to any GDP row.
function queryUnits(q) {
  if (SEARCH_SYNONYMS[q]) return [{ text: q, targets: SEARCH_SYNONYMS[q] }];
  const words = tokenize(q);
  const consumed = new Set();
  const units = [];
  for (const alias of SYNONYM_KEYS) {
    const parts = tokenize(alias);
    if (!parts.length) continue;
    for (let i = 0; i <= words.length - parts.length; i += 1) {
      if (parts.some((_part, offset) => consumed.has(i + offset))) continue;
      const exact = parts.every((part, offset) => words[i + offset] === part);
      const partial = parts.length === 1 && words.length === 1 && words[i].length >= 3 && parts[0].startsWith(words[i]);
      const inflection = parts.length === 1 && russianStem(words[i]) === russianStem(parts[0]);
      const typo = parts.length === 1 && oneEdit(words[i], parts[0]);
      if (!exact && !partial && !typo && !inflection) continue;
      parts.forEach((_part, offset) => consumed.add(i + offset));
      units.push({ text: words.slice(i, i + parts.length).join(' '), targets: SEARCH_SYNONYMS[alias], corrected: !exact });
      break;
    }
  }
  words.forEach((word, index) => {
    if (!consumed.has(index) && !STOP_WORDS.has(word)) units.push({ text: word });
  });
  return units;
}

function strings(values) {
  return values.flatMap((value) => Array.isArray(value) ? value : [value])
    .filter((value) => typeof value === 'string' || typeof value === 'number')
    .map(normalizeSearchQuery).filter(Boolean);
}

function searchDocument(item, searchKind) {
  const codes = itemCodes(item);
  const names = strings([item.name, item.name_ru, item.name_en, item.label, item.search_label]);
  const geoSlug = searchKind === 'country' || searchKind === 'region'
    ? (item.slug || item.value || item.country_slug || item.region_slug)
    : null;
  const identities = [item.country_slug, item.region_slug, geoSlug];
  const aliases = identities.map((identity) => GEO_ALIASES[identity]).filter(Boolean);
  const metadata = strings([
    item.category, item.category_ru, item.section, item.section_name, item.section_ru, item.section_en,
    item.seo_keywords, item.keywords, item.search_aliases, item.search_context,
    item.country_name, item.country_name_en, item.country_code,
    item.region_name, item.region_name_en, item.region_code,
    item.unit, item.unit_ru, item.unit_en, item.frequency, FREQUENCY_TERMS[item.frequency],
    ...(Array.isArray(item.search_frequencies) ? item.search_frequencies : []).map((frequency) => FREQUENCY_TERMS[frequency] || frequency),
    item.mode, item.group, item.hint, ...identities, ...aliases,
  ]);
  // Human vocabulary for materialized generic siblings; this describes the
  // row's existing representation, never invents an unavailable aggregation.
  if (codes.some((c) => /(?:^|-)avg(?:-|$)/.test(c))) metadata.push('средняя среднее average mean');
  if (codes.some((c) => /(?:^|-)yoy(?:-|$)/.test(c))) metadata.push('год к году годовой рост year on year yoy');
  return { item, codes, names, metadata, nameTokens: names.flatMap(tokenize), metaTokens: [...codes, ...metadata].flatMap(tokenize) };
}

function lexicalTermScore(term, doc) {
  const words = tokenize(term);
  if (!words.length) return -1;
  const scoreToken = (word) => {
    if (doc.nameTokens.includes(word) || doc.codes.includes(word)) return 100;
    if (word.length >= 2 && doc.nameTokens.some((token) => token.startsWith(word))) return 82;
    if (doc.metaTokens.includes(word)) return 65;
    if (word.length >= 2 && doc.metaTokens.some((token) => token.startsWith(word))) return 52;
    const stem = russianStem(word);
    if (stem.length >= 5 && doc.nameTokens.some((token) => russianStem(token) === stem)) return 72;
    if (stem.length >= 5 && doc.metaTokens.some((token) => russianStem(token) === stem)) return 45;
    if (COUNT_WORDS.has(word) && doc.nameTokens.some((token) => COUNT_WORDS.has(token))) return 65;
    if (doc.nameTokens.some((token) => oneEdit(word, token))) return 35;
    if (doc.metaTokens.some((token) => oneEdit(word, token))) return 25;
    return -1;
  };
  const scores = words.map(scoreToken);
  return scores.some((score) => score < 0) ? -1 : scores.reduce((sum, score) => sum + score, 0) / scores.length;
}

function matchesPercentQualifier(doc, q) {
  if (!q.includes('%')) return true;
  const fields = [...doc.codes, ...doc.names, ...doc.metadata]
    .map((field) => field.replace(/(\d)\s+%/g, '$1%'));
  const amounts = q.match(/\d+(?:[.,]\d+)?\s*%/g) || [];
  if (amounts.length) {
    return amounts.every((amount) => fields.some((field) => hasPhrase(field, amount.replace(/\s/g, ''))));
  }
  return fields.some((field) => field.includes('%'));
}

function scoreDocument(doc, q, units) {
  // A percentage is a literal qualifier. Tokenization must not turn 100% into
  // a loose 100 prefix or silently drop a requested percentage unit.
  if (!matchesPercentQualifier(doc, q)) return -1;
  const exactCode = doc.codes.includes(q);
  const exactName = doc.names.includes(q);
  if (!units.length) return exactCode ? 10000 : exactName ? 9500 : -1;
  let score = 0;
  for (const unit of units) {
    const lexical = lexicalTermScore(unit.text, doc);
    const target = unit.targets && codeMatchesTargets(doc.item, unit.targets)
      ? (doc.codes.some((code) => unit.targets.includes(code)) ? 160 : 120) - (unit.corrected ? 15 : 0)
      : -1;
    const match = Math.max(lexical, target);
    if (match < 0) return -1;
    score += match;
  }
  if (exactCode) return 10000 + score;
  if (exactName) return 9500 + score;
  // Preserve canonical intent above merely matching noisy category/SEO fields.
  return score + (doc.names.some((name) => name.startsWith(q)) ? 20 : 0);
}

/** Rank a supplied eligible pool; preserves objects, full results and stable ties. */
export function filterSearchOptions(options, rawQuery, {
  limit = 0, getSearchItem = (item) => item, searchKind,
} = {}) {
  const list = Array.isArray(options) ? options : [];
  const q = normalizeSearchQuery(rawQuery);
  if (!q) return limit > 0 ? list.slice(0, limit) : list;
  const docs = list.map((item, index) => ({ original: item, index, ...searchDocument(getSearchItem(item) || {}, searchKind) }));
  const units = queryUnits(q);
  let ranked = docs.map((doc) => ({ ...doc, score: scoreDocument(doc, q, units) })).filter((doc) => doc.score >= 0);
  // Layout correction is fallback only: valid short codes/names stay literal.
  if (!ranked.length && /[a-zа-я]{3}/.test(q)) {
    const corrected = correctSearchKeyboardLayout(q);
    if (corrected !== q) {
      const correctedUnits = queryUnits(corrected);
      ranked = docs.map((doc) => ({ ...doc, score: scoreDocument(doc, corrected, correctedUnits) })).filter((doc) => doc.score >= 0);
    }
  }
  ranked.sort((a, b) => b.score - a.score || a.index - b.index);
  const result = ranked.map((doc) => doc.original);
  return limit > 0 ? result.slice(0, limit) : result;
}

/**
 * Ранг: точное имя/код → canonical intent → имя → семейство → метаданные → fuzzy.
 * Ограниченный fuzzy имеет меньший вес; раскладка исправляется только при нуле результатов.
 */
export function filterSearchIndicators(indicators, rawQuery, { limit = 600 } = {}) {
  const q = normalizeSearchQuery(rawQuery);
  if (!q) return [];
  const seen = new Set();
  const results = filterSearchOptions(indicators, q).filter((item) => {
    const key = item.key || item.code || item.concept_slug;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return limit > 0 ? results.slice(0, limit) : results;
}

/** Для мирового /world/search: короткий синоним раскрываем в латинский код. */
export function expandSearchQuery(raw) {
  const q = normalizeSearchQuery(raw);
  if (!q) return '';
  const direct = SEARCH_SYNONYMS[q];
  if (direct?.length) return direct[0];
  return String(raw || '').trim();
}
