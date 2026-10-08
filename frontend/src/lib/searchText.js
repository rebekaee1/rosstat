/**
 * Человеческий язык выдачи поиска: названия и единицы без служебных слов, «Инфляция в Германии» вместо
 * «Гармонизированный индекс потребительских цен». Методологические подробности (база индекса, цепные
 * объёмы) остаются на странице показателя; в строке выдачи они только мешают выбрать.
 */

const LETTERS = 'а-яёa-z0-9';

/** Целое слово без lookbehind (старые iPhone его не разбирают): граница слева захватывается и возвращается. */
function word(pattern, replacement) {
  return [
    new RegExp(`(^|[^${LETTERS}])(?:${pattern})(?![${LETTERS}])`, 'giu'),
    (_match, pre) => `${pre}${replacement}`,
  ];
}

const RU_TITLE_RULES = [
  [/\s*\((?:\d{4}\s*=\s*100|\d{4}=100)\)/giu, ''],
  [/,?\s*(?:индекс\s+)?\d{4}\s*=\s*100\b/giu, ''],
  [/,?\s*цепны[ехм]\s+объ[её]м\S*/giu, ''],
  word('ИПЦ', 'потребительские цены'),
  word('HICP', 'потребительские цены (метод ЕС)'),
  word('CPI', 'потребительские цены'),
  [/сектор(?:а|е)?\s+государственного\s+управления/giu, 'государства'],
  [/упрощ[её]нн\S*\s+энергобаланс\S*/giu, 'энергобаланс'],
  [/валов\S+\s+внутренн\S+\s+потреблени\S*/giu, 'потребление энергии'],
  [/денежн\S*\s+агрегат\S*/giu, 'денежная масса'],
];

const EN_TITLE_RULES = [
  [/\s*\((?:\d{4}\s*=\s*100)\)/giu, ''],
  [/,?\s*(?:index\s+)?\d{4}\s*=\s*100\b/giu, ''],
  [/,?\s*chain[- ]linked volumes\S*/giu, ''],
  [/harmoni[sz]ed index of consumer prices/giu, 'consumer prices (EU method)'],
  word('HICP', 'consumer prices (EU method)'),
  word('CPI', 'consumer prices'),
  [/general government/giu, 'government'],
  [/simplified energy balance\S*/giu, 'energy balance'],
  [/gross inland (?:consumption|energy consumption)/giu, 'energy consumption'],
];

const RU_UNIT_RULES = [
  [/тыс\.\s*т\s*н\.\s*э\./giu, 'тыс. тонн нефтяного эквивалента'],
  [/\bUSD\s*\/\s*баррель/giu, '$ за баррель'],
  [/\bUSD\s*\/\s*тонн\S*/giu, '$ за тонну'],
  [/\b100\s+млн\s+юан\S*/giu, 'сотни млн юаней'],
  [/%\s*ЭАН/giu, '% от рабочей силы'],
  [/\s*\(\s*\d{4}\s*=\s*100\s*\)/giu, ''],
  [/,?\s*\d{4}\s*=\s*100\b/giu, ''],
];

const EN_UNIT_RULES = [
  [/\bUSD\s*\/\s*barrel/giu, '$ per barrel'],
  [/\bUSD\s*\/\s*tonne/giu, '$ per tonne'],
  [/\b100\s+million\s+yuan/giu, 'hundreds of millions of yuan'],
  [/\s*\(\s*\d{4}\s*=\s*100\s*\)/giu, ''],
  [/,?\s*\d{4}\s*=\s*100\b/giu, ''],
  [/thousand tonnes of oil equivalent|ktoe/giu, 'thousand tonnes of oil equivalent'],
];

function tidy(text) {
  return String(text)
    .replace(/\s+,/g, ',')
    .replace(/,\s*,/g, ',')
    .replace(/\(\s*\)/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[,\s—–-]+|[,\s—–-]+$/g, '')
    .trim();
}

function apply(text, rules) {
  let out = String(text || '');
  for (const [pattern, replacement] of rules) out = out.replace(pattern, replacement);
  return tidy(out);
}

