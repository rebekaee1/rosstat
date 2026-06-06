/**
 * Карта семейств режимов отображения для индикаторов.
 *
 * Каждое «family» соответствует ОДНОЙ карточке в каталоге (видимой
 * пользователю), а внутри неё лежат несколько «режимов» — каждый со своим
 * derived-кодом или с client-side трансформацией.
 *
 * Решение: ADR-0001 + звонок 2026-05-22. Унифицируем дублирующиеся
 * листинги (exports / exports-yoy / exports-qoq → одна карточка
 * «Экспорт товаров» c переключателем).
 *
 * Структура:
 *   VIEW_MODE_FAMILIES[parentCode] = {
 *     label: 'Экспорт товаров',
 *     modes: [
 *       { mode: 'level', label: 'Уровень', code: '<parent>', unit?: '...' },
 *       { mode: 'yoy',   label: 'к г/г',   code: '<parent>-yoy', unit: '%' },
 *       { mode: 'mom',   label: 'MoM %',   code: '<parent>', unit: '%', transform: 'mom' },
 *       ...
 *     ],
 *   }
 *
 * Поля режима:
 *   - mode      — ключ URL-параметра ?mode=… (обязательный, уникальный в семье)
 *   - label     — подпись для UI (обязательная)
 *   - code      — backend-код, чьи точки рендерятся (или родительский,
 *                 если transform виртуальный)
 *   - unit      — переопределение единицы parent'а (только если режим её меняет)
 *   - frequency — переопределение частоты parent'а: подменяется в pill под
 *                 breadcrumbs и заголовке графика. Обязательно для каждого
 *                 не-`level` mode, у которого target sibling имеет частоту,
 *                 отличную от родителя (см. trap «View-mode family metadata
 *                 leak» в CONTEXT.md). Для virtual transforms `mom` явно
 *                 указывать не нужно — frequency остаётся родительская.
 *   - transform — виртуальный transform (`'mom'`) — точки считаются на фронте,
 *                 backend не дёргается
 *
 * Поведение URL:
 *   - level → `/indicators/<parent>` без `?mode`
 *   - другие → `/indicators/<parent>?mode=<mode>`
 *
 * Семьи (по фазам грамотной унификации):
 *   - Phase 1 — внешняя торговля (exports/imports/balance/current-account
 *               quarterly + monthly с MoM)
 *   - Phase 2 — рынок труда (unemployment; wages-nominal → wagesNominalViewMode*)
 *   - Phase 3 — недвижимость (housing-price-primary/secondary)
 *
 * Phase 4 (ставки) и Phase 5 (daily) держим вне этого реестра:
 *   - ставки — отдельный VariantGroupPicker (срок 1y / 1-3y / >3y),
 *     не «режим отображения».
 *   - daily — agregation transform реализован отдельно (см. `aggregateTransform`
 *     в этом же файле, экспортируется для использования в Detail).
 */

