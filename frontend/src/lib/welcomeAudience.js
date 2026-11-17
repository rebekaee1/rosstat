/**
 * Приветственный экран для иностранной аудитории (17.11.2026): чьи источники и какие страны показать посетителю.
 *
 * Язык сайта по-прежнему задаёт хост (решение владельца 31.08.2026, ADR-0013): эта функция язык не выбирает и никуда
 * не перенаправляет. Она отвечает на другой вопрос: из какой страны человек, чтобы на шаге «Свежие данные» стояли
 * знакомые ему ведомства, а на шаге «Сравнение» — его страна.
 *
 * Сигналы, по убыванию силы:
 *  1. часовой пояс устройства (`Intl.DateTimeFormat().resolvedOptions().timeZone`): он про место, а не про привычку;
 *  2. регион в языке браузера (`navigator.languages`: `en-GB`, `pt-BR`, `de`); `en-US` стоит по умолчанию у половины мира,
 *     поэтому сам по себе он значит «США» только когда пояс не возразил;
 *  3. ничего не узнали — общий международный набор.
 * На сервер ничего не уходит, в события аналитики страна не пишется.
 *
 * Источники перечислены только те, что действительно подключены (docs/data_sources.md, «Национальные паспорта»,
 * `backend/app/data/world_national_core/*.yaml`, Евростат и МВФ). Корея и Мексика отдельного набора не имеют: их
 * национальные ряды зависят от ключей доступа, поэтому им показывается общий набор.
 */
const EU_EFTA = new Set([
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT',
  'RO', 'SK', 'SI', 'ES', 'SE', 'IS', 'LI', 'NO', 'CH',
]);

/** Название страны на английском и её страница на сайте (для шага «Сравнение»). */
const COUNTRY_NAMES = {
  US: 'United States', GB: 'United Kingdom', CA: 'Canada', AU: 'Australia', JP: 'Japan', IN: 'India', BR: 'Brazil', CN: 'China',
  DE: 'Germany', FR: 'France', IT: 'Italy', ES: 'Spain', NL: 'Netherlands', PL: 'Poland', SE: 'Sweden', CH: 'Switzerland',
  AT: 'Austria', BE: 'Belgium', IE: 'Ireland', PT: 'Portugal', GR: 'Greece', FI: 'Finland', DK: 'Denmark', NO: 'Norway',
  CZ: 'Czechia', HU: 'Hungary', RO: 'Romania',
};

/** Наборы: до трёх источников (сцена покажет столько, сколько помещается) и страна для сравнения рядом с домашней. */
const AUDIENCES = {
  US: { sources: ['FRED', 'BLS', 'BEA'], peer: 'CA' },
  GB: { sources: ['ONS', 'Bank of England', 'IMF'], peer: 'DE' },
  CA: { sources: ['Statistics Canada', 'Bank of Canada', 'IMF'], peer: 'US' },
  AU: { sources: ['ABS', 'RBA', 'IMF'], peer: 'US' },
  JP: { sources: ['Bank of Japan', 'e-Stat', 'IMF'], peer: 'US' },
  IN: { sources: ['MOSPI', 'RBI', 'IMF'], peer: 'CN' },
  BR: { sources: ['Banco Central', 'IBGE', 'IMF'], peer: 'US' },
  CN: { sources: ['NBS', 'CFETS', 'IMF'], peer: 'US' },
  EU: { sources: ['Eurostat', 'ECB', 'IMF'], peer: 'FR' },
  WORLD: { sources: ['IMF', 'Eurostat', 'FRED'], home: 'US', peer: 'DE' },
};

