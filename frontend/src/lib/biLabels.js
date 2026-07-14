// Словарь ярлыков BI (этап 4б BI 2.1): единая точка перевода машинных
// значений измерений в человеческие русские подписи. Любая карточка
// /admin/bi, показывающая слаг/код/транслит, обязана пройти через эти
// функции — чтобы «yandex_search», «ru-RU» и «Saint Petersburg» не уходили
// на экран сырыми.

/* ---------- Каналы привлечения ---------- */

// Покрывает обе номенклатуры: traffic_source Метрики (organic/link/saved…)
// и наш classify_channel (search/referral/campaign…).
export const CHANNEL_RU = {
  ad: 'Реклама (РСЯ)',
  organic: 'Поисковые системы',
  search: 'Поисковые системы',
  campaign: 'Рассылки и посевы',
  direct: 'Прямые заходы',
  referral: 'Переходы с сайтов',
  link: 'Переходы с сайтов',
  internal: 'Внутренние переходы',
  recommend: 'Рекомендательные системы',
  social: 'Социальные сети',
  saved: 'Сохранённые страницы',
  unknown: 'Не определён',
};

export const channelLabel = (k) => CHANNEL_RU[k] || (k ? k : '(не определён)');

/* ---------- Устройства ---------- */

export const DEVICE_RU = {
  desktop: 'Компьютеры', mobile: 'Смартфоны', tablet: 'Планшеты',
  tv: 'Телевизоры', bot: 'Роботы', unknown: 'Не определено',
};

export const deviceLabel = (k) => DEVICE_RU[k] || (k ? k : '(не определено)');

/* ---------- Поисковые системы ---------- */

// Ключи search_engine из повизитки Метрики (root-идентификаторы Logs API).
const ENGINE_RU = {
  yandex: 'Яндекс', yandex_search: 'Яндекс', yandex_mobile: 'Яндекс (моб.)',
  google: 'Google', google_search: 'Google',
  bing: 'Bing', duckduckgo: 'DuckDuckGo', 'mail.ru': 'Поиск Mail.ru',
  mail_ru: 'Поиск Mail.ru', mailru: 'Поиск Mail.ru', rambler: 'Рамблер',
  yahoo: 'Yahoo', ecosia: 'Ecosia', startpage: 'Startpage',
};

export const engineLabel = (k) =>
  ENGINE_RU[String(k || '').toLowerCase()] || (k ? k : '(не определён)');

/* ---------- Языки браузера ---------- */

// Intl.DisplayNames покрывает любой BCP-47-код («ru-RU» → «русский»)
// без словаря; капитализируем первую букву для подписи.
let _langNames = null;
try {
  _langNames = new Intl.DisplayNames(['ru'], { type: 'language' });
} catch { /* старый браузер — покажем код как есть */ }

export function languageLabel(code) {
  if (!code) return '(не определён)';
  try {
    const name = _langNames?.of(code);
    if (name && name !== code) return name.charAt(0).toUpperCase() + name.slice(1);
  } catch { /* невалидный код */ }
  return code;
}

/* ---------- Часовые пояса ---------- */

