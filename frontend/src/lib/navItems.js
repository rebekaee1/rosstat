/**
 * Пункты главного меню — один источник для десктопа и мобилки.
 *
 * Живут отдельно от `Navbar.jsx`: файл компонента должен экспортировать только
 * компонент, иначе ломается горячая перезагрузка при разработке.
 */

import {
  calendarPath,
  comparePath,
  countryPath,
  homePath,
  regionHubPath,
  russiaHomePath,
  todayPath,
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

/**
 * Меню телефона: те же разделы, что в шапке без JS и на статических страницах (Сегодня, Регионы, Страны,
 * Календарь), но сгруппированные. Десктопная пилюля всех не вмещает, поэтому длинный список живёт только здесь.
 * `icon` — имя значка (Navbar сопоставляет его с lucide), `to` с хешем ведёт к каталогу стран на главной.
 */
export function mobileNavGroups(locale) {
  const primary = primaryNav(locale);
  const byId = Object.fromEntries(primary.map((item) => [item.id, item]));
  const main = [
    { id: 'home', icon: 'home', ...byId.home },
    { id: 'countries', icon: 'globe', to: '/#countries', match: '/#countries', labelKey: 'shell.nav.countries' },
    { id: 'world-rating', icon: 'chart', ...byId['world-rating'] },
    { id: 'compare', icon: 'compare', ...byId.compare },
  ];
  if (byId['united-states']) {
    main.splice(2, 0, { id: 'united-states', icon: 'flag', ...byId['united-states'] });
  }
  const russiaItems = [
    { id: 'today', icon: 'clock', to: todayPath(), match: todayPath(), labelKey: 'shell.nav.today' },
    { id: 'regions', icon: 'map', to: regionHubPath(), match: regionHubPath(), labelKey: 'shell.nav.regions' },
    { id: 'calendar', icon: 'calendar', to: calendarPath(), match: calendarPath(), labelKey: 'shell.nav.calendar' },
  ];
  if (byId.russia) russiaItems.unshift({ id: 'russia', icon: 'landmark', ...byId.russia });
  return [
    { id: 'main', titleKey: null, items: main },
    { id: 'russia', titleKey: 'shell.nav.groupRussia', items: russiaItems },
  ];
}
