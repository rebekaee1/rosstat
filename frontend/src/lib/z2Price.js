// Месячная страница цены региона: чистые помощники (без React) — свежесть ряда, сравнение, изменение за период, группы «Ещё в разделе».
import { NBSP } from './regionUi';

/** Порядок групп цен (price_group от API). Неизвестные группы идут после известных. */
export const PRICE_GROUP_ORDER = [
  'Продукты', 'ЖКХ', 'Транспорт', 'Связь', 'Жильё', 'Услуги',
  'Лекарства', 'Одежда и товары', 'Отдых', 'Топливо', 'Прочее',
];

/** YYYYMM / «YYYY-MM» / {year, month} → {year, month} или null. */
export function parseYm(v) {
  if (v == null || v === '') return null;
  if (typeof v === 'object' && v.year && v.month) return { year: +v.year, month: +v.month };
  const digits = String(v).replace(/\D/g, '');
  if (digits.length !== 6) return null;
  const year = +digits.slice(0, 4);
  const month = +digits.slice(4);
  return month >= 1 && month <= 12 ? { year, month } : null;
}

export function ymLabel(v, locale = 'ru') {
  const ym = parseYm(v);
  if (!ym) return '';
  const name = new Date(2000, ym.month - 1, 1)
    .toLocaleDateString(locale === 'en' ? 'en-US' : 'ru-RU', { month: 'long' });
  return `${name} ${ym.year}`;
}

/** «сентября 2025» (родительный падеж для «с …»). */
export function ymLabelFrom(v, locale = 'ru') {
  const ym = parseYm(v);
  if (!ym) return '';
  if (locale === 'en') return ymLabel(v, locale);
  const m = new Date(2000, ym.month - 1, 1).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }).replace(/^\d+\s*/, '');
  return `${m} ${ym.year}`;
}

/** Поле может лежать в `indicator` или на верхнем уровне ответа. */
export function pickField(active, key) {
  const v = active?.indicator?.[key];
  return v !== undefined && v !== null ? v : (active?.[key] ?? null);
}

/** Изменение последней точки к точке `months` месяцев назад, % (null, если такой точки нет). */
export function changeOverMonths(series, months) {
  if (!Array.isArray(series) || series.length < 2) return null;
  const last = series[series.length - 1];
  const idx = last.year * 12 + last.month - months;
  const prev = series.find((p) => p.year * 12 + p.month === idx);
  if (!prev || !prev.value) return null;
  return { pct: ((last.value - prev.value) / Math.abs(prev.value)) * 100, from: prev };
}

export function signedPct(pct, locale = 'ru', digits = 1) {
  const dec = locale === 'en' ? '.' : ',';
  const abs = Math.abs(pct).toFixed(digits).replace('.', dec);
  const tiny = Math.abs(pct) < 0.05;
  const sign = tiny ? '' : pct > 0 ? '+' : '−';
  return `${sign}${abs}${NBSP}%`;
}

/** Сравнение региона с Россией и Москвой: [{key, value, month, pct}] (пусто без compare; для Москвы — только Россия). */
export function compareRows(compare, regionSlug, lastValue) {
  if (!compare || typeof compare !== 'object' || !(lastValue > 0)) return [];
  const rows = [];
  for (const key of ['russia', 'moskva']) {
    if (key === 'moskva' && regionSlug === 'moskva') continue;
    const c = compare[key];
    if (!c || c.value == null || !(Number(c.value) > 0)) continue;
    rows.push({
      key,
      value: Number(c.value),
      month: c.month ?? null,
      pct: ((lastValue - Number(c.value)) / Number(c.value)) * 100,
    });
  }
  return rows;
}

/** Группы соседних позиций: группа текущей первой, дальше по PRICE_GROUP_ORDER; внутри живые раньше снятых. Без price_group — null. */
export function groupSiblings(siblings, currentGroup) {
  if (!Array.isArray(siblings) || !siblings.length) return null;
  if (!siblings.some((s) => s.price_group)) return null;
  const map = new Map();
  siblings.forEach((s, i) => {
    const g = s.price_group || 'Прочее';
    if (!map.has(g)) map.set(g, []);
    map.get(g).push({ s, i });
  });
  const rank = (g) => {
    if (g === currentGroup) return -1;
    const k = PRICE_GROUP_ORDER.indexOf(g);
    return k === -1 ? 100 : k;
  };
  return [...map.entries()]
    .sort((a, b) => rank(a[0]) - rank(b[0]))
    .map(([group, items]) => ({
      group,
      items: items
        .sort((a, b) => (Number(!!a.s.is_discontinued) - Number(!!b.s.is_discontinued)) || (a.i - b.i))
        .map((x) => x.s),
    }));
}

