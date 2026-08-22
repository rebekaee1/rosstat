/**
 * Пункты главного меню — один источник для десктопа и мобилки.
 *
 * Живут отдельно от `Navbar.jsx`: файл компонента должен экспортировать только
 * компонент, иначе ломается горячая перезагрузка при разработке.
 */

import {
  comparePath,
  homePath,
  russiaHomePath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';

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
  { id: 'world-rating', to: WORLD_RATING_TO, match: '/world/rating', labelKey: 'nav.worldRating' },
  {
    id: 'compare',
    to: comparePath(),
    match: comparePath(),
    labelKey: 'nav.compareIndicators',
    shortLabelKey: 'nav.compare',
  },
];

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
