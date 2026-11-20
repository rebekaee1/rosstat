/**
 * Поиск и раздел сайта (круг «Туризм», 20.11.2026, зона z6).
 * Раздел определяется по адресу страницы: из «Туризма» поиск получает свои «Популярное» и просит у сервера
 * туристские ряды страны и региона. Вне раздела всё как раньше.
 */

export const SECTION_TOURISM = 'tourism';

/** Страницы раздела «Туризм»: категория, показатели с кодом `tour…`, их региональные страницы и рейтинги. */
const TOURISM_PATH = /^\/russia\/category\/tourism(?:\/|$)|\/(?:indicator|region-rating)\/tour[\w-]*|\/region\/[^/]+\/tour[\w-]*/i;

/** @returns {'tourism'|null} */
export function searchSectionOf(pathname) {
  const path = String(pathname || '').split(/[?#]/)[0];
  return TOURISM_PATH.test(path) ? SECTION_TOURISM : null;
}

/** Ключи «Популярного» для раздела; null — общий список. */
export const SECTION_EXAMPLE_KEYS = Object.freeze({
  [SECTION_TOURISM]: Object.freeze([
    'kt6_search_example_1',
    'kt6_search_example_2',
    'kt6_search_example_3',
    'kt6_search_example_4',
    'kt6_search_example_5',
    'kt6_search_example_6',
  ]),
});

const CYRILLIC = /[а-яё]/i;
// Два латинских слова подряд: «Tourism in Russia». Одиночные «USD/RUB», «Brent» — не язык, а обозначения.
const LATIN_WORD = /[a-z]{3,}\s+[a-z]{2,}/i;

/** Единый вид для сравнения: регистр, «ё», лишние пробелы. */
const sameKey = (text) => String(text || '').toLocaleLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();

/**
 * Недавно просмотренные страницы для окна поиска: без повторов (по названию и адресу) и на языке интерфейса.
 * Название сохраняется при посещении, поэтому после смены языка в списке остаются страницы на другом языке:
 * в английском интерфейсе скрываются русские названия, в русском — чисто английские.
 */
export function cleanRecentPages(pages, locale = 'ru') {
  const titles = new Set();
  const paths = new Set();
  const out = [];
  for (const page of pages || []) {
    const title = String(page?.title || '');
    const wrongLanguage = locale === 'en'
      ? CYRILLIC.test(title)
      : LATIN_WORD.test(title) && !CYRILLIC.test(title);
    if (wrongLanguage) continue;
    const titleKey = sameKey(title);
    const pathKey = String(page?.path || '').split(/[?#]/)[0];
    if (titles.has(titleKey) || paths.has(pathKey)) continue;
    titles.add(titleKey);
    paths.add(pathKey);
    out.push(page);
  }
  return out;
}

/** Недавние запросы без повторов с точностью до регистра, «ё» и пробелов; страницы с тем же названием не дублируют запросы. */
export function cleanRecentQueries(queries, pages = []) {
  const seen = new Set((pages || []).map((page) => sameKey(page?.title)));
  const out = [];
  for (const text of queries || []) {
    const key = sameKey(text);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(text);
  }
  return out;
}