export const VIEW_MODE_FAMILIES = {
  // ============================================================
  // Phase 1 — Trade (quarterly)
  // ============================================================
  exports: {
    label: 'Экспорт товаров',
    modes: [
      { mode: 'level', label: 'Уровень',  code: 'exports' },
      { mode: 'yoy',   label: 'YoY %',    code: 'exports-yoy', unit: '%', frequency: 'quarterly' },
      { mode: 'qoq',   label: 'QoQ %',    code: 'exports-qoq', unit: '%', frequency: 'quarterly' },
    ],
  },
  imports: {
    label: 'Импорт товаров',
    modes: [
      { mode: 'level', label: 'Уровень',  code: 'imports' },
      { mode: 'yoy',   label: 'YoY %',    code: 'imports-yoy', unit: '%', frequency: 'quarterly' },
      { mode: 'qoq',   label: 'QoQ %',    code: 'imports-qoq', unit: '%', frequency: 'quarterly' },
    ],
  },
  'trade-balance': {
    label: 'Торговый баланс',
    modes: [
      { mode: 'level',   label: 'Уровень',   code: 'trade-balance' },
      { mode: 'yoy_abs', label: 'YoY, абс.', code: 'trade-balance-yoy-abs', frequency: 'quarterly' },
    ],
  },
  'current-account': {
    label: 'Сальдо текущего счёта',
    modes: [
      { mode: 'level',   label: 'Уровень',   code: 'current-account' },
      { mode: 'yoy_abs', label: 'YoY, абс.', code: 'current-account-yoy-abs', frequency: 'quarterly' },
    ],
  },

  // === Phase 1 monthly counterparts — MoM% on-the-fly ===
  'exports-monthly': {
    label: 'Экспорт товаров (помесячно)',
    modes: [
      { mode: 'level', label: 'Уровень', code: 'exports-monthly' },
      { mode: 'mom',   label: 'MoM %',   code: 'exports-monthly', unit: '%', transform: 'mom' },
    ],
  },
  'imports-monthly': {
    label: 'Импорт товаров (помесячно)',
    modes: [
      { mode: 'level', label: 'Уровень', code: 'imports-monthly' },
      { mode: 'mom',   label: 'MoM %',   code: 'imports-monthly', unit: '%', transform: 'mom' },
    ],
  },
  'services-exports-monthly': {
    label: 'Экспорт услуг (помесячно)',
    modes: [
      { mode: 'level', label: 'Уровень', code: 'services-exports-monthly' },
      { mode: 'mom',   label: 'MoM %',   code: 'services-exports-monthly', unit: '%', transform: 'mom' },
    ],
  },
  'services-imports-monthly': {
    label: 'Импорт услуг (помесячно)',
    modes: [
      { mode: 'level', label: 'Уровень', code: 'services-imports-monthly' },
      { mode: 'mom',   label: 'MoM %',   code: 'services-imports-monthly', unit: '%', transform: 'mom' },
    ],
  },

  // ============================================================
  // Phase 2 — Labour market
  // ============================================================
  //
  // wages-nominal — wagesNominalViewMode* (уровень C), см. WagesNominalIndicatorControls.
  // gdp-nominal — gdpNominalViewMode* (уровень C), см. GdpNominalIndicatorControls.
  // gdp-real — gdpRealViewMode* (уровень C), см. GdpRealIndicatorControls.
  // unemployment — unemploymentViewMode* (уровень C), см. UnemploymentIndicatorControls.

  // Phase 3 housing — housingViewMode* (как ИПЦ), см. HousingIndicatorControls.
  // ИЦП (ppi) — ppiViewMode*, см. PpiIndicatorControls.
};

/**
 * Mapping daily-aggregation `granularity` → `frequency` для эффективного
 * indicator'а. Используется в `IndicatorDetail.jsx`, чтобы pill/title
 * отражали фактическую агрегированную частоту daily-индикаторов (Phase 5).
 */
export const DAILY_AGG_FREQUENCY = {
  week: 'weekly',
  month: 'monthly',
  quarter: 'quarterly',
  year: 'annual',
};

// ----------------------------------------------------------------------
// Virtual transforms (client-side derived)
// ----------------------------------------------------------------------

/**
 * MoM% (месяц к предыдущему месяцу).
 *
 * Вход:  массив `{date, value}` в любом порядке.
 * Выход: массив `{date, value}` той же формы, но `value` — `(val_t / val_{t-1} - 1) * 100`,
 *        округлённый до 2 знаков. Первый элемент исходного ряда отбрасывается;
 *        пары с нулевым знаменателем отбрасываются.
 */
export function applyMoMTransform(points) {
  if (!points || points.length < 2) return [];
  const sorted = [...points].sort((a, b) => {
    const da = new Date(a.date).getTime();
    const db = new Date(b.date).getTime();
    return da - db;
  });
  const out = [];
  for (let i = 1; i < sorted.length; i++) {
    const prev = Number(sorted[i - 1].value);
    const cur = Number(sorted[i].value);
    if (!prev) continue;
    const mom = Math.round((cur / prev - 1) * 100 * 100) / 100;
    out.push({ ...sorted[i], value: mom });
  }
  return out;
}

