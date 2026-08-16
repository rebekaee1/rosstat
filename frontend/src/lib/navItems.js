/**
 * Пункты главного меню — один источник для десктопа и мобилки.
 *
 * Живут отдельно от `Navbar.jsx`: файл компонента должен экспортировать только
 * компонент, иначе ломается горячая перезагрузка при разработке.
 */

export const WORLD_RATING_TO = '/world/rating/unemployment-rate';

/**
 * `match` — префикс пути для подсветки; побеждает самый длинный матч
 * (чтобы /world/rating/... не подсвечивал «Мировая экономика»).
 */
export const PRIMARY_NAV = [
  { id: 'world-rating', to: WORLD_RATING_TO, match: '/world/rating', label: 'Рейтинг стран' },
  { id: 'world', to: '/world', match: '/world', label: 'Мировая экономика' },
  { id: 'compare', to: '/compare', match: '/compare', label: 'Сравнение', desktopOnlyXl: true },
];

/** Самый длинный совпавший префикс среди пунктов; граница сегмента обязательна. */
export function resolveActiveNavId(pathname, items = PRIMARY_NAV) {
  let bestId = null;
  let bestLen = -1;
  for (const item of items) {
    const prefix = item.match || item.to;
    const hit = pathname === prefix || pathname.startsWith(`${prefix}/`);
    if (hit && prefix.length > bestLen) {
      bestLen = prefix.length;
      bestId = item.id;
    }
  }
  return bestId;
}
