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
  forecastsPath,
  homePath,
  regionHubPath,
  russiaCategoriesPath,
  russiaCategoryPath,
  russiaHomePath,
  todayPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';

export const UNITED_STATES_SLUG = 'united-states';

export const WORLD_RATING_TO = worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT);

/** «Курсы валют»: страница с курсами ЦБ, рынком и конвертером. */
export const RATES_TO = russiaCategoryPath('currencies');

/** Раздел «Прогнозы»: настоящая страница-витрина; объяснение метода остаётся второй ссылкой «Как мы считаем». */
export const FORECASTS_TO = forecastsPath();

/**
 * `match` — префикс пути для подсветки; побеждает самый длинный матч.
 * `exact` — только для главной: префикс «/» иначе совпал бы со всем сайтом.
 * `shortLabelKey` — подпись до xl: в пилюлю не влезает полное название, а
 * прятать сам пункт нельзя — иначе раздел становится недостижим (overlap
 * логотипа ловится только `scripts/e2e/navbar-overlap.mjs`).
 * `hintKey` — подпись под пунктом в меню телефона и планшета («что внутри»).
 * Главная не пункт меню: на неё ведёт логотип. Меню мировое: страны, рейтинг, сравнение, прогнозы;
 * Россия — один раскрывающийся раздел, а не половина списка.
 */
export const PRIMARY_NAV = [
  { id: 'home', to: homePath(), match: homePath(), exact: true, labelKey: 'common.home' },
  {
    id: 'countries',
    to: '/#countries',
    match: '/#countries',
    labelKey: 'w6b.nav.countries',
    shortLabelKey: 'w6b.nav.countriesShort',
    hintKey: 'w6b.nav.countries.hint',
    icon: 'globe',
  },
  {
    id: 'world-rating',
    to: WORLD_RATING_TO,
    match: '/world/rating',
    labelKey: 'nav.worldRating',
    shortLabelKey: 'w6b.nav.ratingShort',
    hintKey: 'w6b.nav.rating.hint',
    icon: 'chart',
  },
  {
    id: 'compare',
    to: comparePath(),
    match: comparePath(),
    labelKey: 'nav.compare',
    hintKey: 'w6b.nav.compare.hint',
    icon: 'compare',
  },
  {
    id: 'forecasts',
    to: FORECASTS_TO,
    match: '/forecasts',
    labelKey: 'w6b.nav.forecasts',
    hintKey: 'w6b.nav.forecasts.hint',
    icon: 'trend',
  },
  {
    id: 'currencies',
    to: RATES_TO,
    match: RATES_TO,
    labelKey: 'z2.nav.rates',
    shortLabelKey: 'z2.nav.ratesShort',
    hintKey: 'w6b.nav.currencies.hint',
    icon: 'coins',
  },
  { id: 'russia', to: russiaHomePath(), match: russiaHomePath(), labelKey: 'nav.russia' },
  {
    id: 'united-states',
    to: countryPath(UNITED_STATES_SLUG),
    match: countryPath(UNITED_STATES_SLUG),
    labelKey: 'nav.unitedStates',
    shortLabelKey: 'nav.usa',
  },
];

/** Пункты верхней пилюли (десктоп): без главной, RU держит «Россия», EN — «США» на том же месте. */
export function primaryNav(locale) {
  const hidden = new Set(['home', locale === 'en' ? 'russia' : 'united-states']);
  return PRIMARY_NAV.filter((item) => !hidden.has(item.id));
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
 * Меню телефона и планшета. Сверху мировые разделы (страны, рейтинг, сравнение, прогнозы, категории, валюты,
 * «Как мы считаем»), у каждого короткая подпись. Россия одной раскрывающейся строкой; калькуляторы и
 * «О проекте» рисует Navbar. `icon` — имя значка (Navbar сопоставляет его с lucide).
 */
export function mobileNavGroups(locale) {
  const byId = Object.fromEntries(PRIMARY_NAV.map((item) => [item.id, item]));
  const main = [
    byId.countries,
    byId['world-rating'],
    byId.compare,
    byId.forecasts,
    {
      id: 'categories', icon: 'layers', to: russiaCategoriesPath(), match: russiaCategoriesPath(),
      labelKey: 'w6b.nav.categories', hintKey: 'w6b.nav.categories.hint',
    },
    {
      id: 'currencies', icon: 'coins', to: russiaCategoryPath('currencies'), match: russiaCategoryPath('currencies'),
      labelKey: 'z2.nav.rates', hintKey: 'w6b.nav.currencies.hint',
    },
    {
      id: 'methodology', icon: 'book', to: '/methodology', match: '/methodology',
      labelKey: 'w6b.nav.method', hintKey: 'w6b.nav.method.hint',
    },
  ];
  if (locale === 'en') {
    main.splice(1, 0, { ...byId['united-states'], icon: 'flag', hintKey: 'w6b.nav.us.hint' });
  }
  const russiaItems = [
    { id: 'russia', icon: 'landmark', to: russiaHomePath(), match: russiaHomePath(), labelKey: 'w6b.nav.russiaEconomy' },
    { id: 'today', icon: 'clock', to: todayPath(), match: todayPath(), labelKey: 'w6b.nav.russiaToday' },
    { id: 'regions', icon: 'map', to: regionHubPath(), match: regionHubPath(), labelKey: 'shell.nav.regions' },
    { id: 'calendar', icon: 'calendar', to: calendarPath(), match: calendarPath(), labelKey: 'shell.nav.calendar' },
  ];
  return [
    { id: 'main', titleKey: null, items: main },
    {
      id: 'russia', titleKey: 'shell.nav.groupRussia', hintKey: 'w6b.nav.russia.hint', icon: 'landmark',
      collapsible: true, items: russiaItems,
    },
  ];
}
