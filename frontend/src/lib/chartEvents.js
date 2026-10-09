// Отметки событий на графиках (круг 11, зона C).
// Короткий общий справочник крупных событий мировой и российской экономики. Подписи только называют событие
// и ничего не говорят о его последствиях: связь события со скачком на графике читатель решает сам.
// Названия лежат в i18n (`c11c.event.<id>`), здесь только даты.

/** Дата — первый день месяца события. Порядок по времени. */
export const CHART_EVENTS = Object.freeze([
  { id: 'ussr1991', date: '1991-12-01' },
  { id: 'asia1997', date: '1997-07-01' },
  { id: 'russia1998', date: '1998-08-01' },
  { id: 'euro1999', date: '1999-01-01' },
  { id: 'crisis2008', date: '2008-09-01' },
  { id: 'eurozone2010', date: '2010-05-01' },
  { id: 'ruble2014', date: '2014-12-01' },
  { id: 'brexit2016', date: '2016-06-01' },
  { id: 'covid2020', date: '2020-03-01' },
  { id: 'sanctions2022', date: '2022-02-01' },
  { id: 'rates2022', date: '2022-03-01' },
  { id: 'banks2023', date: '2023-03-01' },
]);

const DAY = 86400000;

function ms(date) {
  const t = Date.parse(`${String(date ?? '').slice(0, 10)}T00:00:00Z`);
  return Number.isFinite(t) ? t : NaN;
}

/** Типичный шаг между точками в днях (медиана): день, месяц, квартал, год. */
export function medianStepDays(dates) {
  const times = (dates || []).map(ms).filter(Number.isFinite).sort((a, b) => a - b);
  if (times.length < 2) return 0;
  const gaps = [];
  for (let i = 1; i < times.length; i += 1) gaps.push((times[i] - times[i - 1]) / DAY);
  gaps.sort((a, b) => a - b);
  return gaps[Math.floor(gaps.length / 2)];
}

/**
 * События, которые попадают в окно графика, привязанные к его датам.
 * Точка графика стоит в начале своего периода (месяца, года), поэтому событие ставится на последнюю точку,
 * которая не позже события и отстоит от него меньше одного шага: события 2008-09 у годового ряда это 2008, у месячного сентябрь.
 * Событие раньше первой точки или позже последней в список не попадает; прогноз никогда не получает отметок.
 *
 * @param {string[]} dates даты точек окна по возрастанию (ISO)
 * @returns {Array<{id: string, date: string, at: string, year: number}>} `at` — дата точки графика для оси X
 */
export function eventsInWindow(dates, events = CHART_EVENTS) {
  const list = (dates || []).map((d) => String(d).slice(0, 10)).filter((d) => Number.isFinite(ms(d)));
  if (list.length < 2) return [];
  const step = medianStepDays(list) || 31;
  const first = ms(list[0]);
  const last = ms(list[list.length - 1]);
  const out = [];
  const used = new Set();
  for (const event of events) {
    const at = ms(event.date);
    if (at < first || at > last + step * DAY) continue;
    let hit = null;
    for (let i = list.length - 1; i >= 0; i -= 1) {
      if (ms(list[i]) <= at) { hit = list[i]; break; }
    }
    if (!hit) continue;
    if ((at - ms(hit)) / DAY >= step * 1.05 + 1) continue;
    if (used.has(`${event.id}`)) continue;
    used.add(event.id);
    out.push({
      id: event.id, date: event.date, at: hit, year: Number(event.date.slice(0, 4)),
    });
  }
  return out;
}

/**
 * Какие из отметок получают подпись года: соседние подписи ближе `minGapPx` не печатаем.
 * @param {Array<{at:string}>} marks
 * @param {string[]} dates даты точек окна
 * @param {number} plotPx ширина области построения
 */
export function labelledMarks(marks, dates, plotPx, minGapPx = 30) {
  const n = (dates || []).length;
  if (!marks.length || n < 2 || !(plotPx > 0)) return new Set();
  const index = new Map(dates.map((d, i) => [String(d).slice(0, 10), i]));
  const shown = new Set();
  let lastX = -Infinity;
  for (const mark of marks) {
    const i = index.get(mark.at);
    if (i == null) continue;
    const x = (i / (n - 1)) * plotPx;
    if (x - lastX >= minGapPx) { shown.add(mark.id); lastX = x; }
  }
  return shown;
}