/** Название строки без служебных слов; пустой результат никогда не возвращается (остаётся исходное название). */
export function plainTitle(name, locale = 'ru') {
  const original = String(name || '');
  let cleaned = apply(original, locale === 'en' ? EN_TITLE_RULES : RU_TITLE_RULES);
  // Замена в начале названия не должна съедать заглавную букву.
  if (cleaned && cleaned !== original && /^\p{Lu}/u.test(original)) {
    cleaned = cleaned.charAt(0).toLocaleUpperCase(locale === 'en' ? 'en' : 'ru') + cleaned.slice(1);
  }
  return cleaned || original;
}

/** Единица измерения для человека: «$ за баррель», «сотни млн юаней». */
export function plainUnit(unit, locale = 'ru') {
  const original = String(unit || '');
  const cleaned = apply(original, locale === 'en' ? EN_UNIT_RULES : RU_UNIT_RULES);
  return cleaned || original;
}

// Страны, для которых известна форма «в …»: без неё остаётся нейтральное «Инфляция: Страна».
const RU_IN = {
  'Россия': 'в России', 'США': 'в США', 'Германия': 'в Германии', 'Франция': 'во Франции', 'Китай': 'в Китае',
  'Япония': 'в Японии', 'Великобритания': 'в Великобритании', 'Италия': 'в Италии', 'Испания': 'в Испании',
  'Польша': 'в Польше', 'Турция': 'в Турции', 'Индия': 'в Индии', 'Бразилия': 'в Бразилии', 'Канада': 'в Канаде',
  'Австралия': 'в Австралии', 'Мексика': 'в Мексике', 'Южная Корея': 'в Южной Корее', 'Нидерланды': 'в Нидерландах',
  'Бельгия': 'в Бельгии', 'Австрия': 'в Австрии', 'Швейцария': 'в Швейцарии', 'Швеция': 'в Швеции',
  'Норвегия': 'в Норвегии', 'Дания': 'в Дании', 'Финляндия': 'в Финляндии', 'Ирландия': 'в Ирландии',
  'Португалия': 'в Португалии', 'Греция': 'в Греции', 'Чехия': 'в Чехии', 'Венгрия': 'в Венгрии',
  'Румыния': 'в Румынии', 'Болгария': 'в Болгарии', 'Словакия': 'в Словакии', 'Словения': 'в Словении',
  'Хорватия': 'в Хорватии', 'Эстония': 'в Эстонии', 'Латвия': 'в Латвии', 'Литва': 'в Литве',
  'Люксембург': 'в Люксембурге', 'Мальта': 'на Мальте', 'Кипр': 'на Кипре', 'Исландия': 'в Исландии',
  'Сербия': 'в Сербии', 'Черногория': 'в Черногории', 'Албания': 'в Албании', 'Северная Македония': 'в Северной Македонии',
  'Украина': 'в Украине', 'Беларусь': 'в Беларуси', 'Казахстан': 'в Казахстане', 'Азербайджан': 'в Азербайджане',
  'Армения': 'в Армении', 'Грузия': 'в Грузии', 'Молдавия': 'в Молдавии', 'Индонезия': 'в Индонезии',
  'Саудовская Аравия': 'в Саудовской Аравии', 'Аргентина': 'в Аргентине', 'ЮАР': 'в ЮАР', 'Израиль': 'в Израиле',
  'Египет': 'в Египте', 'Таиланд': 'в Таиланде', 'Вьетнам': 'во Вьетнаме', 'Сингапур': 'в Сингапуре',
  'Чили': 'в Чили', 'Колумбия': 'в Колумбии', 'Перу': 'в Перу', 'Новая Зеландия': 'в Новой Зеландии',
};

const EN_THE = new Set(['united states', 'united kingdom', 'netherlands', 'philippines', 'czech republic', 'united arab emirates']);

/** «в Германии» для известной страны, иначе null. */
export function inCountry(name, locale = 'ru') {
  const text = String(name || '').trim();
  if (!text) return null;
  if (locale === 'en') return `in ${EN_THE.has(text.toLowerCase()) ? 'the ' : ''}${text}`;
  return RU_IN[text] || null;
}

/** «Инфляция в Германии» / «Inflation in Germany»; без известной формы — «Инфляция: Германия». */
export function inflationTitle(country, t, locale = 'ru') {
  const where = inCountry(country, locale);
  return where ? t('w6d.search.inflationIn', { where }) : t('shell3.search.inflation', { country });
}

