import { unitSuffix } from './format';

// Заголовок и подписи линий «Сравнения» человеческими словами: «Безработица: Германия и Франция»,
// а не повтор всей легенды («Уровень безработицы — Германия — Уровень безработицы — Франция»).

/** Перечисление «A, B и C» по правилам языка. */
export function joinList(items, locale = 'ru') {
  const list = (items || []).filter(Boolean);
  if (list.length <= 1) return list[0] || '';
  try {
    return new Intl.ListFormat(locale === 'en' ? 'en' : 'ru', { style: 'long', type: 'conjunction' }).format(list);
  } catch {
    const word = locale === 'en' ? 'and' : 'и';
    return `${list.slice(0, -1).join(', ')} ${word} ${list[list.length - 1]}`;
  }
}

/** Короткое название показателя: свой словарь по слагу, иначе название из каталога. */
export function conceptShortLabel(slug, fallback, t) {
  if (!slug) return fallback;
  const text = t(`w6g.concept.${slug}`, '');
  return text || fallback;
}

/**
 * series: [{ name, isWorld, ind: { conceptSlug, conceptName, countryName } }].
 * Возвращает { headline, labels }: подписи линий (по порядку рядов) и заголовок графика.
 * Мировые ряды с общим показателем: «Показатель: страна и страна», линии подписаны странами;
 * с общей страной: «Страна: показатель и показатель», линии подписаны показателями;
 * иначе заголовок собран из названий через «и», а линии подписаны полными названиями.
 */
export function compareLabels(series, { t, locale = 'ru', fallback = '' }) {
  const items = (series || []).filter(Boolean);
  const names = items.map((s) => s.name || fallback);
  if (!items.length) return { headline: fallback, labels: [] };
  const worldInfo = items.map((s) => (s.isWorld && s.ind?.countryName && s.ind?.conceptName
    ? {
      country: s.ind.countryName,
      concept: conceptShortLabel(s.ind.conceptSlug, s.ind.conceptName, t),
    }
    : null));
  if (items.length > 1 && worldInfo.every(Boolean)) {
    const concepts = [...new Set(worldInfo.map((w) => w.concept))];
    const countries = [...new Set(worldInfo.map((w) => w.country))];
    if (concepts.length === 1) {
      return {
        headline: `${concepts[0]}: ${joinList(countries, locale)}`,
        labels: worldInfo.map((w) => w.country),
      };
    }
    if (countries.length === 1) {
      return {
        headline: `${countries[0]}: ${joinList(concepts, locale)}`,
        labels: worldInfo.map((w) => w.concept),
      };
    }
  }
  if (items.length === 1 && worldInfo[0]) {
    return {
      headline: `${worldInfo[0].concept}: ${worldInfo[0].country}`,
      labels: [worldInfo[0].country],
    };
  }
  return { headline: joinList(names, locale), labels: names };
}

const UNIT_WORDS = {
  '‰': { ru: 'на 1000 жителей', en: 'per 1,000 people' },
  'USD/баррель': { ru: '$ за баррель', en: '$ per barrel' },
  'USD/barrel': { ru: '$ за баррель', en: '$ per barrel' },
};

/** Единица рядом с названием в списке: словами там, где знак непонятен («‰» -> «на 1000 жителей»). */
export function unitHint(unit, locale = 'ru') {
  const words = UNIT_WORDS[unit];
  if (words) return words[locale === 'en' ? 'en' : 'ru'];
  return unitSuffix(unit);
}
