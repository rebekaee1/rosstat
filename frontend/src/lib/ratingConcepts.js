/**
 * Показатели рейтинга стран для человека: группы, значки и короткий заголовок страницы.
 * Список понятий приходит с сервера (`/world/rating/concepts`); здесь только смысловая раскладка
 * по группам и тексты. Неизвестное понятие попадает в группу «Другое» и не пропадает.
 */
import { homeConceptLabel } from './homeWorkbench';
import { MESSAGES } from '../i18n/messages';

export const RATING_GROUPS = Object.freeze([
  {
    id: 'economy',
    labelKey: 'w6d.rating.group.economy',
    slugs: ['gdp-usd', 'gdp-per-capita-usd', 'gdp-per-capita-eu', 'gdp-volume-annual', 'gdp-volume-quarterly'],
  },
  {
    id: 'prices-work',
    labelKey: 'w6d.rating.group.pricesWork',
    slugs: ['hicp-index', 'unemployment-rate', 'activity-rate'],
  },
  {
    id: 'state',
    labelKey: 'w6d.rating.group.state',
    slugs: ['government-debt-gdp', 'budget-balance-gdp', 'long-term-interest-rate', 'policy-rate'],
  },
  {
    id: 'people',
    labelKey: 'w6d.rating.group.people',
    slugs: ['population'],
  },
]);

const OTHER_GROUP = Object.freeze({ id: 'other', labelKey: 'w6d.rating.group.other', slugs: [] });

/** Ключ значка (имя lucide-иконки в компоненте) по понятию. */
export const RATING_ICON_KEYS = Object.freeze({
  'gdp-usd': 'banknote',
  'gdp-per-capita-usd': 'coins',
  'gdp-per-capita-eu': 'scale',
  'gdp-volume-annual': 'banknote',
  'gdp-volume-quarterly': 'banknote',
  'hicp-index': 'trending',
  'unemployment-rate': 'briefcase',
  'activity-rate': 'activity',
  'government-debt-gdp': 'landmark',
  'budget-balance-gdp': 'piggy',
  'long-term-interest-rate': 'percent',
  'policy-rate': 'percent',
  population: 'users',
});

export function ratingIconKey(slug) {
  return RATING_ICON_KEYS[slug] || 'chart';
}

/** Раскладка понятий по группам в порядке RATING_GROUPS; пустые группы не возвращаются. */
export function groupRatingConcepts(concepts = []) {
  const list = (concepts || []).filter((item) => item?.slug);
  const bySlug = new Map(list.map((item) => [item.slug, item]));
  const used = new Set();
  const groups = [];
  for (const group of RATING_GROUPS) {
    const items = group.slugs.map((slug) => bySlug.get(slug)).filter(Boolean);
    items.forEach((item) => used.add(item.slug));
    if (items.length) groups.push({ ...group, items });
  }
  const rest = list.filter((item) => !used.has(item.slug));
  if (rest.length) groups.push({ ...OTHER_GROUP, items: rest });
  return groups;
}

/** Показатели, которые лежат в быстрой полосе рядом с «Все показатели». */
export const RATING_QUICK_SLUGS = Object.freeze(['gdp-usd', 'hicp-index', 'unemployment-rate', 'population']);

export function quickRatingConcepts(concepts = []) {
  const bySlug = new Map((concepts || []).filter((item) => item?.slug).map((item) => [item.slug, item]));
  return RATING_QUICK_SLUGS.map((slug) => bySlug.get(slug)).filter(Boolean);
}

/**
 * Короткий заголовок страницы рейтинга: «ВВП стран мира, 2025» и подзаголовок «в текущих долларах США».
 * Для понятия без своих текстов берётся короткое имя и единица с сервера.
 */
export function ratingHeading(slug, { t, name = '', unit = '', year = null }) {
  const headKey = `w6d.rating.h1.${slug}`;
  const subKey = `w6d.rating.sub.${slug}`;
  const known = Object.prototype.hasOwnProperty.call(MESSAGES.ru, headKey);
  const head = known ? t(headKey) : homeConceptLabel(slug, t, name);
  const title = year != null ? t('w6d.rating.h1Year', { head, year }) : head;
  const subtitle = known && Object.prototype.hasOwnProperty.call(MESSAGES.ru, subKey) ? t(subKey) : String(unit || '');
  return { title, subtitle };
}
