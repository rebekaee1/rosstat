/**
 * Справочные факты о странах каталога: столица и валюта. Это не ряды данных и не меняются годами, поэтому лежат
 * в клиенте: профиль страны заполняется сразу, без отдельного запроса. Ключ — код страны, как в каталоге.
 * Значение: столица [ru, en], валюта [ru, en].
 */
const EURO = ['Евро', 'Euro'];

const REFERENCE = {
  AT: { capital: ['Вена', 'Vienna'], currency: EURO },
  BE: { capital: ['Брюссель', 'Brussels'], currency: EURO },
  BG: { capital: ['София', 'Sofia'], currency: ['Болгарский лев', 'Bulgarian lev'] },
  HR: { capital: ['Загреб', 'Zagreb'], currency: EURO },
  CY: { capital: ['Никосия', 'Nicosia'], currency: EURO },
  CZ: { capital: ['Прага', 'Prague'], currency: ['Чешская крона', 'Czech koruna'] },
  DK: { capital: ['Копенгаген', 'Copenhagen'], currency: ['Датская крона', 'Danish krone'] },
  EE: { capital: ['Таллин', 'Tallinn'], currency: EURO },
  FI: { capital: ['Хельсинки', 'Helsinki'], currency: EURO },
  FR: { capital: ['Париж', 'Paris'], currency: EURO },
  DE: { capital: ['Берлин', 'Berlin'], currency: EURO },
  GR: { capital: ['Афины', 'Athens'], currency: EURO },
  EL: { capital: ['Афины', 'Athens'], currency: EURO },
  HU: { capital: ['Будапешт', 'Budapest'], currency: ['Венгерский форинт', 'Hungarian forint'] },
  IE: { capital: ['Дублин', 'Dublin'], currency: EURO },
  IT: { capital: ['Рим', 'Rome'], currency: EURO },
  LV: { capital: ['Рига', 'Riga'], currency: EURO },
  LT: { capital: ['Вильнюс', 'Vilnius'], currency: EURO },
  LU: { capital: ['Люксембург', 'Luxembourg'], currency: EURO },
  MT: { capital: ['Валлетта', 'Valletta'], currency: EURO },
  NL: { capital: ['Амстердам', 'Amsterdam'], currency: EURO },
  PL: { capital: ['Варшава', 'Warsaw'], currency: ['Польский злотый', 'Polish zloty'] },
  PT: { capital: ['Лиссабон', 'Lisbon'], currency: EURO },
  RO: { capital: ['Бухарест', 'Bucharest'], currency: ['Румынский лей', 'Romanian leu'] },
  SK: { capital: ['Братислава', 'Bratislava'], currency: EURO },
  SI: { capital: ['Любляна', 'Ljubljana'], currency: EURO },
  ES: { capital: ['Мадрид', 'Madrid'], currency: EURO },
  SE: { capital: ['Стокгольм', 'Stockholm'], currency: ['Шведская крона', 'Swedish krona'] },
  IS: { capital: ['Рейкьявик', 'Reykjavik'], currency: ['Исландская крона', 'Icelandic krona'] },
  NO: { capital: ['Осло', 'Oslo'], currency: ['Норвежская крона', 'Norwegian krone'] },
  CH: { capital: ['Берн', 'Bern'], currency: ['Швейцарский франк', 'Swiss franc'] },
  GB: { capital: ['Лондон', 'London'], currency: ['Фунт стерлингов', 'Pound sterling'] },
  UK: { capital: ['Лондон', 'London'], currency: ['Фунт стерлингов', 'Pound sterling'] },
  TR: { capital: ['Анкара', 'Ankara'], currency: ['Турецкая лира', 'Turkish lira'] },
  RS: { capital: ['Белград', 'Belgrade'], currency: ['Сербский динар', 'Serbian dinar'] },
  ME: { capital: ['Подгорица', 'Podgorica'], currency: EURO },
  MK: { capital: ['Скопье', 'Skopje'], currency: ['Македонский денар', 'Macedonian denar'] },
  AL: { capital: ['Тирана', 'Tirana'], currency: ['Албанский лек', 'Albanian lek'] },
  BA: { capital: ['Сараево', 'Sarajevo'], currency: ['Конвертируемая марка', 'Convertible mark'] },
  XK: { capital: ['Приштина', 'Pristina'], currency: EURO },
  UA: { capital: ['Киев', 'Kyiv'], currency: ['Гривна', 'Hryvnia'] },
  MD: { capital: ['Кишинёв', 'Chisinau'], currency: ['Молдавский лей', 'Moldovan leu'] },
  GE: { capital: ['Тбилиси', 'Tbilisi'], currency: ['Лари', 'Lari'] },
  AM: { capital: ['Ереван', 'Yerevan'], currency: ['Армянский драм', 'Armenian dram'] },
  AZ: { capital: ['Баку', 'Baku'], currency: ['Азербайджанский манат', 'Azerbaijani manat'] },
  US: { capital: ['Вашингтон', 'Washington, D.C.'], currency: ['Доллар США', 'US dollar'] },
  CA: { capital: ['Оттава', 'Ottawa'], currency: ['Канадский доллар', 'Canadian dollar'] },
  JP: { capital: ['Токио', 'Tokyo'], currency: ['Иена', 'Yen'] },
  KR: { capital: ['Сеул', 'Seoul'], currency: ['Южнокорейская вона', 'South Korean won'] },
  CN: { capital: ['Пекин', 'Beijing'], currency: ['Юань', 'Yuan'] },
  IN: { capital: ['Нью-Дели', 'New Delhi'], currency: ['Индийская рупия', 'Indian rupee'] },
  BR: { capital: ['Бразилиа', 'Brasilia'], currency: ['Бразильский реал', 'Brazilian real'] },
  MX: { capital: ['Мехико', 'Mexico City'], currency: ['Мексиканское песо', 'Mexican peso'] },
  AU: { capital: ['Канберра', 'Canberra'], currency: ['Австралийский доллар', 'Australian dollar'] },
  NZ: { capital: ['Веллингтон', 'Wellington'], currency: ['Новозеландский доллар', 'New Zealand dollar'] },
  ZA: { capital: ['Претория', 'Pretoria'], currency: ['Рэнд', 'Rand'] },
  IL: { capital: ['Иерусалим', 'Jerusalem'], currency: ['Шекель', 'Shekel'] },
  RU: { capital: ['Москва', 'Moscow'], currency: ['Рубль', 'Ruble'] },
};

/** Столица и валюта страны на языке страницы; нет записи — null (поле просто не показываем). */
export function countryReference(code, locale = 'ru') {
  const entry = REFERENCE[String(code || '').toUpperCase()];
  if (!entry) return null;
  const i = locale === 'en' ? 1 : 0;
  return { capital: entry.capital[i], currency: entry.currency[i] };
}
