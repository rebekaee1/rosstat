/**
 * Carte des режимов отображения для индикаторов внешней торговли.
 *
 * Каждый «family» соответствует одной карточке в каталоге (видимой
 * пользователю), а внутри неё лежат несколько готовых derived-кодов,
 * каждый со своей семантикой. Доступные режимы (зависит от индикатора):
 *   - `level`   — собственный ряд (млн $, sum), без преобразования.
 *   - `yoy`     — derived `*-yoy`, % к тому же кварталу год назад
 *                 (имеет смысл только для рядов с **положительной** базой).
 *   - `qoq`     — derived `*-qoq`, % к предыдущему кварталу.
 *   - `yoy_abs` — derived `*-yoy-abs`, **разница в единицах источника** к г/г.
 *                 Применяется к balances со знаком (trade-balance,
 *                 current-account): процент YoY от balance с переходом через
 *                 ноль даёт тысячи процентов и пугает пользователя.
 *
 * Пользователь видит ОДНУ карточку «Экспорт товаров», переключает
 * вид через `ViewModePicker` — URL принимает `?mode=yoy`/`?mode=qoq`,
 * страница перерисовывается на соответствующий derived без ухода
 * на отдельную route. Решение оформлено как звонок 2026-05-22 + ADR-0001
 * (derived = режим отображения, не самостоятельный листинг).
 *
 * Структура:
 *   TRADE_VIEW_MODE_FAMILIES[parentCode] = {
 *     label: 'Экспорт товаров',
 *     modes: [
 *       { mode: 'level', label: 'Уровень', code: '<parent>', unit?: '...' },
 *       { mode: 'yoy',   label: 'к г/г',   code: '<parent>-yoy', unit: '%' },
 *       ...
 *     ],
 *   }
 *
 * Поле `unit` — необязательное; задаётся **только если режим меняет
 * единицу относительно parent**. Для `yoy %` / `qoq %` → '%', для
 * `yoy_abs` → unit parent'а (сохраняется), для `level` — undefined.
 */

export const TRADE_VIEW_MODE_FAMILIES = {
  exports: {
    label: 'Экспорт товаров',
    modes: [
      { mode: 'level', label: 'Уровень',  code: 'exports' },
      { mode: 'yoy',   label: 'YoY %',    code: 'exports-yoy', unit: '%' },
      { mode: 'qoq',   label: 'QoQ %',    code: 'exports-qoq', unit: '%' },
    ],
  },
  imports: {
    label: 'Импорт товаров',
    modes: [
      { mode: 'level', label: 'Уровень',  code: 'imports' },
      { mode: 'yoy',   label: 'YoY %',    code: 'imports-yoy', unit: '%' },
      { mode: 'qoq',   label: 'QoQ %',    code: 'imports-qoq', unit: '%' },
    ],
  },
  'trade-balance': {
    label: 'Торговый баланс',
    modes: [
      { mode: 'level',   label: 'Уровень',         code: 'trade-balance' },
      { mode: 'yoy_abs', label: 'YoY, абс.',       code: 'trade-balance-yoy-abs' },
    ],
  },
  'current-account': {
    label: 'Сальдо текущего счёта',
    modes: [
      { mode: 'level',   label: 'Уровень',         code: 'current-account' },
      { mode: 'yoy_abs', label: 'YoY, абс.',       code: 'current-account-yoy-abs' },
    ],
  },

  // === Monthly counterparts — MoM% on-the-fly (звонок 2026-05-22) ===
  //
  // Помесячные ряды (`*-monthly`) дают возможность смотреть «месяц к месяцу»
  // напрямую: derived в БД мы не создаём (избегаем дублирования) — режим
  // MoM% рассчитывается **на frontend** из baseDataPoints. Виртуальный
  // transform отмечается полем `transform: 'mom'`; код режима остаётся
  // равным parent monthly indicator, потому что backend-данных по нему нет.
  //
  // `applyMoMTransform` ниже превращает массив `[{date, value}, ...]`
  // в массив `[{date_t, (val_t/val_{t-1} - 1) * 100}]`. Точки без
  // валидного предшественника отбрасываются (например, первый месяц ряда
  // и месяцы с нулевым знаменателем).
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
  // trade-balance-monthly содержит значения с переходом через ноль (сальдо),
  // поэтому MoM% от него даст мусор — для него отдельный режим не добавляем,
  // оставляем только level. Для YoY у месячного ряда нет смысла (нет
  // backend-derived; считать на frontend по 12-месячному лагу — отдельная
  // итерация, если попросит пользователь).
};

/**
 * Преобразовать ряд точек в ряд MoM% (месяц к предыдущему месяцу).
 *
 * Вход:  массив `{date, value}` в любом порядке.
 * Выход: массив `{date, value}` той же формы, но `value` — `(val_t / val_{t-1} - 1) * 100`,
 *        округлённый до 2 знаков. Первый элемент исходного ряда отбрасывается
 *        (нет предшественника); пары с нулевым знаменателем отбрасываются.
 *
 * Использование: virtual transform для monthly indicators
 * (см. TRADE_VIEW_MODE_FAMILIES['*-monthly'] выше).
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

/** Resolve trade family by parent code, or null if not a trade family root. */
export function findTradeViewModeFamily(code) {
  return TRADE_VIEW_MODE_FAMILIES[code] || null;
}

/** Find the derived code for a (parent, mode) pair. */
export function tradeModeCode(parentCode, mode) {
  const family = findTradeViewModeFamily(parentCode);
  if (!family) return parentCode;
  const m = family.modes.find((x) => x.mode === mode);
  return m?.code ?? parentCode;
}
