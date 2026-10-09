/**
 * Предметы для кнопок кабинета (круг 11, F): страница называет, что можно сохранить и за чем следить, а кнопки
 * («В избранное» — SaveButton, «Следить» — WatchButton) рисует зона кабинета через `CabinetActionsSlot`.
 * Виды и ключи совпадают с договорённостью `lib/cabinetItems.js` (indicator | world | country | region | rating_view).
 * Ничего не хранит и не вызывает сеть.
 */
import {
  countryPath, indicatorPath, regionIndicatorPath, regionPath, russiaIndicatorPath, worldRatingPath, worldRatingYearPath,
} from './sitePaths';

const clean = (title) => (typeof title === 'string' ? title.trim().slice(0, 200) : '');

/**
 * Российский показатель (`/russia/indicator/{code}`). `only: 'watch'` просит нарисовать один колокольчик «Следить»
 * без «В избранное» (событие календаря).
 */
export function russiaIndicatorSubject(code, title, { only = null } = {}) {
  if (!code) return null;
  return {
    ...(only ? { only } : {}),
    kind: 'indicator',
    itemKey: String(code),
    title: clean(title),
    payload: { path: russiaIndicatorPath(code) },
    watch: { subjectKind: 'indicator', subjectKey: String(code) },
  };
}

/** Показатель страны мира (`/{страна}/indicator/{code}`). */
export function worldIndicatorSubject(countrySlug, code, title) {
  if (!countrySlug || !code) return null;
  return {
    kind: 'world',
    itemKey: String(code),
    title: clean(title),
    payload: { path: indicatorPath(countrySlug, code), country_slug: countrySlug },
    watch: { subjectKind: 'world', subjectKey: String(code), countrySlug },
  };
}

/** Страна. */
export function countrySubject(slug, title) {
  if (!slug) return null;
  return { kind: 'country', itemKey: String(slug), title: clean(title), payload: { path: countryPath(slug) }, watch: null };
}

/** Регион России (профиль). */
export function regionSubject(slug, title) {
  if (!slug) return null;
  return { kind: 'region', itemKey: String(slug), title: clean(title), payload: { path: regionPath(slug) }, watch: null };
}

/** Региональный показатель: слежение идёт за рядом региона. */
export function regionIndicatorSubject(regionSlug, code, title) {
  if (!regionSlug || !code) return null;
  return {
    kind: 'region',
    itemKey: String(regionSlug),
    title: clean(title),
    payload: { path: regionIndicatorPath(regionSlug, code) },
    watch: { subjectKind: 'region', subjectKey: String(code), regionSlug },
  };
}

/**
 * Вид рейтинга: показатель, год, группа и добавленные колонки. Ключ одинаков для одного и того же набора,
 * поэтому повторное сохранение не плодит копии.
 */
export function ratingViewSubject({ concept, year = null, group = 'all', cols = [], title = '' } = {}) {
  if (!concept) return null;
  const parts = [concept];
  if (group && group !== 'all') parts.push(`group=${group}`);
  if (cols.length) parts.push(`cols=${cols.join(',')}`);
  const path = year ? worldRatingYearPath(concept, year) : worldRatingPath(concept);
  const query = [group && group !== 'all' ? `group=${group}` : '', cols.length ? `cols=${cols.join(',')}` : '']
    .filter(Boolean).join('&');
  return {
    kind: 'rating_view',
    itemKey: parts.join('|'),
    title: clean(title),
    payload: { path: query ? `${path}?${query}` : path, cols, group },
    watch: null,
  };
}
