// R6-A: вопрос про работу и доходы без ответа (зарплата врачей, учителей) ведёт к ближайшим рядам, а не к курсу доллара.
const LABOUR_RE = /(зарплат|заработн|оклад|получа|доход|труд|занят|работ|вакан|пенси|пособ|безработ|прожиточ|мрот|salar|wage|pay\b|income|jobs?\b|employ|pension)/i;
const STOP = new Set(['в', 'во', 'на', 'по', 'за', 'для', 'и', 'у', 'из', 'сколько', 'какая', 'какой', 'какие', 'средняя', 'средний', 'the', 'in', 'of', 'for', 'and', 'how', 'much', 'do']);

export function isLabourQuery(query) {
  return LABOUR_RE.test(String(query || ''));
}

// Место из запроса: слова, которые не про работу и не служебные («зарплата врачей самара» → «самара»).
export function placeFromQuery(query) {
  const words = String(query || '').toLowerCase().replace(/ё/g, 'е').match(/[a-zа-я0-9]+/g) || [];
  // Подсказки по-русски: латинские слова места в них не подмешиваем.
  const rest = words.filter((w) => /^[а-я0-9]+$/.test(w) && !LABOUR_RE.test(w) && !STOP.has(w) && !/^(врач|учител|медик|инженер|програм|строител|водител|продавц)/.test(w));
  return rest.slice(-2).join(' ');
}

// R7-A: МРОТ — одна федеральная величина, ряда по региону нет; говорим это прямо, а не про «профессии».
const MROT_RE = /(мрот|минимальн[а-я]* (зарплат|заработн|оплат)|minimum wage)/i;
export function isMrotQuery(query) {
  return MROT_RE.test(String(query || ''));
}

// R7-A: пустая выдача по региону (backend назвал регион) — ближайшие ряды этого региона, а не общий список.
const LOCAL_KEYS = ['r7a.local.cpi', 'r7a.local.wage', 'r7a.local.unemployment', 'r7a.local.population', 'r7a.local.prices', 'r7a.local.housing'];
export function localSuggestions(regionName, t) {
  const place = String(regionName || '').trim();
  if (!place) return [];
  return LOCAL_KEYS.map((key) => `${t(key)} ${place}`);
}

export function labourNoteKey(query) {
  return isMrotQuery(query) ? 'r7a.search.mrotNote' : 'r6a.search.labourNote';
}

export function labourSuggestions(query, t, regionName) {
  if (!isLabourQuery(query)) return [];
  const place = String(regionName || '').trim() || placeFromQuery(query).replace(/(^|\s)([а-я])/g, (m, a, b) => a + b.toUpperCase());
  return ['r6a.labour.wage', 'r6a.labour.unemployment', 'r6a.labour.living', 'r6a.labour.pension', 'r6a.labour.income']
    .map((key) => [String(t(key)), place].filter(Boolean).join(' '));
}

/**
 * «Попробуйте, например» под пустой выдачей (14.11.2026). Запрос назвал регион — подсказки по этому региону
 * («Инфляция Воронежская область», «Зарплата …»), а не курсы валют и популярное по сайту («Курс узбекского сума»
 * под запросом о посевных площадях). Без региона — как раньше: три курса и популярные запросы, без повторов.
 */
export function tryTheseExamples({ suggest = [], regionName, popular = [], t }) {
  // Сервер подобрал соседей по разделу Росстата и региону («Валовой сбор картофеля Воронежская область») — они ближе всего.
  const near = (Array.isArray(suggest) ? suggest : []).filter(Boolean).map(String);
  if (near.length) return near.slice(0, 6);
  const local = localSuggestions(regionName, t);
  if (local.length) return local.slice(0, 6);
  return [...new Set([
    ...['z4s.empty.rate.1', 'z4s.empty.rate.2', 'z4s.empty.rate.3'].map((key) => t(key)),
    ...popular.slice(0, 6),
  ].map((text) => String(text)))].slice(0, 6);
}
