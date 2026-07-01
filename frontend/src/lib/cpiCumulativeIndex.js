/**
 * Накопленный индекс уровня цен из месячного %-ряда ИПЦ (база 100 = январь 2000).
 *
 * Детерминированное client-side преобразование месячного м/м-ряда (значения
 * 100.x) в непрерывный уровень цен с фиксированной базой. Точки до базы
 * достраиваются обратным цепным делением (значения 90-х микроскопические на
 * фоне 100 — это ожидаемо: гиперинфляция первой половины 90-х).
 *
 * Архитектура (ADR-0006): накопленный индекс остаётся client-side display-
 * transform, а НЕ backend-derived рядом (тот же класс, что daily-aggregation).
 * Единая точка истины — используется и карточкой индикатора
 * (`useIndicatorViewModeData`), и режимом сравнения (`compareRepresentation`).
 */

export const CPI_INDEX_BASE_DATE = '2000-01-01';
export const CPI_INDEX_BASE_VALUE = 100;

// До базы значения уровня << 1 — два знака схлопнули бы их в 0.00, поэтому
// для малых значений сохраняем 4 значащие цифры.
export function roundIndexLevel(v) {
  return Math.abs(v) >= 1 ? +v.toFixed(2) : +v.toPrecision(4);
}

export function buildCumulativeIndex(rawPoints) {
  if (!Array.isArray(rawPoints) || !rawPoints.length) return [];
  const pts = rawPoints
    .slice()
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  let baseIdx = pts.findIndex((p) => String(p.date) >= CPI_INDEX_BASE_DATE);
  if (baseIdx === -1) baseIdx = pts.length - 1;
  const out = new Array(pts.length);
  out[baseIdx] = { ...pts[baseIdx], value: CPI_INDEX_BASE_VALUE };
  let acc = CPI_INDEX_BASE_VALUE;
  for (let i = baseIdx + 1; i < pts.length; i++) {
    acc *= Number(pts[i].value) / 100;
    out[i] = { ...pts[i], value: roundIndexLevel(acc) };
  }
  acc = CPI_INDEX_BASE_VALUE;
  for (let i = baseIdx - 1; i >= 0; i--) {
    // value точки i+1 — м/м-прирост к месяцу i: уровень(i) = уровень(i+1) / (м/м / 100).
    acc /= Number(pts[i + 1].value) / 100;
    out[i] = { ...pts[i], value: roundIndexLevel(acc) };
  }
  return out;
}
