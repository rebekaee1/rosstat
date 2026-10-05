// Подбор «популярных» показателей для карты территорий и группировка остальных по темам.
// Нужен, чтобы над картой не было стены из десятков кнопок вроде «Потребительские расходы по
// функциям: Личная гигиена»: шесть понятных тем сверху, остальное — поиск и аккордеоны по темам.

import { groupUsSections, shortUsIndicatorName } from './usCatalogTopics';

const norm = (s) => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();

// Порядок = приоритет: то, что человек ищет чаще всего.
const POPULAR_PATTERNS = [
  /безработ|unemploy/,
  /доход|income/,
  /населен|population/,
  /инфляц|индекс цен|потребительск\S* цен|price|inflation|cpi/,
  /жиль|ипотек|недвижим|hous|home/,
  /врп|ввп|валов|gdp/,
  /зарплат|заработн|wage|earnings/,
  /бедност|poverty/,
];

const MAX_POPULAR_NAME = 42;

/**
 * Не больше `limit` понятных тем: сначала показатель по умолчанию, затем по списку приоритетов
 * (названия без двоеточия — «разбивки» вроде «Расходы: Личная гигиена» остаются в темах).
 */
export function pickPopularIndicators(indicators, defaultCode, limit = 6) {
  const list = Array.isArray(indicators) ? indicators : [];
  const picked = [];
  const seen = new Set();
  const take = (item) => {
    if (!item || seen.has(item.code) || picked.length >= limit) return;
    seen.add(item.code);
    picked.push(item);
  };
  const plain = (i) => !String(i.name || '').includes(':') && String(i.name || '').length <= MAX_POPULAR_NAME;
  take(list.find((i) => i.code === defaultCode && plain(i)));
  for (const re of POPULAR_PATTERNS) {
    const match = list
      .filter((i) => plain(i) && re.test(norm(i.name)))
      .sort((a, b) => String(a.name).length - String(b.name).length)[0];
    take(match);
  }
  for (const i of list) if (plain(i)) take(i);
  // Если простых названий почти нет — берём как есть, лишь бы набор не был пустым.
  if (picked.length < 3) for (const i of list) take(i);
  return picked;
}

/** Показатели по темам в порядке появления темы; без темы — в `fallbackName`. */
export function groupIndicatorsByTopic(indicators, fallbackName = '') {
  const groups = [];
  const index = new Map();
  for (const item of Array.isArray(indicators) ? indicators : []) {
    const name = item.section || fallbackName;
    if (!index.has(name)) {
      const g = { name, items: [] };
      index.set(name, g);
      groups.push(g);
    }
    index.get(name).items.push(item);
  }
  return groups;
}

export function buildTopicGroups({ indicators, sections, usTopics, locale, fallbackName }) {
  const covered = Array.isArray(sections)
    ? sections.reduce((n, sec) => n + (sec.indicators?.length || 0), 0)
    : 0;
  // Темы США берём только если разделы покрывают весь список; иначе — группировка по названию раздела.
  if (usTopics && covered > 0 && covered >= (indicators?.length || 0)) {
    return groupUsSections(sections, locale).map((g) => ({
      id: g.id,
      name: g.label,
      count: g.count,
      blocks: g.sections.map((sec) => ({
        title: sec.name,
        items: (sec.indicators || []).map((i) => ({ code: i.code, name: shortUsIndicatorName(i.name, sec.name, locale) })),
      })),
    }));
  }
  return groupIndicatorsByTopic(indicators, fallbackName).map((g) => ({
    id: g.name,
    name: g.name,
    count: g.items.length,
    blocks: [{ title: '', items: g.items }],
  }));
}
