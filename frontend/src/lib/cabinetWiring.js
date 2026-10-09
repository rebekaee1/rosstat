/**
 * Круг 11, интеграция: как страницы передают свои предметы кнопкам кабинета («Сохранить», «Следить»).
 * Чистые функции без сети и без хранилища. Компоненты-обёртки — `components/cabinet/CabinetWiring.jsx`.
 *
 * Ключи записей (договорённость `impl4-b.md`, раздел 4; `lib/cabinetItems.js`):
 *   показатель России  indicator + код;        мировой ряд  world + код ряда (адрес в payload.path);
 *   страна             country + slug;         регион       region + slug;
 *   сравнение          comparison + comparisonKeyFromSearch(«codes=…&rep=…»);
 *   расчёт             calc + нормализованная строка параметров (её строит страница калькулятора);
 *   вид рейтинга       rating_view + показатель|группа|колонки (`lib/cabinetSubjects.js::ratingViewSubject`).
 */
import { comparisonKeyFromSearch } from './cabinetItems';
import { comparePath } from './sitePaths';

const CALC_PATHS = Object.freeze({
  inflation: '/calculator',
  mortgage: '/calculator/mortgage',
  compound: '/calculator/compound',
});

/** Поля расчёта, которые страница калькулятора читает из адреса (`lib/useCalcUrlSync.js`). */
const CALC_PARAMS = Object.freeze({
  inflation: ['amount', 'from', 'to', 'country', 'cur'],
  mortgage: ['price', 'down', 'rate', 'years'],
  compound: ['initial', 'monthly', 'rate', 'years', 'inflation', 'cur'],
});

/**
 * Описание сравнения от страницы (`ComparePage` → `renderSave(spec)`, `spec.payload = { codes, rep?, names? }`)
 * в свойства общей кнопки. Ключ — строка адреса только из значимых параметров (коды и виды рядов), упорядоченная:
 * тот же набор, открытый с другими служебными параметрами, не плодит копию.
 */
export function comparisonSaveProps(spec) {
  const codes = String(spec?.payload?.codes || '').trim();
  if (!codes) return null;
  const rep = String(spec?.payload?.rep || '').trim();
  const params = new URLSearchParams({ codes });
  if (rep) params.set('rep', rep);
  const itemKey = comparisonKeyFromSearch(params.toString());
  if (!itemKey || itemKey.length > 300) return null;
  const names = Array.isArray(spec?.payload?.names)
    ? spec.payload.names.filter((n) => typeof n === 'string' && n.trim()).map((n) => n.trim().slice(0, 120)).slice(0, 6)
    : [];
  return {
    kind: 'comparison',
    itemKey,
    title: typeof spec?.title === 'string' ? spec.title.trim().slice(0, 200) : '',
    payload: {
      path: `${comparePath()}?${itemKey}`,
      codes,
      ...(rep ? { rep } : {}),
      ...(names.length ? { names } : {}),
    },
  };
}

/**
 * Адрес сохранённого расчёта: страница калькулятора и его параметры в адресе, чтобы «Открыть» из кабинета
 * показывало тот же расчёт, даже если человек сохранил его до того, как адрес обновился.
 */
export function calcSavedPath(payload) {
  const page = payload?.page;
  const base = CALC_PATHS[page];
  if (!base) return null;
  const params = new URLSearchParams();
  for (const key of CALC_PARAMS[page]) {
    const value = payload[key];
    if (value != null && value !== '') params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}