const TZ_CITY_RU = {
  Moscow: 'Москва', Kaliningrad: 'Калининград', Samara: 'Самара',
  Yekaterinburg: 'Екатеринбург', Omsk: 'Омск', Novosibirsk: 'Новосибирск',
  Krasnoyarsk: 'Красноярск', Irkutsk: 'Иркутск', Yakutsk: 'Якутск',
  Vladivostok: 'Владивосток', Magadan: 'Магадан', Kamchatka: 'Камчатка',
  Saratov: 'Саратов', Volgograd: 'Волгоград', Kirov: 'Киров',
  Ulyanovsk: 'Ульяновск', Barnaul: 'Барнаул', Tomsk: 'Томск',
  Chita: 'Чита', Khandyga: 'Хандыга', 'Ust-Nera': 'Усть-Нера',
  Sakhalin: 'Сахалин', Srednekolymsk: 'Среднеколымск', Anadyr: 'Анадырь',
  Minsk: 'Минск', Kiev: 'Киев', Kyiv: 'Киев', Almaty: 'Алма-Ата',
  Tashkent: 'Ташкент', Baku: 'Баку', Yerevan: 'Ереван', Tbilisi: 'Тбилиси',
  Bishkek: 'Бишкек', Dushanbe: 'Душанбе', Ashgabat: 'Ашхабад',
  Chisinau: 'Кишинёв', Riga: 'Рига', Vilnius: 'Вильнюс', Tallinn: 'Таллин',
  London: 'Лондон', Paris: 'Париж', Berlin: 'Берлин', Istanbul: 'Стамбул',
  Dubai: 'Дубай', 'Tel_Aviv': 'Тель-Авив', 'New_York': 'Нью-Йорк',
  'Los_Angeles': 'Лос-Анджелес', Belgrade: 'Белград', Warsaw: 'Варшава',
  Prague: 'Прага', Amsterdam: 'Амстердам', Madrid: 'Мадрид', Rome: 'Рим',
  Helsinki: 'Хельсинки', Bangkok: 'Бангкок', Shanghai: 'Шанхай',
  Tokyo: 'Токио', Seoul: 'Сеул', Singapore: 'Сингапур', Bucharest: 'Бухарест',
  Nicosia: 'Никосия', Larnaca: 'Ларнака', Limassol: 'Лимасол',
};

export function timezoneLabel(tz) {
  if (!tz) return '(не определён)';
  // Etc/GMT-3 — знак ИНВЕРТИРОВАН по стандарту IANA: GMT-3 = UTC+3.
  const etc = /^Etc\/GMT([+-])(\d+)$/.exec(tz);
  if (etc) {
    const sign = etc[1] === '-' ? '+' : '−';
    return `UTC${sign}${etc[2]}`;
  }
  const city = tz.split('/').pop();
  const ru = TZ_CITY_RU[city];
  return ru || city.replace(/_/g, ' ');
}

/* ---------- Города (транслит Метрики → русские имена) ---------- */

