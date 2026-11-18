/**
 * Переход к периоду в таблице истории (18.11.2026, Пульс за 17.11).
 *
 * На боевом за 30 дней «Вперёд» в таблице нажали 1164 раза 127 человек: 44 загрузки страницы листали
 * восемь страниц и больше (до 91 на Brent), чтобы дойти до нужного года. Поле «От» нажали 151 человек.
 * Здесь — чистые функции для выбора года (или отрезка страниц у годовых рядов) и для поиска строки
 * по дате, плюс общий канал «точка выбрана на графике → таблица идёт к этой дате».
 */

const PICK_EVENT = 'fe:period-pick';

function iso(date) {
  return String(date ?? '').slice(0, 10);
}

/**
 * Список переходов для строк в текущем порядке показа.
 * - Есть хотя бы два разных года и ряд не годовой — по годам: «2026», «2025», … (страница, где год начинается в этом порядке).
 * - Годовой ряд или один год — по страницам с подписью отрезка: «2025–2006», «май – янв».
 * Возвращает `{ kind, options: [{ value, label, page }] }`; `options` пуст, если страница одна.
 */
export function periodJumpOptions(rows, pageSize, { yearMode = false, pageLabel } = {}) {
  const list = rows || [];
  const size = Math.max(1, pageSize || 1);
  const pages = Math.ceil(list.length / size);
  if (pages <= 1) return { kind: 'none', options: [] };
  const years = new Set(list.map((row) => iso(row?.date).slice(0, 4)).filter(Boolean));
  if (!yearMode && years.size >= 2) {
    const seen = new Map();
    list.forEach((row, index) => {
      const year = iso(row?.date).slice(0, 4);
      if (year && !seen.has(year)) seen.set(year, Math.floor(index / size));
    });
    return {
      kind: 'year',
      options: [...seen.entries()].map(([year, page]) => ({ value: year, label: year, page })),
    };
  }
  const options = [];
  for (let page = 0; page < pages; page += 1) {
    const first = list[page * size];
    const last = list[Math.min(list.length, (page + 1) * size) - 1];
    const label = pageLabel
      ? pageLabel(first?.date, last?.date)
      : `${iso(first?.date).slice(0, 4)}–${iso(last?.date).slice(0, 4)}`;
    options.push({ value: String(page), label, page });
  }
  return { kind: 'page', options };
}

/** Значение перехода, которое соответствует открытой странице (год первой строки или номер страницы). */
export function currentJumpValue(jump, rows, page, pageSize) {
  if (!jump?.options?.length) return '';
  if (jump.kind === 'year') {
    const first = (rows || [])[page * pageSize];
    return iso(first?.date).slice(0, 4);
  }
  return String(page);
}

/**
 * Строка, ближайшая к дате, в текущем порядке показа: точная дата, иначе соседняя в сторону листания
 * (по убыванию — первая не позже даты, по возрастанию — первая не раньше). Возвращает `{ index, date }` или null.
 */
export function nearestRow(rows, date, { asc = false } = {}) {
  const list = rows || [];
  const target = iso(date);
  if (!list.length || !target) return null;
  let index = list.findIndex((row) => (asc ? iso(row?.date) >= target : iso(row?.date) <= target));
  if (index < 0) index = list.length - 1;
  return { index, date: list[index]?.date };
}

/** Точка выбрана на графике: таблица истории на странице переходит к ней. */
export function emitPeriodPick(date, source = 'chart') {
  if (typeof window === 'undefined' || !date) return;
  window.dispatchEvent(new CustomEvent(PICK_EVENT, { detail: { date: iso(date), source } }));
}

/** Подписка на выбор точки; возвращает отписку. */
export function onPeriodPick(handler) {
  if (typeof window === 'undefined') return () => {};
  const listener = (event) => handler(event.detail || {});
  window.addEventListener(PICK_EVENT, listener);
  return () => window.removeEventListener(PICK_EVENT, listener);
}
