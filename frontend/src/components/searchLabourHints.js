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

export function labourSuggestions(query, t) {
  if (!isLabourQuery(query)) return [];
  const place = placeFromQuery(query);
  return ['r6a.labour.wage', 'r6a.labour.unemployment', 'r6a.labour.living', 'r6a.labour.pension', 'r6a.labour.income']
    .map((key) => [String(t(key)), place].filter(Boolean).join(' '));
}
