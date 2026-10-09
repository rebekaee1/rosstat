/**
 * Круг 11 (зона B): общие правила для сохранённого и слежения в кабинете.
 * Чистые функции без сети и без хранилища: ими пользуются кнопки, список в кабинете и тесты.
 *
 * Договорённость по полям записи `saved` (её соблюдают все зоны, которые ставят `SaveButton`):
 *   kind      indicator | world | country | region | comparison | calc | rating_view
 *   itemKey   что однозначно называет объект (код показателя, slug страны, строка адреса сравнения)
 *   title     человекочитаемое имя (без кодов и служебных слов)
 *   payload   необязательно: { path } адрес страницы для «Открыть» (по умолчанию текущая страница),
 *             { subtitle } вторая строка, { names: [..] } названия рядов сравнения.
 *             Диапазонов (`lower`/`upper`) в записи быть не может: сервер отвечает 422.
 */
import {
  comparePath, countryPath, indicatorPath, regionPath, regionRatingPath,
  russiaIndicatorPath, worldRatingPath, WORLD_RATING_DEFAULT_CONCEPT,
} from './sitePaths';

export const SAVED_KINDS = Object.freeze(['indicator', 'world', 'country', 'region', 'comparison', 'calc', 'rating_view']);
export const WATCH_KINDS = Object.freeze(['indicator', 'world', 'region']);

/** Ключи подписей вида записи (русский и английский тексты лежат в `c11b.kind.*`). */
export const KIND_LABEL_KEY = Object.freeze({
  indicator: 'c11b.kind.indicator',
  world: 'c11b.kind.world',
  country: 'c11b.kind.country',
  region: 'c11b.kind.region',
  comparison: 'c11b.kind.comparison',
  calc: 'c11b.kind.calc',
  rating_view: 'c11b.kind.rating_view',
});

/** Порядок разделов «Избранного» (сравнения живут в своей вкладке). */
export const FAVORITE_KIND_ORDER = Object.freeze(['indicator', 'world', 'country', 'region', 'rating_view', 'calc']);

const MAX_PATH = 600;

/** Адрес только внутри сайта: начинается с «/», без «//», обратной косой, управляющих знаков. */
export function safePath(value) {
  if (typeof value !== 'string') return null;
  const v = value.trim();
  if (!v.startsWith('/') || v.startsWith('//') || v.length > MAX_PATH) return null;
  if ([...v].some((ch) => ch === '\\' || ch.charCodeAt(0) <= 32 || ch.charCodeAt(0) === 127)) return null;
  return v;
}

/** Адрес текущей страницы без якоря; пусто вне браузера. */
export function currentPagePath() {
  try {
    return safePath(`${window.location.pathname}${window.location.search}`) || null;
  } catch {
    return null;
  }
}

/** Ключ записи в виде «вид|ключ» для карт и сравнения. */
export const itemId = (kind, key) => `${kind}\u0001${key}`;

/** Приводит ввод к виду, который принимает сервер (длины, обязательные поля). Возвращает null, если записать нельзя. */
export function normalizeSavedInput({ kind, itemKey, title, payload } = {}) {
  if (!SAVED_KINDS.includes(kind)) return null;
  const key = typeof itemKey === 'string' ? itemKey.trim() : '';
  if (!key || key.length > 300) return null;
  const out = { kind, itemKey: key };
  const name = typeof title === 'string' ? title.trim().slice(0, 200) : '';
  if (name) out.title = name;
  const body = payload && typeof payload === 'object' && !Array.isArray(payload) ? { ...payload } : {};
  const path = safePath(body.path) || currentPagePath();
  if (path) body.path = path; else delete body.path;
  if (Object.keys(body).length) out.payload = body;
  return out;
}

/** Куда ведёт строка избранного: сохранённый адрес, иначе адрес по виду записи. */
export function savedItemHref(item) {
  const direct = safePath(item?.payload?.path);
  if (direct) return direct;
  const key = String(item?.item_key ?? item?.itemKey ?? '');
  switch (item?.kind) {
    case 'indicator': return key ? russiaIndicatorPath(key) : null;
    case 'country': return key ? countryPath(key) : null;
    case 'region': return key ? regionPath(key) : null;
    case 'comparison': return key ? `${comparePath()}?${key.replace(/^\?/, '')}` : comparePath();
    case 'rating_view': return worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT);
    case 'calc': return '/calculator';
    default: return null;
  }
}

/** Куда ведёт строка слежения. Для региональных рядов страница рейтинга (регион в записи не хранится). */
export function watchHref(watch) {
  const key = String(watch?.subject_key ?? '');
  if (!key) return null;
  if (watch.subject_kind === 'indicator') return russiaIndicatorPath(key);
  if (watch.subject_kind === 'world') return watch.country_slug ? indicatorPath(watch.country_slug, key) : null;
  if (watch.subject_kind === 'region') return regionRatingPath(key);
  return null;
}

/** Строка адреса сравнения (то, что стоит после «?») как ключ записи. Порядок параметров фиксируется, чтобы повтор не дублировал запись. */
export function comparisonKeyFromSearch(search) {
  const raw = String(search || '').replace(/^\?/, '');
  if (!raw) return '';
  const params = new URLSearchParams(raw);
  const pairs = [...params.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return pairs.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v).replace(/%2C/gi, ',')}`).join('&');
}

/** Код ошибки предметной проверки API (`detail.code`) или статус-подсказка. */
export function cabinetErrorCode(err) {
  const detail = err?.response?.data?.detail;
  if (detail && typeof detail === 'object' && typeof detail.code === 'string') return detail.code;
  const status = err?.response?.status;
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (!err?.response) return 'network';
  return 'error';
}

/** Ключ текста ошибки по коду (тексты — `c11b.err.*`). */
export function cabinetErrorKey(code) {
  switch (code) {
    case 'limit_reached': return 'c11b.err.limit';
    case 'subject_not_found': return 'c11b.err.subjectGone';
    case 'network': return 'c11b.err.network';
    case 'unauthorized': return 'c11b.err.unauthorized';
    default: return 'c11b.err.generic';
  }
}
