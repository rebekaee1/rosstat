/**
 * Предзагрузка «Главного» страны (`#fe-country-bootstrap`): сервер кладёт в head
 * до четырёх карточек с точками мини-графика (backend/app/services/seo_country_figures.py).
 * Карточки рисуются сразу, без запросов; пока предзагрузки нет или она не подходит,
 * поведение прежнее (отдельные запросы).
 *
 * Данные не кладём в query client: ряд предзагрузки урезан до окна мини-графика,
 * а ключ `world-indicator-data` общий со страницей показателя, где нужна вся история.
 */
import { resolveBrowserLocale } from '../i18n/locale';

export const COUNTRY_BOOTSTRAP_ID = 'fe-country-bootstrap';
const SUPPORTED_VERSION = 1;

let cached;
let cachedRead = false;

export function resetCountryBootstrapCache() {
  cached = undefined;
  cachedRead = false;
}

function readRaw() {
  if (cachedRead) return cached;
  cachedRead = true;
  cached = null;
  if (typeof document === 'undefined') return null;
  const el = document.getElementById(COUNTRY_BOOTSTRAP_ID);
  if (!el?.textContent) return null;
  try {
    const data = JSON.parse(el.textContent);
    if (data && typeof data === 'object' && data.v === SUPPORTED_VERSION && Array.isArray(data.overview)) {
      cached = data;
    }
  } catch {
    cached = null;
  }
  return cached;
}

/**
 * Предзагрузка этой страны на этом языке или null.
 * Документ описывает одну страну: при переходе на другую (SPA) данные не подходят.
 */
export function readCountryBootstrap(slug, locale) {
  const data = readRaw();
  if (!data || !slug || data.slug !== slug) return null;
  if (data.locale && data.locale !== (locale || resolveBrowserLocale())) return null;
  return data.overview.length ? data : null;
}

/**
 * Точки мини-графика для карточки: только если карточка и предзагрузка про один и тот же
 * ряд, дату и значение. Если живой каталог уже новее серверного снимка, берём сеть.
 * @returns {Array<{date: string, value: number}> | null}
 */
export function preloadedFigurePoints(preload, item) {
  if (!preload || !item) return null;
  const match = preload.overview.find((entry) => entry?.indicator_code === item.indicator_code
    && entry.concept_slug === item.concept_slug);
  if (!match || match.date !== item.date || Number(match.value) !== Number(item.value)) return null;
  const points = (match.points || [])
    .filter((pair) => Array.isArray(pair) && Number.isFinite(Number(pair[1])))
    .map((pair) => ({ date: String(pair[0]), value: Number(pair[1]) }));
  return points.length > 1 ? points : null;
}