/** Годовые отметки оси X месячного ряда: от последнего года назад, шаг 1/2/5/10/20, не больше `max`. */
export function yearTickPeriods(points, max = 5) {
  if (!points?.length) return [];
  const firstYear = points[0].year;
  const lastYear = points[points.length - 1].year;
  const span = lastYear - firstYear;
  const cap = Math.max(2, max);
  let step = 1;
  for (const s of [1, 2, 5, 10, 20]) {
    step = s;
    if (Math.floor(span / s) + 1 <= cap) break;
  }
  const out = [];
  for (let y = lastYear; y >= firstYear; y -= step) {
    const p = points.find((d) => d.year === y);
    if (p) out.unshift(p.period);
  }
  return out;
}

const upFirst = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

/** Короткое имя цены без ведомственного шаблона: «Средняя цена: яйца куриные, рублей за 10 штук» → «Яйца куриные». Запасной путь, пока API не отдал short_name. */
export function shortPriceName(name, unit) {
  if (!name) return name;
  let s = String(name).replace(/^Средняя цена:\s*/i, '');
  if (unit && s.endsWith(`, ${unit}`)) s = s.slice(0, -(unit.length + 2));
  s = s.replace(/,\s*рубл\S*\s+(за|в)\s.*$/i, '');
  return upFirst(s.trim()) || name;
}

/** «рублей за 10 штук» → «за 10 штук»; «рублей в месяц» → «в месяц»; иначе ''. */
export function unitSuffix(unit) {
  const m = /^рубл\S*\s+((?:за|в)\s+.+)$/i.exec(unit || '');
  return m ? m[1] : '';
}

const PER_ONE = { 'штук': 'штуку', 'таблеток': 'таблетку', 'капсул': 'капсулу', 'ампул': 'ампулу' };
/** Цена за одну штуку/таблетку для упаковок «за 10 штук»: {value, word} или null. */
export function perUnitPrice(unit, value) {
  const m = /за\s+(\d+)\s+(штук|таблеток|капсул|ампул)(?![а-яё])/i.exec(unit || '');
  if (!m || !(Number(m[1]) > 1) || !(value > 0)) return null;
  return { value: value / Number(m[1]), word: PER_ONE[m[2].toLowerCase()] };
}

const GROUP_RULES = [
  ['Топливо', /бензин|дизельн|топлив/i],
  ['Лекарства', /таблеток|капсул|ампул|мазь|сироп|лекарств|порошок/i],
  ['Связь', /абонентск|связ|интернет|телефон|радиоточк|антенн|телеканал/i],
  ['Транспорт', /проезд|такси|билет|автобус|метро|трамвай|троллейбус|перевозк/i],
  ['ЖКХ', /отоплен|горяч|холодн|водоснабж|электроэнерг|природн.*газ|водоотвед|канализац|вывоз|содержани|найм/i],
  ['Жильё', /квартир|аренд|жиль|недвижим/i],
  ['Услуги', /стрижк|химчистк|ремонт|услуг|баня|парикмахер|прачеч|фотограф|ритуал|обучен/i],
  ['Одежда и товары', /костюм|пальто|куртк|обувь|сапог|платье|рубашк|джинс|телевизор|холодильник|стиральн|утюг|пылесос|мебель|трикотаж|шерст|ткан/i],
  ['Отдых', /путёвк|путевк|санатор|кино|театр|абонемент/i],
  ['Продукты', /хлеб|молоко|мясо|говядин|свинин|куриц|курин|яйц|сыр|масло|сахар|мука|крупа|рис|греч|картофел|овощ|фрукт|яблок|капуст|морковь|лук|рыба|колбас|сосиск|творог|кефир|сметан|вермишел|макарон|чай|кофе|соль|консерв|конфет|печень|шоколад|пшен|помидор|огурц|банан|апельсин|сельд/i],
];
/** Запасная группа по названию, пока API не отдал price_group. */
export function guessPriceGroup(name, unit) {
  const text = `${name || ''} ${unit || ''}`;
  for (const [g, re] of GROUP_RULES) if (re.test(text)) return g;
  return 'Прочее';
}