const CITY_RU = {
  Moscow: 'Москва', 'Saint Petersburg': 'Санкт-Петербург',
  Novosibirsk: 'Новосибирск', Yekaterinburg: 'Екатеринбург', Kazan: 'Казань',
  'Nizhny Novgorod': 'Нижний Новгород', Chelyabinsk: 'Челябинск',
  Samara: 'Самара', Omsk: 'Омск', 'Rostov-on-Don': 'Ростов-на-Дону',
  Ufa: 'Уфа', Krasnoyarsk: 'Красноярск', Voronezh: 'Воронеж', Perm: 'Пермь',
  Volgograd: 'Волгоград', Krasnodar: 'Краснодар', Saratov: 'Саратов',
  Tyumen: 'Тюмень', Tolyatti: 'Тольятти', Izhevsk: 'Ижевск',
  Barnaul: 'Барнаул', Ulyanovsk: 'Ульяновск', Irkutsk: 'Иркутск',
  Khabarovsk: 'Хабаровск', Yaroslavl: 'Ярославль', Vladivostok: 'Владивосток',
  Makhachkala: 'Махачкала', Tomsk: 'Томск', Orenburg: 'Оренбург',
  Kemerovo: 'Кемерово', Novokuznetsk: 'Новокузнецк', Ryazan: 'Рязань',
  Astrakhan: 'Астрахань', 'Naberezhnye Chelny': 'Набережные Челны',
  Penza: 'Пенза', Lipetsk: 'Липецк', Kirov: 'Киров', Cheboksary: 'Чебоксары',
  Tula: 'Тула', Kaliningrad: 'Калининград', Balashikha: 'Балашиха',
  Kursk: 'Курск', Sochi: 'Сочи', Stavropol: 'Ставрополь',
  'Ulan-Ude': 'Улан-Удэ', Tver: 'Тверь', Magnitogorsk: 'Магнитогорск',
  Ivanovo: 'Иваново', Bryansk: 'Брянск', Belgorod: 'Белгород',
  Surgut: 'Сургут', Vladimir: 'Владимир', Chita: 'Чита',
  'Nizhny Tagil': 'Нижний Тагил', Arkhangelsk: 'Архангельск',
  Simferopol: 'Симферополь', Kaluga: 'Калуга', Smolensk: 'Смоленск',
  Volzhsky: 'Волжский', Yakutsk: 'Якутск', Sevastopol: 'Севастополь',
  Murmansk: 'Мурманск', Vologda: 'Вологда', Saransk: 'Саранск',
  Tambov: 'Тамбов', Grozny: 'Грозный', Sterlitamak: 'Стерлитамак',
  Petrozavodsk: 'Петрозаводск', Kostroma: 'Кострома', Khimki: 'Химки',
  Himki: 'Химки', Podolsk: 'Подольск', Mytishchi: 'Мытищи',
  Korolyov: 'Королёв', Lyubertsy: 'Люберцы', Krasnogorsk: 'Красногорск',
  Odintsovo: 'Одинцово', Zelenograd: 'Зеленоград',
  Minsk: 'Минск', Almaty: 'Алма-Ата', Tashkent: 'Ташкент', Baku: 'Баку',
  Yerevan: 'Ереван', Tbilisi: 'Тбилиси', Bishkek: 'Бишкек',
  Chisinau: 'Кишинёв', Astana: 'Астана', Karaganda: 'Караганда',
  // Дальнее зарубежье: GeoIP отдаёт латиницу — русифицируем частые.
  Amsterdam: 'Амстердам', Berlin: 'Берлин', London: 'Лондон', Paris: 'Париж',
  Helsinki: 'Хельсинки', Frankfurt: 'Франкфурт', Warsaw: 'Варшава',
  Prague: 'Прага', Vienna: 'Вена', Istanbul: 'Стамбул', Dubai: 'Дубай',
  'Tel Aviv': 'Тель-Авив', Limassol: 'Лимасол', Larnaca: 'Ларнака',
  Nicosia: 'Никосия', Belgrade: 'Белград', Riga: 'Рига', Vilnius: 'Вильнюс',
  Tallinn: 'Таллин', 'New York': 'Нью-Йорк', 'San Jose': 'Сан-Хосе',
  'San Francisco': 'Сан-Франциско', 'Los Angeles': 'Лос-Анджелес',
  Beijing: 'Пекин', Shanghai: 'Шанхай', Tokyo: 'Токио', Seoul: 'Сеул',
  Singapore: 'Сингапур', Bangkok: 'Бангкок', Bucharest: 'Бухарест',
};

export const cityLabel = (name) => {
  if (!name) return '(не определён)';
  // DB-IP иногда добавляет округ в скобках («Moscow (Tsentralnyy ...)»).
  const base = name.replace(/\s*\(.+\)$/, '');
  return CITY_RU[base] || base;
};

/* ---------- Регионы (GeoIP en → русские имена) ---------- */

