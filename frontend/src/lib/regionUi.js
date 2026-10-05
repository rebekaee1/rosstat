// Человеческая подача региональных чисел: единица всегда рядом, процент с одним знаком,
// «₽» и «%» не отрываются от числа (неразрывный пробел). Используется на страницах регионов и штатов.
import { shortUnit } from './regionsApi';

export const NBSP = ' ';

function numberLocale(locale) {
  return locale === 'en' ? 'en-US' : 'ru-RU';
}

/** Единица для показа: «₽», «%», «тыс. чел.»; пустая строка, если единицу нельзя назвать коротко. */
export function unitLabel(unit, locale = 'ru') {
  const raw = (unit || '').trim();
  if (!raw) return '';
  const short = shortUnit(raw);
  if (short === '% г/г') return locale === 'en' ? '% YoY' : '% за год';
  const perPop = raw.toLowerCase().match(/^на\s*(\d[\d\s\u00a0]*)\s+(человек|жителей)/);
  if (perPop) {
    const n = perPop[1].replace(/\D/g, '');
    return locale === 'en' ? `per ${Number(n).toLocaleString('en-US')} people` : `на ${n} чел.`;
  }
  if (short) return short.replace(/^тыс /, 'тыс. ');
  const u = raw.toLowerCase();
  if (/процент|percent|%/.test(u)) return '%';
  if (/тысяч человек|thousand people/.test(u)) return locale === 'en' ? 'thous. people' : 'тыс. чел.';
  if (/рубл|ruble/.test(u)) return '₽';
  return '';
}

export function isPercentUnit(unit) {
  return unitLabel(unit) === '%' || unitLabel(unit) === '% за год' || unitLabel(unit) === '% YoY';
}

/** Число без единицы: проценты и малые величины — с одним знаком («1,0», «3,4»), крупные — целые. */
export function formatRegionNumber(value, unit, locale = 'ru') {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const num = Number(value);
  const abs = Math.abs(num);
  const percent = isPercentUnit(unit);
  let min = 0;
  let max;
  if (abs >= 10000) max = 0;
  else if (abs >= 100) max = percent ? 1 : 1;
  else if (abs >= 10) max = 1;
  else if (abs >= 1) max = percent ? 1 : 2;
  else max = 2;
  if (percent && abs < 100) min = max >= 1 ? 1 : 0;
  return num.toLocaleString(numberLocale(locale), { minimumFractionDigits: min, maximumFractionDigits: max });
}

/** «3,4 %» / «162 572 ₽» / «13 150 тыс. чел.» — единица не отрывается от числа. */
export function formatRegionWithUnit(value, unit, locale = 'ru') {
  const text = formatRegionNumber(value, unit, locale);
  if (text === '—') return text;
  const label = unitLabel(unit, locale);
  return label ? `${text}${NBSP}${label.replace(/ /g, NBSP)}` : text;
}

/** Изменение в процентах для бейджа: «44,4 %», «меньше 0,1 %». */
export function formatDeltaPercent(pct, locale = 'ru') {
  const abs = Math.abs(Number(pct));
  const dec = locale === 'en' ? '.' : ',';
  if (!Number.isFinite(abs)) return '';
  if (abs < 0.1) return `<0${dec}1${NBSP}%`;
  return `${abs.toFixed(1).replace('.', dec)}${NBSP}%`;
}

/**
 * Изменение показателя в процентах (инфляция, безработица, доля бедных) — это не «+32,9 %»,
 * а разница в процентных пунктах: «+3,1 п.п.». Возвращает null, если сравнивать нечего.
 */
export function formatPointsDelta(value, prevValue, locale = 'ru') {
  const a = Number(value);
  const b = Number(prevValue);
  if (value == null || prevValue == null || !Number.isFinite(a) || !Number.isFinite(b)) return null;
  const diff = a - b;
  const abs = Math.abs(diff);
  const dec = locale === 'en' ? '.' : ',';
  const unit = locale === 'en' ? 'p.p.' : 'п.п.';
  if (abs < 0.05) return { diff: 0, text: `0${NBSP}${unit}` };
  const sign = diff > 0 ? '+' : '−';
  return { diff, text: `${sign}${abs.toFixed(1).replace('.', dec)}${NBSP}${unit}` };
}

/**
 * Неразрывные пробелы в числах внутри текста: «на 10 000 человек» не рвётся на «10 / 000»,
 * «5 %» и «3 ₽» не отрываются от числа.
 */
export function glueNumbers(text) {
  return String(text ?? '')
    .replace(/(\d) (?=\d{3}(?!\d))/g, `$1${NBSP}`)
    .replace(/(\d) (?=[%‰₽$€£¥])/g, `$1${NBSP}`);
}

const DEMOGRAPHIC_LOAD = /коэффициент[а-яё]*\s+демографической\s+нагрузки/i;

/**
 * Показатели без единицы, которые обычному человеку не понятны («274»), получают понятное название.
 * Остальные названия не трогаем.
 */