/**
 * Period bucket key для агрегации daily-индикаторов.
 *
 * `granularity` ∈ {'week', 'month', 'quarter', 'year'}.
 * Возвращает строку-ключ, по которой группируются точки в bucket'ы.
 *
 * - week:    ISO неделя (год+неделя), bucket — конец недели (воскресенье).
 * - month:   `YYYY-MM`, bucket — последний день месяца.
 * - quarter: `YYYY-Q`,  bucket — последний день квартала.
 * - year:    `YYYY`,    bucket — 31 декабря.
 */
function bucketEndDate(date, granularity) {
  const d = new Date(date);
  if (granularity === 'year') {
    return new Date(Date.UTC(d.getUTCFullYear(), 11, 31)).toISOString().slice(0, 10);
  }
  if (granularity === 'quarter') {
    const q = Math.floor(d.getUTCMonth() / 3);
    const endMonth = q * 3 + 2;
    const endDay = new Date(Date.UTC(d.getUTCFullYear(), endMonth + 1, 0)).getUTCDate();
    return new Date(Date.UTC(d.getUTCFullYear(), endMonth, endDay)).toISOString().slice(0, 10);
  }
  if (granularity === 'month') {
    const endDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
    return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), endDay)).toISOString().slice(0, 10);
  }
  // ISO week: воскресенье текущей недели (для простоты — последний день
  // в окне «Mon-Sun»). JS Date: getUTCDay() returns 0 (Sun) .. 6 (Sat).
  const day = d.getUTCDay() === 0 ? 7 : d.getUTCDay();
  const sunday = new Date(d);
  sunday.setUTCDate(d.getUTCDate() + (7 - day));
  return sunday.toISOString().slice(0, 10);
}

/**
 * Среднее по bucket'ам (для daily → weekly/monthly/quarterly/annual avg).
 *
 * Точки группируются по `granularity` ({'week','month','quarter','year'}),
 * внутри bucket'а считается арифметическое среднее `value`. Bucket'ы
 * сортируются по конечной дате; на выход — массив `{date, value}`,
 * где `date` — конец bucket'а, `value` — среднее.
 *
 * Используется как virtual transform для daily-индикаторов: key-rate,
 * ruonia, cbr-fx-*, gold-price → пользователь может смотреть динамику
 * на укрупнённой частоте без backend-derived (Phase 5).
 */
export function applyAggregateTransform(points, granularity) {
  if (!points || points.length === 0) return [];
  if (!['week', 'month', 'quarter', 'year'].includes(granularity)) return points;
  const groups = new Map();
  for (const p of points) {
    if (p?.date == null || p.value == null) continue;
    const key = bucketEndDate(p.date, granularity);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(Number(p.value));
  }
  const out = [];
  for (const [key, vals] of groups) {
    if (!vals.length) continue;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    out.push({ date: key, value: Math.round(avg * 10000) / 10000 });
  }
  out.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  return out;
}

// ----------------------------------------------------------------------
// Lookups
// ----------------------------------------------------------------------

/** Resolve family by parent code, or null if code is not a family root. */
export function findViewModeFamily(code) {
  if (VIEW_MODE_FAMILIES[code]) return VIEW_MODE_FAMILIES[code];
  for (const family of Object.values(VIEW_MODE_FAMILIES)) {
    if (family.modes.some((m) => m.code === code)) return family;
  }
  return null;
}

/** Родительская карточка и mode для derived-URL (housing-yoy-* → parent?mode=yoy). */
export function viewModeCanonicalTarget(code) {
  for (const [parentCode, family] of Object.entries(VIEW_MODE_FAMILIES)) {
    const modeMeta = family.modes.find((m) => m.code === code);
    if (modeMeta && modeMeta.mode !== 'level') {
      return { parentCode, mode: modeMeta.mode };
    }
  }
  return null;
}

/** Find the derived code for a (parent, mode) pair. */
export function viewModeCode(parentCode, mode) {
  const family = findViewModeFamily(parentCode);
  if (!family) return parentCode;
  const m = family.modes.find((x) => x.mode === mode);
  return m?.code ?? parentCode;
}