const GEO_REGION_RU = {
  Moscow: 'Москва', 'Moscow Oblast': 'Московская область',
  'St.-Petersburg': 'Санкт-Петербург', 'Saint Petersburg': 'Санкт-Петербург',
  'Leningrad Oblast': 'Ленинградская область',
  'Novosibirsk Oblast': 'Новосибирская область',
  'Sverdlovsk Oblast': 'Свердловская область',
  Tatarstan: 'Татарстан', 'Republic of Tatarstan': 'Татарстан',
  'Nizhny Novgorod Oblast': 'Нижегородская область',
  'Chelyabinsk Oblast': 'Челябинская область',
  'Samara Oblast': 'Самарская область', 'Omsk Oblast': 'Омская область',
  'Rostov Oblast': 'Ростовская область',
  Bashkortostan: 'Башкортостан', 'Republic of Bashkortostan': 'Башкортостан',
  'Krasnoyarsk Krai': 'Красноярский край',
  'Voronezh Oblast': 'Воронежская область', 'Perm Krai': 'Пермский край',
  'Volgograd Oblast': 'Волгоградская область',
  'Krasnodar Krai': 'Краснодарский край',
  'Saratov Oblast': 'Саратовская область', 'Tyumen Oblast': 'Тюменская область',
  'Irkutsk Oblast': 'Иркутская область', 'Kemerovo Oblast': 'Кемеровская область',
  'Khabarovsk Krai': 'Хабаровский край', 'Primorsky Krai': 'Приморский край',
  'Stavropol Krai': 'Ставропольский край', Udmurtia: 'Удмуртия',
  'Kaliningrad Oblast': 'Калининградская область',
  'Tula Oblast': 'Тульская область', 'Yaroslavl Oblast': 'Ярославская область',
  'Tver Oblast': 'Тверская область', 'Belgorod Oblast': 'Белгородская область',
  'Vladimir Oblast': 'Владимирская область', 'Kursk Oblast': 'Курская область',
  'Lipetsk Oblast': 'Липецкая область', 'Ryazan Oblast': 'Рязанская область',
  'Penza Oblast': 'Пензенская область', 'Kirov Oblast': 'Кировская область',
  'Orenburg Oblast': 'Оренбургская область', 'Tomsk Oblast': 'Томская область',
  'Ulyanovsk Oblast': 'Ульяновская область',
  'Astrakhan Oblast': 'Астраханская область',
  Dagestan: 'Дагестан', Crimea: 'Крым', 'Republic of Crimea': 'Крым',
  // Частые зарубежные (в основном хостинг-трафик и релоканты).
  Washington: 'Вашингтон (штат)', California: 'Калифорния',
  'North Holland': 'Северная Голландия', 'Minsk City': 'Минск', Minsk: 'Минск',
};

// Хвосты «X Oblast / X Krai» вне словаря русифицируем по суффиксу,
// чтобы не мешать латиницу с кириллицей в одной колонке.
export const geoRegionLabel = (name) => {
  if (!name) return '(не определён)';
  if (GEO_REGION_RU[name]) return GEO_REGION_RU[name];
  const m = /^(.+?)\s+(Oblast|Krai)$/.exec(name);
  if (m) return `${cityLabel(m[1])} (${m[2] === 'Oblast' ? 'обл.' : 'край'})`;
  return name;
};

/* ---------- Блоки страниц ([data-block]) ---------- */

// Названия разделов сборника «Регионы России» — блоки region-section-N
// на карточке региона.
const REGION_SECTION_RU = {
  1: 'Население', 2: 'Труд', 3: 'Уровень жизни населения', 4: 'Образование',
  5: 'Здравоохранение', 6: 'Культура, отдых и туризм',
  7: 'Земельные ресурсы и экология', 8: 'Валовой региональный продукт',
  9: 'Основные фонды', 10: 'Инвестиции', 11: 'Организации',
  12: 'Промышленное производство', 13: 'Сельское хозяйство',
  14: 'Строительство', 15: 'Торговля и услуги населению', 16: 'Транспорт',
  17: 'Информационные технологии', 18: 'Наука и инновации', 19: 'Финансы',
  20: 'Цены и тарифы', 21: 'Внешняя торговля', 22: 'Правонарушения',
};

const BLOCK_RU = {
  chart: 'График индикатора',
  'compare-chart': 'График сравнения',
  'compare-add': 'Добавление ряда в сравнение',
  'region-chart': 'График показателя региона',
  'region-rating': 'Рейтинг регионов',
  'regions-map': 'Карта регионов',
  related: 'Связанные индикаторы',
  'related-categories': 'Связанные категории',
  methodology: 'Методология',
  faq: 'Вопросы и ответы',
  contrasts: 'Контрасты регионов',
  categories: 'Сетка категорий',
  'category-list': 'Список индикаторов категории',
  'calc-form': 'Форма калькулятора',
  'calc-result': 'Результат калькулятора',
  'calc-methodology': 'Методология калькулятора',
  about: 'О проекте',
};