export function plainIndicatorTitle(name, locale = 'ru') {
  const raw = glueNumbers(String(name || ''));
  if (!DEMOGRAPHIC_LOAD.test(raw)) return raw;
  const en = locale === 'en';
  if (/моложе/i.test(raw)) {
    return en ? 'Children per 1,000 working-age people' : 'Детей на 1000 человек трудоспособного возраста';
  }
  if (/старше/i.test(raw)) {
    return en ? 'Older people per 1,000 working-age people' : 'Людей старшего возраста на 1000 человек трудоспособного возраста';
  }
  if (/всего|total/i.test(raw)) {
    return en ? 'Children and older people per 1,000 working-age people' : 'Детей и пожилых на 1000 человек трудоспособного возраста';
  }
  return raw;
}

/**
 * Подсказка «что это значит» одной фразой для названий, которые без экономического образования не читаются.
 * Возвращает пустую строку, если название и так понятно. Правил немного и они точные: лучше промолчать, чем ошибиться.
 */
export function explainIndicator(name, unit, locale = 'ru') {
  const raw = String(name || '');
  const en = locale === 'en';
  if (DEMOGRAPHIC_LOAD.test(raw)) {
    return en
      ? 'How many children and older people there are for every 1,000 people of working age.'
      : 'Сколько детей и пожилых приходится на каждую тысячу человек трудоспособного возраста.';
  }
  if (/\bВРП\b|валов[а-яё]+ региональн/i.test(raw)) {
    return en
      ? 'Gross regional product: the value of everything produced in the region in a year.'
      : 'Валовой региональный продукт: стоимость всего, что произвели в регионе за год.';
  }
  if (/коэффициент\s+(миграционного|естественного)/i.test(raw)) {
    return en
      ? 'The change in population per 10,000 residents: positive means the population grows.'
      : 'Изменение численности на 10 000 жителей: плюс означает рост населения.';
  }
  if (/индекс\s+потребительских\s+цен/i.test(raw)) {
    return en
      ? 'How much consumer prices changed compared with the previous period.'
      : 'Насколько изменились потребительские цены по сравнению с прошлым периодом.';
  }
  if (isPercentUnit(unit) && /уровень|доля|удельный вес/i.test(raw)) {
    return en
      ? 'A share in percent. A change is given in percentage points: the difference between two shares.'
      : 'Доля в процентах. Изменение показано в процентных пунктах: это разница между двумя долями.';
  }
  return '';
}

/** Название показателя без хвоста «, единица» и без лишних пробелов — для коротких подписей. */
export function plainName(name) {
  return glueNumbers(String(name || '').replace(/\s+/g, ' ').trim());
}

const COMPACT_RULES_RU = {
  '₽': [[1e6, 'млн ₽', 1e6]],
  'млн ₽': [[1e6, 'трлн ₽', 1e6], [1e3, 'млрд ₽', 1e3]],
  'млрд ₽': [[1e3, 'трлн ₽', 1e3]],
  'тыс. ₽': [[1e3, 'млн ₽', 1e3]],
  'тыс. чел.': [[1e3, 'млн чел.', 1e3]],
};
const COMPACT_RULES_EN = {
  '₽': [[1e6, 'mln ₽', 1e6]],
  'mln ₽': [[1e6, 'trn ₽', 1e6], [1e3, 'bln ₽', 1e3]],
  'bln ₽': [[1e3, 'trn ₽', 1e3]],
  'thous. ₽': [[1e3, 'mln ₽', 1e3]],
  'thous. people': [[1e3, 'mln people', 1e3]],
};

/** Число и единица раздельно: число можно выделить жирным, единицу оставить обычной («0,4» + «на 1000 чел.»). */
export function compactParts(value, unit, locale = 'ru') {
  const num = Number(value);
  if (value == null || !Number.isFinite(num)) return { num: '—', unit: '' };
  const label = unitLabel(unit, locale);
  const rules = (locale === 'en' ? COMPACT_RULES_EN : COMPACT_RULES_RU)[label];
  const abs = Math.abs(num);
  const hit = rules?.find(([threshold]) => abs >= threshold);
  if (!hit) return { num: formatRegionNumber(value, unit, locale), unit: label.replace(/ /g, NBSP) };
  const scaled = num / hit[2];
  const text = scaled.toLocaleString(numberLocale(locale), {
    minimumFractionDigits: 0,
    maximumFractionDigits: Math.abs(scaled) >= 100 ? 0 : 1,
  });
  return { num: text, unit: hit[1].replace(/ /g, NBSP) };
}

/** Крупные величины в узких карточках: «8 118 831 млн ₽» → «8,1 трлн ₽», «13 150 тыс. чел.» → «13,2 млн чел.». */
export function formatRegionCompact(value, unit, locale = 'ru') {
  const parts = compactParts(value, unit, locale);
  return parts.unit ? `${parts.num}${NBSP}${parts.unit}` : parts.num;
}

const NOISY_FIRST = /беженц|убежищ|вынужденн/i;
const LEAD_NAME = /^(среднегодовая |постоянная )?численность (постоянного )?населения(?![а-яё])(?!.*(беженц|убежищ|лиц))/i;

/** В разделе сначала главное («Численность населения»), узкие и служебные строки — в конец; порядок остальных сохраняется. */
export function prioritizeIndicators(indicators) {
  const score = (item) => {
    const name = String(item?.name || '');
    if (LEAD_NAME.test(name)) return 0;
    if (NOISY_FIRST.test(name)) return 2;
    return 1;
  };
  return indicators
    .map((item, index) => ({ item, index, score: score(item) }))
    .sort((a, b) => a.score - b.score || a.index - b.index)
    .map((entry) => entry.item);
}
