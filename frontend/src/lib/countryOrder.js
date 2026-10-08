/** Страны, которые сравнивают чаще всего: стоят в начале списка, остальные по алфавиту. */
export const PRIORITY_COUNTRIES = ['russia', 'united-states', 'china', 'germany', 'india'];

/**
 * Страны каталога сравнения по размеру ВВП в текущих долларах (оценка МВФ на 2025 год; Россия — расчёт платформы).
 * Порядок для английского сайта: там Россия не стоит первой, а идёт на своём месте по размеру экономики.
 * Страны, которых нет в списке, встают после него в том порядке, в каком пришли.
 */
export const GDP_COUNTRY_ORDER = Object.freeze([
  'united-states', 'china', 'germany', 'japan', 'united-kingdom', 'india', 'france', 'russia', 'italy',
  'canada', 'brazil', 'spain', 'south-korea', 'australia', 'mexico', 'turkey', 'netherlands',
  'switzerland', 'poland', 'belgium', 'ireland', 'sweden', 'israel', 'austria', 'norway', 'denmark',
  'romania', 'south-africa', 'czechia', 'portugal', 'finland', 'greece', 'new-zealand', 'hungary',
  'ukraine', 'slovakia', 'bulgaria', 'croatia', 'luxembourg', 'serbia', 'lithuania', 'slovenia',
  'azerbaijan', 'latvia', 'estonia', 'cyprus', 'iceland', 'georgia', 'bosnia', 'albania', 'armenia',
  'malta', 'moldova', 'north-macedonia', 'montenegro',
]);

/** Место страны по ВВП (0 — самая большая); неизвестная страна — после всех. */
export function gdpRank(slug) {
  const index = GDP_COUNTRY_ORDER.indexOf(slug);
  return index === -1 ? GDP_COUNTRY_ORDER.length : index;
}

/** Страны по убыванию ВВП; неизвестные остаются в исходном порядке после известных. `slugOf` достаёт slug из элемента. */
export function orderCountriesByGdp(items, slugOf = (item) => item?.country_slug || item?.key || item?.slug) {
  // sort стабилен: страны вне списка сохраняют порядок, в котором пришли.
  return [...(items || [])].sort((a, b) => gdpRank(slugOf(a)) - gdpRank(slugOf(b)));
}

/**
 * Порядок для выбора стран. Русская версия: «Россия, США, Китай, Германия, Индия», затем остальные в порядке,
 * заданном выше по потоку (алфавит). Английская версия: по размеру ВВП, Россия на своём месте, не первой.
 * Особый пункт «average» остаётся самым первым в обоих случаях.
 */
export function orderCountryOptions(options, locale = 'ru') {
  const isAverage = (option) => option.code === 'average';
  if (locale === 'en') {
    const list = [...(options || [])];
    const average = list.filter(isAverage);
    const rest = orderCountriesByGdp(list.filter((option) => !isAverage(option)));
    return [...average, ...rest];
  }
  const rank = (option) => {
    if (isAverage(option)) return -1;
    const index = PRIORITY_COUNTRIES.indexOf(option.country_slug);
    return index === -1 ? PRIORITY_COUNTRIES.length : index;
  };
  // sort стабилен: внутри «остальных» алфавитный порядок сохраняется.
  return [...(options || [])].sort((a, b) => rank(a) - rank(b));
}
