/**
 * Тексты событий календаря для человека.
 *
 * Названия, описания и отчётные периоды приходят из базы в служебном виде («Заседание ЦБ по ключевой ставке
 * (опорное)», «Ставка RUONIA», «сентябрь 2026», «Q2 2026»). Раскрываем их здесь, на выходе, чтобы
 * не менять данные, на которые завязаны ключи событий и группировка.
 */
import { plural } from './calcFormat';

const CYRILLIC_RE = /[А-Яа-яЁё]/;

const MONTH_STEMS = [
  ['январ', 'January'], ['феврал', 'February'], ['март', 'March'], ['апрел', 'April'],
  ['мая', 'May'], ['май', 'May'], ['июн', 'June'], ['июл', 'July'], ['август', 'August'],
  ['сентябр', 'September'], ['октябр', 'October'], ['ноябр', 'November'], ['декабр', 'December'],
];
const MONTH_WORD_RE = /(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*/gi;
const ROMAN_QUARTER = { I: 1, II: 2, III: 3, IV: 4 };
const ROMAN = ['', 'I', 'II', 'III', 'IV'];

/** «Индекс потребительских цен (ИПЦ)» → без скобочной аббревиатуры; служебные пометки заседаний — по-человечески. */
export function plainEventTitle(title, locale = 'ru') {
  let text = String(title || '').trim();
  if (!text) return '';
  if (locale === 'en') {
    text = text
      .replace(/^CBR Key Rate Decision\s*\((?:core|interim)\)$/i, 'Key rate decision')
      .replace(/^RUONIA Rate$/i, 'Overnight interbank rate');
  } else {
    text = text
      .replace(/^Заседание ЦБ по ключевой ставке\s*\((?:опорное|промежуточное)\)$/i, 'Решение по ключевой ставке')
      .replace(/^Ставка RUONIA$/i, 'Однодневная ставка межбанковских кредитов');
  }
  return text.replace(/\s*\([A-ZА-ЯЁ]{2,6}\)\s*$/u, '').trim();
}

/**
 * Описание события для человека: расшифровывает сокращения, которые встречаются в описаниях из базы
 * (RUONIA, ИПЦ, ИЦП, ВРП), и оставляет одну первую фразу: «что это», без абзацев про методологию.
 */
export function plainEventText(text, locale = 'ru') {
  let out = String(text || '').trim();
  if (!out) return '';
  // Аббревиатура в скобках после расшифровки («индекс потребительских цен (ИПЦ)») — лишняя.
  out = out.replace(/\s*\((?:ИПЦ|ИЦП|ВРП|RUONIA|CPI)\)/g, '');
  if (locale === 'en') {
    out = out
      .replace(/\b(?:the\s+)?RUONIA(?:\s+rate)?\b/gi, 'overnight interbank rate')
      .replace(/\bCPI\b/g, 'consumer prices (inflation)');
  } else {
    out = out
      .replace(/(?:ставк[аиу]\s+)?\bRUONIA\b/gi, 'ставка по однодневным кредитам между банками')
      // \b в JavaScript не видит кириллицу, поэтому границы слова — через lookaround.
      .replace(/(?<![А-Яа-яЁё])ИПЦ(?![А-Яа-яЁё])/g, 'инфляция')
      .replace(/(?<![А-Яа-яЁё])ИЦП(?![А-Яа-яЁё])/g, 'цены производителей')
      .replace(/(?<![А-Яа-яЁё])ВРП(?![А-Яа-яЁё])/g, 'производство региона');
  }
  const sentence = out.match(/^.+?[.!?](?=\s|$)/);
  const first = sentence ? sentence[0].trim() : out;
  return first.charAt(0).toUpperCase() + first.slice(1);
}

/** Короткое название для клетки календаря: два-три слова, без служебных слов. */
export function shortEventTitle(title, locale = 'ru') {
  const text = plainEventTitle(title, locale);
  if (!text) return '';
  const KNOWN = locale === 'en'
    ? [[/^Key rate decision$/i, 'Key rate'], [/consumer price/i, 'Inflation'], [/producer price/i, 'Producer prices']]
    : [[/^Решение по ключевой ставке$/i, 'Ключевая ставка'], [/потребительских цен/i, 'Инфляция'], [/цен производителей/i, 'Цены производителей']];
  for (const [re, short] of KNOWN) if (re.test(text)) return short;
  const words = text.split(/\s+/);
  return words.length > 3 ? `${words.slice(0, 3).join(' ')}…` : text;
}

function englishMonth(stemText) {
  const low = stemText.toLowerCase();
  const hit = MONTH_STEMS.find(([stem]) => low.startsWith(stem));
  return hit ? hit[1] : stemText;
}

/** Отчётный период «сентябрь 2026» / «Q2 2026» / «II квартал 2026» на языке страницы; нераспознанное по-русски в EN скрываем. */
export function localizeReferencePeriod(ref, locale = 'ru') {
  const text = String(ref || '').trim();
  if (!text) return '';
  const q = text.match(/^Q([1-4])\s+(\d{4})$/i) || text.match(/^([IV]+)\s+квартал\s+(\d{4})$/i);
  if (q) {
    const n = /^\d$/.test(q[1]) ? Number(q[1]) : ROMAN_QUARTER[q[1].toUpperCase()];
    if (n) return locale === 'en' ? `Q${n} ${q[2]}` : `${ROMAN[n]} квартал ${q[2]}`;
  }
  if (locale !== 'en') return text;
  const out = text.replace(MONTH_WORD_RE, (m) => englishMonth(m));
  return CYRILLIC_RE.test(out) ? '' : out;
}

/** Форма числа для t('…one|few|many'): в английском только one и many. */
export function pluralForm(n, locale) {
  return locale === 'en' ? (n === 1 ? 'one' : 'many') : plural(n, 'one', 'few', 'many');
}

/**
 * Описание для группы событий одной публикации. Индекс цен и его части («cpi», «cpi-food», «cpi-services»)
 * показывают описание головного показателя; если события разные по смыслу (экспорт, импорт, сальдо),
 * а описания у них различаются, общего описания нет — лучше пусто, чем описание одной из частей.
 */
export function groupDescription(events) {
  const list = (Array.isArray(events) ? events : []).filter(Boolean);
  if (!list.length) return undefined;
  const descriptions = new Set(list.map((ev) => ev.description || ''));
  if (descriptions.size === 1) return list[0].description;
  const head = list.reduce((best, ev) => (
    String(ev.indicator_code || '~').length < String(best.indicator_code || '~').length ? ev : best
  ), list[0]);
  const headCode = String(head.indicator_code || '');
  const nested = headCode && list.every((ev) => String(ev.indicator_code || '').startsWith(headCode));
  return nested ? head.description : undefined;
}
