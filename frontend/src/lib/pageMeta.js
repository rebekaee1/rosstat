/**
 * Клиентское зеркало серверных PAGE_META / CATEGORY_META / world SEO.
 * Источник: backend → scripts/export-page-meta.py → pageMeta.generated.json.
 * Не дублировать строки здесь — править seo_content.py / seo_world.py и
 * перегенерировать зеркало.
 */
import { resolveBrowserLocale } from '../i18n/locale';
import pageMeta from './pageMeta.generated.json';

/** @param {'ru'|'en'|undefined} locale — omit → browser (?preview_locale / host). */
function resolvePageMetaLocale(locale) {
  if (locale === 'en' || locale === 'ru') return locale;
  return resolveBrowserLocale();
}

/** @param {'ru'|'en'} [locale] — EN twin from pageMeta.en when filled. */
export function getPageSeo(slug, locale) {
  if (resolvePageMetaLocale(locale) === 'en') {
    return pageMeta.en?.pages?.[slug] || pageMeta.pages[slug] || null;
  }
  return pageMeta.pages[slug] || null;
}

/** @param {'ru'|'en'} [locale] */
export function getCategorySeo(slug, locale) {
  if (resolvePageMetaLocale(locale) === 'en') {
    return pageMeta.en?.categories?.[slug] || pageMeta.categories[slug] || null;
  }
  return pageMeta.categories[slug] || null;
}

/** @param {'ru'|'en'} [locale] */
export function getWorldHomeSeo(locale) {
  if (resolvePageMetaLocale(locale) === 'en' && pageMeta.en?.world?.home) {
    return pageMeta.en.world.home;
  }
  return pageMeta.world.home;
}

/** Подмешивает SEO-поля CATEGORY_META в UI-карточки категорий. */
export function withCategorySeo(defs) {
  return defs.map((def) => {
    const seo = pageMeta.categories[def.slug];
    if (!seo) {
      throw new Error(`pageMeta: нет категории ${def.slug}`);
    }
    return {
      ...def,
      name: seo.name,
      seoTitle: seo.title,
      seoDescription: seo.description,
      seoH1: seo.h1,
    };
  });
}

export function worldCountryGenitive(slug, nameRu) {
  return pageMeta.world.countryGenitive[slug] || nameRu || '';
}

/** «1 показатель» / «22 показателя» / «105 показателей» — как seo_world._n_indicators_phrase. */
export function worldIndicatorsPhrase(n, locale) {
  const count = Math.abs(Number(n) || 0);
  if (resolvePageMetaLocale(locale) === 'en') {
    const worldEn = pageMeta.en?.world || {};
    const tpl = count === 1
      ? (worldEn.nIndicatorsOne || '{n} indicator')
      : (worldEn.nIndicatorsMany || '{n} indicators');
    return tpl.replace('{n}', String(count));
  }
  const mod10 = count % 10;
  const mod100 = count % 100;
  let word = 'показателей';
  if (mod10 === 1 && mod100 !== 11) word = 'показатель';
  else if (mod10 >= 2 && mod10 <= 4 && ![12, 13, 14].includes(mod100)) word = 'показателя';
  return `${count} ${word}`;
}

/**
 * H1 / document.title страницы страны.
 * EN: WORLD_TEMPLATES_EN.country_title («Economy of {country}: …»).
 * RU: родительный шаблон countryTitleTemplate.
 * @param {string} slug
 * @param {string} name — locale-facing имя (EN: name_en / API name)
 * @param {'ru'|'en'} [locale]
 */
export function worldCountryTitle(slug, name, locale) {
  const loc = resolvePageMetaLocale(locale);
  if (loc === 'en') {
    const tpl = pageMeta.en?.world?.countryTitleTemplate
      || 'Economy of {country}: statistics and indicators';
    return tpl.replace('{country}', name || '');
  }
  const genitive = worldCountryGenitive(slug, name);
  return pageMeta.world.countryTitleTemplate.replace('{genitive}', genitive);
}

/**
 * Описание страницы страны — те же шаблоны, что SSR в seo_world.
 * hasNational + sourcePhrase: если есть non-eurostat ряды.
 * @param {'ru'|'en'} [opts.locale]
 */
export function worldCountryDescription(slug, nameRu, indicatorCount, {
  hasNational = false,
  sourcePhrase = 'Евростат',
  locale,
} = {}) {
  const loc = resolvePageMetaLocale(locale);
  const name = nameRu || '';
  const nPhrase = worldIndicatorsPhrase(indicatorCount, loc);
  if (loc === 'en') {
    const worldEn = pageMeta.en?.world || {};
    const template = hasNational
      ? (worldEn.countryDescNationalTemplate
        || '{country}: {n_phrase} — prices, GDP, labor market, trade, and finance. '
          + 'Source: {source_phrase}. Charts and latest values on Forecast Economy.')
      : (worldEn.countryDescEurostatTemplate
        || '{country}: {n_phrase} from Eurostat — prices, GDP, labor market, trade, '
          + 'and finance. Charts and latest values on Forecast Economy.');
    return template
      .replace('{country}', name)
      .replace('{name}', name)
      .replace('{n_phrase}', nPhrase)
      .replace('{source_phrase}', sourcePhrase);
  }
  const template = hasNational
    ? pageMeta.world.countryDescNationalTemplate
    : pageMeta.world.countryDescEurostatTemplate;
  return template
    .replace('{name}', name)
    .replace('{n_phrase}', nPhrase)
    .replace('{source_phrase}', sourcePhrase);
}

export default pageMeta;