/**
 * Тема строки для значка: рынок труда, цены, население, валюта, энергия, ставки и так далее.
 * Определяется по названию и единице; незнакомое получает общий значок графика.
 */
const TOPICS = [
  ['labour', /безработ|занятост|зарплат|заработн|\bwage|salary|employ|labou?r|unemploy/i],
  ['prices', /инфляц|потребительск|цены|price|inflation|\bcpi\b|ипц|hicp/i],
  ['people', /населен|рожда|смертност|демограф|жител|population|birth|death|mortality/i],
  ['energy', /нефт|\bгаз\b|brent|\boil\b|\bgas\b|бензин|топлив|fuel|energy|энерг|diesel|дизел|\bcoal\b|уголь/i],
  ['metal', /золот|\bgold\b|silver|серебр|copper|\bмедь\b|metal/i],
  ['money', /курс|валют|\busd|\beur\b|\bcny|exchange|currency|dollar|доллар|евро|юан|bitcoin|биткоин|\bbtc\b|crypto|крипт/i],
  ['rates', /ставк|yield|доходност|облигац|\bbond|ruonia|key rate|interest|deposit|вклад|ипотек|mortgage/i],
  ['housing', /жиль|квартир|housing|dwelling/i],
  ['output', /ввп|\bgdp\b|производств|production|промышлен|industr|output|розничн|retail/i],
  ['state', /долг|бюджет|\bdebt|budget|deficit|дефицит/i],
];

export function searchTopic(item) {
  const text = `${item?.name || ''} ${item?.name_en || ''} ${item?.code || ''} ${item?.category || ''}`;
  for (const [topic, pattern] of TOPICS) if (pattern.test(text)) return topic;
  return 'chart';
}

/** Мировой рыночный ряд: значок глобуса вместо флага страны-эмитента. */
export function isGlobalMarketRow(item) {
  if (!item) return false;
  return /^(?:мировой рынок|global markets?|world market)$/i.test(String(item.country_name || '').trim());
}

const INDEX_UNIT_RE = /index|индекс|\d{4}\s*=\s*100/i;

/** Единица-индекс («индекс 2015 = 100»): само число без базы ничего не говорит, его прячем в «Подробнее». */
export function isIndexUnit(unit) {
  return INDEX_UNIT_RE.test(String(unit || ''));
}

/**
 * Подпись «Открываем: …» только из названия: числа, суммы и проценты, попавшие в строку, убираются,
 * четырёхзначные годы остаются («ВВП России, 2024»).
 */
export function openingLabel(name) {
  const text = String(name || '');
  const stripped = text
    .split(/\s+[—–]\s+/)[0]
    .replace(
      /(?:^|\s)[+−-]?\d[\d\s.,]*(?:\s?(?:%|млрд|млн|тыс\S*|трлн|bn|m|k))?(?=\s|$|,)/giu,
      (match) => (/^\s?\d{4}$/.test(match) ? match : ''),
    )
    .replace(/\s{2,}/g, ' ')
    .replace(/[\s,:;]+$/g, '')
    .trim();
  return stripped || text;
}

/** Группы выдачи по теме: крупные первыми, «прочее» последним. Метка темы — сообщение `z8.search.topic.<id>`. */
export function groupByTopic(rows, topicOf) {
  const groups = new Map();
  for (const row of rows) {
    const id = topicOf(row);
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(row);
  }
  return [...groups.entries()]
    .map(([id, list]) => ({ id, rows: list }))
    .sort((a, b) => (a.id === 'chart') - (b.id === 'chart') || b.rows.length - a.rows.length);
}

/**
 * Круг 9 (Q2): исправленный запрос показываем человеку только если он читается: слово не смешивает кириллицу и латиницу
 * (так выглядит неудачный разбор перевёрнутой раскладки). Остальную проверку («распознаны все слова») делает сервер.
 */
export function isReadableCorrection(text) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  if (!words.length) return false;
  return words.every((word) => !(/[A-Za-z]/.test(word) && /[А-Яа-яЁё]/.test(word)));
}