export function blockLabel(slug) {
  if (!slug) return '(не определён)';
  const m = /^region-section-(\d+)$/.exec(slug);
  if (m) {
    const name = REGION_SECTION_RU[Number(m[1])];
    return name ? `Раздел региона: ${name}` : `Раздел карточки региона №${m[1]}`;
  }
  return BLOCK_RU[slug] || slug;
}

/* ---------- Разделы сайта (зеркало page_section бэкенда) ---------- */

const SECTION_RULES = [
  ['/indicator', 'Индикаторы'],
  ['/category', 'Категории'],
  ['/region-rating', 'Рейтинги регионов'],
  ['/region-vs', 'Сравнение регионов'],
  ['/regions/map', 'Карта регионов'],
  ['/regions', 'Каталог регионов'],
  ['/region', 'Карточки регионов'],
  ['/compare', 'Сравнение'],
  ['/calculator', 'Калькуляторы'],
  ['/calendar', 'Календарь'],
  ['/today', 'Страницы «сегодня»'],
  ['/about', 'О проекте'],
  ['/methodology', 'Методология'],
  ['/account', 'Кабинет'],
  ['/login', 'Вход'],
  ['/register', 'Регистрация'],
  ['/admin', 'Служебные'],
];

export function pageSectionRu(path) {
  const p = (path || '').split('?')[0];
  if (!p || p === '/') return 'Главная';
  for (const [prefix, name] of SECTION_RULES) {
    if (p.startsWith(prefix)) return name;
  }
  return 'Прочее';
}

/* ---------- Конструктор «Срезы»: метрики и измерения ---------- */

export const SLICE_METRIC_RU = {
  sessions: 'Сессии',
  visitors: 'Посетители',
  pageviews: 'Просмотры страниц',
  clicks: 'Клики',
  engaged_sessions: 'Вовлечённые сессии',
  micro_goals: 'Микро-цели',
  macro_goals: 'Макро-цели',
  metrika_visits: 'Визиты (Метрика)',
  metrika_goal_visits: 'Визиты с бизнес-целью (Метрика)',
};

export const SLICE_DIM_RU = {
  day: 'День',
  hour: 'Час',
  channel: 'Канал',
  device: 'Устройство',
  browser: 'Браузер',
  os: 'Операционная система',
  is_new: 'Новый посетитель',
  entry_page: 'Страница входа',
  page: 'Страница',
  event_type: 'Тип события',
  traffic_source: 'Источник трафика',
  search_engine: 'Поисковая система',
  value: 'Значение',
};

export const sliceMetricLabel = (k) => SLICE_METRIC_RU[k] || k;
export const sliceDimLabel = (k) => SLICE_DIM_RU[k] || k;

/* ---------- Схлопывание поисковых фраз ---------- */

/**
 * Готовит словарь {фраза: count} к показу таблицей: отбрасывает односимвольный
 * мусор, схлопывает префиксы-недопечатки («чело» → «человек», если полная
 * фраза тоже встречалась) и сортирует по убыванию.
 */
export function collapsePhrases(dict, { minLen = 3, limit = 15 } = {}) {
  const entries = Object.entries(dict || {})
    .map(([k, v]) => [String(k).trim(), Number(v) || 0])
    .filter(([k, v]) => k.length >= minLen && v > 0);
  // Длинные сначала: короткая фраза вливается в самую популярную надстройку.
  entries.sort((a, b) => b[0].length - a[0].length);
  const kept = [];
  for (const [phrase, count] of entries) {
    const host = kept
      .filter(([k]) => k.startsWith(phrase) && k !== phrase)
      .sort((a, b) => b[1] - a[1])[0];
    if (host) host[1] += count;
    else kept.push([phrase, count]);
  }
  return kept
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([phrase, count]) => ({ phrase, count }));
}
