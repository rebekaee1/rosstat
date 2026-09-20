/**
 * Пункты главного меню — один источник для десктопа и мобилки.
 *
 * Живут отдельно от `Navbar.jsx`: файл компонента должен экспортировать только
 * компонент, иначе ломается горячая перезагрузка при разработке.
 */

import {
  comparePath,
  countryPath,
  homePath,
  russiaHomePath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';

export const UNITED_STATES_SLUG = 'united-states';

export const WORLD_RATING_TO = worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT);

/**
 * `match` — префикс пути для подсветки; побеждает самый длинный матч.
 * `exact` — только для главной: префикс «/» иначе совпал бы со всем сайтом.
 * `shortLabelKey` — подпись до xl: в пилюлю не влезает полное название, а
 * прятать сам пункт нельзя — иначе раздел становится недостижим (overlap
 * логотипа ловится только `scripts/e2e/navbar-overlap.mjs`).
 */
export const PRIMARY_NAV = [
  { id: 'home', to: homePath(), match: homePath(), exact: true, labelKey: 'common.home' },
  { id: 'russia', to: russiaHomePath(), match: russiaHomePath(), labelKey: 'nav.russia' },
  {
    id: 'united-states',
    to: countryPath(UNITED_STATES_SLUG),
    match: countryPath(UNITED_STATES_SLUG),
    labelKey: 'nav.unitedStates',
    shortLabelKey: 'nav.usa',
  },
  { id: 'world-rating', to: WORLD_RATING_TO, match: '/world/rating', labelKey: 'nav.worldRating' },
  {
    id: 'compare',
    to: comparePath(),
    match: comparePath(),
    labelKey: 'nav.compareIndicators',
    shortLabelKey: 'nav.compare',
  },
];

/**
 * Primary-пункты для локали: RU держит «Россия», EN — «United States»
 * на том же месте. Страницы /russia на EN остаются, но не как главный пункт.
 * Подсветка активного пункта (`resolveActiveNavId`) считается по ПОЛНОМУ
 * PRIMARY_NAV, иначе скрытие ломало бы aria-current на страницах раздела.
 */
export function primaryNav(locale) {
  if (locale === 'en') {
    return PRIMARY_NAV.filter((item) => item.id !== 'russia');
  }
  return PRIMARY_NAV.filter((item) => item.id !== 'united-states');
}

/** Самый длинный совпавший префикс среди пунктов; граница сегмента обязательна. */
export function resolveActiveNavId(pathname, items = PRIMARY_NAV) {
  let bestId = null;
  let bestLen = -1;
  for (const item of items) {
    const prefix = item.match || item.to;
    const hit = item.exact
      ? pathname === prefix
      : pathname === prefix || pathname.startsWith(`${prefix}/`);
    if (hit && prefix.length > bestLen) {
      bestLen = prefix.length;
      bestId = item.id;
    }
  }
  return bestId;
}
