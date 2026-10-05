// Валюта страны для калькулятора инфляции: вместо «нац. валюта» человек видит «в австралийских долларах» и «A$100 000».
// Слаги — как в каталоге стран. Подпись поля: «Сумма в австралийских долларах» / «Amount in Australian dollars».
//
// Болгария: с 1 января 2026 года в обращении евро. Расчёт от валюты не зависит (множитель цен один и тот же),
// поэтому подпись показывает действующую сегодня валюту страны.

const D = (code, symbol, ruIn, enName, prefix = false) => ({ code, symbol, ruIn, enName, prefix });

export const RUB = D('RUB', '₽', 'рублях', 'rubles');
const USD = D('USD', '$', 'долларах США', 'US dollars', true);
const EUR = D('EUR', '€', 'евро', 'euros', true);

export const COUNTRY_CURRENCY = {
  russia: RUB,
  'united-states': USD,
  'united-kingdom': D('GBP', '£', 'фунтах стерлингов', 'pounds sterling', true),
  australia: D('AUD', 'A$', 'австралийских долларах', 'Australian dollars', true),
  canada: D('CAD', 'C$', 'канадских долларах', 'Canadian dollars', true),
  'new-zealand': D('NZD', 'NZ$', 'новозеландских долларах', 'New Zealand dollars', true),
  japan: D('JPY', '¥', 'иенах', 'yen', true),
  china: D('CNY', 'CN¥', 'китайских юанях', 'Chinese yuan', true),
  india: D('INR', '₹', 'индийских рупиях', 'Indian rupees', true),
  'south-korea': D('KRW', '₩', 'вонах', 'South Korean won', true),
  turkey: D('TRY', '₺', 'турецких лирах', 'Turkish lira', true),
  israel: D('ILS', '₪', 'шекелях', 'Israeli shekels', true),
  brazil: D('BRL', 'R$', 'бразильских реалах', 'Brazilian reais', true),
  mexico: D('MXN', 'Mex$', 'мексиканских песо', 'Mexican pesos', true),
  ukraine: D('UAH', '₴', 'гривнах', 'hryvnias', true),
  georgia: D('GEL', '₾', 'лари', 'lari', true),
  azerbaijan: D('AZN', '₼', 'азербайджанских манатах', 'Azerbaijani manats', true),
  armenia: D('AMD', '֏', 'драмах', 'drams', true),
  switzerland: D('CHF', 'CHF', 'швейцарских франках', 'Swiss francs'),
  'south-africa': D('ZAR', 'R', 'рэндах', 'South African rand', true),
  poland: D('PLN', 'zł', 'злотых', 'zlotys'),
  czechia: D('CZK', 'Kč', 'чешских кронах', 'Czech koruna'),
  hungary: D('HUF', 'Ft', 'форинтах', 'forints'),
  romania: D('RON', 'lei', 'румынских леях', 'Romanian lei'),
  sweden: D('SEK', 'kr', 'шведских кронах', 'Swedish krona'),
  norway: D('NOK', 'kr', 'норвежских кронах', 'Norwegian krone'),
  denmark: D('DKK', 'kr', 'датских кронах', 'Danish krone'),
  iceland: D('ISK', 'kr', 'исландских кронах', 'Icelandic krona'),
  serbia: D('RSD', 'дин.', 'сербских динарах', 'Serbian dinars'),
  'north-macedonia': D('MKD', 'ден.', 'македонских денарах', 'Macedonian denars'),
  albania: D('ALL', 'L', 'албанских леках', 'Albanian lek'),
  moldova: D('MDL', 'L', 'молдавских леях', 'Moldovan lei'),
  bosnia: D('BAM', 'KM', 'конвертируемых марках', 'convertible marks'),
  kosovo: EUR,
  montenegro: EUR,
  // Зона евро (на 2026 год, включая Болгарию).
  austria: EUR,
  belgium: EUR,
  bulgaria: EUR,
  croatia: EUR,
  cyprus: EUR,
  estonia: EUR,
  finland: EUR,
  france: EUR,
  germany: EUR,
  greece: EUR,
  ireland: EUR,
  italy: EUR,
  latvia: EUR,
  lithuania: EUR,
  luxembourg: EUR,
  malta: EUR,
  netherlands: EUR,
  portugal: EUR,
  slovakia: EUR,
  slovenia: EUR,
  spain: EUR,
};

/** Валюта страны или null, если страны нет в таблице (тогда подпись остаётся нейтральной). */
export function currencyForCountry(slug) {
  return COUNTRY_CURRENCY[String(slug || '').toLowerCase()] || null;
}

function group(digits, locale) {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, locale === 'en' ? ',' : String.fromCharCode(160));
}

/**
 * Сумма с валютой по правилам языка: «A$100,000» / «71 827 €». Цифры целые.
 * Без валюты возвращает просто число.
 */
export function formatMoney(value, currency, locale = 'ru') {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const rounded = Math.round(Number(value));
  const body = (rounded < 0 ? '-' : '') + group(Math.abs(rounded).toString(), locale);
  if (!currency) return body;
  if (locale === 'en' && currency.prefix) return `${currency.symbol}${body}`;
  return `${body}${String.fromCharCode(160)}${currency.symbol}`;
}

/** «в австралийских долларах» / «in Australian dollars». */
export function currencyInPhrase(currency, locale = 'ru') {
  if (!currency) return '';
  return locale === 'en' ? `in ${currency.enName}` : `в ${currency.ruIn}`;
}