const TZ_EXACT = {
  'Europe/London': 'GB', 'Europe/Belfast': 'GB', 'Europe/Dublin': 'IE', 'Europe/Berlin': 'DE', 'Europe/Busingen': 'DE', 'Europe/Paris': 'FR',
  'Europe/Rome': 'IT', 'Europe/Madrid': 'ES', 'Atlantic/Canary': 'ES', 'Europe/Amsterdam': 'NL', 'Europe/Warsaw': 'PL',
  'Europe/Stockholm': 'SE', 'Europe/Zurich': 'CH', 'Europe/Vienna': 'AT', 'Europe/Brussels': 'BE', 'Europe/Lisbon': 'PT',
  'Europe/Athens': 'GR', 'Europe/Helsinki': 'FI', 'Europe/Copenhagen': 'DK', 'Europe/Oslo': 'NO', 'Europe/Prague': 'CZ',
  'Europe/Budapest': 'HU', 'Europe/Bucharest': 'RO', 'Europe/Sofia': 'BG', 'Europe/Zagreb': 'HR', 'Europe/Ljubljana': 'SI',
  'Europe/Bratislava': 'SK', 'Europe/Tallinn': 'EE', 'Europe/Riga': 'LV', 'Europe/Vilnius': 'LT', 'Europe/Luxembourg': 'LU',
  'Europe/Malta': 'MT', 'Asia/Nicosia': 'CY', 'Atlantic/Reykjavik': 'IS', 'Europe/Vaduz': 'LI',
  'Asia/Tokyo': 'JP', 'Asia/Kolkata': 'IN', 'Asia/Calcutta': 'IN', 'Asia/Shanghai': 'CN', 'Asia/Urumqi': 'CN',
  'America/Sao_Paulo': 'BR', 'America/Bahia': 'BR', 'America/Fortaleza': 'BR', 'America/Recife': 'BR', 'America/Manaus': 'BR',
  'America/Belem': 'BR', 'America/Toronto': 'CA', 'America/Vancouver': 'CA', 'America/Edmonton': 'CA', 'America/Winnipeg': 'CA',
  'America/Halifax': 'CA', 'America/St_Johns': 'CA', 'America/Regina': 'CA', 'America/Montreal': 'CA',
  'America/New_York': 'US', 'America/Chicago': 'US', 'America/Denver': 'US', 'America/Los_Angeles': 'US', 'America/Phoenix': 'US',
  'America/Anchorage': 'US', 'America/Detroit': 'US', 'America/Boise': 'US', 'Pacific/Honolulu': 'US',
};

function countryFromTimeZone(timeZone) {
  const tz = String(timeZone || '');
  if (!tz) return null;
  if (TZ_EXACT[tz]) return TZ_EXACT[tz];
  if (tz.startsWith('Australia/')) return 'AU';
  if (/^America\/(Indiana|Kentucky|North_Dakota)\//.test(tz)) return 'US';
  return null;
}

function countryFromLanguages(languages) {
  for (const raw of Array.isArray(languages) ? languages : []) {
    const tag = String(raw || '');
    const region = /^[a-z]{2,3}(?:-[A-Za-z]{4})?-([A-Za-z]{2})\b/.exec(tag)?.[1]?.toUpperCase();
    if (region) return { country: region, weak: tag.toLowerCase() === 'en-us' };
    const lang = tag.toLowerCase();
    const byLanguage = { de: 'DE', fr: 'FR', it: 'IT', es: 'ES', nl: 'NL', pl: 'PL', sv: 'SE', ja: 'JP', hi: 'IN', pt: 'PT', zh: 'CN' }[lang];
    if (byLanguage) return { country: byLanguage, weak: false };
  }
  return null;
}

/** Страна посетителя по сигналам браузера или null. `known` — пояс или язык хоть что-то сказали. */
export function detectVisitorCountry({ timeZone, languages } = {}) {
  const byZone = countryFromTimeZone(timeZone);
  if (byZone) return byZone;
  const byLang = countryFromLanguages(languages);
  if (!byLang) return null;
  // `en-US` без подтверждения поясом: человек может быть где угодно. Пояс назван, но нам не знаком — не гадаем.
  if (byLang.weak && timeZone && !String(timeZone).startsWith('America/') && !String(timeZone).startsWith('Pacific/')) return null;
  return byLang.country;
}

/**
 * Набор для приветственного экрана.
 * @returns {{ key: string, sources: string[], home: string, peer: string }} `home` и `peer` — английские названия стран.
 */
export function welcomeAudience(signals = {}) {
  const country = detectVisitorCountry(signals);
  const key = country && AUDIENCES[country] ? country : (country && EU_EFTA.has(country) ? 'EU' : 'WORLD');
  const set = AUDIENCES[key];
  const homeCode = key === 'WORLD' ? set.home : (key === 'EU' ? country : key);
  const peerCode = set.peer === homeCode ? 'DE' : set.peer;
  return {
    key,
    sources: set.sources,
    home: COUNTRY_NAMES[homeCode] || COUNTRY_NAMES.US,
    peer: COUNTRY_NAMES[peerCode] || COUNTRY_NAMES.DE,
  };
}

/** Сигналы этого браузера; любая ошибка даёт пустой набор (общий международный вариант). */
export function readBrowserSignals() {
  const out = { timeZone: null, languages: [] };
  try { out.timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch { /* нет Intl */ }
  try {
    const nav = typeof navigator !== 'undefined' ? navigator : null;
    out.languages = nav?.languages?.length ? [...nav.languages] : (nav?.language ? [nav.language] : []);
  } catch { /* недоступно */ }
  return out;
}
